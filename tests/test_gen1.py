# SPDX-FileCopyrightText: 2026 GARDENA GmbH
#
# SPDX-License-Identifier: LGPL-3.0-or-later

import pytest

from gardena_smart_local_api.devices.device_builder import create_devices_from_messages
from gardena_smart_local_api.devices.gen1 import (
    Gen1BatteryMixin,
    Gen1Device,
)
from gardena_smart_local_api.devices.irrigation import Gen1WaterControl
from gardena_smart_local_api.messages import IngressMessageList

from .conftest import build_delete_event


@pytest.mark.asyncio
async def test_gen1_device_is_gen1(water_control_message):
    water_control = list(
        (await create_devices_from_messages(water_control_message)).values()
    )[0]
    assert isinstance(water_control, Gen1Device)


@pytest.mark.asyncio
async def test_gen1_serial_number(water_control):
    serial_number = water_control.serial_number
    assert serial_number is not None
    assert isinstance(serial_number, str)
    assert len(serial_number) > 0


@pytest.mark.asyncio
async def test_gen1_online_status(water_control):
    online = water_control.is_online
    assert online is not None
    assert isinstance(online, bool)


@pytest.mark.asyncio
async def test_gen1_rf_link_quality(water_control):
    rf_quality = water_control.rf_link_quality
    # rf_link_quality might be None for some devices
    if rf_quality is not None:
        assert isinstance(rf_quality, int)
        assert 0 <= rf_quality <= 100


@pytest.mark.asyncio
async def test_water_control_specific(water_control):
    assert isinstance(water_control, Gen1WaterControl)
    assert isinstance(water_control, Gen1BatteryMixin)

    battery_level = water_control.battery_level
    assert battery_level is not None
    assert isinstance(battery_level, float)
    assert 0 <= battery_level <= 100

    button_config_time = water_control.button_config_time
    if button_config_time is not None:
        assert isinstance(button_config_time, int)

    serial_number = water_control.serial_number
    assert serial_number is not None
    assert isinstance(serial_number, str)
    assert serial_number == "00095101"


@pytest.mark.asyncio
async def test_gen1_build_command_obj(water_control):
    request_list = water_control.build_command_obj(3)
    request = request_list.root[0]

    assert request.op == "write"
    assert request.entity.device == water_control.id
    assert request.entity.service == "lemonbeatd"
    assert request.entity.path.object_name == "lemonbeat"
    assert request.entity.path.object_instance_id == "0"
    assert request.entity.path.resource_name == "command"
    assert request.payload == {"vi": 3}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("watering_timer", "expected"),
    [(3597, True), (-3597, True), (0, False)],
)
async def test_gen1_is_valve_open_scheduled_watering(
    water_control, watering_timer, expected
):
    event = IngressMessageList.model_validate_json(f"""
        [
          {{
            "entity": {{ "device": "{water_control.id}", "path": "lemonbeat/0" }},
            "metadata": {{ "sequence": 1, "source": "lemonbeatd" }},
            "op": "update",
            "payload": {{
              "watering_timer_1": {{ "ts": 1774970419, "vi": {watering_timer} }},
              "_urn": "urn:oma:lwm2m:x:31000"
            }}
          }}
        ]
        """)
    water_control.update_data(event.root[0])

    assert water_control.is_valve_open(0) is expected


@pytest.mark.asyncio
async def test_gen1_build_refresh_battery_level_obj(water_control):
    request = water_control.build_refresh_battery_level_obj().root[0]

    assert request.op == "write"
    assert request.entity.path.resource_name == "command"
    assert request.payload == {"vi": water_control.get_command("measure_battery")}


@pytest.mark.asyncio
async def test_gen1_build_refresh_rf_link_quality_obj(water_control):
    request = water_control.build_refresh_rf_link_quality_obj().root[0]

    assert request.op == "read"
    assert request.entity.path.object_name == "lemonbeat"
    assert request.entity.path.object_instance_id == "0"
    assert request.entity.path.resource_name == "rf_link_quality"


@pytest.mark.asyncio
async def test_gen1_error(water_control):
    assert water_control.error == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("attribute", "resource_name"),
    [
        ("battery_level", "battery_level"),
        ("rf_link_quality", "rf_link_quality"),
        ("error", "error"),
        ("has_frost_warning", "frost_warning"),
    ],
)
async def test_gen1_returns_none_when_resource_missing(
    water_control, attribute, resource_name
):
    water_control.update_data(
        build_delete_event(water_control.id, f"lemonbeat/0/{resource_name}")
    )

    assert getattr(water_control, attribute) is None


@pytest.mark.asyncio
async def test_gen1_schedule_config_and_count(water_control):
    config = water_control.schedule_config
    assert config is not None
    assert isinstance(config, bytes)
    assert len(config) == 252
    assert water_control.schedule_count == 36


@pytest.mark.asyncio
async def test_gen1_schedule_count_without_config(water_control):
    water_control.update_data(
        build_delete_event(water_control.id, "lemonbeat/0/schedule_config")
    )

    assert water_control.schedule_config is None
    assert water_control.schedule_count == 0


@pytest.mark.asyncio
async def test_gen1_build_refresh_schedule_config_obj(water_control):
    request = water_control.build_refresh_schedule_config_obj().root[0]

    assert request.op == "read"
    assert request.entity.path.resource_name == "schedule_config"


@pytest.mark.asyncio
async def test_gen1_build_clear_schedules_obj(water_control):
    request = water_control.build_clear_schedules_obj().root[0]

    assert request.op == "write"
    assert request.entity.path.resource_name == "schedule_config"
    assert request.payload == {"vo": ""}


@pytest.mark.asyncio
async def test_gen1_button_config_time(water_control):
    button_config_time = water_control.get_button_config_time()
    assert button_config_time is not None
    assert isinstance(button_config_time, int)


@pytest.mark.asyncio
async def test_gen1_button_config_time_invalid_valve_id(water_control):
    with pytest.raises(ValueError, match="Invalid valve ID"):
        water_control.get_button_config_time(valve_id=99)


@pytest.mark.asyncio
async def test_gen1_build_refresh_button_config_time_obj(water_control):
    request = water_control.build_refresh_button_config_time_obj().root[0]

    assert request.op == "read"
    assert request.entity.path.object_name == "lemonbeat"
    assert request.entity.path.object_instance_id == "0"
    assert request.entity.path.resource_name == "button_config_time"


@pytest.mark.asyncio
async def test_gen1_build_set_button_config_time_obj(water_control):
    request = water_control.build_set_button_config_time_obj(900).root[0]

    assert request.op == "write"
    assert request.entity.path.resource_name == "button_config_time"
    assert request.payload == {"vi": 900}


@pytest.mark.asyncio
async def test_gen1_button_config_time_missing(water_control):
    water_control.update_data(
        build_delete_event(water_control.id, "lemonbeat/0/button_config_time")
    )

    assert water_control.get_button_config_time() is None


@pytest.mark.asyncio
async def test_gen1_get_watering_timer(water_control):
    timer = water_control.get_watering_timer(0)
    assert timer is not None
    assert isinstance(timer, int)


@pytest.mark.asyncio
async def test_gen1_get_watering_timer_missing(water_control):
    water_control.update_data(
        build_delete_event(water_control.id, "lemonbeat/0/watering_timer_1")
    )

    assert water_control.get_watering_timer(0) is None
    assert water_control.is_valve_open(0) is None


@pytest.mark.asyncio
async def test_gen1_is_valve_open_invalid_valve_id(water_control):
    with pytest.raises(ValueError, match="Invalid valve ID"):
        water_control.is_valve_open(valve_id=99)


@pytest.mark.asyncio
async def test_gen1_build_open_valve_obj(water_control):
    request = water_control.build_open_valve_obj(duration_seconds=600).root[0]

    assert request.op == "write"
    assert request.entity.path.resource_name == "watering_timer_1"
    assert request.payload == {"vi": 600}


@pytest.mark.asyncio
async def test_gen1_build_open_valve_obj_invalid_valve_id(water_control):
    with pytest.raises(ValueError, match="Invalid valve ID"):
        water_control.build_open_valve_obj(valve_id=99)


@pytest.mark.asyncio
async def test_gen1_build_close_valve_obj(water_control):
    request = water_control.build_close_valve_obj().root[0]

    assert request.op == "write"
    assert request.entity.path.resource_name == "watering_timer_1"
    assert request.payload == {"vi": 0}


@pytest.mark.asyncio
async def test_gen1_build_close_valve_obj_invalid_valve_id(water_control):
    with pytest.raises(ValueError, match="Invalid valve ID"):
        water_control.build_close_valve_obj(valve_id=99)


@pytest.mark.asyncio
async def test_gen1_build_close_all_valves_obj(water_control):
    request = water_control.build_close_all_valves_obj().root[0]

    assert request.op == "write"
    assert request.entity.path.resource_name == "watering_timer_1"
    assert request.payload == {"vi": 0}


@pytest.mark.asyncio
async def test_gen1_water_control_temperature(water_control):
    temperature = water_control.temperature
    assert temperature is not None
    assert isinstance(temperature, int)


@pytest.mark.asyncio
async def test_gen1_water_control_temperature_missing(water_control):
    water_control.update_data(
        build_delete_event(water_control.id, "lemonbeat/0/ambient_temperature")
    )

    assert water_control.temperature is None


@pytest.mark.asyncio
async def test_gen1_water_control_valve_count_and_ids(water_control):
    assert water_control.valve_count == 1
    assert water_control.valve_ids == [0]
