"""Tests for dynamic device system."""

import json
import pytest
from pathlib import Path

from smart_system_local.devices.dynamic import DynamicDevice, DynamicObject, DynamicResource


def load_test_devices():
    """Load test devices at collection time for parametrization."""
    data_file = Path(__file__).parent / "data" / "devices.json"
    with open(data_file) as f:
        responses = json.load(f)
    return [
        pytest.param(device_id, {device_id: device_data}, id=device_id)
        for response in responses
        for device_id, device_data in response["payload"].items()
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("device_id,device_data", load_test_devices())
async def test_device_builder_creates_device(device_id, device_data):
    """Test that device builder can create a device."""
    device = await DynamicDevice.from_raw(device_data)
    
    assert device is not None
    assert isinstance(device, DynamicDevice)
    assert device.id == device_id


@pytest.mark.asyncio
@pytest.mark.parametrize("device_id,device_data", load_test_devices())
async def test_dynamic_device_has_objects(device_id, device_data):
    """Test that dynamic device has expected objects."""
    device = await DynamicDevice.from_raw(device_data)
    
    assert len(device.objects) > 0
    assert "device" in device.objects
    assert "connection_status" in device.objects


@pytest.mark.asyncio
@pytest.mark.parametrize("device_id,device_data", load_test_devices())
async def test_dynamic_device_get_resource(device_id, device_data):
    """Test getting resource values from dynamic device."""
    device = await DynamicDevice.from_raw(device_data)
    
    # Get model number
    model_number = device.get_resource("device", 0, "model_number")
    assert model_number is not None
    assert isinstance(model_number, str)
    
    # Get online status
    online = device.get_resource("connection_status", 0, "online")
    assert isinstance(online, bool)


@pytest.mark.asyncio
@pytest.mark.parametrize("device_id,device_data", load_test_devices())
async def test_dynamic_device_properties(device_id, device_data):
    """Test dynamic device inherited properties."""
    device = await DynamicDevice.from_raw(device_data)
    
    assert device.model_number is not None
    assert device.serial_number is not None
    assert device.firmware_version is not None
    assert isinstance(device.is_online, bool)


@pytest.mark.asyncio
async def test_dynamic_object_creation():
    """Test DynamicObject creation."""
    object_data = {
        "object_id": 28180,
        "resources": {
            "state": {"type": "vi", "access": "r"},
            "available": {"type": "vb", "access": "r"},
        }
    }
    
    obj = DynamicObject("actuator", "0", object_data)
    
    assert obj.name == "actuator"
    assert obj.object_instance_id == "0"
    assert obj.object_id == 28180
    assert len(obj.resources) == 2
    assert "state" in obj.resources
    assert "available" in obj.resources


@pytest.mark.asyncio
async def test_dynamic_resource_properties():
    """Test DynamicResource properties."""
    resource_data = {
        "type": "vi",
        "access": "rw",
        "unit": "s",
        "description": "Duration in seconds"
    }
    
    resource = DynamicResource("duration", resource_data, "actuator", "0")
    
    assert resource.name == "duration"
    assert resource.object_name == "actuator"
    assert resource.type == "vi"
    assert resource.access == "rw"
    assert resource.unit == "s"
    assert resource.is_readable
    assert resource.is_writable


@pytest.mark.asyncio
async def test_dynamic_resource_read_only():
    """Test read-only resource."""
    resource_data = {"type": "vb", "access": "r"}
    resource = DynamicResource("online", resource_data, "connection_status", "0")
    
    assert resource.is_readable
    assert not resource.is_writable


@pytest.mark.asyncio
async def test_dynamic_resource_write_only():
    """Test write-only resource."""
    resource_data = {"type": "vi", "access": "w"}
    resource = DynamicResource("command", resource_data, "lemonbeat", "0")
    
    assert not resource.is_readable
    assert resource.is_writable


@pytest.mark.asyncio
async def test_dynamic_device_set_resource():
    """Test building a write request for a resource."""
    device_id = "test_device"
    device_data = {
        device_id: {
            "device": {
                "0": {
                    "model_number": {"vs": "469"}
                }
            },
            "actuator": {
                "0": {
                    "state": {"vi": 0}
                }
            }
        }
    }
    
    device = await DynamicDevice.from_raw(device_data)
    
    # This should work - creating a write request (not actually writing)
    write_request = device.set_resource("actuator", 0, "paused_until", 1234567890)
    
    assert write_request["op"] == "write"
    assert write_request["entity"]["device"] == device_id
    assert "actuator/0/paused_until" in write_request["entity"]["path"]
    assert write_request["payload"]["vi"] == 1234567890


@pytest.mark.asyncio
@pytest.mark.parametrize("device_id,device_data", load_test_devices())
async def test_device_model_name(device_id, device_data):
    """Test getting device model name."""
    device = await DynamicDevice.from_raw(device_data)
    
    assert device.device_name is not None
    assert device.device_type_name is not None
