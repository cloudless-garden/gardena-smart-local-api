#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 GARDENA GmbH
#
# SPDX-License-Identifier: LGPL-3.0-or-later

import asyncio
import sys

from gardena_smart_local_api.devices import Gen1Mower1, Gen1Mower2, Gen2Mower
from gardena_smart_local_api.examples import ExampleApp
from gardena_smart_local_api.messages import ErrorMessage

COMPATIBLE = (Gen1Mower1, Gen1Mower2, Gen2Mower)


async def main():
    extra_args = [
        {
            "name_or_flags": ["command"],
            "nargs": 1,
            "choices": ("list", "start", "stop", "pause", "status"),
            "help": "List applicable devices, start/stop/pause mowing or show status",
        },
        {
            "name_or_flags": ["duration"],
            "nargs": "?",
            "default": 1,
            "type": float,
            "help": "Duration to mow in hours (default: 1h)",
        },
    ]

    async with ExampleApp(COMPATIBLE, extra_args) as app:
        match app.args.command[0]:
            case "list":
                app.list_devices()

            case "start":
                if (mower := app.device) is None:
                    return 1
                assert isinstance(mower, COMPATIBLE)
                duration = int(app.args.duration * 3600)
                request = mower.build_start_mowing_obj(duration)
                result = await app.send_request(request)
                if result is None or not result[0].success:
                    print("Failed to start mowing")
                    if result is not None and isinstance(result[0], ErrorMessage):
                        print(f"Error: {result[0].error_message}")
                    return 1

            case "stop":
                if (mower := app.device) is None:
                    return 1
                assert isinstance(mower, COMPATIBLE)
                request = mower.build_stop_mowing_obj()
                result = await app.send_request(request)
                if result is None or not result[0].success:
                    print("Failed to stop mowing")
                    if result is not None and isinstance(result[0], ErrorMessage):
                        print(f"Error: {result[0].error_message}")
                    return 1

            case "pause":
                if (mower := app.device) is None:
                    return 1
                if not isinstance(mower, Gen2Mower):
                    print("Pausing not supported")
                    return 1
                request = mower.build_pause_mowing_obj()
                result = await app.send_request(request)
                if result is None or not result[0].success:
                    print("Failed to pause mowing")
                    if result is not None and isinstance(result[0], ErrorMessage):
                        print(f"Error: {result[0].error_message}")
                    return 1

            case "status":
                if (mower := app.device) is None:
                    return 1
                assert isinstance(mower, COMPATIBLE)
                print(f"Mower State: {mower.state}")
                print(f"Battery Level: {mower.battery_level}%")
                print(f"Charging Cycles: {mower.charging_cycles}")
                print(f"Cutting Time: {mower.cutting_time}h")
                print(f"Running Time: {mower.running_time}h")
                print(f"Collisions: {mower.collisions}")
                print(f"Guide Wire Length: {mower.guide_wire_length}m")
                print(f"RF Link Quality: {mower.rf_link_quality}%")


if __name__ == "__main__":
    rc = asyncio.run(main())
    sys.exit(rc)
