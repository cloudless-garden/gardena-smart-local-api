#!/usr/bin/env python3
import asyncio
import sys

from rich.live import Live
from rich.text import Text

from gardena_smart_local_api.devices import Sensor1, Sensor2
from gardena_smart_local_api.examples import ExampleApp

COMPATIBLE = (Sensor1, Sensor2)


async def main():
    extra_args = [
        {
            "name_or_flags": ["command"],
            "nargs": 1,
            "choices": ("list", "read"),
            "help": "List applicable devices or read sensor values",
        },
        {
            "name_or_flags": ["duration"],
            "nargs": "?",
            "default": 1,
            "type": int,
            "help": "Duration to watch the sensor values (default 1s)",
        },
    ]

    async with ExampleApp(COMPATIBLE, extra_args) as app:
        match app.args.command[0]:
            case "list":
                app.list_devices()

            case "read":
                if (sensor := app.device) is None:
                    return 1
                assert isinstance(sensor, COMPATIBLE)
                try:
                    await asyncio.wait_for(
                        _display(app, sensor), timeout=app.args.duration
                    )
                except TimeoutError:
                    pass


async def _display(app, sensor):
    with Live(auto_refresh=False) as live:
        while True:
            out = f"Sensor {sensor.id}:\n"
            out += f"  Temperature:     {sensor.temperature}°C\n"
            out += f"  Soil moisture:   {sensor.soil_moisture}%\n"
            if isinstance(sensor, Sensor1):
                out += f"  Light:           {sensor.light}lx\n"
            out += f"  Battery:         {sensor.battery_level}%\n"
            out += f"  RF link quality: {sensor.rf_link_quality}%\n"
            out += f"  Frost warning:   {sensor.has_frost_warning}\n"
            out += f"  Error:           {sensor.error}"

            live.update(Text(out))
            live.refresh()

            request = sensor.build_refresh_temperature_obj()
            await app.send_request(request)
            request = sensor.build_refresh_soil_moisture_obj()
            await app.send_request(request)
            if isinstance(sensor, Sensor1):
                request = sensor.build_refresh_light_obj()
                await app.send_request(request)
            request = sensor.build_refresh_battery_level_obj()
            await app.send_request(request)
            request = sensor.build_refresh_rf_link_quality_obj()
            await app.send_request(request)


if __name__ == "__main__":
    rc = asyncio.run(main())
    sys.exit(rc)
