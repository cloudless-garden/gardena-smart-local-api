import pytest

from gardena_smart_local_api.devices.gen1 import Gen1Device
from gardena_smart_local_api.devices.power import PowerAdapter


@pytest.mark.asyncio
async def test_power_adapter_is_power_adapter(power_adapter):
    assert isinstance(power_adapter, PowerAdapter)
    assert isinstance(power_adapter, Gen1Device)


@pytest.mark.asyncio
async def test_power_adapter_serial_number(power_adapter):
    assert power_adapter.serial_number == "00037776"


@pytest.mark.asyncio
async def test_power_adapter_is_online(power_adapter):
    assert power_adapter.is_online is True


@pytest.mark.asyncio
async def test_power_adapter_rf_link_quality(power_adapter):
    rf = power_adapter.rf_link_quality
    assert rf is not None
    assert isinstance(rf, int)
    assert rf == 100


@pytest.mark.asyncio
async def test_power_adapter_power_timer(power_adapter):
    assert power_adapter.power_timer == 0


@pytest.mark.asyncio
async def test_power_adapter_is_off(power_adapter):
    assert power_adapter.is_output_enabled is False


@pytest.mark.asyncio
async def test_power_adapter_error(power_adapter):
    assert power_adapter.error == 0


@pytest.mark.asyncio
async def test_power_adapter_update_event(power_adapter, power_adapter_update_event):
    event = power_adapter_update_event[0]
    power_adapter.update_data(event)
    assert power_adapter.power_timer == 3597
    assert power_adapter.is_output_enabled is True


@pytest.mark.asyncio
async def test_power_adapter_build_enable_output(power_adapter):
    request = power_adapter.build_enable_output_obj(120).root[0]
    assert request.op == "write"
    assert request.entity.device == power_adapter.id
    assert request.entity.path.object_name == "lemonbeat"
    assert request.entity.path.object_instance_id == "0"
    assert request.entity.path.resource_name == "power_timer"
    assert request.payload == {"vi": 120}


@pytest.mark.asyncio
async def test_power_adapter_build_disable_output(power_adapter):
    request = power_adapter.build_disable_output_obj().root[0]
    assert request.op == "write"
    assert request.entity.device == power_adapter.id
    assert request.entity.path.object_name == "lemonbeat"
    assert request.entity.path.object_instance_id == "0"
    assert request.entity.path.resource_name == "power_timer"
    assert request.payload == {"vi": 0}


@pytest.mark.asyncio
async def test_power_adapter_build_identify(power_adapter):
    request = power_adapter.build_identify_obj().root[0]
    assert request.op == "write"
    assert request.entity.device == power_adapter.id
    assert request.entity.path.object_name == "lemonbeat"
    assert request.entity.path.object_instance_id == "0"
    assert request.entity.path.resource_name == "command"
    assert request.payload == {"vi": 37}
