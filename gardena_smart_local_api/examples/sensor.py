#!/usr/bin/env python3
import asyncio
import sys

from gardena_smart_local_api.devices import Sensor1, Sensor2
from gardena_smart_local_api.examples import ExampleApp


async def main():
    extra_args = [
        {
            "name_or_flags": ["command"],
            "nargs": 1,
            "choices": ("list", "read"),
            "help": "List devices or read sensor values",
        },
    ]

    async with ExampleApp(extra_args) as app:
        match app.args.command[0]:
            case "list":
                for dev_id, device in app.devices.items():
                    print(f"{dev_id} ({device.model_definition.name})")

            case "read":
                if app.args.device_id is None:
                    print("No device ID provided")
                    return 1
                sensor = app.devices[app.args.device_id]
                if not isinstance(sensor, (Sensor1, Sensor2)):
                    print("Incompatible device selected")
                    return 1
                print(f"Sensor {sensor.id}:")
                print(f"  Temperature:     {sensor.temperature}°C")
                print(f"  Soil moisture:   {sensor.soil_moisture}%")
                if isinstance(sensor, Sensor1):
                    print(f"  Light:           {sensor.light} lx")
                print(f"  Battery:         {sensor.battery_level}%")
                print(f"  RF link quality: {sensor.rf_link_quality}%")
                print(f"  Frost warning:   {sensor.has_frost_warning}")
                print(f"  Error:           {sensor.error}")


if __name__ == "__main__":
    rc = asyncio.run(main())
    sys.exit(rc)
