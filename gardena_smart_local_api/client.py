# SPDX-FileCopyrightText: 2026 GARDENA GmbH
#
# SPDX-License-Identifier: LGPL-3.0-or-later

"""WebSocket transport and request/reply lifecycle for a GARDENA smart Gateway.

Callers only deal with Request/Reply objects and pushed Events; connection,
authentication, framing, reconnects, and request/reply correlation live
here instead of being implemented by every caller.

Uses aiohttp rather than a dedicated WebSocket library so a caller that
already runs an aiohttp.ClientSession (e.g. Home Assistant's shared, pooled
session) can hand it in and have this client reuse it instead of opening a
second connection pool. A caller without one of its own (the CLI examples)
gets a session created and owned by this client instead.
"""

import asyncio
import base64
import contextlib
import hashlib
import logging
import ssl
from collections.abc import Awaitable, Callable
from types import TracebackType
from typing import Self

import aiohttp

from .devices import DeviceMap, build_discovery_obj, create_devices_from_messages
from .messages import EgressMessageList, ErrorMessage, Event, IngressMessageList, Reply

_LOGGER = logging.getLogger(__name__)

# Wait before reconnecting, whether the socket dropped with an error or
# closed cleanly, so a gateway that flaps does not spin the loop.
RECONNECT_DELAY = 5

# How long connect() waits for the first connection, including the
# on_connect hook, before giving up.
CONNECT_TIMEOUT = 30

# How many unsolicited messages `events` holds before the oldest is dropped.
EVENT_QUEUE_SIZE = 1000

# How long discover_devices() waits for the gateway's discovery replies.
DISCOVERY_TIMEOUT = 30


class AuthenticationError(Exception):
    """The gateway rejected the configured password (HTTP 401)."""


class DiscoveryError(Exception):
    """The gateway answered a discovery request with an error."""


def _no_verify_ssl_context() -> ssl.SSLContext:
    """Return an SSL context that accepts the gateway's self-signed certificate.

    Used when no fingerprint is given: the connection is encrypted but the
    gateway is not authenticated.
    """
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


def _parse_fingerprint(fingerprint: str) -> bytes:
    """Return the SHA-256 digest for a hex fingerprint, with or without colons."""
    try:
        digest = bytes.fromhex(fingerprint.replace(":", ""))
    except ValueError:
        digest = b""
    if len(digest) != hashlib.sha256().digest_size:
        raise ValueError(
            "fingerprint must be a SHA-256 hash: 64 hexadecimal digits, "
            "optionally separated by colons"
        )
    return digest


class GatewayClient:
    """Maintain a WebSocket connection to a GARDENA smart Gateway.

    Owns authentication, frame parsing, reconnect supervision, and
    request/reply correlation. Messages that are not a reply to a pending
    request (i.e. pushed Events) are handed to `on_event`.

    With `queue_events=True`, every message that is not the reply to a
    pending request is also put on the `events` queue, so a caller can
    consume them with `await client.events.get()` instead of (or besides) a
    callback. The queue holds `EVENT_QUEUE_SIZE` messages; when nobody
    consumes it, the oldest are dropped.

    Use it as an async context manager, or call `connect()` and
    `disconnect()` yourself:

        async with GatewayClient("GARDENA-123456", 8443, "password") as client:
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
    loop, so it must not wait for the reply to a request.
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
        queue_events: bool = False,
    ) -> None:
        self.host = host
        self.port = port
        self.uri = f"wss://{host}:{port}"
        auth_bytes = f"_:{password}".encode()
        self._auth_header = f"Basic {base64.b64encode(auth_bytes).decode('ascii')}"
        self._on_event = on_event
        # Called after every successful (re)connect, not just the first —
        # callers that need to re-run a protocol handshake (e.g. discovery)
        # after a reconnect hook in here.
        self._on_connect = on_connect

        # A caller-supplied session is theirs: we never close it. Without
        # one, connect() creates one lazily and disconnect() closes it.
        self._session = session
        self._owns_session = session is None

        # With a fingerprint the gateway must present exactly that certificate
        # (SHA-256 of the DER form, hex, colons allowed); a mismatch fails the
        # connect with aiohttp.ServerFingerprintMismatch. Without one, any
        # certificate is accepted.
        self._ssl_context: ssl.SSLContext | aiohttp.Fingerprint = (
            aiohttp.Fingerprint(_parse_fingerprint(fingerprint))
            if fingerprint is not None
            else _no_verify_ssl_context()
        )
        # Called when the password is rejected after the first connect; the
        # client then stops, because retrying only hammers the gateway.
        self._on_auth_failed = on_auth_failed
        self._on_disconnect = on_disconnect
        self._certificate: bytes | None = None
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._task: asyncio.Task[None] | None = None
        self._pending_replies: dict[str, asyncio.Future[Reply | ErrorMessage]] = {}
        self._connected_result: asyncio.Future[None] | None = None
        self._outage_logged = False
        self._events: asyncio.Queue[Event | Reply | ErrorMessage] | None = (
            asyncio.Queue(maxsize=EVENT_QUEUE_SIZE) if queue_events else None
        )

    @property
    def connected(self) -> bool:
        """Return True if the WebSocket to the gateway is currently open."""
        return self._ws is not None and not self._ws.closed

    @property
    def events(self) -> asyncio.Queue[Event | Reply | ErrorMessage]:
        """Messages that are not the reply to a pending request.

        Raises `RuntimeError` unless the client was created with
        `queue_events=True`.
        """
        if self._events is None:
            raise RuntimeError("Create the client with queue_events=True")
        return self._events

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
        return hashlib.sha256(self._certificate).hexdigest()

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
        """Stop the connection and its reconnect-supervision loop."""
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
                    ssl=self._ssl_context,
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
                    # The first attempt: connect() raises, the caller reports it.
                    self._connected_result.set_exception(err)
                elif not self._outage_logged:
                    _LOGGER.error("Lost connection to GARDENA smart Gateway: %s", err)
                    self._outage_logged = True
                else:
                    _LOGGER.debug("Reconnect to GARDENA smart Gateway failed: %s", err)
            finally:
                self._ws = None
                self._fail_pending_replies()

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
        done, _ = await asyncio.wait(
            {hook, read_task}, return_when=asyncio.FIRST_COMPLETED
        )
        if hook not in done:
            hook.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await hook
            raise ConnectionError("Connection lost while running on_connect")
        hook.result()

    @staticmethod
    async def _call(callback: Callable[[], Awaitable[None] | None]) -> None:
        result = callback()
        if result is not None:
            await result

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

    def _fail_pending_replies(self) -> None:
        for fut in self._pending_replies.values():
            if not fut.done():
                fut.set_exception(
                    ConnectionError("WebSocket disconnected before a reply arrived")
                )
        self._pending_replies.clear()

    async def _read_loop(self, ws: aiohttp.ClientWebSocketResponse) -> None:
        """Read frames until the connection drops, dispatching each message."""
        async for msg in ws:
            match msg.type:
                case aiohttp.WSMsgType.TEXT:
                    raw = msg.data
                case aiohttp.WSMsgType.BINARY:
                    raw = msg.data.decode("utf-8")
                case aiohttp.WSMsgType.ERROR:
                    _LOGGER.error("WebSocket error: %s", ws.exception())
                    return
                case aiohttp.WSMsgType.CLOSED | aiohttp.WSMsgType.CLOSING:
                    return
                case _:
                    continue

            try:
                messages = IngressMessageList.model_validate_json(raw)
            except Exception:  # noqa: BLE001
                _LOGGER.debug("Ignoring unparsable message from gateway: %s", raw)
                continue

            for message in messages:
                if (
                    isinstance(message, Reply | ErrorMessage)
                    and message.request_id in self._pending_replies
                ):
                    fut = self._pending_replies.pop(message.request_id)
                    if not fut.done():
                        fut.set_result(message)
                    continue

                self._enqueue(message)
                if isinstance(message, Event) and self._on_event is not None:
                    try:
                        result = self._on_event(message)
                        if result is not None:
                            await result
                    except Exception:
                        _LOGGER.exception("Error in on_event callback")

    def _enqueue(self, message: Event | Reply | ErrorMessage) -> None:
        if self._events is None:
            return
        if self._events.full():
            self._events.get_nowait()
            _LOGGER.debug("Event queue full, dropped the oldest message")
        self._events.put_nowait(message)

    async def send_request(
        self,
        request: EgressMessageList,
        wait_for_response_sec: float = 0,
    ) -> IngressMessageList:
        """Send a request, optionally waiting for its reply(ies)."""
        if self._ws is None:
            raise ConnectionError("Cannot send request: WebSocket not connected")

        if wait_for_response_sec <= 0:
            await self._ws.send_str(str(request))
            return IngressMessageList([])

        loop = asyncio.get_running_loop()
        pending_ids = {
            req.request_id for req in request.root if req.request_id is not None
        }
        futures: dict[str, asyncio.Future[Reply | ErrorMessage]] = {
            rid: loop.create_future() for rid in pending_ids
        }
        self._pending_replies.update(futures)

        try:
            await self._ws.send_str(str(request))
            async with asyncio.timeout(wait_for_response_sec):
                replies = await asyncio.gather(*futures.values())
            return IngressMessageList(list(replies))
        finally:
            for rid in pending_ids:
                self._pending_replies.pop(rid, None)

    async def discover_devices(self, timeout: float = DISCOVERY_TIMEOUT) -> DeviceMap:
        """Ask the gateway for its devices and build them from the replies.

        Raises `TimeoutError` if the gateway does not answer within `timeout`
        seconds, and `DiscoveryError` if it rejects a discovery request, so a
        rejection is not mistaken for a gateway without devices.
        """
        replies = await self.send_request(
            build_discovery_obj(), wait_for_response_sec=timeout
        )
        for reply in replies:
            if isinstance(reply, ErrorMessage) or not reply.success:
                reason = reply.error_message if isinstance(reply, ErrorMessage) else ""
                raise DiscoveryError(f"The gateway rejected the discovery: {reason}")
        return await create_devices_from_messages(replies)
