#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 GARDENA GmbH
#
# SPDX-License-Identifier: LGPL-3.0-or-later

import asyncio
import sys

from rich.live import Live
from rich.text import Text

from gardena_smart_local_api.devices import Gen1Mower1, Gen1Mower2, Gen2Mower
from gardena_smart_local_api.examples import ExampleApp
from gardena_smart_local_api.messages import ErrorMessage

COMPATIBLE = (Gen1Mower1, Gen1Mower2, Gen2Mower)


async def _display_position(mower: Gen1Mower2 | Gen2Mower):
    with Live(auto_refresh=False) as live:
        while True:
            await asyncio.sleep(0.5)
            position = mower.position
            if position is None:
                out = "Mower position: unknown"
            else:
                out = (
                    f"Mower position: {position.latitude:.7f}, {position.longitude:.7f}"
                )
                if position.heading is not None:
                    out += f", heading: {position.heading:.1f}°"
            live.update(Text(out))
            live.refresh()


async def main():
    extra_args = [
        {
            "name_or_flags": ["command"],
            "nargs": 1,
            "choices": ("list", "start", "stop", "pause", "status", "position"),
            "help": "List applicable devices, start/stop/pause mowing or show status",
        },
        {
            "name_or_flags": ["duration"],
            "nargs": "?",
            "default": 1,
            "type": float,
            "help": "Duration to mow in hours, or to report position in"
            " seconds (default: 1)",
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
                print(f"Mower state: {mower.state}")

            case "position":
                if (mower := app.device) is None:
                    return 1
                assert isinstance(mower, COMPATIBLE)
                if isinstance(mower, Gen1Mower1):
                    print("Position reporting not supported")
                    return 1
                duration = int(app.args.duration)
                if isinstance(mower, Gen2Mower) and duration < 60:
                    duration = 60
                request = mower.build_start_position_reporting_obj(duration)
                result = await app.send_request(request)
                if result is None or not result[0].success:
                    print("Failed to start position reporting")
                    if result is not None and isinstance(result[0], ErrorMessage):
                        print(f"Error: {result[0].error_message}")
                    return 1

                print(f"Displaying position for {app.args.duration}s")
                try:
                    await asyncio.wait_for(
                        _display_position(mower), timeout=app.args.duration
                    )
                except TimeoutError:
                    pass


if __name__ == "__main__":
    rc = asyncio.run(main())
    sys.exit(rc)
