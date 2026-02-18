import pytest

from gardena_smart_local_api.devices.device_builder import create_devices_from_messages
from gardena_smart_local_api.devices.gen1 import (
    Gen1BatteryPoweredGen1Device,
    Gen1Device,
    WaterControl,
)


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
    assert isinstance(water_control, WaterControl)
    assert isinstance(water_control, Gen1BatteryPoweredGen1Device)

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
