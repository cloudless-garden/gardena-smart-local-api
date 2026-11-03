# SPDX-FileCopyrightText: 2026 GARDENA GmbH
#
# SPDX-License-Identifier: LGPL-3.0-or-later

import asyncio
import base64
import contextlib
import json
import logging
import ssl
from collections.abc import Awaitable, Callable
from types import TracebackType
from typing import Any, Self

import aiohttp
from pydantic import TypeAdapter, ValidationError

from ..devices import DeviceMap, build_discovery_obj, create_devices_from_messages
from ..messages import EgressMessageList, ErrorMessage, Event, IngressMessageList, Reply
from .certificate import (
    fingerprint_from_certificate,
    hostname_from_certificate,
    no_verify_ssl_context,
    parse_fingerprint,
)
from .errors import AuthenticationError, DiscoveryError
from .replies import PendingReplies

_LOGGER = logging.getLogger(__name__)

# Wait before reconnecting, whether the socket dropped with an error or
# closed cleanly, so a gateway that flaps does not spin the loop.
RECONNECT_DELAY = 5

# How many messages the `messages` queue holds before the oldest is dropped.
MESSAGE_QUEUE_SIZE = 1000

# How long discover_devices() waits for the gateway's discovery replies.
DISCOVERY_TIMEOUT = 30

# How long connect() waits for the first connection, including the
# on_connect hook, before giving up. Leaves room for the handshake on top of
# a hook that runs a full discovery.
CONNECT_TIMEOUT = DISCOVERY_TIMEOUT + 10


_INGRESS_MESSAGE = TypeAdapter(Event | Reply | ErrorMessage)


def _require_positive(timeout: float) -> None:
    """Reject a timeout that would not wait for the replies at all."""
    if timeout <= 0:
        raise ValueError("timeout must be positive")


def _parse_frame(raw: str) -> list[Event | Reply | ErrorMessage]:
    """Parse the messages of a frame, skipping the ones that are not understood.

    A frame can carry replies next to a message of a type this client does
    not know, so one bad message must not cost the others.
    """
    try:
        items = json.loads(raw)
    except ValueError:
        items = None
    if not isinstance(items, list):
        _LOGGER.debug("Ignoring unparsable frame from gateway: %s", raw)
        return []

    messages: list[Event | Reply | ErrorMessage] = []
    for item in items:
        try:
            messages.append(_INGRESS_MESSAGE.validate_python(item))
        except ValidationError:
            _LOGGER.debug("Ignoring unknown message from gateway: %s", item)
    return messages


class GatewayClient:
    """Maintain a WebSocket connection to a GARDENA smart Gateway.

    Owns authentication, frame parsing, reconnect supervision, and
    request/reply correlation. Pushed Events are handed to `on_event`, if
    given.

    With `queue_messages=True`, every message that is not the reply to a
    pending request is also put on the `messages` queue, so a caller can
    consume them with `await client.messages.get()` instead of (or besides) a
    callback. The queue holds `MESSAGE_QUEUE_SIZE` messages; when nobody
    consumes it, the oldest are dropped.

    Use it as an async context manager, or call `connect()` and
    `disconnect()` yourself. Without a `fingerprint` any certificate is
    accepted, so the password goes to whoever answers. Learn the fingerprint
    once, store it, and pass it on every later connection:

        # Once, at setup.
        certificate = await fetch_certificate("GARDENA-123456", 8443)
        fingerprint = fingerprint_from_certificate(certificate)

        # From then on, only that gateway is talked to.
        async with GatewayClient(
            "GARDENA-123456", 8443, "password", fingerprint=fingerprint
        ) as client:
            devices = await client.discover_devices()

    `connect()` raises if the first connection fails and leaves the client
    stopped. Once connected, a lost connection is re-established in the
    background: `on_disconnect` runs when an established connection drops,
    `on_connect` runs again after each reconnect, and requests that were
    waiting for a reply fail with `ConnectionError`. Neither runs for
    `disconnect()`.

    The callbacks may be plain functions or coroutine functions. An
    exception raised by `on_event`, `on_disconnect` or `on_auth_failed` is
    logged and does not affect the connection. `on_event` runs in the read
    loop, so it must not wait for the reply to a request. No callback may
    await `disconnect()`, which raises `RuntimeError` there.
    """

    def __init__(
        self,
        host: str,
        port: int,
        password: str,
        *,
        on_event: Callable[[Event], Awaitable[None] | None] | None = None,
        on_connect: Callable[[], Awaitable[None] | None] | None = None,
        session: aiohttp.ClientSession | None = None,
        fingerprint: str | None = None,
        on_auth_failed: Callable[[], Awaitable[None] | None] | None = None,
        on_disconnect: Callable[[], Awaitable[None] | None] | None = None,
        queue_messages: bool = False,
    ) -> None:
        self.host = host
        self.port = port
        self.uri = f"wss://{host}:{port}"
        auth_bytes = f"_:{password}".encode()
        self._auth_header = f"Basic {base64.b64encode(auth_bytes).decode('ascii')}"
        self._on_event = on_event
        self._on_connect = on_connect

        # A caller-supplied session is theirs: we never close it. Without
        # one, connect() creates one lazily and disconnect() closes it.
        self._session = session
        self._owns_session = session is None

        # With a fingerprint the gateway must present exactly that certificate
        # (SHA-256 of the DER form, hex, colons allowed); a mismatch fails the
        # connect with aiohttp.ServerFingerprintMismatch. Without one, any
        # certificate is accepted.
        self._ssl: ssl.SSLContext | aiohttp.Fingerprint = (
            aiohttp.Fingerprint(parse_fingerprint(fingerprint))
            if fingerprint is not None
            else no_verify_ssl_context()
        )
        # Called when the password is rejected after the first connect; the
        # client then stops, because retrying only hammers the gateway.
        self._on_auth_failed = on_auth_failed
        self._on_disconnect = on_disconnect
        self._certificate: bytes | None = None
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._task: asyncio.Task[None] | None = None
        # The tasks that currently run a callback; disconnect() would wait
        # for the very task it is called from.
        self._callback_tasks: set[asyncio.Task[Any] | None] = set()
        self._pending_replies = PendingReplies()
        self._connected_result: asyncio.Future[None] | None = None
        self._outage_logged = False
        self._messages: asyncio.Queue[Event | Reply | ErrorMessage] | None = (
            asyncio.Queue(maxsize=MESSAGE_QUEUE_SIZE) if queue_messages else None
        )

    @property
    def connected(self) -> bool:
        return self._ws is not None and not self._ws.closed

    @property
    def messages(self) -> asyncio.Queue[Event | Reply | ErrorMessage]:
        """Messages that are not the reply to a pending request.

        Raises `RuntimeError` unless the client was created with
        `queue_messages=True`.
        """
        if self._messages is None:
            raise RuntimeError("Create the client with queue_messages=True")
        return self._messages

    @property
    def certificate(self) -> bytes | None:
        """The DER certificate the gateway presented on the last connection."""
        return self._certificate

    @property
    def fingerprint(self) -> str | None:
        """The SHA-256 fingerprint (hex) of `certificate`.

        Pass it as `fingerprint` to pin the gateway on later connections.
        """
        if self._certificate is None:
            return None
        return fingerprint_from_certificate(self._certificate)

    @property
    def certificate_hostname(self) -> str | None:
        """The gateway's mDNS hostname (e.g. ``GARDENA-123456``) from `certificate`.

        None before the first connection, or if the certificate has no such
        name (older firmware).
        """
        if self._certificate is None:
            return None
        return hostname_from_certificate(self._certificate)

    async def __aenter__(self) -> Self:
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.disconnect()

    async def connect(self) -> None:
        """Connect to the gateway, waiting for the first attempt to succeed.

        Raises `AuthenticationError` if the gateway rejects the password,
        `TimeoutError` if there is no connection after `CONNECT_TIMEOUT`
        seconds, and the underlying error for any other failure. After a
        failure the client is stopped and `connect()` can be called again.
        """
        if self._task is not None:
            if not self._task.done():
                raise RuntimeError("Already connected or connecting")
            # The supervisor stopped by itself, e.g. after a rejected password.
            self._task = None
        if self._session is None:
            self._session = aiohttp.ClientSession()
        self._outage_logged = False
        self._connected_result = asyncio.get_running_loop().create_future()
        self._task = asyncio.create_task(self._run())
        try:
            async with asyncio.timeout(CONNECT_TIMEOUT):
                await self._connected_result
        except BaseException:
            await self.disconnect()
            raise

    async def disconnect(self) -> None:
        """Stop the connection and its reconnect-supervision loop.

        Raises `RuntimeError` when called from a callback. Start it as a
        task there: `asyncio.create_task(client.disconnect())`.
        """
        if asyncio.current_task() in self._callback_tasks:
            raise RuntimeError(
                "disconnect() cannot be called from a callback, it would wait "
                "for itself; use asyncio.create_task(client.disconnect())"
            )
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        if self._owns_session and self._session is not None:
            await self._session.close()
            self._session = None

    async def _run(self) -> None:
        """Keep a connection open, reconnecting on failure until cancelled."""
        assert self._session is not None  # connect() always sets this first
        while True:
            established = False
            try:
                async with self._session.ws_connect(
                    self.uri,
                    ssl=self._ssl,
                    heartbeat=30,
                    headers={"Authorization": self._auth_header},
                ) as ws:
                    self._ws = ws
                    self._store_certificate(ws)
                    if self._outage_logged:
                        _LOGGER.info(
                            "Reconnected to GARDENA smart Gateway at %s", self.uri
                        )
                        self._outage_logged = False
                    else:
                        _LOGGER.info(
                            "Connected to GARDENA smart Gateway at %s", self.uri
                        )

                    read_task = asyncio.create_task(self._read_loop(ws))
                    try:
                        await self._run_on_connect(read_task)
                        established = True
                        if self._connected_result and not self._connected_result.done():
                            self._connected_result.set_result(None)
                        await read_task
                    finally:
                        if not read_task.done():
                            read_task.cancel()
                            with contextlib.suppress(asyncio.CancelledError):
                                await read_task
            except asyncio.CancelledError:
                raise
            except Exception as err:  # noqa: BLE001 - supervisor must not crash
                if (
                    isinstance(err, aiohttp.WSServerHandshakeError)
                    and err.status == 401
                ):
                    auth_error = AuthenticationError(
                        "The GARDENA smart Gateway rejected the password"
                    )
                    auth_error.__cause__ = err
                    if self._connected_result and not self._connected_result.done():
                        self._connected_result.set_exception(auth_error)
                    else:
                        _LOGGER.error("%s, stopping", auth_error)
                        await self._call_safely(self._on_auth_failed, "on_auth_failed")
                    return
                if self._connected_result and not self._connected_result.done():
                    # The first attempt: connect() raises it to the caller.
                    self._connected_result.set_exception(err)
                elif not self._outage_logged:
                    _LOGGER.error("Lost connection to GARDENA smart Gateway: %s", err)
                    self._outage_logged = True
                else:
                    _LOGGER.debug("Reconnect to GARDENA smart Gateway failed: %s", err)
            finally:
                self._ws = None
                self._pending_replies.fail_all()

            if established:
                await self._call_safely(self._on_disconnect, "on_disconnect")
            await asyncio.sleep(RECONNECT_DELAY)

    async def _run_on_connect(self, read_task: asyncio.Task[None]) -> None:
        """Run the on_connect hook, aborting it if the connection drops.

        The hook runs concurrently with the read loop: a hook like "re-run
        discovery" needs replies to be read while it waits for them.
        """
        if self._on_connect is None:
            return
        hook = asyncio.ensure_future(self._call(self._on_connect))
        try:
            done, _ = await asyncio.wait(
                {hook, read_task}, return_when=asyncio.FIRST_COMPLETED
            )
            if hook not in done:
                raise ConnectionError("Connection lost while running on_connect")
            hook.result()
        finally:
            # Also when this is cancelled by disconnect() or the connect timeout.
            if not hook.done():
                hook.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await hook

    async def _call(
        self, callback: Callable[..., Awaitable[None] | None], *args: Any
    ) -> None:
        task = asyncio.current_task()
        self._callback_tasks.add(task)
        try:
            result = callback(*args)
            if result is not None:
                await result
        finally:
            self._callback_tasks.discard(task)

    async def _call_safely(
        self, callback: Callable[[], Awaitable[None] | None] | None, name: str
    ) -> None:
        if callback is None:
            return
        try:
            await self._call(callback)
        except Exception:
            _LOGGER.exception("Error in %s callback", name)

    def _store_certificate(self, ws: aiohttp.ClientWebSocketResponse) -> None:
        ssl_object = ws.get_extra_info("ssl_object")
        if ssl_object is not None:
            self._certificate = ssl_object.getpeercert(binary_form=True)

    async def _read_loop(self, ws: aiohttp.ClientWebSocketResponse) -> None:
        """Read frames until the connection drops, dispatching each message."""
        async for msg in ws:
            match msg.type:
                case aiohttp.WSMsgType.TEXT:
                    raw = msg.data
                case aiohttp.WSMsgType.BINARY:
                    try:
                        raw = msg.data.decode("utf-8")
                    except UnicodeDecodeError:
                        _LOGGER.debug("Ignoring non-UTF-8 binary frame from gateway")
                        continue
                case aiohttp.WSMsgType.ERROR:
                    _LOGGER.error("WebSocket error: %s", ws.exception())
                    return
                case aiohttp.WSMsgType.CLOSED | aiohttp.WSMsgType.CLOSING:
                    return
                case _:
                    continue

            for message in _parse_frame(raw):
                if isinstance(
                    message, Reply | ErrorMessage
                ) and self._pending_replies.resolve(message):
                    continue

                self._enqueue(message)
                if isinstance(message, Event) and self._on_event is not None:
                    try:
                        await self._call(self._on_event, message)
                    except Exception:
                        _LOGGER.exception("Error in on_event callback")

    def _enqueue(self, message: Event | Reply | ErrorMessage) -> None:
        if self._messages is None:
            return
        if self._messages.full():
            self._messages.get_nowait()
            _LOGGER.debug("Event queue full, dropped the oldest message")
        self._messages.put_nowait(message)

    async def send_request(
        self,
        request: EgressMessageList,
        timeout: float | None = None,
    ) -> IngressMessageList:
        """Send a request and, with a `timeout`, wait for its replies.

        Without a `timeout` the request is sent and no reply is waited for.
        With one, the replies are returned in the order of the messages in
        the request, or `TimeoutError` is raised after `timeout` seconds.
        Raises `ValueError` if `timeout` is not positive.
        """
        if timeout is not None:
            _require_positive(timeout)
        if self._ws is None or self._ws.closed:
            raise ConnectionError("Cannot send request: WebSocket not connected")

        if timeout is None:
            await self._ws.send_str(str(request))
            return IngressMessageList([])

        request_ids: list[str] = []
        for req in request.root:
            if req.request_id is not None:
                request_ids.append(req.request_id)
        if not request_ids or len(request_ids) != len(request.root):
            raise ValueError(
                "A request that waits for replies needs a request_id in every message"
            )
        if len(set(request_ids)) != len(request_ids):
            raise ValueError("The request_ids of one request must be unique")
        futures = self._pending_replies.expect(request_ids)

        try:
            await self._ws.send_str(str(request))
            async with asyncio.timeout(timeout):
                replies = await asyncio.gather(*futures.values())
            return IngressMessageList(list(replies))
        finally:
            self._pending_replies.forget(request_ids)

    async def discover_devices(self, timeout: float = DISCOVERY_TIMEOUT) -> DeviceMap:
        """Ask the gateway for its devices and build them from the replies.

        Raises `TimeoutError` if the gateway does not answer within `timeout`
        seconds, and `DiscoveryError` if a discovery request fails with an error, so a
        failure is not mistaken for a gateway without devices. The error
        carries the devices of the discovery requests that succeeded. Raises
        `ValueError` if `timeout` is not positive.
        """
        replies = await self.send_request(build_discovery_obj(), timeout=timeout)
        failure = self._failure(replies)
        if failure is None:
            return await create_devices_from_messages(replies)
        succeeded: list[Event | Reply | ErrorMessage] = []
        for reply in replies:
            if isinstance(reply, Reply) and reply.success:
                succeeded.append(reply)
        devices = await create_devices_from_messages(IngressMessageList(succeeded))
        raise DiscoveryError(f"The discovery failed{failure}", replies, devices)

    @staticmethod
    def _failure(replies: IngressMessageList) -> str | None:
        """Return the reason of the first failed reply, None if all succeeded.

        The reason is empty if the gateway gave none.
        """
        for reply in replies:
            if isinstance(reply, ErrorMessage):
                return f": {reply.error_message}"
            if isinstance(reply, Reply) and not reply.success:
                return ""
        return None
