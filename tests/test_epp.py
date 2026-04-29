import pytest

from gardena_smart_local_api.devices.device_builder import create_devices_from_messages
from gardena_smart_local_api.devices.gen1 import Gen1Device
from gardena_smart_local_api.devices.irrigation import OperatingMode, Pump, PumpState


@pytest.mark.asyncio
async def test_epp_is_pump(epp_message):
    device = list((await create_devices_from_messages(epp_message)).values())[0]
    assert isinstance(device, Pump)
    assert isinstance(device, Gen1Device)


@pytest.mark.asyncio
async def test_epp_serial_number(epp):
    assert epp.serial_number == "00007426"


@pytest.mark.asyncio
async def test_epp_is_online(epp):
    assert epp.is_online is True


@pytest.mark.asyncio
async def test_epp_rf_link_quality(epp):
    assert epp.rf_link_quality == 100


@pytest.mark.asyncio
async def test_epp_pump_mode(epp):
    assert epp.pump_mode == 0


@pytest.mark.asyncio
async def test_epp_pump_state(epp):
    assert epp.pump_state == PumpState.PUMP_IS_JUST_STARTING


@pytest.mark.asyncio
async def test_epp_is_running(epp):
    assert epp.is_running is False


@pytest.mark.asyncio
async def test_epp_outlet_pressure(epp):
    assert epp.outlet_pressure == 0.0


@pytest.mark.asyncio
async def test_epp_outlet_temperature(epp):
    assert epp.outlet_temperature == 20


@pytest.mark.asyncio
async def test_epp_flow_rate(epp):
    assert epp.flow_rate == 100


@pytest.mark.asyncio
async def test_epp_flow_total(epp):
    assert epp.flow_total == 133


@pytest.mark.asyncio
async def test_epp_flow_since_last_reset(epp):
    assert epp.flow_since_last_reset == 0


@pytest.mark.asyncio
async def test_epp_has_frost_warning(epp):
    assert epp.has_frost_warning is False


@pytest.mark.asyncio
async def test_epp_operating_mode(epp):
    assert epp.operating_mode == OperatingMode.SCHEDULED


@pytest.mark.asyncio
async def test_epp_valve_count(epp):
    assert epp.valve_count == 1


@pytest.mark.asyncio
async def test_epp_valve_ids(epp):
    assert epp.valve_ids == [0]


@pytest.mark.asyncio
async def test_epp_watering_timer(epp):
    assert epp.get_watering_timer(0) == 0


@pytest.mark.asyncio
async def test_epp_is_valve_open(epp):
    assert epp.is_valve_open(0) is False
