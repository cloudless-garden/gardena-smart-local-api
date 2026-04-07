import pytest

from gardena_smart_local_api.devices import create_devices_from_messages
from gardena_smart_local_api.devices.gen1 import Gen1BatteryMixin
from gardena_smart_local_api.devices.sensors import Sensor1


@pytest.mark.asyncio
async def test_sensor1_is_sensor(sensor1):
    assert isinstance(sensor1, Sensor1)
    assert isinstance(sensor1, Gen1BatteryMixin)


@pytest.mark.asyncio
async def test_sensor1_serial_number(sensor1):
    assert sensor1.serial_number == "00045875"


@pytest.mark.asyncio
async def test_sensor1_is_online(sensor1):
    assert sensor1.is_online is True


@pytest.mark.asyncio
async def test_sensor1_battery_level(sensor1):
    battery = sensor1.battery_level
    assert battery is not None
    assert isinstance(battery, float)
    assert 0 <= battery <= 100


@pytest.mark.asyncio
async def test_sensor1_rf_link_quality(sensor1):
    rf = sensor1.rf_link_quality
    assert rf is not None
    assert isinstance(rf, int)
    assert rf == 100


@pytest.mark.asyncio
async def test_sensor1_temperature(sensor1):
    temp = sensor1.temperature
    assert temp is not None
    assert isinstance(temp, int)
    assert temp == 20


@pytest.mark.asyncio
async def test_sensor1_light(sensor1):
    light = sensor1.light
    assert light is not None
    assert isinstance(light, int)


@pytest.mark.asyncio
async def test_sensor1_frost_warning(sensor1):
    frost = sensor1.has_frost_warning
    assert frost is not None
    assert isinstance(frost, bool)
    assert frost is False


@pytest.mark.asyncio
async def test_sensor1_error(sensor1):
    assert sensor1.error == 0


@pytest.mark.asyncio
async def test_sensor1_update_event(sensor1_and_update_event):
    devices = await create_devices_from_messages(sensor1_and_update_event)
    sensor = list(devices.values())[0]
    assert isinstance(sensor, Sensor1)
