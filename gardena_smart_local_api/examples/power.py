#!/usr/bin/env python3
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
            "choices": ("list", "on", "off", "identify"),
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

    async with ExampleApp(extra_args) as app:
        match app.args.command[0]:
            case "list":
                app.list_devices(COMPATIBLE)

            case "on":
                if app.args.device_id is None:
                    print("No device ID provided")
                    return 1
                pa = app.devices[app.args.device_id]
                if not isinstance(pa, COMPATIBLE):
                    print("Incompatible device selected")
                    return 1
                request = pa.build_enable_output_obj(app.args.duration)
                result = await app.send_request(request)
                if result is not None and not result[0].success:
                    print("Failed to turn on")
                    if isinstance(result[0], ErrorMessage):
                        print(f"Error: {result[0].error_message}")
                    return 1

            case "off":
                if app.args.device_id is None:
                    print("No device ID provided")
                    return 1
                pa = app.devices[app.args.device_id]
                if not isinstance(pa, COMPATIBLE):
                    print("Incompatible device selected")
                    return 1
                request = pa.build_disable_output_obj()
                result = await app.send_request(request)
                if result is not None and not result[0].success:
                    print("Failed to turn off")
                    if isinstance(result[0], ErrorMessage):
                        print(f"Error: {result[0].error_message}")
                    return 1

            case "identify":
                if app.args.device_id is None:
                    print("No device ID provided")
                    return 1
                pa = app.devices[app.args.device_id]
                if not isinstance(pa, COMPATIBLE):
                    print("Incompatible device selected")
                    return 1
                request = pa.build_identify_obj()
                result = await app.send_request(request)
                if result is not None and not result[0].success:
                    print("Failed to identify")
                    if isinstance(result[0], ErrorMessage):
                        print(f"Error: {result[0].error_message}")
                    return 1


if __name__ == "__main__":
    rc = asyncio.run(main())
    sys.exit(rc)
