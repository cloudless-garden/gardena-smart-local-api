#!/usr/bin/env python3
import asyncio
import sys

from gardena_smart_local_api.devices import (
    Gen1WaterControl,
    Gen2IrrigationControl,
    Gen2WaterControl,
    TimeslotState,
)
from gardena_smart_local_api.examples import ExampleApp
from gardena_smart_local_api.messages import ErrorMessage

COMPATIBLE = (Gen2IrrigationControl, Gen1WaterControl, Gen2WaterControl)


async def main():
    extra_args = [
        {
            "name_or_flags": ["command"],
            "nargs": 1,
            "choices": ("list", "start", "stop", "status"),
            "help": "List applicable devices or start/stop watering",
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
            "default": 60,
            "type": int,
            "help": "Duration to water in seconds (default: 60s)",
        },
    ]

    async with ExampleApp(COMPATIBLE, extra_args) as app:
        match app.args.command[0]:
            case "list":
                app.list_devices()

            case "start":
                if (wc := app.device) is None:
                    return 1
                assert isinstance(wc, COMPATIBLE)

                try:
                    request = wc.build_open_valve_obj(
                        app.args.valve_id if app.args.valve_id is not None else 0,
                        app.args.duration,
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
                if isinstance(wc, (Gen2IrrigationControl, Gen2WaterControl)):
                    status = wc.get_timeslot_state(app.args.valve_id)
                    if status == TimeslotState.ERROR:
                        print("Device refused to start watering")

            case "stop":
                if (wc := app.device) is None:
                    return 1
                assert isinstance(wc, COMPATIBLE)

                if app.args.valve_id is not None:
                    try:
                        request = wc.build_close_valve_obj(app.args.valve_id)
                    except ValueError:
                        print(f"Invalid valve ID provided: {app.args.valve_id}")
                        return 1
                else:
                    request = wc.build_close_all_valves_obj()

                result = await app.send_request(request)

                if result is None or not result[0].success:
                    print("Failed to stop watering")
                    if result is not None and isinstance(result[0], ErrorMessage):
                        print(f"Error: {result[0].error_message}")
                    return 1

            case "status":
                if (wc := app.device) is None:
                    return 1
                assert isinstance(wc, COMPATIBLE)

                try:
                    status = wc.is_valve_open(
                        app.args.valve_id if app.args.valve_id is not None else 0,
                    )
                except ValueError:
                    print(f"Invalid valve ID provided: {app.args.valve_id}")
                    return 1

                print(f"Valve is open: {status}")
                print(f"Error: {wc.error}")


if __name__ == "__main__":
    rc = asyncio.run(main())
    sys.exit(rc)
