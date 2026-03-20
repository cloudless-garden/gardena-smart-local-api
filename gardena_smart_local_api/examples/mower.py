#!/usr/bin/env python3
import asyncio
import sys

from gardena_smart_local_api.devices import Gen1Mower
from gardena_smart_local_api.examples import ExampleApp
from gardena_smart_local_api.messages import ErrorMessage


async def main():
    extra_args = [
        {
            "name_or_flags": ["command"],
            "nargs": 1,
            "choices": ("list", "start", "stop"),
            "help": "List devices or start/stop mowing",
        },
        {
            "name_or_flags": ["duration"],
            "nargs": "?",
            "default": 1,
            "type": float,
            "help": "Duration to mow in hours (default: 1h)",
        },
    ]

    async with ExampleApp(extra_args) as app:
        match app.args.command[0]:
            case "list":
                for dev_id, device in app.devices.items():
                    print(f"{dev_id} ({device.model_definition.type})")

            case "start":
                if app.args.device_id is None:
                    print("No device ID provided")
                    return 1
                mower = app.devices[app.args.device_id]
                if not isinstance(mower, Gen1Mower):
                    print("Incompatible device selected")
                    return 1
                duration = int(app.args.duration * 3600)
                request = mower.build_start_mowing_obj(0, duration)
                result = await app.send_request(request)
                if result is not None and not result[0].success:
                    print("Failed to start mowing")
                    if isinstance(result[0], ErrorMessage):
                        print(f"Error: {result[0].error_message}")
                    return 1

            case "stop":
                if app.args.device_id is None:
                    print("No device ID provided")
                    return 1
                mower = app.devices[app.args.device_id]
                if not isinstance(mower, Gen1Mower):
                    print("Incompatible device selected")
                    return 1
                request = mower.build_stop_mowing_obj()
                result = await app.send_request(request)
                if result is not None and not result[0].success:
                    print("Failed to stop mowing")
                    if isinstance(result[0], ErrorMessage):
                        print(f"Error: {result[0].error_message}")
                    return 1


if __name__ == "__main__":
    rc = asyncio.run(main())
    sys.exit(rc)
