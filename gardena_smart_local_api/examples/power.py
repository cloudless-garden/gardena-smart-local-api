#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 GARDENA GmbH
#
# SPDX-License-Identifier: LGPL-3.0-or-later

import asyncio
import sys

from gardena_smart_local_api.devices import PowerAdapter
from gardena_smart_local_api.examples import ExampleApp
from gardena_smart_local_api.messages import ErrorMessage

COMPATIBLE = (PowerAdapter,)


async def main():
    extra_args = [
        {
            "name_or_flags": ["command"],
            "nargs": 1,
            "choices": (
                "list",
                "on",
                "off",
                "identify",
                "read-schedules",
                "clear-schedules",
            ),
            "help": "List applicable devices, identify or turn power on/off",
        },
        {
            "name_or_flags": ["duration"],
            "nargs": "?",
            "default": 60,
            "type": int,
            "help": "Duration to power on in seconds (default: 60s)",
        },
    ]

    async with ExampleApp(COMPATIBLE, extra_args) as app:
        match app.args.command[0]:
            case "list":
                app.list_devices()

            case "on":
                if (pa := app.device) is None:
                    return 1
                assert isinstance(pa, COMPATIBLE)
                request = pa.build_enable_output_obj(app.args.duration)
                result = await app.send_request(request)
                if result is None or not result[0].success:
                    print("Failed to turn on")
                    if result is not None and isinstance(result[0], ErrorMessage):
                        print(f"Error: {result[0].error_message}")
                    return 1

            case "off":
                if (pa := app.device) is None:
                    return 1
                assert isinstance(pa, COMPATIBLE)
                request = pa.build_disable_output_obj()
                result = await app.send_request(request)
                if result is None or not result[0].success:
                    print("Failed to turn off")
                    if result is not None and isinstance(result[0], ErrorMessage):
                        print(f"Error: {result[0].error_message}")
                    return 1

            case "identify":
                if (pa := app.device) is None:
                    return 1
                assert isinstance(pa, COMPATIBLE)
                request = pa.build_identify_obj()
                result = await app.send_request(request)
                if result is None or not result[0].success:
                    print("Failed to identify")
                    if result is not None and isinstance(result[0], ErrorMessage):
                        print(f"Error: {result[0].error_message}")
                    return 1

            case "read-schedules":
                if (pa := app.device) is None:
                    return 1
                assert isinstance(pa, COMPATIBLE)
                request = pa.build_refresh_sun_schedule_config_obj()
                result = await app.send_request(request)
                if result is None or not result[0].success:
                    print("Failed to read schedules")
                    if result is not None and isinstance(result[0], ErrorMessage):
                        print(f"Error: {result[0].error_message}")
                    return 1
                if pa.schedule_count == 0:
                    print("No schedules configured")
                else:
                    assert pa.sun_schedule_config is not None
                    raw = pa.sun_schedule_config.hex()
                    print(f"{pa.schedule_count} schedule(s), raw: {raw}")

            case "clear-schedules":
                if (pa := app.device) is None:
                    return 1
                assert isinstance(pa, COMPATIBLE)
                result = await app.send_request(pa.build_clear_schedules_obj())
                if result is None or not result[0].success:
                    print("Failed to clear schedules")
                    if result is not None and isinstance(result[0], ErrorMessage):
                        print(f"Error: {result[0].error_message}")
                    return 1


if __name__ == "__main__":
    rc = asyncio.run(main())
    sys.exit(rc)
