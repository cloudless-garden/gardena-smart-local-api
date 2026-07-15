#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 GARDENA GmbH
#
# SPDX-License-Identifier: LGPL-3.0-or-later

import asyncio
import sys

from gardena_smart_local_api.devices import (
    Gen1IrrigationControl,
    Gen1WaterControl,
    Gen2IrrigationControl,
    Gen2WaterControl,
    TimeslotState,
)
from gardena_smart_local_api.devices.irrigation import Gen1IrrigationScheduleMixin
from gardena_smart_local_api.examples import ExampleApp
from gardena_smart_local_api.messages import ErrorMessage

COMPATIBLE = (
    Gen1IrrigationControl,
    Gen1WaterControl,
    Gen2IrrigationControl,
    Gen2WaterControl,
)


async def main():
    extra_args = [
        {
            "name_or_flags": ["command"],
            "nargs": 1,
            "choices": (
                "list",
                "start",
                "stop",
                "clear-schedules",
                "read-schedules",
                "read-button-time",
                "set-button-time",
            ),
            "help": "List devices, start/stop watering, or read/clear schedules",
        },
        {
            "name_or_flags": ["valve_id"],
            "nargs": "?",
            "type": int,
            "help": "Valve to open/close (default: 0)",
        },
        {
            "name_or_flags": ["duration"],
            "nargs": "?",
            "type": int,
            "help": "Duration to water in seconds (start, default: 60s) or button "
            "time in seconds (set-button-time, required)",
        },
    ]

    async with ExampleApp(COMPATIBLE, extra_args) as app:
        match app.args.command[0]:
            case "list":
                app.list_devices()

            case "start":
                if (irrigation_device := app.device) is None:
                    return 1
                assert isinstance(irrigation_device, COMPATIBLE)

                try:
                    request = irrigation_device.build_open_valve_obj(
                        app.args.valve_id if app.args.valve_id is not None else 0,
                        app.args.duration if app.args.duration is not None else 60,
                    )
                except ValueError:
                    print(f"Invalid valve ID provided: {app.args.valve_id}")
                    return 1

                result = await app.send_request(request)

                if result is None or not result[0].success:
                    print("Failed to start watering")
                    if result is not None and isinstance(result[0], ErrorMessage):
                        print(f"Error: {result[0].error_message}")
                    return 1
                if isinstance(
                    irrigation_device, (Gen2IrrigationControl, Gen2WaterControl)
                ):
                    status = irrigation_device.get_timeslot_state(app.args.valve_id)
                    if status == TimeslotState.ERROR:
                        print("Device refused to start watering")

            case "stop":
                if (irrigation_device := app.device) is None:
                    return 1
                assert isinstance(irrigation_device, COMPATIBLE)

                if app.args.valve_id is not None:
                    try:
                        request = irrigation_device.build_close_valve_obj(
                            app.args.valve_id
                        )
                    except ValueError:
                        print(f"Invalid valve ID provided: {app.args.valve_id}")
                        return 1
                else:
                    request = irrigation_device.build_close_all_valves_obj()

                result = await app.send_request(request)

                if result is None or not result[0].success:
                    print("Failed to stop watering")
                    if result is not None and isinstance(result[0], ErrorMessage):
                        print(f"Error: {result[0].error_message}")
                    return 1

            case "clear-schedules":
                if (irrigation_device := app.device) is None:
                    return 1
                assert isinstance(irrigation_device, COMPATIBLE)

                if not isinstance(irrigation_device, Gen1IrrigationScheduleMixin):
                    print("clear-schedules only supported on Gen1 devices")
                    return 1

                result = await app.send_request(
                    irrigation_device.build_clear_schedules_obj()
                )

                if result is None or not result[0].success:
                    print("Failed to clear schedules")
                    if result is not None and isinstance(result[0], ErrorMessage):
                        print(f"Error: {result[0].error_message}")
                    return 1

            case "read-schedules":
                if (irrigation_device := app.device) is None:
                    return 1
                assert isinstance(irrigation_device, COMPATIBLE)

                if not isinstance(irrigation_device, Gen1IrrigationScheduleMixin):
                    print("read-schedules only supported on Gen1 devices")
                    return 1

                result = await app.send_request(
                    irrigation_device.build_refresh_schedule_config_obj()
                )
                if result is None or not result[0].success:
                    print("Failed to read schedules")
                    if result is not None and isinstance(result[0], ErrorMessage):
                        print(f"Error: {result[0].error_message}")
                    return 1

                if irrigation_device.schedule_count == 0:
                    print("No schedules configured")
                else:
                    assert irrigation_device.schedule_config is not None
                    raw = irrigation_device.schedule_config.hex()
                    print(f"{irrigation_device.schedule_count} schedule(s), raw: {raw}")

            case "read-button-time":
                if (irrigation_device := app.device) is None:
                    return 1
                assert isinstance(irrigation_device, COMPATIBLE)

                if isinstance(irrigation_device, Gen1WaterControl):
                    valve_ids = [0]
                    request = irrigation_device.build_read_button_config_time_obj()
                elif isinstance(
                    irrigation_device, (Gen2WaterControl, Gen2IrrigationControl)
                ):
                    valve_ids = (
                        [app.args.valve_id]
                        if app.args.valve_id is not None
                        else irrigation_device.valve_ids
                    )
                    try:
                        requests = [
                            irrigation_device.build_refresh_button_config_time_obj(
                                valve_id
                            )
                            for valve_id in valve_ids
                        ]
                    except ValueError:
                        print(f"Invalid valve ID provided: {app.args.valve_id}")
                        return 1
                    request = requests[0]
                    for r in requests[1:]:
                        request = request + r
                else:
                    print("read-button-time not supported on this device")
                    return 1

                result = await app.send_request(request)
                if result is None or not all(r.success for r in result):
                    print("Failed to read button time")
                    if result is not None:
                        for r in result:
                            if isinstance(r, ErrorMessage):
                                print(f"Error: {r.error_message}")
                    return 1

                if isinstance(irrigation_device, Gen1WaterControl):
                    print(f"Button time: {irrigation_device.button_config_time}s")
                else:
                    assert isinstance(
                        irrigation_device, (Gen2WaterControl, Gen2IrrigationControl)
                    )
                    for valve_id in valve_ids:
                        button_time = irrigation_device.get_button_config_time(valve_id)
                        print(f"Valve {valve_id} button time: {button_time}s")

            case "set-button-time":
                if (irrigation_device := app.device) is None:
                    return 1
                assert isinstance(irrigation_device, COMPATIBLE)

                if app.args.duration is None:
                    print("set-button-time requires a duration (in seconds)")
                    return 1

                valve_id = app.args.valve_id if app.args.valve_id is not None else 0

                if isinstance(irrigation_device, Gen1WaterControl):
                    request = irrigation_device.build_set_button_config_time_obj(
                        app.args.duration
                    )
                elif isinstance(
                    irrigation_device, (Gen2WaterControl, Gen2IrrigationControl)
                ):
                    try:
                        request = irrigation_device.build_set_button_config_time_obj(
                            app.args.duration, valve_id
                        )
                    except ValueError:
                        print(f"Invalid valve ID provided: {app.args.valve_id}")
                        return 1
                else:
                    print("set-button-time not supported on this device")
                    return 1

                result = await app.send_request(request)
                if result is None or not result[0].success:
                    print("Failed to set button time")
                    if result is not None and isinstance(result[0], ErrorMessage):
                        print(f"Error: {result[0].error_message}")
                    return 1


if __name__ == "__main__":
    rc = asyncio.run(main())
    sys.exit(rc)
