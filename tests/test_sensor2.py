import pytest

from gardena_smart_local_api.devices.gen1 import Gen1BatteryMixin
from gardena_smart_local_api.devices.sensors import Sensor2


@pytest.mark.asyncio
async def test_sensor2_is_sensor(sensor2):
    assert isinstance(sensor2, Sensor2)
    assert isinstance(sensor2, Gen1BatteryMixin)


@pytest.mark.asyncio
async def test_sensor2_serial_number(sensor2):
    assert sensor2.serial_number == "00002865"


@pytest.mark.asyncio
async def test_sensor2_is_online(sensor2):
    assert sensor2.is_online is True


@pytest.mark.asyncio
async def test_sensor2_battery_level(sensor2):
    battery = sensor2.battery_level
    assert battery is not None
    assert isinstance(battery, float)
    assert 0 <= battery <= 100


@pytest.mark.asyncio
async def test_sensor2_rf_link_quality(sensor2):
    rf = sensor2.rf_link_quality
    assert rf is not None
    assert isinstance(rf, int)
    assert rf == 100


@pytest.mark.asyncio
async def test_sensor2_soil_moisture(sensor2):
    moisture = sensor2.soil_moisture
    assert moisture is not None
    assert isinstance(moisture, int)
    assert moisture == 100


@pytest.mark.asyncio
async def test_sensor2_temperature(sensor2):
    temp = sensor2.temperature
    assert temp is not None
    assert isinstance(temp, int)
    assert temp == 22


@pytest.mark.asyncio
async def test_sensor2_frost_warning(sensor2):
    frost = sensor2.has_frost_warning
    assert frost is not None
    assert isinstance(frost, bool)
    assert frost is False


@pytest.mark.asyncio
async def test_sensor2_error(sensor2):
    assert sensor2.error == 0


@pytest.mark.asyncio
async def test_sensor2_update_event(sensor2, sensor2_update_event):
    event = sensor2_update_event[0]
    sensor2.update_data(event)
    assert sensor2.soil_moisture == 42
