#!/usr/bin/env python3
import asyncio
import sys

from gardena_smart_local_api.devices import Gen1WaterControl, Gen2WaterControl
from gardena_smart_local_api.examples import ExampleApp
from gardena_smart_local_api.messages import ErrorMessage


async def main():
    extra_args = [
        {
            "name_or_flags": ["command"],
            "nargs": 1,
            "choices": ("list", "start", "stop"),
            "help": "List devices or start/stop watering",
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

    async with ExampleApp(extra_args) as app:
        match app.args.command[0]:
            case "list":
                for dev_id, device in app.devices.items():
                    print(f"{dev_id} ({device.model_definition.name})")

            case "start":
                if app.args.device_id is None:
                    print("No device ID provided")
                    return 1

                wc = app.devices[app.args.device_id]

                if not isinstance(wc, (Gen1WaterControl, Gen2WaterControl)):
                    print("Incompatible device selected")
                    return 1

                if isinstance(wc, Gen1WaterControl):
                    request = wc.build_set_watering_timer_obj(app.args.duration)
                else:
                    if (
                        app.args.valve_id is not None
                        and not 0 <= app.args.valve_id < wc.valve_count
                    ):
                        print(
                            f'Valve ID "{app.args.valve_id}" out of range, '
                            f"valid IDs: 0...{wc.valve_count - 1}"
                        )
                        return 1
                    request = wc.build_open_valve_obj(
                        app.args.valve_id if app.args.valve_id is not None else 0,
                        app.args.duration,
                    )

                result = await app.send_request(request)

                if result is not None and not result[0].success:
                    print("Failed to start watering")
                    if isinstance(result[0], ErrorMessage):
                        print(f"Error: {result[0].error_message}")
                    return 1

            case "stop":
                if app.args.device_id is None:
                    print("No device ID provided")
                    return 1

                wc = app.devices[app.args.device_id]

                if not isinstance(wc, (Gen1WaterControl, Gen2WaterControl)):
                    print("Incompatible device selected")
                    return 1

                if isinstance(wc, Gen1WaterControl):
                    request = wc.build_stop_watering_obj()
                else:
                    if (
                        app.args.valve_id is not None
                        and not 0 <= app.args.valve_id < wc.valve_count
                    ):
                        print(
                            f'Valve ID "{app.args.valve_id}" out of range, '
                            f"valid IDs: 0...{wc.valve_count - 1}"
                        )
                        return 1
                    if app.args.valve_id is not None:
                        request = wc.build_close_valve_obj(app.args.valve_id)
                    else:
                        request = wc.build_close_all_valves_obj()

                result = await app.send_request(request)

                if result is not None and not result[0].success:
                    print("Failed to stop watering")
                    if isinstance(result[0], ErrorMessage):
                        print(f"Error: {result[0].error_message}")
                    return 1


if __name__ == "__main__":
    rc = asyncio.run(main())
    sys.exit(rc)
