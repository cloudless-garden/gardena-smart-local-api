# SPDX-FileCopyrightText: 2026 GARDENA GmbH
#
# SPDX-License-Identifier: LGPL-3.0-or-later

import asyncio
import hashlib
import json
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest
import pytest_asyncio

import gardena_smart_local_api.client.gateway as client_module
from gardena_smart_local_api.client import (
    AuthenticationError,
    DiscoveryError,
    GatewayClient,
)
from gardena_smart_local_api.devices import build_discovery_obj
from gardena_smart_local_api.messages import (
    EgressMessageList,
    Entity,
    ErrorMessage,
    Event,
    Reply,
    Request,
)
from gardena_smart_local_api.resources import IpsoPath


def _as_session(fake: object) -> aiohttp.ClientSession:
    return cast(aiohttp.ClientSession, fake)


class _FakeSSLObject:
    """Stand-in for the ssl.SSLObject of an established TLS connection."""

    def __init__(self, certificate: bytes) -> None:
        self._certificate = certificate

    def getpeercert(self, binary_form: bool = False) -> bytes:
        return self._certificate


class _FakeWS:
    """Stand-in for an aiohttp.ClientWebSocketResponse: an async-iterable queue."""

    def __init__(self) -> None:
        self.sent: list[str] = []
        self.closed = False
        self.certificate = b"gateway-certificate"
        self._queue: asyncio.Queue = asyncio.Queue()

    def push(self, raw: str) -> None:
        import aiohttp

        self._queue.put_nowait(aiohttp.WSMessage(aiohttp.WSMsgType.TEXT, raw, None))

    def push_binary(self, data: bytes) -> None:
        self._queue.put_nowait(aiohttp.WSMessage(aiohttp.WSMsgType.BINARY, data, None))

    def push_closed(self) -> None:
        self._queue.put_nowait(aiohttp.WSMessage(aiohttp.WSMsgType.CLOSED, None, None))

    def get_extra_info(self, name: str, default=None):
        if name == "ssl_object":
            return _FakeSSLObject(self.certificate)
        return default

    async def send_str(self, data: str) -> None:
        self.sent.append(data)

    def __aiter__(self):
        return self

    async def __anext__(self):
        return await self._queue.get()


class _FakeWSConnectCtx:
    """Stand-in for `session.ws_connect(...)`: an async context manager."""

    def __init__(self, ws: _FakeWS) -> None:
        self._ws = ws

    async def __aenter__(self) -> _FakeWS:
        return self._ws

    async def __aexit__(self, *args) -> None:
        return None


class _FakeSession:
    """Stand-in for an aiohttp.ClientSession: records ws_connect calls."""

    def __init__(self, ws: _FakeWS) -> None:
        self._ws = ws
        self.ws_connect_calls: list[dict] = []
        self.closed = False

    def ws_connect(self, url, **kwargs):
        self.ws_connect_calls.append({"url": url, **kwargs})
        return _FakeWSConnectCtx(self._ws)

    async def close(self) -> None:
        self.closed = True


def _request(request_id: str = "req-1") -> EgressMessageList:
    return EgressMessageList(
        [
            Request(
                entity=Entity(
                    device="dev-1",
                    path=IpsoPath(
                        object_name="lemonbeat",
                        object_instance_id="0",
                        resource_name="command",
                    ),
                    service="lemonbeatd",
                ),
                op="write",
                payload={"vi": 1},
                request_id=request_id,
            )
        ]
    )


@pytest.fixture
def fake_ws() -> _FakeWS:
    return _FakeWS()


@pytest.fixture
def fake_session(fake_ws: _FakeWS) -> _FakeSession:
    return _FakeSession(fake_ws)


@pytest_asyncio.fixture
async def connected_client(fake_session: _FakeSession, fake_ws: _FakeWS):
    client = GatewayClient(
        "gateway.local",
        8443,
        "secret",
        session=_as_session(fake_session),
        queue_messages=True,
    )
    await client.connect()
    yield client, fake_ws
    await client.disconnect()


@pytest.mark.asyncio
async def test_connect_sends_basic_auth_header(fake_session: _FakeSession) -> None:
    client = GatewayClient(
        "gateway.local", 8443, "secret", session=_as_session(fake_session)
    )

    await client.connect()
    await client.disconnect()

    assert fake_session.ws_connect_calls
    headers = fake_session.ws_connect_calls[0]["headers"]
    assert headers["Authorization"].startswith("Basic ")


@pytest.mark.asyncio
async def test_injected_session_is_not_closed_by_client(
    fake_session: _FakeSession,
) -> None:
    """A caller-supplied session is theirs: disconnect() must not close it."""
    client = GatewayClient(
        "gateway.local", 8443, "secret", session=_as_session(fake_session)
    )

    await client.connect()
    await client.disconnect()

    assert fake_session.closed is False


@pytest.mark.asyncio
async def test_owned_session_is_closed_on_disconnect() -> None:
    """Without an injected session, the client creates and owns (closes) one."""
    client = GatewayClient("gateway.local", 8443, "secret")
    created_session = MagicMock()
    created_session.ws_connect = MagicMock(
        side_effect=ConnectionError("no real connection in this test")
    )
    created_session.close = AsyncMock()

    import gardena_smart_local_api.client.gateway as client_module

    original_session_cls = client_module.aiohttp.ClientSession
    client_module.aiohttp.ClientSession = MagicMock(  # ty: ignore[invalid-assignment]
        return_value=created_session
    )
    try:
        task = asyncio.ensure_future(client.connect())
        # The connect loop will keep retrying against the broken session;
        # we only care that it created and will own one.
        await asyncio.sleep(0)
        assert client._session is created_session
        assert client._owns_session is True
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        await client.disconnect()
    finally:
        client_module.aiohttp.ClientSession = original_session_cls

    created_session.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_request_resolves_on_matching_reply(connected_client) -> None:
    client, ws = connected_client

    task = asyncio.ensure_future(client.send_request(_request("req-1"), timeout=1))
    await asyncio.sleep(0)  # let send_request register its pending future
    ws.push('[{"request_id": "req-1", "success": true, "payload": {}}]')

    replies = await task
    assert len(replies) == 1
    assert replies[0].request_id == "req-1"
    assert replies[0].success is True
    assert ws.sent  # the request was actually sent


@pytest.mark.asyncio
async def test_send_request_returns_the_replies_in_request_order(
    connected_client,
) -> None:
    client, ws = connected_client
    ids = [f"req-{n}" for n in range(8)]
    request = EgressMessageList([_request(rid).root[0] for rid in ids])

    task = asyncio.ensure_future(client.send_request(request, timeout=1))
    await asyncio.sleep(0)
    replies = ", ".join(
        f'{{"request_id": "{rid}", "success": true, "payload": {{}}}}'
        for rid in reversed(ids)
    )
    ws.push(f"[{replies}]")

    assert [reply.request_id for reply in await task] == ids


@pytest.mark.asyncio
async def test_send_request_resolves_on_error_message(connected_client) -> None:
    client, ws = connected_client

    task = asyncio.ensure_future(client.send_request(_request("req-2"), timeout=1))
    await asyncio.sleep(0)
    ws.push(
        '[{"request_id": "req-2", "success": false, '
        '"metadata": {"error_source": "gateway"}, "payload": {"vs": "not allowed"}}]'
    )

    replies = await task
    assert len(replies) == 1
    assert replies[0].success is False
    assert replies[0].error_message == "not allowed"


@pytest.mark.asyncio
async def test_send_request_times_out_without_reply(connected_client) -> None:
    client, _ws = connected_client

    with pytest.raises(TimeoutError):
        await client.send_request(_request("req-3"), timeout=0.05)


@pytest.mark.asyncio
async def test_pushed_event_is_dispatched_to_on_event(
    fake_session: _FakeSession, fake_ws: _FakeWS
) -> None:
    received = []
    client = GatewayClient(
        "gateway.local",
        8443,
        "secret",
        on_event=lambda e: received.append(e),
        session=_as_session(fake_session),
    )

    await client.connect()
    fake_ws.push(
        '[{"op": "update", "payload": {}, "entity": {"device": "dev-1", '
        '"path": {"object_name": "lemonbeat", "object_instance_id": "0", '
        '"resource_name": "command"}}}]'
    )
    for _ in range(20):
        if received:
            break
        await asyncio.sleep(0.01)
    await client.disconnect()

    assert len(received) == 1
    assert received[0].entity.device == "dev-1"


@pytest.mark.asyncio
@pytest.mark.parametrize("timeout", [0, -1])
async def test_send_request_rejects_a_timeout_that_is_not_positive(
    connected_client, timeout
) -> None:
    client, ws = connected_client
    sent_before = len(ws.sent)

    with pytest.raises(ValueError, match="timeout must be positive"):
        await client.send_request(_request("req-4"), timeout=timeout)
    assert len(ws.sent) == sent_before


@pytest.mark.asyncio
async def test_send_request_without_wait_does_not_block(connected_client) -> None:
    client, ws = connected_client

    result = await client.send_request(_request("req-4"))

    assert len(result) == 0
    assert ws.sent


@pytest.mark.asyncio
@pytest.mark.parametrize("missing_id", [True, False])
async def test_send_request_waiting_for_replies_needs_request_ids(
    connected_client, missing_id: bool
) -> None:
    client, ws = connected_client
    request = _request("req-x") if missing_id else EgressMessageList([])
    if missing_id:
        request.root[0].request_id = None

    with pytest.raises(ValueError):
        await client.send_request(request, timeout=1)

    assert ws.sent == []


@pytest.mark.asyncio
async def test_send_request_rejects_duplicate_request_ids(connected_client) -> None:
    client, ws = connected_client
    request = _request("req-d") + _request("req-d")

    with pytest.raises(ValueError, match="unique"):
        await client.send_request(request, timeout=1)

    assert ws.sent == []


@pytest.mark.asyncio
async def test_send_request_rejects_a_request_id_that_is_already_waiting(
    connected_client,
) -> None:
    client, ws = connected_client
    first = asyncio.ensure_future(client.send_request(_request("req-w"), timeout=1))
    await asyncio.sleep(0)

    with pytest.raises(ValueError, match="already waiting"):
        await client.send_request(_request("req-w"), timeout=1)

    ws.push('[{"request_id": "req-w", "success": true, "payload": {}}]')
    assert len(await first) == 1


@pytest.mark.asyncio
async def test_on_connect_runs_concurrently_with_read_loop(
    fake_session: _FakeSession, fake_ws: _FakeWS
) -> None:
    """on_connect can itself send a request and await its reply.

    This is the shape a caller uses to re-run discovery after every
    (re)connect: on_connect must not block the read loop that resolves it.
    """

    async def _discover(client: GatewayClient) -> None:
        await client.send_request(_request("discovery"), timeout=1)

    client = GatewayClient(
        "gateway.local", 8443, "secret", session=_as_session(fake_session)
    )
    client._on_connect = lambda: _discover(client)  # noqa: SLF001 - set the connect hook directly

    connect_task = asyncio.ensure_future(client.connect())
    for _ in range(20):
        if fake_ws.sent:
            break
        await asyncio.sleep(0.01)
    fake_ws.push('[{"request_id": "discovery", "success": true, "payload": {}}]')

    await asyncio.wait_for(connect_task, timeout=1)
    await client.disconnect()

    assert fake_ws.sent


class _ScriptedSession:
    """Session whose successive ws_connect calls yield a socket or raise."""

    def __init__(self, *outcomes) -> None:
        self._outcomes = list(outcomes)
        self.ws_connect_calls: list[dict] = []
        self.closed = False

    def ws_connect(self, url, **kwargs):
        self.ws_connect_calls.append({"url": url, **kwargs})
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return _FakeWSConnectCtx(outcome)

    async def close(self) -> None:
        self.closed = True


def _rejected_password() -> aiohttp.WSServerHandshakeError:
    return aiohttp.WSServerHandshakeError(MagicMock(), (), status=401)


@pytest.mark.asyncio
async def test_fingerprint_pins_the_certificate(fake_session: _FakeSession) -> None:
    """With a fingerprint, the connection must present exactly that certificate."""
    client = GatewayClient(
        "gateway.local",
        8443,
        "secret",
        session=_as_session(fake_session),
        fingerprint="ab" * 32,
    )

    await client.connect()
    await client.disconnect()

    ssl_arg = fake_session.ws_connect_calls[0]["ssl"]
    assert isinstance(ssl_arg, aiohttp.Fingerprint)
    assert ssl_arg.fingerprint == bytes.fromhex("ab" * 32)


@pytest.mark.asyncio
async def test_without_fingerprint_any_certificate_is_accepted(
    fake_session: _FakeSession,
) -> None:
    """Without a fingerprint the connection is encrypted but not authenticated."""
    client = GatewayClient(
        "gateway.local", 8443, "secret", session=_as_session(fake_session)
    )

    await client.connect()
    await client.disconnect()

    ssl_arg = fake_session.ws_connect_calls[0]["ssl"]
    assert ssl_arg.verify_mode.name == "CERT_NONE"


@pytest.mark.asyncio
async def test_rejected_password_on_first_connect_raises_and_stops() -> None:
    """A 401 on the first connect reaches the caller and is not retried."""
    session = _ScriptedSession(_rejected_password())
    on_auth_failed = MagicMock()
    client = GatewayClient(
        "gateway.local",
        8443,
        "wrong",
        session=_as_session(session),
        on_auth_failed=on_auth_failed,
    )

    with pytest.raises(AuthenticationError):
        await client.connect()
    await client.disconnect()

    assert len(session.ws_connect_calls) == 1
    on_auth_failed.assert_not_called()


@pytest.mark.asyncio
async def test_rejected_password_after_connect_calls_back_and_stops(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 401 on a later reconnect notifies the caller and stops retrying."""
    monkeypatch.setattr(client_module, "RECONNECT_DELAY", 0)
    ws = _FakeWS()
    session = _ScriptedSession(ws, _rejected_password())
    auth_failed = asyncio.Event()
    client = GatewayClient(
        "gateway.local",
        8443,
        "secret",
        session=_as_session(session),
        on_auth_failed=auth_failed.set,
    )

    await client.connect()
    ws.push_closed()
    await asyncio.wait_for(auth_failed.wait(), timeout=1)
    assert client._task is not None
    await asyncio.wait_for(client._task, timeout=1)
    await client.disconnect()

    assert len(session.ws_connect_calls) == 2


@pytest.mark.asyncio
async def test_async_with_connects_and_disconnects(fake_session: _FakeSession) -> None:
    async with GatewayClient(
        "gateway.local", 8443, "secret", session=_as_session(fake_session)
    ) as client:
        assert len(fake_session.ws_connect_calls) == 1

    assert client._task is None


@pytest.mark.asyncio
async def test_connect_twice_raises(connected_client) -> None:
    client, _ws = connected_client

    with pytest.raises(RuntimeError):
        await client.connect()


@pytest.mark.asyncio
async def test_failed_first_connect_stops_the_client() -> None:
    """A first connect that fails leaves nothing retrying in the background."""
    session = _ScriptedSession(ConnectionError("unreachable"))
    client = GatewayClient(
        "gateway.local", 8443, "secret", session=_as_session(session)
    )

    with pytest.raises(ConnectionError):
        await client.connect()

    assert client._task is None
    assert len(session.ws_connect_calls) == 1


@pytest.mark.asyncio
async def test_failed_first_connect_closes_an_owned_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created_session = MagicMock()
    created_session.ws_connect = MagicMock(side_effect=ConnectionError("unreachable"))
    created_session.close = AsyncMock()
    monkeypatch.setattr(
        client_module.aiohttp, "ClientSession", MagicMock(return_value=created_session)
    )
    client = GatewayClient("gateway.local", 8443, "secret")

    with pytest.raises(ConnectionError):
        await client.connect()

    created_session.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_connect_times_out(monkeypatch: pytest.MonkeyPatch) -> None:
    """A gateway that never answers does not block connect() forever."""
    monkeypatch.setattr(client_module, "CONNECT_TIMEOUT", 0.05)

    class _HangingSession(_FakeSession):
        def ws_connect(self, url, **kwargs):
            return _Hang()

    class _Hang:
        async def __aenter__(self):
            await asyncio.sleep(10)

        async def __aexit__(self, *args) -> None:
            return None

    session = _HangingSession(_FakeWS())
    client = GatewayClient(
        "gateway.local", 8443, "secret", session=_as_session(session)
    )

    with pytest.raises(TimeoutError):
        await client.connect()

    assert client._task is None


@pytest.mark.asyncio
async def test_error_in_on_event_does_not_drop_the_connection(
    fake_session: _FakeSession, fake_ws: _FakeWS
) -> None:
    received = []

    def on_event(event) -> None:
        received.append(event)
        if len(received) == 1:
            raise ValueError("boom")

    client = GatewayClient(
        "gateway.local",
        8443,
        "secret",
        on_event=on_event,
        session=_as_session(fake_session),
    )
    event = (
        '[{"op": "update", "payload": {}, "entity": {"device": "dev-1", '
        '"path": {"object_name": "lemonbeat", "object_instance_id": "0", '
        '"resource_name": "command"}}}]'
    )

    await client.connect()
    fake_ws.push(event)
    fake_ws.push(event)
    for _ in range(20):
        if len(received) == 2:
            break
        await asyncio.sleep(0.01)
    await client.disconnect()

    assert len(received) == 2
    assert len(fake_session.ws_connect_calls) == 1


@pytest.mark.asyncio
async def test_discover_devices_sends_discovery_and_builds_devices(
    connected_client,
) -> None:
    client, ws = connected_client

    task = asyncio.ensure_future(client.discover_devices(timeout=1))
    await asyncio.sleep(0)
    sent = json.loads(ws.sent[-1])
    ws.push(
        json.dumps(
            [
                {"request_id": r["request_id"], "success": True, "payload": {}}
                for r in sent
            ]
        )
    )

    devices = await task
    assert len(sent) == len(build_discovery_obj())
    assert len(devices) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("timeout", [0, -1])
async def test_discover_devices_rejects_a_timeout_that_is_not_positive(
    connected_client, timeout
) -> None:
    client, ws = connected_client
    sent_before = len(ws.sent)

    with pytest.raises(ValueError, match="timeout must be positive"):
        await client.discover_devices(timeout=timeout)
    assert len(ws.sent) == sent_before


_EVENT = (
    '{"op": "update", "payload": {}, "entity": {"device": "dev-1", '
    '"path": {"object_name": "lemonbeat", "object_instance_id": "0", '
    '"resource_name": "command"}}}'
)


async def _next_event(client: GatewayClient):
    return await asyncio.wait_for(client.messages.get(), timeout=1)


@pytest.mark.asyncio
async def test_messages_queue_receives_pushed_events(connected_client) -> None:
    client, ws = connected_client

    ws.push(f"[{_EVENT}]")

    event = await _next_event(client)
    assert isinstance(event, Event)
    assert event.entity.device == "dev-1"


@pytest.mark.asyncio
async def test_messages_queue_skips_replies_to_pending_requests(
    connected_client,
) -> None:
    client, ws = connected_client

    task = asyncio.ensure_future(client.send_request(_request("req-5"), timeout=1))
    await asyncio.sleep(0)
    ws.push(f'[{{"request_id": "req-5", "success": true, "payload": {{}}}}, {_EVENT}]')
    await task

    event = await _next_event(client)
    assert isinstance(event, Event)
    assert client.messages.empty()


@pytest.mark.asyncio
async def test_messages_queue_keeps_unsolicited_replies_and_errors(
    connected_client,
) -> None:
    client, ws = connected_client

    ws.push(
        '[{"request_id": "late", "success": true, "payload": {}}, '
        '{"success": false, "metadata": {"error_source": "gateway"}, '
        '"payload": {"vs": "oops"}}]'
    )

    reply = await _next_event(client)
    error = await _next_event(client)
    assert isinstance(reply, Reply)
    assert reply.request_id == "late"
    assert isinstance(error, ErrorMessage)


@pytest.mark.asyncio
async def test_messages_queue_drops_the_oldest_when_full(
    monkeypatch: pytest.MonkeyPatch, fake_session: _FakeSession, fake_ws: _FakeWS
) -> None:
    monkeypatch.setattr(client_module, "MESSAGE_QUEUE_SIZE", 2)
    delivered = asyncio.Event()
    count = 0

    def on_event(event: Event) -> None:
        nonlocal count
        count += 1
        if count == 3:
            delivered.set()

    client = GatewayClient(
        "gateway.local",
        8443,
        "secret",
        on_event=on_event,
        session=_as_session(fake_session),
        queue_messages=True,
    )
    await client.connect()

    for device in ("dev-1", "dev-2", "dev-3"):
        fake_ws.push(f"[{_EVENT.replace('dev-1', device)}]")
    await asyncio.wait_for(delivered.wait(), timeout=1)
    await client.disconnect()

    first = await client.messages.get()
    second = await client.messages.get()
    assert isinstance(first, Event)
    assert isinstance(second, Event)
    assert [first.entity.device, second.entity.device] == ["dev-2", "dev-3"]


@pytest.mark.asyncio
async def test_events_are_queued_and_passed_to_on_event(
    fake_session: _FakeSession, fake_ws: _FakeWS
) -> None:
    received = []
    client = GatewayClient(
        "gateway.local",
        8443,
        "secret",
        on_event=received.append,
        session=_as_session(fake_session),
        queue_messages=True,
    )
    await client.connect()

    fake_ws.push(f"[{_EVENT}]")
    event = await _next_event(client)
    await client.disconnect()

    assert received == [event]


@pytest.mark.asyncio
async def test_discover_devices_raises_when_a_discovery_request_fails(
    connected_client,
) -> None:
    client, ws = connected_client

    task = asyncio.ensure_future(client.discover_devices(timeout=1))
    await asyncio.sleep(0)
    sent = json.loads(ws.sent[-1])
    replies = [
        {"request_id": r["request_id"], "success": True, "payload": {}} for r in sent
    ]
    replies[0] = {
        "request_id": sent[0]["request_id"],
        "success": False,
        "metadata": {"error_source": "gateway"},
        "payload": {"vs": "not allowed"},
    }
    ws.push(json.dumps(replies))

    with pytest.raises(DiscoveryError, match="not allowed") as raised:
        await task
    assert len(raised.value.devices) == 0


@pytest.mark.asyncio
async def test_discovery_error_carries_the_devices_of_the_working_service(
    connected_client, single_device_json
) -> None:
    client, ws = connected_client
    device_payload = json.loads(single_device_json)[0]["payload"]

    task = asyncio.ensure_future(client.discover_devices(timeout=1))
    await asyncio.sleep(0)
    sent = json.loads(ws.sent[-1])
    ws.push(
        json.dumps(
            [
                {
                    "request_id": sent[0]["request_id"],
                    "success": True,
                    "payload": device_payload,
                },
                {
                    "request_id": sent[1]["request_id"],
                    "success": False,
                    "payload": {},
                },
            ]
        )
    )

    with pytest.raises(DiscoveryError) as raised:
        await task
    assert list(raised.value.devices) == list(device_payload)
    assert len(raised.value.replies) == 2


@pytest.mark.asyncio
async def test_discover_devices_raises_on_an_unsuccessful_reply(
    connected_client,
) -> None:
    client, ws = connected_client

    task = asyncio.ensure_future(client.discover_devices(timeout=1))
    await asyncio.sleep(0)
    sent = json.loads(ws.sent[-1])
    ws.push(
        json.dumps(
            [
                {"request_id": r["request_id"], "success": False, "payload": {}}
                for r in sent
            ]
        )
    )

    with pytest.raises(DiscoveryError):
        await task


@pytest.mark.asyncio
async def test_messages_queue_is_off_by_default(fake_session: _FakeSession) -> None:
    client = GatewayClient(
        "gateway.local", 8443, "secret", session=_as_session(fake_session)
    )

    with pytest.raises(RuntimeError):
        client.messages  # noqa: B018


@pytest.mark.asyncio
async def test_certificate_and_fingerprint_are_available_after_connect(
    fake_session: _FakeSession, fake_ws: _FakeWS
) -> None:
    client = GatewayClient(
        "gateway.local", 8443, "secret", session=_as_session(fake_session)
    )
    assert client.certificate is None
    assert client.fingerprint is None

    await client.connect()
    await client.disconnect()

    assert client.certificate == b"gateway-certificate"
    assert client.fingerprint == hashlib.sha256(b"gateway-certificate").hexdigest()


@pytest.mark.asyncio
async def test_on_disconnect_runs_when_an_established_connection_drops(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(client_module, "RECONNECT_DELAY", 0)
    ws = _FakeWS()
    session = _ScriptedSession(ws, _rejected_password())
    on_disconnect = MagicMock()
    auth_failed = asyncio.Event()
    client = GatewayClient(
        "gateway.local",
        8443,
        "secret",
        session=_as_session(session),
        on_disconnect=on_disconnect,
        on_auth_failed=auth_failed.set,
    )

    await client.connect()
    ws.push_closed()
    await asyncio.wait_for(auth_failed.wait(), timeout=1)
    await client.disconnect()

    on_disconnect.assert_called_once_with()


@pytest.mark.asyncio
async def test_on_disconnect_does_not_run_for_disconnect_or_failed_connects() -> None:
    on_disconnect = MagicMock()
    failing = GatewayClient(
        "gateway.local",
        8443,
        "secret",
        session=_as_session(_ScriptedSession(ConnectionError("unreachable"))),
        on_disconnect=on_disconnect,
    )
    with pytest.raises(ConnectionError):
        await failing.connect()

    ws = _FakeWS()
    client = GatewayClient(
        "gateway.local",
        8443,
        "secret",
        session=_as_session(_ScriptedSession(ws)),
        on_disconnect=on_disconnect,
    )
    await client.connect()
    await client.disconnect()

    on_disconnect.assert_not_called()


@pytest.mark.asyncio
async def test_connection_loss_during_on_connect_fails_fast() -> None:
    """A hook waiting on the gateway is aborted when the socket drops."""
    ws = _FakeWS()
    hook_cancelled = asyncio.Event()

    async def on_connect() -> None:
        ws.push_closed()
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            hook_cancelled.set()
            raise

    client = GatewayClient(
        "gateway.local",
        8443,
        "secret",
        session=_as_session(_ScriptedSession(ws)),
        on_connect=on_connect,
    )

    with pytest.raises(ConnectionError):
        await asyncio.wait_for(client.connect(), timeout=1)

    assert hook_cancelled.is_set()


@pytest.mark.asyncio
async def test_connect_timeout_cancels_the_on_connect_hook(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(client_module, "CONNECT_TIMEOUT", 0.05)
    hook_cancelled = asyncio.Event()

    async def on_connect() -> None:
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            hook_cancelled.set()
            raise

    client = GatewayClient(
        "gateway.local",
        8443,
        "secret",
        session=_as_session(_ScriptedSession(_FakeWS())),
        on_connect=on_connect,
    )

    with pytest.raises(TimeoutError):
        await client.connect()

    assert hook_cancelled.is_set()


@pytest.mark.asyncio
async def test_error_in_on_auth_failed_does_not_escape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(client_module, "RECONNECT_DELAY", 0)
    ws = _FakeWS()
    called = asyncio.Event()

    def on_auth_failed() -> None:
        called.set()
        raise ValueError("boom")

    client = GatewayClient(
        "gateway.local",
        8443,
        "secret",
        session=_as_session(_ScriptedSession(ws, _rejected_password())),
        on_auth_failed=on_auth_failed,
    )

    await client.connect()
    ws.push_closed()
    await asyncio.wait_for(called.wait(), timeout=1)
    await asyncio.sleep(0)
    await client.disconnect()


@pytest.mark.asyncio
async def test_disconnect_from_on_event_raises_instead_of_deadlocking(
    fake_session: _FakeSession, fake_ws: _FakeWS
) -> None:
    errors: list[RuntimeError] = []

    async def on_event(event) -> None:
        try:
            await client.disconnect()
        except RuntimeError as err:
            errors.append(err)

    client = GatewayClient(
        "gateway.local",
        8443,
        "secret",
        on_event=on_event,
        session=_as_session(fake_session),
    )
    await client.connect()
    fake_ws.push(
        '[{"op": "update", "payload": {}, "entity": {"device": "dev-1", '
        '"path": {"object_name": "lemonbeat", "object_instance_id": "0", '
        '"resource_name": "command"}}}]'
    )
    for _ in range(20):
        if errors:
            break
        await asyncio.sleep(0.01)
    await asyncio.wait_for(client.disconnect(), timeout=1)

    assert len(errors) == 1
    assert "asyncio.create_task(client.disconnect())" in str(errors[0])


@pytest.mark.asyncio
async def test_disconnect_can_be_started_as_a_task_from_on_event(
    fake_session: _FakeSession, fake_ws: _FakeWS
) -> None:
    disconnecting: list[asyncio.Task[None]] = []

    def on_event(event) -> None:
        disconnecting.append(asyncio.create_task(client.disconnect()))

    client = GatewayClient(
        "gateway.local",
        8443,
        "secret",
        on_event=on_event,
        session=_as_session(fake_session),
    )
    await client.connect()
    fake_ws.push(
        '[{"op": "update", "payload": {}, "entity": {"device": "dev-1", '
        '"path": {"object_name": "lemonbeat", "object_instance_id": "0", '
        '"resource_name": "command"}}}]'
    )
    for _ in range(20):
        if disconnecting:
            break
        await asyncio.sleep(0.01)
    await asyncio.wait_for(disconnecting[0], timeout=1)

    assert client._task is None


@pytest.mark.asyncio
async def test_disconnect_from_on_connect_fails_the_connect(
    fake_session: _FakeSession,
) -> None:
    client = GatewayClient(
        "gateway.local",
        8443,
        "secret",
        on_connect=lambda: client.disconnect(),
        session=_as_session(fake_session),
    )

    with pytest.raises(RuntimeError, match="disconnect"):
        await asyncio.wait_for(client.connect(), timeout=1)


@pytest.mark.asyncio
async def test_disconnect_from_the_supervisor_callbacks_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """on_disconnect and on_auth_failed run in the supervisor task itself."""
    monkeypatch.setattr(client_module, "RECONNECT_DELAY", 0)
    ws = _FakeWS()
    errors: dict[str, RuntimeError] = {}
    auth_failed = asyncio.Event()

    async def try_disconnect(name: str) -> None:
        try:
            await client.disconnect()
        except RuntimeError as err:
            errors[name] = err

    async def on_auth_failed() -> None:
        await try_disconnect("on_auth_failed")
        auth_failed.set()

    client = GatewayClient(
        "gateway.local",
        8443,
        "secret",
        session=_as_session(_ScriptedSession(ws, _rejected_password())),
        on_disconnect=lambda: try_disconnect("on_disconnect"),
        on_auth_failed=on_auth_failed,
    )
    await client.connect()
    ws.push_closed()
    await asyncio.wait_for(auth_failed.wait(), timeout=1)
    await asyncio.wait_for(client.disconnect(), timeout=1)

    assert set(errors) == {"on_disconnect", "on_auth_failed"}


@pytest.mark.asyncio
async def test_connect_works_again_after_a_rejected_password(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(client_module, "RECONNECT_DELAY", 0)
    first_ws = _FakeWS()
    second_ws = _FakeWS()
    auth_failed = asyncio.Event()
    client = GatewayClient(
        "gateway.local",
        8443,
        "secret",
        session=_as_session(
            _ScriptedSession(first_ws, _rejected_password(), second_ws)
        ),
        on_auth_failed=auth_failed.set,
    )

    await client.connect()
    first_ws.push_closed()
    await asyncio.wait_for(auth_failed.wait(), timeout=1)
    await asyncio.sleep(0)
    await client.connect()
    await client.disconnect()


@pytest.mark.parametrize(
    "fingerprint",
    [
        "AB" * 32,
        ":".join(["ab"] * 32),
        ":".join(["AB"] * 32),
    ],
)
def test_fingerprint_accepts_hex_with_or_without_colons(fingerprint: str) -> None:
    client = GatewayClient("gateway.local", 8443, "secret", fingerprint=fingerprint)

    assert isinstance(client._ssl, aiohttp.Fingerprint)
    assert client._ssl.fingerprint == bytes.fromhex("ab" * 32)


@pytest.mark.parametrize("fingerprint", ["", "xyz", "ab" * 20, "ab" * 33, "ab:cd:"])
def test_fingerprint_must_be_a_sha256_hash(fingerprint: str) -> None:
    with pytest.raises(ValueError, match="SHA-256"):
        GatewayClient("gateway.local", 8443, "secret", fingerprint=fingerprint)


@pytest.mark.asyncio
async def test_failed_first_connect_is_not_logged_as_a_lost_connection(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level("DEBUG", logger="gardena_smart_local_api.client")
    ws = _FakeWS()
    client = GatewayClient(
        "gateway.local",
        8443,
        "secret",
        session=_as_session(_ScriptedSession(ConnectionError("unreachable"), ws)),
    )

    with pytest.raises(ConnectionError):
        await client.connect()
    await client.connect()
    await client.disconnect()

    messages = [record.getMessage() for record in caplog.records]
    assert not any("Lost connection" in m for m in messages)
    assert not any("Reconnected" in m for m in messages)
    assert any(m.startswith("Connected to") for m in messages)


@pytest.mark.asyncio
async def test_a_lost_connection_is_logged_and_the_reconnect_reported(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(client_module, "RECONNECT_DELAY", 0)
    caplog.set_level("INFO", logger="gardena_smart_local_api.client")
    first_ws = _FakeWS()
    second_ws = _FakeWS()
    client = GatewayClient(
        "gateway.local",
        8443,
        "secret",
        session=_as_session(
            _ScriptedSession(first_ws, ConnectionError("dropped"), second_ws)
        ),
    )

    await client.connect()
    first_ws.push_closed()
    for _ in range(50):
        if any("Reconnected" in r.getMessage() for r in caplog.records):
            break
        await asyncio.sleep(0.01)
    await client.disconnect()

    messages = [record.getMessage() for record in caplog.records]
    assert any("Lost connection" in m for m in messages)
    assert any("Reconnected" in m for m in messages)


@pytest.mark.asyncio
async def test_send_request_raises_connection_error_on_a_closing_socket(
    connected_client,
) -> None:
    client, ws = connected_client
    ws.closed = True

    with pytest.raises(ConnectionError):
        await client.send_request(build_discovery_obj())

    assert ws.sent == []


@pytest.mark.asyncio
async def test_binary_frame_that_is_not_utf8_is_skipped(connected_client) -> None:
    client, ws = connected_client

    ws.push_binary(b"\xff\xfe")
    ws.push(f"[{_EVENT}]")

    event = await _next_event(client)
    assert isinstance(event, Event)
    assert client.connected


@pytest.mark.asyncio
@pytest.mark.parametrize("frame", ["not json", '{"request_id": "req-1"}', "null"])
async def test_frame_that_is_not_a_list_of_messages_is_skipped(
    connected_client, frame: str
) -> None:
    client, ws = connected_client

    ws.push(frame)
    ws.push(f"[{_EVENT}]")

    event = await _next_event(client)
    assert isinstance(event, Event)
    assert client.connected


@pytest.mark.asyncio
async def test_unknown_message_does_not_drop_the_rest_of_its_frame(
    connected_client,
) -> None:
    client, ws = connected_client

    task = asyncio.ensure_future(client.send_request(_request("req-1"), timeout=1))
    await asyncio.sleep(0)
    ws.push(
        '[{"unknown": "future message"}, '
        '{"request_id": "req-1", "success": true, "payload": {}}, '
        f"{_EVENT}]"
    )

    replies = await task
    assert [reply.request_id for reply in replies] == ["req-1"]
    event = await _next_event(client)
    assert isinstance(event, Event)
    assert client.messages.empty()
