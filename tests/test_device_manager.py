# SPDX-FileCopyrightText: 2026 GARDENA GmbH
#
# SPDX-License-Identifier: LGPL-3.0-or-later

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import gardena_smart_local_api.client.manager as manager_module
from gardena_smart_local_api.client import (
    DeviceManager,
    DiscoveryError,
    InclusionError,
    RequestError,
)
from gardena_smart_local_api.devices import DeviceMap, Sensor1
from gardena_smart_local_api.messages import Event, IngressMessageList, Reply
from gardena_smart_local_api.resources import IpsoPath
from gardena_smart_local_api.sgtin96 import SGTIN96Info

from .test_client import _as_session, fake_session, fake_ws  # noqa: F401

pytestmark = pytest.mark.asyncio

SENSOR_ID = "3034F8EE901267400000B333"


def _event(
    device: str | None = "dev-1",
    op: str = "update",
    path: str = "lemonbeat/0",
    service: str | None = None,
    payload: dict | None = None,
) -> Event:
    entity: dict[str, str] = {"path": path}
    if device is not None:
        entity["device"] = device
    if service is not None:
        entity["service"] = service
    message = {
        "op": op,
        "entity": entity,
        "metadata": {"source": "lemonbeatd", "sequence": 1},
        "payload": payload or {},
    }
    return IngressMessageList.model_validate_json(json.dumps([message]))[0]


def _includable_event(
    instance_id: str | None = "inst-1",
    identifier: str | None = SENSOR_ID,
    service: str | None = "lemonbeatd",
    op: str = "update",
) -> Event:
    path = (
        "includable_device"
        if instance_id is None
        else f"includable_device/{instance_id}"
    )
    payload = {} if identifier is None else {"identifier": {"vs": identifier}}
    return _event(device=None, op=op, path=path, service=service, payload=payload)


@pytest.fixture
def changed() -> list[frozenset[str]]:
    return []


@pytest.fixture
def manager(changed: list[frozenset[str]]) -> DeviceManager:
    return DeviceManager(
        "gateway.local", 8443, "secret", on_devices_changed=changed.append
    )


@pytest.fixture
def quick_rediscovery():
    with patch.object(manager_module, "UNKNOWN_DEVICE_DISCOVERY_DEBOUNCE", 0.01):
        yield


async def _know(
    manager: DeviceManager, changed: list[frozenset[str]], *devices
) -> None:
    """Make the manager know the devices, without leaving a notification behind."""
    discovered = DeviceMap({device.id: device for device in devices})
    with patch.object(
        manager.client, "discover_devices", AsyncMock(return_value=discovered)
    ):
        await manager.discover()
    changed.clear()


# --- wiring ---


async def test_the_client_reports_back_to_the_manager() -> None:
    on_disconnect, on_auth_failed = MagicMock(), MagicMock()
    session = MagicMock()

    with patch.object(manager_module, "GatewayClient") as client_class:
        manager = DeviceManager(
            "gateway.local",
            8443,
            "secret",
            session=session,
            fingerprint="ab" * 32,
            on_disconnect=on_disconnect,
            on_auth_failed=on_auth_failed,
        )

    client_class.assert_called_once_with(
        "gateway.local",
        8443,
        "secret",
        session=session,
        fingerprint="ab" * 32,
        on_connect=manager._on_connect,
        on_event=manager._on_event,
        on_disconnect=on_disconnect,
        on_auth_failed=on_auth_failed,
    )
    assert manager.client is client_class.return_value


async def test_context_manager_connects_and_disconnects(
    manager: DeviceManager,
) -> None:
    with (
        patch.object(manager.client, "connect", AsyncMock()) as connect,
        patch.object(manager.client, "disconnect", AsyncMock()) as disconnect,
    ):
        async with manager:
            connect.assert_awaited_once_with()
            disconnect.assert_not_awaited()

    disconnect.assert_awaited_once_with()


# --- through the client ---


async def test_a_gateway_that_connects_discovers_and_pushes(
    changed: list[frozenset[str]],
    fake_session,  # noqa: F811 - the fixtures of test_client
    fake_ws,  # noqa: F811
    water_control_json,
    update_event_json,
) -> None:
    manager = DeviceManager(
        "gateway.local",
        8443,
        "secret",
        session=_as_session(fake_session),
        on_devices_changed=changed.append,
    )

    connecting = asyncio.ensure_future(manager.connect())
    for _ in range(100):
        if fake_ws.sent:
            break
        await asyncio.sleep(0.01)
    # The gateway answers the discovery with the water control it knows.
    requests = json.loads(fake_ws.sent[-1])
    known = json.loads(water_control_json)
    replies = []
    for number, request in enumerate(requests):
        reply = known[number] if number < len(known) else {"success": True}
        replies.append({"payload": {}, **reply, "request_id": request["request_id"]})
    fake_ws.push(json.dumps(replies))
    await asyncio.wait_for(connecting, 2)

    [device_id] = manager.devices
    assert changed == [frozenset({device_id})]

    # Then it pushes an update for that device.
    fake_ws.push(update_event_json)
    for _ in range(100):
        if len(changed) == 2:
            break
        await asyncio.sleep(0.01)
    await manager.disconnect()

    assert changed[1] == frozenset({device_id})


# --- discovery ---


async def test_every_connect_discovers_the_devices(
    manager: DeviceManager, changed: list[frozenset[str]], water_control
) -> None:
    discover = AsyncMock(return_value=DeviceMap({water_control.id: water_control}))

    with patch.object(manager.client, "discover_devices", discover):
        await manager._on_connect()

    discover.assert_awaited_once()
    assert manager.devices[water_control.id] is water_control
    assert changed == [frozenset({water_control.id})]


async def test_discovery_replaces_the_devices(
    manager: DeviceManager, changed: list[frozenset[str]], water_control, sensor1
) -> None:
    await _know(manager, changed, sensor1)

    with patch.object(
        manager.client,
        "discover_devices",
        AsyncMock(return_value=DeviceMap({water_control.id: water_control})),
    ):
        await manager.discover()

    assert list(manager.devices) == [water_control.id]
    assert changed == [frozenset({sensor1.id, water_control.id})]


async def test_failed_discovery_keeps_the_devices(
    manager: DeviceManager, changed: list[frozenset[str]], water_control
) -> None:
    await _know(manager, changed, water_control)
    error = DiscoveryError("failed", IngressMessageList([]), DeviceMap({}))

    with (
        patch.object(manager.client, "discover_devices", AsyncMock(side_effect=error)),
        pytest.raises(DiscoveryError),
    ):
        await manager.discover()

    assert list(manager.devices) == [water_control.id]
    assert changed == []


async def test_discovery_can_leave_the_notification_to_the_caller(
    manager: DeviceManager, changed: list[frozenset[str]], water_control
) -> None:
    with patch.object(
        manager.client,
        "discover_devices",
        AsyncMock(return_value=DeviceMap({water_control.id: water_control})),
    ):
        await manager.discover(notify=False)

    assert water_control.id in manager.devices
    assert changed == []


# --- callbacks ---


async def test_the_callback_may_be_a_coroutine_function(
    water_control,
) -> None:
    calls: list[frozenset[str]] = []

    async def on_devices_changed(ids: frozenset[str]) -> None:
        calls.append(ids)

    manager = DeviceManager(
        "gateway.local", 8443, "secret", on_devices_changed=on_devices_changed
    )
    with patch.object(
        manager.client,
        "discover_devices",
        AsyncMock(return_value=DeviceMap({water_control.id: water_control})),
    ):
        await manager.discover()

    assert calls == [frozenset({water_control.id})]


async def test_an_error_in_the_callback_is_logged_not_raised(
    water_control, caplog: pytest.LogCaptureFixture
) -> None:
    manager = DeviceManager(
        "gateway.local",
        8443,
        "secret",
        on_devices_changed=MagicMock(side_effect=ValueError("boom")),
    )
    with patch.object(
        manager.client,
        "discover_devices",
        AsyncMock(return_value=DeviceMap({water_control.id: water_control})),
    ):
        await manager.discover()

    assert "Error in on_devices_changed callback" in caplog.text
    assert water_control.id in manager.devices


async def test_the_callback_is_optional(water_control) -> None:
    manager = DeviceManager("gateway.local", 8443, "secret")
    with patch.object(
        manager.client,
        "discover_devices",
        AsyncMock(return_value=DeviceMap({water_control.id: water_control})),
    ):
        await manager.discover()

    assert water_control.id in manager.devices


# --- events ---


async def test_an_event_updates_the_device(
    manager: DeviceManager,
    changed: list[frozenset[str]],
    water_control,
    update_event,
) -> None:
    await _know(manager, changed, water_control)

    await manager._on_event(update_event[0])

    battery = water_control.get_value(
        IpsoPath(
            object_name="lemonbeat",
            object_instance_id="0",
            resource_name="battery_level",
        )
    )
    assert battery == 65
    assert changed == [frozenset({water_control.id})]


async def test_an_event_without_a_device_is_ignored(
    manager: DeviceManager, changed: list[frozenset[str]]
) -> None:
    await manager._on_event(_event(device=None))

    assert changed == []


async def test_a_device_removal_drops_the_device(
    manager: DeviceManager, changed: list[frozenset[str]], water_control
) -> None:
    await _know(manager, changed, water_control)

    await manager._on_event(_event(device=water_control.id, op="delete", path=""))

    assert water_control.id not in manager.devices
    assert changed == [frozenset({water_control.id})]


async def test_the_removal_of_a_value_keeps_the_device(
    manager: DeviceManager, changed: list[frozenset[str]], water_control
) -> None:
    await _know(manager, changed, water_control)

    await manager._on_event(_event(device=water_control.id, op="delete"))

    assert water_control.id in manager.devices
    assert changed == [frozenset({water_control.id})]


async def test_an_event_for_a_device_being_excluded_is_ignored(
    manager: DeviceManager,
    changed: list[frozenset[str]],
    quick_rediscovery,
    water_control,
    update_event,
) -> None:
    # The device is out of the device map while it is excluded. Its events must
    # not be taken for those of a new device, as the discovery that follows
    # would bring it back.
    manager._excluding[water_control.id] = water_control
    discover = AsyncMock()

    with patch.object(manager, "discover", discover):
        await manager._on_event(update_event[0])
        await asyncio.sleep(0.1)

    discover.assert_not_awaited()
    assert changed == []


async def test_a_failing_event_is_logged_and_skipped(
    manager: DeviceManager,
    changed: list[frozenset[str]],
    caplog: pytest.LogCaptureFixture,
) -> None:
    with patch.object(
        manager, "_apply_event", AsyncMock(side_effect=RuntimeError("bad"))
    ):
        await manager._on_event(_event())

    assert "Error handling event" in caplog.text
    assert changed == []


# --- devices that were added without the manager ---


async def test_a_burst_for_an_unknown_device_causes_one_discovery(
    manager: DeviceManager, quick_rediscovery
) -> None:
    discover = AsyncMock()

    with patch.object(manager, "discover", discover):
        for device in ("dev-1", "dev-1", "dev-2"):
            await manager._on_event(_event(device=device))
        await asyncio.sleep(0.1)

    discover.assert_awaited_once()


async def test_an_unknown_device_that_is_being_included_causes_no_discovery(
    manager: DeviceManager, quick_rediscovery
) -> None:
    manager._including.add("dev-1")
    discover = AsyncMock()

    with patch.object(manager, "discover", discover):
        await manager._on_event(_event(device="dev-1"))
        await asyncio.sleep(0.1)

    discover.assert_not_awaited()


async def test_the_removal_of_an_unknown_device_causes_no_discovery(
    manager: DeviceManager, quick_rediscovery
) -> None:
    discover = AsyncMock()

    with patch.object(manager, "discover", discover):
        await manager._on_event(_event(device="dev-1", op="delete", path=""))
        await asyncio.sleep(0.1)

    discover.assert_not_awaited()


async def test_an_event_during_a_running_discovery_asks_for_one_more(
    manager: DeviceManager, quick_rediscovery
) -> None:
    release = asyncio.Event()
    started = asyncio.Event()
    calls = 0

    async def _discover(**kwargs: object) -> None:
        nonlocal calls
        calls += 1
        started.set()
        if calls == 1:
            await release.wait()

    with patch.object(manager, "discover", _discover):
        await manager._on_event(_event(device="dev-1"))
        await asyncio.wait_for(started.wait(), 1)
        await manager._on_event(_event(device="dev-2"))
        release.set()
        await asyncio.sleep(0.1)

    assert calls == 2


async def test_a_failing_discovery_is_logged_and_can_be_retried(
    manager: DeviceManager, quick_rediscovery, caplog: pytest.LogCaptureFixture
) -> None:
    discover = AsyncMock(side_effect=[TimeoutError(), None])

    with patch.object(manager, "discover", discover):
        await manager._on_event(_event(device="dev-1"))
        await asyncio.sleep(0.1)
        assert "Discovery for unknown device(s) failed" in caplog.text
        await manager._on_event(_event(device="dev-1"))
        await asyncio.sleep(0.1)

    assert discover.await_count == 2


# --- includable devices ---


async def test_a_device_in_inclusion_mode_is_listed(manager: DeviceManager) -> None:
    await manager._on_event(_includable_event())

    device = manager.includable_devices["inst-1"]
    assert device.device_id == SENSOR_ID
    assert device.service == "lemonbeatd"
    info = SGTIN96Info.from_hex(SENSOR_ID)
    assert device.name == f"{await info.get_model_name()} {info.serial:08d}"
    assert device.device_class is Sensor1
    manager._includable_timers["inst-1"].cancel()


async def test_includable_devices_are_a_copy(manager: DeviceManager) -> None:
    await manager._on_event(_includable_event())

    manager.includable_devices.clear()

    assert "inst-1" in manager.includable_devices
    manager._includable_timers["inst-1"].cancel()


async def test_a_device_in_inclusion_mode_is_not_a_change_of_the_devices(
    manager: DeviceManager, changed: list[frozenset[str]]
) -> None:
    await manager._on_event(_includable_event())

    assert changed == []
    manager._includable_timers["inst-1"].cancel()


async def test_a_heartbeat_keeps_the_device_listed(manager: DeviceManager) -> None:
    await manager._on_event(_includable_event())
    first_timer = manager._includable_timers["inst-1"]

    await manager._on_event(_includable_event())

    assert first_timer.cancelled()
    assert list(manager.includable_devices) == ["inst-1"]
    manager._includable_timers["inst-1"].cancel()


async def test_a_silent_device_leaves_the_list(manager: DeviceManager) -> None:
    with patch.object(manager_module, "INCLUDABLE_HEARTBEAT_TIMEOUT", 0.01):
        await manager._on_event(_includable_event())
        assert "inst-1" in manager.includable_devices
        await asyncio.sleep(0.1)

    assert manager.includable_devices == {}
    assert manager._includable_timers == {}


async def test_a_device_leaving_inclusion_mode_is_forgotten(
    manager: DeviceManager,
) -> None:
    await manager._on_event(_includable_event())

    await manager._on_event(_includable_event(op="delete"))

    assert manager.includable_devices == {}
    assert manager._includable_timers == {}


@pytest.mark.parametrize(
    "event",
    [
        pytest.param(_includable_event(instance_id=None), id="no-instance"),
        pytest.param(_includable_event(service=None), id="no-service"),
        pytest.param(_includable_event(identifier=None), id="no-identifier"),
        pytest.param(_includable_event(identifier="nonsense"), id="bad-identifier"),
    ],
)
async def test_an_incomplete_includable_event_is_ignored(
    manager: DeviceManager, event: Event
) -> None:
    await manager._on_event(event)

    assert manager.includable_devices == {}
    for timer in manager._includable_timers.values():
        timer.cancel()


# --- inclusion ---


async def _make_includable(manager: DeviceManager) -> None:
    await manager._on_event(_includable_event())
    manager._includable_timers.pop("inst-1").cancel()


async def test_a_device_is_included(
    manager: DeviceManager, changed: list[frozenset[str]], sensor1
) -> None:
    await _make_includable(manager)

    async def _send(request: object, timeout: float) -> IngressMessageList:
        # The gateway takes the device out of inclusion mode right away.
        manager._includable.pop("inst-1")
        return IngressMessageList([])

    with (
        patch.object(manager.client, "send_request", _send),
        patch.object(
            manager.client,
            "discover_devices",
            AsyncMock(return_value=DeviceMap({sensor1.id: sensor1})),
        ),
    ):
        device = await manager.include_device("inst-1")

    assert device is sensor1
    assert changed == [frozenset({sensor1.id})]
    assert not manager._including


async def test_the_notification_for_an_included_device_can_be_left_to_the_caller(
    manager: DeviceManager, changed: list[frozenset[str]], sensor1
) -> None:
    await _make_includable(manager)

    async def _send(request: object, timeout: float) -> IngressMessageList:
        manager._includable.pop("inst-1")
        return IngressMessageList([])

    with (
        patch.object(manager.client, "send_request", _send),
        patch.object(
            manager.client,
            "discover_devices",
            AsyncMock(return_value=DeviceMap({sensor1.id: sensor1})),
        ),
    ):
        await manager.include_device("inst-1", notify=False)

    assert sensor1.id in manager.devices
    assert changed == []


async def test_an_unknown_instance_cannot_be_included(manager: DeviceManager) -> None:
    with pytest.raises(InclusionError, match="inst-1"):
        await manager.include_device("inst-1")


@pytest.mark.parametrize(
    "outcome",
    [
        TimeoutError(),
        ConnectionError("not connected"),
        RequestError("rejected", IngressMessageList([])),
    ],
)
async def test_an_inclusion_the_gateway_does_not_accept_fails(
    manager: DeviceManager, outcome: Exception
) -> None:
    await _make_includable(manager)

    with (
        patch.object(manager.client, "send_request", AsyncMock(side_effect=outcome)),
        pytest.raises(InclusionError) as error,
    ):
        await manager.include_device("inst-1")

    assert error.value.__cause__ is outcome
    assert not manager._including


async def test_an_inclusion_a_device_never_finishes_fails(
    manager: DeviceManager,
) -> None:
    await _make_includable(manager)

    with (
        patch.object(manager_module, "INCLUSION_TIMEOUT", 1),
        patch.object(manager_module.asyncio, "sleep", AsyncMock()),
        patch.object(manager.client, "send_request", AsyncMock()),
        pytest.raises(InclusionError, match="Timeout"),
    ):
        await manager.include_device("inst-1")

    assert not manager._including


async def test_an_inclusion_finishing_during_the_last_wait_succeeds(
    manager: DeviceManager, sensor1
) -> None:
    await _make_includable(manager)

    async def _sleep(_delay: float) -> None:
        manager._includable.pop("inst-1", None)

    with (
        patch.object(manager_module, "INCLUSION_TIMEOUT", 1),
        patch.object(manager_module.asyncio, "sleep", _sleep),
        patch.object(manager.client, "send_request", AsyncMock()),
        patch.object(
            manager.client,
            "discover_devices",
            AsyncMock(return_value=DeviceMap({sensor1.id: sensor1})),
        ),
    ):
        assert await manager.include_device("inst-1") is sensor1


async def test_an_inclusion_fails_if_the_discovery_afterwards_fails(
    manager: DeviceManager,
) -> None:
    await _make_includable(manager)

    async def _send(request: object, timeout: float) -> IngressMessageList:
        manager._includable.pop("inst-1")
        return IngressMessageList([])

    with (
        patch.object(manager.client, "send_request", _send),
        patch.object(
            manager.client, "discover_devices", AsyncMock(side_effect=TimeoutError)
        ),
        pytest.raises(InclusionError, match="discovery"),
    ):
        await manager.include_device("inst-1")

    assert not manager._including


async def test_an_inclusion_fails_if_the_device_is_not_found_afterwards(
    manager: DeviceManager,
) -> None:
    await _make_includable(manager)

    async def _send(request: object, timeout: float) -> IngressMessageList:
        manager._includable.pop("inst-1")
        return IngressMessageList([])

    with (
        patch.object(manager.client, "send_request", _send),
        patch.object(
            manager.client,
            "discover_devices",
            AsyncMock(return_value=DeviceMap({})),
        ),
        pytest.raises(InclusionError, match="not found"),
    ):
        await manager.include_device("inst-1")


# --- exclusion ---


async def test_an_excluded_device_is_gone(
    manager: DeviceManager, changed: list[frozenset[str]], water_control
) -> None:
    await _know(manager, changed, water_control)

    with patch.object(manager.client, "send_request", AsyncMock()) as send:
        await manager.exclude_device(water_control.id)

    send.assert_awaited_once()
    assert water_control.id not in manager.devices
    assert not manager._excluding
    assert changed == [frozenset({water_control.id})]


async def test_excluding_an_unknown_device_does_nothing(
    manager: DeviceManager, changed: list[frozenset[str]]
) -> None:
    with patch.object(manager.client, "send_request", AsyncMock()) as send:
        await manager.exclude_device("dev-1")

    send.assert_not_awaited()
    assert changed == []


@pytest.mark.parametrize(
    "outcome",
    [
        TimeoutError(),
        ConnectionError("not connected"),
        RequestError("rejected", IngressMessageList([])),
        RuntimeError("boom"),
    ],
)
async def test_a_device_the_gateway_does_not_release_comes_back(
    manager: DeviceManager,
    changed: list[frozenset[str]],
    water_control,
    outcome: Exception,
) -> None:
    await _know(manager, changed, water_control)

    with (
        patch.object(manager.client, "send_request", AsyncMock(side_effect=outcome)),
        pytest.raises(type(outcome)),
    ):
        await manager.exclude_device(water_control.id)

    assert manager.devices[water_control.id] is water_control
    assert not manager._excluding
    # Once for taking the device away, once for bringing it back.
    assert changed == [frozenset({water_control.id})] * 2


async def test_a_discovery_during_an_exclusion_does_not_bring_the_device_back(
    manager: DeviceManager, changed: list[frozenset[str]], water_control
) -> None:
    await _know(manager, changed, water_control)

    async def _send(request: object, timeout: float) -> IngressMessageList:
        manager._replace_devices(DeviceMap({water_control.id: water_control}))
        assert water_control.id not in manager.devices
        return IngressMessageList([])

    with patch.object(manager.client, "send_request", _send):
        await manager.exclude_device(water_control.id)

    assert water_control.id not in manager.devices


async def test_a_discovery_started_before_an_exclusion_does_not_bring_the_device_back(
    manager: DeviceManager, changed: list[frozenset[str]], water_control
) -> None:
    # A snapshot taken before the reset still lists the excluded device.
    await _know(manager, changed, water_control)
    release = asyncio.Event()

    async def _discover(timeout: float) -> DeviceMap:
        await release.wait()
        return DeviceMap({water_control.id: water_control})

    with patch.object(manager.client, "discover_devices", _discover):
        discovery = asyncio.create_task(manager.discover())
        await asyncio.sleep(0)
        with patch.object(manager.client, "send_request", AsyncMock()):
            await manager.exclude_device(water_control.id)
        release.set()
        await discovery

    assert water_control.id not in manager.devices


async def test_a_discovery_started_after_an_exclusion_sees_the_device_again(
    manager: DeviceManager, changed: list[frozenset[str]], water_control
) -> None:
    # A device that is included again after its exclusion comes back.
    await _know(manager, changed, water_control)
    with patch.object(manager.client, "send_request", AsyncMock()):
        await manager.exclude_device(water_control.id)

    await _know(manager, changed, water_control)

    assert manager.devices[water_control.id] is water_control


async def test_discoveries_at_the_same_time_each_keep_their_exclusions(
    manager: DeviceManager, changed: list[frozenset[str]], water_control
) -> None:
    # The second discovery started after the exclusion, so its answer counts.
    await _know(manager, changed, water_control)
    first_answer, second_answer = asyncio.Event(), asyncio.Event()
    answers = [first_answer, second_answer]

    async def _discover(timeout: float) -> DeviceMap:
        await answers.pop(0).wait()
        return DeviceMap({water_control.id: water_control})

    with patch.object(manager.client, "discover_devices", _discover):
        first = asyncio.create_task(manager.discover())
        await asyncio.sleep(0)
        with patch.object(manager.client, "send_request", AsyncMock()):
            await manager.exclude_device(water_control.id)
        second = asyncio.create_task(manager.discover())
        await asyncio.sleep(0)
        second_answer.set()
        await second
        assert water_control.id in manager.devices
        first_answer.set()
        await first

    assert water_control.id not in manager.devices
    assert not manager._waiting_discoveries


async def test_a_discovery_that_ends_first_leaves_the_other_one_waiting(
    manager: DeviceManager, changed: list[frozenset[str]], water_control
) -> None:
    # Both discoveries wait with nothing excluded yet. The one that started
    # second gets its answer first, then the device is excluded while the
    # first one still waits.
    await _know(manager, changed, water_control)
    first_answer, second_answer = asyncio.Event(), asyncio.Event()
    answers = [first_answer, second_answer]

    async def _discover(timeout: float) -> DeviceMap:
        await answers.pop(0).wait()
        return DeviceMap({water_control.id: water_control})

    with patch.object(manager.client, "discover_devices", _discover):
        first = asyncio.create_task(manager.discover())
        second = asyncio.create_task(manager.discover())
        await asyncio.sleep(0)
        second_answer.set()
        await second
        with patch.object(manager.client, "send_request", AsyncMock()):
            await manager.exclude_device(water_control.id)
        first_answer.set()
        await first

    assert water_control.id not in manager.devices
    assert not manager._waiting_discoveries


# --- firmware ---


def _firmware_reply(device_id: str, success: bool = True) -> Reply:
    return Reply(
        request_id="1",
        success=success,
        payload={device_id: {"firmware": {"state": "x"}}},
    )


async def test_the_firmware_state_is_applied(
    manager: DeviceManager, changed: list[frozenset[str]], water_control
) -> None:
    await _know(manager, changed, water_control)
    replies = IngressMessageList([_firmware_reply(water_control.id)])

    with patch.object(manager.client, "send_request", AsyncMock(return_value=replies)):
        await manager.refresh_firmware(water_control.id)

    assert water_control.data["firmware"]["state"] == "x"
    assert changed == [frozenset({water_control.id})]


async def test_the_firmware_state_of_an_unknown_device_is_not_asked_for(
    manager: DeviceManager,
) -> None:
    with patch.object(manager.client, "send_request", AsyncMock()) as send:
        await manager.refresh_firmware("dev-1")

    send.assert_not_awaited()


async def test_what_succeeded_is_applied_when_a_firmware_request_fails(
    manager: DeviceManager, changed: list[frozenset[str]], water_control
) -> None:
    await _know(manager, changed, water_control)
    error = RequestError(
        "failed",
        IngressMessageList(
            [
                _firmware_reply(water_control.id),
                Reply(request_id="2", success=False),
            ]
        ),
    )

    with (
        patch.object(manager.client, "send_request", AsyncMock(side_effect=error)),
        pytest.raises(RequestError),
    ):
        await manager.refresh_firmware(water_control.id)

    assert water_control.data["firmware"]["state"] == "x"
    assert changed == [frozenset({water_control.id})]


# --- commands ---


async def test_a_command_holds_the_notifications_back_until_it_settles(
    manager: DeviceManager, changed: list[frozenset[str]], water_control, update_event
) -> None:
    await _know(manager, changed, water_control)

    async def _send(request: object, timeout: float) -> IngressMessageList:
        # The gateway reports the new state while it answers the command.
        await manager._on_event(update_event[0])
        assert changed == []
        return IngressMessageList([])

    with patch.object(manager.client, "send_request", _send):
        await manager.send_command(water_control.id, MagicMock())

    assert changed == [frozenset({water_control.id})]
    assert not manager._commands


async def test_a_rejected_command_settles_too(
    manager: DeviceManager, changed: list[frozenset[str]], water_control
) -> None:
    await _know(manager, changed, water_control)
    error = RequestError("rejected", IngressMessageList([]))

    with (
        patch.object(manager.client, "send_request", AsyncMock(side_effect=error)),
        pytest.raises(RequestError),
    ):
        await manager.send_command(water_control.id, MagicMock())

    assert changed == [frozenset({water_control.id})]
    assert not manager._commands


async def test_overlapping_commands_settle_together(
    manager: DeviceManager, changed: list[frozenset[str]], water_control
) -> None:
    await _know(manager, changed, water_control)
    first_request, second_request = MagicMock(), MagicMock()
    release_first = asyncio.Event()
    second_started = asyncio.Event()

    async def _send(request: object, timeout: float) -> IngressMessageList:
        if request is first_request:
            await release_first.wait()
        else:
            second_started.set()
        return IngressMessageList([])

    with patch.object(manager.client, "send_request", _send):
        first = asyncio.ensure_future(
            manager.send_command(water_control.id, first_request)
        )
        await asyncio.sleep(0)
        await manager.send_command(water_control.id, second_request)
        assert second_started.is_set()
        assert changed == []
        release_first.set()
        await first

    assert changed == [frozenset({water_control.id})]


# --- disconnect ---


async def test_disconnect_stops_everything_that_runs_for_the_manager(
    manager: DeviceManager, quick_rediscovery
) -> None:
    await _make_includable(manager)
    manager._includable_timers["inst-1"] = asyncio.get_running_loop().call_later(
        99, lambda: None
    )
    release = asyncio.Event()

    async def _hang(**kwargs: object) -> None:
        await release.wait()

    with (
        patch.object(manager, "discover", _hang),
        patch.object(manager.client, "disconnect", AsyncMock()) as disconnect,
    ):
        await manager._on_event(_event(device="dev-1"))
        await asyncio.sleep(0.05)  # the discovery is running now
        task = manager._rediscovery_task
        assert task is not None and not task.done()

        await manager.disconnect()

    assert task.cancelled()
    assert manager._rediscovery_task is None
    assert manager._rediscovery_timer is None
    assert manager.includable_devices == {}
    assert manager._includable_timers == {}
    disconnect.assert_awaited_once_with()


async def test_disconnect_cancels_a_pending_discovery(
    manager: DeviceManager,
) -> None:
    manager._rediscovery_timer = asyncio.get_running_loop().call_later(99, lambda: None)

    with patch.object(manager.client, "disconnect", AsyncMock()):
        await manager.disconnect()

    assert manager._rediscovery_timer is None
