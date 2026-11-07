# SPDX-FileCopyrightText: 2026 GARDENA GmbH
#
# SPDX-License-Identifier: LGPL-3.0-or-later

import pytest

from gardena_smart_local_api.devices.gen1 import Gen1BatteryMixin
from gardena_smart_local_api.devices.sensors import Sensor2

from .conftest import build_delete_event


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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("attribute", "resource_name"),
    [("temperature", "soil_temperature"), ("soil_moisture", "soil_moisture")],
)
async def test_sensor2_returns_none_when_resource_missing(
    sensor2, attribute, resource_name
):
    sensor2.update_data(build_delete_event(sensor2.id, f"lemonbeat/0/{resource_name}"))
    assert getattr(sensor2, attribute) is None


@pytest.mark.asyncio
async def test_sensor2_build_refresh_temperature_obj(sensor2):
    request = sensor2.build_refresh_temperature_obj().root[0]
    assert request.op == "write"
    assert request.entity.path.resource_name == "command"
    assert request.payload == {"vi": sensor2.get_command("measure_soil_temperature")}
