#!/usr/bin/env python3
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
            "choices": ("list", "start", "stop", "pause", "status", "zone_map"),
            "help": "List applicable devices, start/stop/pause mowing, show status or upload zone map",
        },
        {
            "name_or_flags": ["cmd_arg"],
            "nargs": "?",
            "default": 1,
            "type": lambda v: float(v) if v.replace(".", "", 1).isdigit() else v,
            "help": "Duration to mow in hours (default: 1h) / map SVG file",
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

            case "zone_map":
                if (mower := app.device) is None:
                    return 1
                if not isinstance(mower, Gen2Mower):
                    print("Zone map upload not supported")
                    return 1
                if not isinstance(app.args.cmd_arg, str) or not app.args.cmd_arg.endswith(".svg"):
                    print("No map file provided")
                    return 1
                try:
                    with open(app.args.cmd_arg, "rb") as f:
                        svg_data = f.read()
                except Exception as e:
                    print(f"Failed to read SVG file: {e}")
                    return 1
                request = mower.build_write_zone_map_obj(svg_data)
                result = await app.send_request(request)
                if result is None or not result[0].success:
                    print("Failed to upload zone map")
                    if result is not None and isinstance(result[0], ErrorMessage):
                        print(f"Error: {result[0].error_message}")
                    return 1


if __name__ == "__main__":
    rc = asyncio.run(main())
    sys.exit(rc)
