import argparse
import asyncio
import base64
import ssl
from collections.abc import Iterable
from typing import Self

import websockets

from gardena_smart_local_api.devices import (
    Device,
    DeviceMap,
    build_discovery_obj,
    create_devices_from_messages,
)
from gardena_smart_local_api.messages import (
    EgressMessageList,
    Event,
    IngressMessageList,
    Reply,
)


class ExampleApp:
    def __init__(self, extra_args: Iterable[dict] = ()):
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "-g",
            "--gateway",
            required=True,
            help="e.g. GARDENA-123456 or IP address",
        )
        parser.add_argument(
            "-p",
            "--password",
            required=True,
            help="First 8 characters of ID found on the back of the gateway",
        )
        parser.add_argument(
            "-d",
            "--device-id",
            required=False,
            help='ID of device to control (list IDs with "list" command)',
        )

        for arg_info in extra_args:
            parser.add_argument(
                *arg_info["name_or_flags"],
                **{k: v for k, v in arg_info.items() if k != "name_or_flags"},
            )

        self.parser = parser
        self.ws = None
        self.devices = DeviceMap({})
        self.events = []
        self.replies = {}
        self._exiting = asyncio.Event()

    async def _receiver(self):
        while not self._exiting.is_set():
            raw = await self.receive()
            if raw is None:
                continue
            msgs = IngressMessageList.model_validate_json(raw)
            for msg in msgs:
                match msg:
                    case Event():
                        self.events.append(msg)
                    case Reply():
                        self.replies[msg.request_id] = msg

    async def _device_updater(self):
        while not self._exiting.is_set():
            for event in self.events[:]:
                if event.op == "update":
                    device_id = event.entity.device
                    if device_id in self.devices:
                        self.devices[device_id].update_data(event)
                        self.events.remove(event)
            await asyncio.sleep(0.5)

    async def connect(self):
        self.args = self.parser.parse_args()
        uri = f"wss://{self.args.gateway}:8443"
        password = self.args.password
        auth = base64.b64encode(f"_:{password}".encode()).decode("ascii")
        headers = {"Authorization": f"Basic {auth}"}

        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        self.ws = await websockets.connect(
            uri,
            ssl=ssl_context,
            additional_headers=headers,
            close_timeout=0,
        )

        self._receive_task = asyncio.create_task(self._receiver())
        self._device_updater_task = asyncio.create_task(self._device_updater())

    async def disconnect(self):
        if self.ws:
            await self.ws.close()
            self.ws = None

    async def send(self, data: str):
        if not self.ws:
            raise RuntimeError("Not connected")
        await self.ws.send(data)

    async def receive(self) -> str | None:
        if not self.ws:
            raise RuntimeError("Not connected")
        try:
            return await asyncio.wait_for(self.ws.recv(), timeout=1.0)
        except TimeoutError:
            pass
        return None

    async def send_request(self, reqs: EgressMessageList) -> IngressMessageList:
        await self.send(str(reqs))

        request_ids = {m.request_id for m in reqs}

        reps = IngressMessageList([])

        for _ in range(10):
            for request_id in request_ids:
                if request_id in self.replies:
                    reps.append(self.replies.pop(request_id))
            if len(reps) == len(reqs):
                break
            await asyncio.sleep(1)

        return reps

    async def discover_devices(self) -> DeviceMap:
        discovery = build_discovery_obj()
        replies = await self.send_request(discovery)
        if replies is None:
            return DeviceMap({})
        return await create_devices_from_messages(replies)

    def list_devices(self, compatible_devices: tuple[type[Device], ...]):
        for dev_id, device in self.devices.items():
            if isinstance(device, compatible_devices):
                print(f"{dev_id} ({device.model_definition.name})")

    async def __aenter__(self) -> Self:
        await self.connect()
        self.devices = await self.discover_devices()
        return self

    async def __aexit__(self, *args):
        self._exiting.set()
        await self._receive_task
        await self._device_updater_task
        await self.disconnect()
