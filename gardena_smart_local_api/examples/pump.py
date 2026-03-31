#!/usr/bin/env python3
import asyncio
import sys

from gardena_smart_local_api.devices import Pump, PumpOperatingMode
from gardena_smart_local_api.examples import ExampleApp
from gardena_smart_local_api.messages import ErrorMessage

COMPATIBLE = (Pump,)


async def main():
    extra_args = [
        {
            "name_or_flags": ["command"],
            "nargs": 1,
            "choices": (
                "list",
                "start",
                "stop",
                "status",
                "identify",
                "set-mode",
                "set-turn-on-pressure",
                "set-dripping-alert",
                "reset-flow",
                "reset-temp-min-max",
            ),
            "help": "Command to execute",
        },
        {
            "name_or_flags": ["value"],
            "nargs": "?",
            "help": (
                "Value for set-* commands or duration in seconds for start. "
                "For set-mode use: " + ", ".join(m.name.lower() for m in PumpOperatingMode)
            ),
        },
    ]

    async with ExampleApp(COMPATIBLE, extra_args) as app:
        match app.args.command[0]:
            case "list":
                app.list_devices()

            case "status":
                if (pump := app.device) is None:
                    return 1
                assert isinstance(pump, COMPATIBLE)
                print(f"Online:              {pump.is_online}")
                print(f"Error:               {pump.error}")
                print(f"Pump error:          {pump.pump_error}")
                print(f"RF link quality:     {pump.rf_link_quality} %")
                print()
                print(f"Running:             {pump.is_running}")
                print(f"Pump state:          {pump.pump_state}")
                print(f"Pump mode:           {pump.pump_mode}")
                print(f"Operating mode:      {pump.operating_mode}")
                print(f"Watering timer:      {pump.get_watering_timer(0)} s")
                print()
                print(f"Outlet pressure:     {pump.outlet_pressure} Bar")
                print(f"Outlet pressure max: {pump.outlet_pressure_max} Bar")
                print(f"Turn-on pressure:    {pump.turn_on_pressure} Bar")
                print(f"Outlet temp:         {pump.outlet_temperature} °C")
                print(f"Outlet temp max:     {pump.outlet_temperature_max} °C")
                print(f"Outlet temp min:     {pump.outlet_temperature_min} °C")
                print()
                print(f"Flow rate:           {pump.flow_rate} L/h")
                print(f"Flow total:          {pump.flow_total} m³")
                print(f"Flow since reset:    {pump.flow_since_last_reset} m³")
                print(f"Dripping alert:      {pump.dripping_alert}")
                print(f"Frost warning:       {pump.has_frost_warning}")

            case "start":
                if (pump := app.device) is None:
                    return 1
                assert isinstance(pump, COMPATIBLE)
                duration = int(app.args.value) if app.args.value is not None else 60
                request = pump.build_open_valve_obj(0, duration)
                result = await app.send_request(request)
                if result is not None and not result[0].success:
                    print("Failed to start pump")
                    if isinstance(result[0], ErrorMessage):
                        print(f"Error: {result[0].error_message}")
                    return 1

            case "stop":
                if (pump := app.device) is None:
                    return 1
                assert isinstance(pump, COMPATIBLE)
                request = pump.build_close_valve_obj(0)
                result = await app.send_request(request)
                if result is not None and not result[0].success:
                    print("Failed to stop pump")
                    if isinstance(result[0], ErrorMessage):
                        print(f"Error: {result[0].error_message}")
                    return 1

            case "identify":
                if (pump := app.device) is None:
                    return 1
                assert isinstance(pump, COMPATIBLE)
                request = pump.build_identify_obj()
                result = await app.send_request(request)
                if result is not None and not result[0].success:
                    print("Failed to identify pump")
                    if isinstance(result[0], ErrorMessage):
                        print(f"Error: {result[0].error_message}")
                    return 1

            case "set-mode":
                if (pump := app.device) is None:
                    return 1
                assert isinstance(pump, COMPATIBLE)
                valid = ", ".join(m.name.lower() for m in PumpOperatingMode)
                if app.args.value is None:
                    print(f"Missing value for set-mode. Available modes: {valid}")
                    return 1
                if app.args.value.upper() not in PumpOperatingMode.__members__:
                    print(f"Invalid mode '{app.args.value}'. Valid modes: {valid}")
                    return 1

                mode = PumpOperatingMode[app.args.value.upper()]
                request = pump.build_set_operating_mode_obj(mode)
                result = await app.send_request(request)
                if result is not None and not result[0].success:
                    print("Failed to set operating mode")
                    if isinstance(result[0], ErrorMessage):
                        print(f"Error: {result[0].error_message}")
                    return 1

            case "set-turn-on-pressure":
                if (pump := app.device) is None:
                    return 1
                assert isinstance(pump, COMPATIBLE)
                if app.args.value is None:
                    print("Missing value for set-turn-on-pressure")
                    return 1
                request = pump.build_set_turn_on_pressure_obj(float(app.args.value))
                result = await app.send_request(request)
                if result is not None and not result[0].success:
                    print("Failed to set turn-on pressure")
                    if isinstance(result[0], ErrorMessage):
                        print(f"Error: {result[0].error_message}")
                    return 1

            case "set-dripping-alert":
                if (pump := app.device) is None:
                    return 1
                assert isinstance(pump, COMPATIBLE)
                if app.args.value is None:
                    print("Missing value for set-dripping-alert")
                    return 1
                request = pump.build_set_dripping_alert_obj(int(app.args.value))
                result = await app.send_request(request)
                if result is not None and not result[0].success:
                    print("Failed to set dripping alert")
                    if isinstance(result[0], ErrorMessage):
                        print(f"Error: {result[0].error_message}")
                    return 1

            case "reset-flow":
                if (pump := app.device) is None:
                    return 1
                assert isinstance(pump, COMPATIBLE)
                request = pump.build_reset_flow_resettable_obj()
                result = await app.send_request(request)
                if result is not None and not result[0].success:
                    print("Failed to reset flow")
                    if isinstance(result[0], ErrorMessage):
                        print(f"Error: {result[0].error_message}")
                    return 1

            case "reset-temp-min-max":
                if (pump := app.device) is None:
                    return 1
                assert isinstance(pump, COMPATIBLE)
                request = pump.build_reset_outlet_temperature_min_max_obj()
                result = await app.send_request(request)
                if result is not None and not result[0].success:
                    print("Failed to reset temperature min/max")
                    if isinstance(result[0], ErrorMessage):
                        print(f"Error: {result[0].error_message}")
                    return 1


if __name__ == "__main__":
    rc = asyncio.run(main())
    sys.exit(rc)
