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
            "choices": ("list", "on", "off", "identify", "status"),
            "help": "List applicable devices, identify, turn power on/off,"
            " or show status",
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

            case "status":
                if (pa := app.device) is None:
                    return 1
                assert isinstance(pa, COMPATIBLE)
                print(f"Output enabled: {pa.is_output_enabled}")
                if pa.error is not None:
                    print(f"Error:          {pa.error}")


if __name__ == "__main__":
    rc = asyncio.run(main())
    sys.exit(rc)
