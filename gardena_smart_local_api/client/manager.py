# SPDX-FileCopyrightText: 2026 GARDENA GmbH
#
# SPDX-License-Identifier: LGPL-3.0-or-later

"""Keep the devices of a GARDENA smart Gateway up to date."""

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from types import TracebackType
from typing import Self

import aiohttp

from ..devices import Device, DeviceMap, build_inclusion_obj
from ..devices.device_builder import MODEL_NUMBER_MAP
from ..messages import EgressMessageList, Event, IngressMessageList, Reply
from ..sgtin96 import SGTIN96Info
from ..utils import deep_merge_dict
from .errors import InclusionError, RequestError
from .gateway import DISCOVERY_TIMEOUT, REQUEST_TIMEOUT, GatewayClient

_LOGGER = logging.getLogger(__name__)

# How long the gateway has to answer an inclusion request.
INCLUDE_TIMEOUT = 10

# How long an included device has to finish its inclusion, which shows as it
# leaving the includable devices.
INCLUSION_TIMEOUT = 30

# How long the gateway has to answer an exclusion request.
EXCLUDE_TIMEOUT = 10

# How long the gateway has to answer the requests for the firmware state.
FIRMWARE_TIMEOUT = 10

# A device in inclusion mode repeats itself regularly. One that stays silent
# for this long left the inclusion mode.
INCLUDABLE_HEARTBEAT_TIMEOUT = 25

# A device that was included outside of this manager, e.g. with the official
# app, shows up as a burst of ordinary events for a device that is not known
# yet. Waiting this long before running a discovery makes one burst cause one
# discovery, not one per event.
UNKNOWN_DEVICE_DISCOVERY_DEBOUNCE = 3

type DevicesChanged = Callable[[frozenset[str]], Awaitable[None] | None]


@dataclass(frozen=True)
class IncludableDevice:
    """A device in inclusion mode that can be included in the gateway."""

    instance_id: str
    service: str
    device_id: str
    name: str
    # The class the device is built as once it is included, so a caller can
    # offer only the kinds of devices it supports.
    device_class: type[Device]


class DeviceManager:
    """Keep the devices of a GARDENA smart Gateway up to date.

    Builds on `GatewayClient`, which it creates from the connection arguments
    and offers as `client`. After every (re)connect the manager discovers the
    devices, and it applies the events the gateway pushes, so `devices` always
    shows the current state. It also finds out about devices that are put in
    inclusion mode, includes and excludes devices, and notices devices that
    were included or removed without it.

        manager = DeviceManager(
            "GARDENA-123456", 8443, "password", on_devices_changed=changed
        )
        async with manager:
            for device in manager.devices.values():
                ...

    `on_devices_changed` is called with the ids of the devices that were added,
    removed or changed. The devices are already up to date then. It may be a
    plain function or a coroutine function, and an exception it raises is
    logged. It runs in the read loop of the client for a pushed event, so it
    must not wait for the reply to a request.

    Requests that change a device go through `send_command`, which holds the
    notifications for that device back until the command has settled, so the
    intermediate states of a command do not show up as changes.
    """

    def __init__(
        self,
        host: str,
        port: int,
        password: str,
        *,
        session: aiohttp.ClientSession | None = None,
        fingerprint: str | None = None,
        on_devices_changed: DevicesChanged | None = None,
        on_disconnect: Callable[[], Awaitable[None] | None] | None = None,
        on_auth_failed: Callable[[], Awaitable[None] | None] | None = None,
    ) -> None:
        self.client = GatewayClient(
            host,
            port,
            password,
            session=session,
            fingerprint=fingerprint,
            on_connect=self._on_connect,
            on_event=self._on_event,
            on_disconnect=on_disconnect,
            on_auth_failed=on_auth_failed,
        )
        self._on_devices_changed = on_devices_changed
        self._devices = DeviceMap({})
        self._includable: dict[str, IncludableDevice] = {}
        self._includable_timers: dict[str, asyncio.TimerHandle] = {}
        # Devices that are being included. Their burst of events must not start
        # a discovery of its own, as the inclusion runs one.
        self._including: set[str] = set()
        # Devices that are being excluded, held back from the device map until
        # the gateway answers, so that neither an event nor a discovery brings
        # them back in the meantime.
        self._excluding: dict[str, Device] = {}
        # Devices with a command in flight, and how many.
        self._commands: dict[str, int] = {}
        self._rediscovery_timer: asyncio.TimerHandle | None = None
        self._rediscovery_task: asyncio.Task[None] | None = None
        # Set when an event for an unknown device arrives while a discovery
        # is already running, as that discovery may not see the device.
        self._rediscovery_again = False

    @property
    def devices(self) -> DeviceMap:
        """The devices of the gateway. Do not change it."""
        return self._devices

    @property
    def includable_devices(self) -> dict[str, IncludableDevice]:
        """The devices in inclusion mode right now, by their instance id."""
        return dict(self._includable)

    @property
    def connected(self) -> bool:
        return self.client.connected

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
        """Connect to the gateway and discover its devices.

        Raises what `GatewayClient.connect` raises, and `DiscoveryError` if the
        gateway answers the discovery with an error.
        """
        await self.client.connect()

    async def disconnect(self) -> None:
        """Stop the connection and everything that runs for the manager."""
        for timer in self._includable_timers.values():
            timer.cancel()
        self._includable_timers.clear()
        self._includable.clear()
        if self._rediscovery_timer is not None:
            self._rediscovery_timer.cancel()
            self._rediscovery_timer = None
        self._rediscovery_again = False
        if self._rediscovery_task is not None:
            self._rediscovery_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._rediscovery_task
            self._rediscovery_task = None
        await self.client.disconnect()

    async def discover(self, *, notify: bool = True) -> None:
        """Ask the gateway for its devices and replace the known ones with them.

        Raises `DiscoveryError` if the gateway answers with an error, in which
        case the known devices stay as they are, and `TimeoutError` if it does
        not answer in time. With `notify=False` `on_devices_changed` is not
        called, and the caller is expected to publish the change.
        """
        devices = await self.client.discover_devices(DISCOVERY_TIMEOUT)
        changed = self._replace_devices(devices)
        _LOGGER.info("Discovery complete, found %d device(s)", len(self._devices))
        if notify:
            await self._notify(changed)

    async def include_device(self, instance_id: str, *, notify: bool = True) -> Device:
        """Include a device that is in inclusion mode, and return it.

        Raises `InclusionError` if the device is not in inclusion mode, if the
        gateway does not accept it or the device does not finish the inclusion
        in time, or if it is not found afterwards. With `notify=False`
        `on_devices_changed` is not called for the new device, and the caller
        is expected to publish it, e.g. once it has set the device up.
        """
        info = self._includable.get(instance_id)
        if info is None:
            raise InclusionError(f"No includable device with instance_id {instance_id}")

        self._including.add(info.device_id)
        try:
            try:
                await self.client.send_request(
                    build_inclusion_obj(info.service, instance_id), INCLUDE_TIMEOUT
                )
            except (RequestError, TimeoutError, ConnectionError) as err:
                raise InclusionError(
                    f"The gateway did not accept {info.device_id}: {err}"
                ) from err

            for _ in range(INCLUSION_TIMEOUT):
                if instance_id not in self._includable:
                    break
                await asyncio.sleep(1)
            # Check once more: the device may have left during the last sleep.
            if instance_id in self._includable:
                raise InclusionError(
                    f"Timeout waiting for the inclusion of {info.device_id}"
                )

            try:
                await self.discover(notify=notify)
            except (RequestError, TimeoutError, ConnectionError) as err:
                raise InclusionError(
                    f"The discovery after the inclusion of {info.device_id} "
                    f"failed: {err}"
                ) from err
            device = self._devices.get(info.device_id)
            if device is None:
                raise InclusionError(
                    f"Included device {info.device_id} not found in discovery"
                )
            _LOGGER.info(
                "Device %s (instance %s) included successfully",
                info.device_id,
                instance_id,
            )
            return device
        finally:
            self._including.discard(info.device_id)

    async def exclude_device(self, device_id: str) -> None:
        """Exclude a device from the gateway, which resets the device.

        Returns without doing anything if the device is not known, as e.g.
        a removal with the official app already took it away. The device
        leaves `devices` right away, and comes back if the gateway does not
        confirm the exclusion. Raises `RequestError`, `TimeoutError` or
        `ConnectionError` then.
        """
        device = self._devices.get(device_id)
        if device is None:
            _LOGGER.debug("Device %s already absent, nothing to exclude", device_id)
            return

        request = device.build_exclusion_obj()
        self._excluding[device_id] = device
        del self._devices[device_id]
        await self._notify({device_id})
        try:
            await self.client.send_request(request, EXCLUDE_TIMEOUT)
        except Exception:
            self._excluding.pop(device_id, None)
            if device_id not in self._devices:
                # Still paired with the gateway: keep its state.
                self._devices[device_id] = device
                await self._notify({device_id})
            raise
        finally:
            self._excluding.pop(device_id, None)
        _LOGGER.info("Device %s excluded successfully", device_id)

    async def refresh_firmware(self, device_id: str) -> None:
        """Ask the gateway for the firmware state of a device and apply it.

        Does nothing for an unknown device. If one of the requests fails, the
        replies of the others are still applied before `RequestError` is
        raised. Also raises `TimeoutError` and `ConnectionError`.
        """
        device = self._devices.get(device_id)
        if device is None:
            return

        request = (
            device.build_refresh_available_firmware_version_obj()
            + device.build_refresh_firmware_update_state_obj()
        )
        failure: RequestError | None = None
        try:
            replies = await self.client.send_request(request, FIRMWARE_TIMEOUT)
        except RequestError as err:
            replies, failure = err.replies, err

        updated = False
        for reply in replies:
            if isinstance(reply, Reply) and reply.success and reply.payload:
                data = reply.payload.get(device_id)
                if data:
                    deep_merge_dict(device.data, data)
                    updated = True
        if updated and device_id not in self._commands:
            await self._notify({device_id})
        if failure is not None:
            raise failure

    async def send_command(
        self,
        device_id: str,
        request: EgressMessageList,
        timeout: float = REQUEST_TIMEOUT,
    ) -> IngressMessageList:
        """Send a request that changes a device, and wait for the replies.

        A command makes the gateway report the new state of the device in
        several frames, one after the other. Until the command has settled the
        events for the device are applied, but `on_devices_changed` is not
        called, so the intermediate states do not show up. It is called once
        when the replies are in, whether they confirm the command or not.

        Raises what `GatewayClient.send_request` raises.
        """
        self._commands[device_id] = self._commands.get(device_id, 0) + 1
        try:
            return await self.client.send_request(request, timeout)
        finally:
            remaining = self._commands.get(device_id, 1) - 1
            if remaining <= 0:
                self._commands.pop(device_id, None)
                await self._notify({device_id})
            else:
                self._commands[device_id] = remaining

    async def _on_connect(self) -> None:
        await self.discover()

    async def _notify(self, device_ids: Iterable[str]) -> None:
        changed = frozenset(device_ids)
        if not changed or self._on_devices_changed is None:
            return
        try:
            result = self._on_devices_changed(changed)
            if result is not None:
                await result
        except Exception:
            _LOGGER.exception("Error in on_devices_changed callback")

    def _replace_devices(self, devices: DeviceMap) -> set[str]:
        """Replace the known devices by a complete discovery result."""
        changed: set[str] = set()
        for device_id in self._devices.keys() - devices.keys():
            _LOGGER.info(
                "Device %s no longer present in discovery, dropping", device_id
            )
            del self._devices[device_id]
            changed.add(device_id)
        for device in devices.values():
            if device.id in self._excluding:
                continue
            if device.id not in self._devices:
                _LOGGER.info(
                    "Added new device: %s (%s)", device.id, device.model_definition.name
                )
            self._devices[device.id] = device
            changed.add(device.id)
        return changed

    async def _on_event(self, event: Event) -> None:
        try:
            changed = await self._apply_event(event)
        except Exception as err:  # noqa: BLE001 - one bad event must not stop the rest
            _LOGGER.warning("Error handling event %s: %s", event, err)
            return
        if changed is not None and changed not in self._commands:
            await self._notify({changed})

    async def _apply_event(self, event: Event) -> str | None:
        """Apply an event to the devices, returning the device it changed."""
        if event.entity.path.object_name == "includable_device":
            await self._apply_includable_event(event)
            return None

        device_id = event.entity.device
        if not device_id:
            _LOGGER.debug("Event does not have device ID, ignoring: %s", event)
            return None
        if device_id in self._excluding:
            return None

        device = self._devices.get(device_id)
        if device is None:
            if event.op != "delete":
                # A device that is not known yet, e.g. included with the
                # official app while we were connected. Not a delete, so it is
                # not just a leftover event of a device that was excluded.
                self._schedule_rediscovery(device_id)
            return None

        if event.op == "delete" and event.entity.path.object_name is None:
            _LOGGER.info("Device %s removed (delete event)", device_id)
            del self._devices[device_id]
            return device_id

        _LOGGER.debug("Updating device %s with event: %s", device_id, event)
        was_online = device.is_online
        device.update_data(event)
        if device.is_online != was_online:
            _LOGGER.info(
                "Device %s connection status changed: online=%s",
                device_id,
                device.is_online,
            )
        return device_id

    def _schedule_rediscovery(self, device_id: str) -> None:
        if device_id in self._including:
            return
        if self._rediscovery_timer is not None:
            # A run is scheduled already; a burst of events for the same
            # unknown device must not keep pushing it back.
            task = self._rediscovery_task
            if task is not None and not task.done():
                # The run is past its request, so it may not see this device.
                self._rediscovery_again = True
            return
        _LOGGER.debug("Event for unknown device %s, scheduling discovery", device_id)
        self._arm_rediscovery()

    def _arm_rediscovery(self) -> None:
        self._rediscovery_timer = asyncio.get_running_loop().call_later(
            UNKNOWN_DEVICE_DISCOVERY_DEBOUNCE, self._start_rediscovery
        )

    def _start_rediscovery(self) -> None:
        self._rediscovery_task = asyncio.get_running_loop().create_task(
            self._rediscover()
        )

    async def _rediscover(self) -> None:
        _LOGGER.info("Running discovery to pick up newly included device(s)")
        try:
            await self.discover()
        except Exception as err:  # noqa: BLE001 - best effort, must not stop the manager
            _LOGGER.warning("Discovery for unknown device(s) failed: %s", err)
        finally:
            # Keep the timer set until the discovery is done; clearing it
            # earlier lets a continued burst start an overlapping run.
            self._rediscovery_timer = None
        # Skipped when cancelled: CancelledError propagates past this point.
        if self._rediscovery_again:
            self._rediscovery_again = False
            self._arm_rediscovery()

    def _expire_includable(self, instance_id: str) -> None:
        _LOGGER.debug("Includable device %s heartbeat timed out, removing", instance_id)
        self._includable.pop(instance_id, None)
        self._includable_timers.pop(instance_id, None)

    async def _apply_includable_event(self, event: Event) -> None:
        instance_id = event.entity.path.object_instance_id
        if instance_id is None:
            return

        timer = self._includable_timers.pop(instance_id, None)
        if timer is not None:
            timer.cancel()

        if event.op == "delete":
            self._includable.pop(instance_id, None)
            _LOGGER.debug("Includable device %s removed (delete event)", instance_id)
            return

        # Every event is a heartbeat: the device is gone once they stop.
        self._includable_timers[instance_id] = asyncio.get_running_loop().call_later(
            INCLUDABLE_HEARTBEAT_TIMEOUT, self._expire_includable, instance_id
        )
        if instance_id in self._includable:
            _LOGGER.debug("Includable device %s heartbeat", instance_id)
            return

        service = event.entity.service
        if service is None:
            return
        identifier = event.payload.get("identifier", {}).get("vs")
        if identifier is None:
            _LOGGER.debug("Includable event for %s lacks identifier", instance_id)
            return
        try:
            sgtin = SGTIN96Info.from_hex(identifier)
        except ValueError:
            _LOGGER.debug(
                "Includable device %s has unparseable identifier %s, ignoring",
                instance_id,
                identifier,
            )
            return

        name = f"{await sgtin.get_model_name()} {sgtin.serial:08d}"
        self._includable[instance_id] = IncludableDevice(
            instance_id=instance_id,
            service=service,
            device_id=identifier,
            name=name,
            device_class=MODEL_NUMBER_MAP.get(sgtin.item_reference, Device),
        )
        _LOGGER.info(
            "Discovered includable device: %s (%s, instance %s)",
            identifier,
            name,
            instance_id,
        )
