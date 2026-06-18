#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 GARDENA GmbH
#
# SPDX-License-Identifier: LGPL-3.0-or-later

import asyncio
import sys

from rich import print

from gardena_smart_local_api.devices import Device, FirmwareUpdateState
from gardena_smart_local_api.examples import ExampleApp
from gardena_smart_local_api.messages import ErrorMessage

extra_args = [
    {
        "name_or_flags": ["command"],
        "nargs": 1,
        "choices": ("status", "update"),
        "help": "Show FOTA status, start update",
    },
]


async def main():
    async with ExampleApp((Device,), extra_args) as app:
        device_id = app.args.device_id
        match app.args.command[0]:
            case "status":
                if device_id is None:
                    print("[red]No device ID provided.[/red]")
                    return 1

                if device_id not in app.devices:
                    print(f"[red]Device {device_id} not found.[/red]")
                    return 1

                print(f"Status: {app.device.firmware_update_state}")
                return 0

            case "update":
                if device_id is None:
                    print("[red]No device ID provided.[/red]")
                    return 1

                if device_id not in app.devices:
                    print(f"[red]Device {device_id} not found.[/red]")
                    return 1

                if app.device.firmware_update_state != FirmwareUpdateState.DOWNLOADED:
                    print(f"[red]No pending update[/red]")

                request = app.device.build_install_firmware_update_obj()
                result = await app.send_request(request)

                if result is None or not result[0].success:
                    print("Failed to stop watering")
                    if result is not None and isinstance(result[0], ErrorMessage):
                        print(f"Error: {result[0].error_message}")
                    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
