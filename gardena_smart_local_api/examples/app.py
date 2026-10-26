# SPDX-FileCopyrightText: 2026 GARDENA GmbH
#
# SPDX-License-Identifier: LGPL-3.0-or-later

import argparse
import asyncio
import contextlib
import signal
import time
from collections.abc import Iterable
from typing import Self

from rich.live import Live
from rich.text import Text

from gardena_smart_local_api.client import AuthenticationError, GatewayClient
from gardena_smart_local_api.devices import Device, DeviceMap
from gardena_smart_local_api.messages import (
    EgressMessageList,
    ErrorMessage,
    Event,
    IngressMessageList,
    Reply,
)

REQUEST_TIMEOUT_SECONDS = 30


class ExampleApp:
    def __init__(
        self,
        compatible_devices: tuple[type[Device], ...],
        extra_args: Iterable[dict] = (),
    ):
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
        parser.add_argument(
            "-j",
            "--dump-json",
            action="store_true",
            help="Save sent/received messages to JSON files in the current directory",
        )
        parser.add_argument(
            "-w",
            "--wait",
            action="store_true",
            help="Do not quit, continue to receive events",
        )

        for arg_info in extra_args:
            parser.add_argument(
                *arg_info["name_or_flags"],
                **{k: v for k, v in arg_info.items() if k != "name_or_flags"},
            )

        self.parser = parser
        self.compatible_devices = compatible_devices
        self.client: GatewayClient | None = None
        self._event_task: asyncio.Task[None] | None = None
        self.devices = DeviceMap({})
        self.events: list[Event] = []
        self.event_count = 0

    async def __aenter__(self) -> Self:
        self.args = self.parser.parse_args()
        self.client = GatewayClient(
            self.args.gateway,
            8443,
            self.args.password,
            queue_events=True,
        )
        try:
            await self.client.connect()
        except AuthenticationError as err:
            raise SystemExit(f"{err}. Check the password.") from err
        self._event_task = asyncio.create_task(self._consume_events())
        try:
            self.devices = await self.client.discover_devices(REQUEST_TIMEOUT_SECONDS)
        except BaseException:
            await self._shutdown()
            raise
        return self

    async def __aexit__(self, *args):
        if self.args.wait:
            done = asyncio.Event()
            loop = asyncio.get_running_loop()
            loop.add_signal_handler(signal.SIGINT, done.set)
            with Live(auto_refresh=False) as live:
                while not done.is_set():
                    await asyncio.sleep(0.5)
                    live.update(
                        Text(
                            f"Events received: {self.event_count}\nPress Ctrl+C to quit"
                        )
                    )
                    live.refresh()

        await self._shutdown()

    async def _shutdown(self) -> None:
        if self._event_task is not None:
            self._event_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._event_task
            self._event_task = None
        if self.client is not None:
            await self.client.disconnect()
            self.client = None

    async def _consume_events(self) -> None:
        assert self.client is not None
        while True:
            message = await self.client.events.get()
            if not isinstance(message, Event):
                if self.args.dump_json:
                    kind = "error" if isinstance(message, ErrorMessage) else "reply"
                    self._dump(message, kind)
                continue

            self.event_count += 1
            if self.args.dump_json:
                self._dump(message, "event")

            if message.op == "update" and message.entity.device in self.devices:
                self.devices[message.entity.device].update_data(message)
            else:
                self.events.append(message)

    def _dump(
        self, message: EgressMessageList | Event | Reply | ErrorMessage, kind: str
    ):
        with open(f"{time.monotonic_ns()}_{kind}.json", "w") as f:
            f.write(message.model_dump_json(exclude_none=True, indent=2) + "\n")

    async def send_request(self, reqs: EgressMessageList) -> IngressMessageList | None:
        if self.client is None:
            raise RuntimeError("Not connected")
        if self.args.dump_json:
            self._dump(reqs, "request")

        try:
            replies = await self.client.send_request(
                reqs, wait_for_response_sec=REQUEST_TIMEOUT_SECONDS
            )
        except TimeoutError:
            print("Timeout receiving reply for command")
            return None

        if self.args.dump_json:
            for reply in replies:
                self._dump(
                    reply, "error" if isinstance(reply, ErrorMessage) else "reply"
                )
        return replies

    def list_devices(self):
        for dev_id, device in self.devices.items():
            if isinstance(device, self.compatible_devices):
                print(f"{dev_id} ({device.model_definition.name})")

    @property
    def device(self) -> Device | None:
        device_id = self.args.device_id
        if device_id is None:
            print("No device ID provided")
            return None
        if device_id not in self.devices:
            print("Invalid device ID provided")
            return None
        device = self.devices[device_id]
        if not isinstance(device, self.compatible_devices):
            print("Incompatible device selected")
            return None
        return device
