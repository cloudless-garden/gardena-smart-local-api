import pytest

from gardena_smart_local_api.devices import (
    create_devices_from_json,
    create_devices_from_messages,
)
from gardena_smart_local_api.resources import IpsoObject, IpsoPath, IpsoResource


@pytest.mark.asyncio
async def test_unknown_device_returns_empty(unknown_device):
    print(unknown_device)
    devices = await create_devices_from_messages(unknown_device)
    assert len(devices) == 0


@pytest.mark.asyncio
async def test_device_get_resource(single_device):
    print(single_device)
    devices = await create_devices_from_messages(single_device)
    device_id, device = list(devices.items())[0]

    model_number = device.get_resource("device", "0", "model_number")
    assert model_number is not None
    assert isinstance(model_number, str)

    online = device.get_resource("connection_status", "0", "online")
    assert isinstance(online, bool)


@pytest.mark.asyncio
async def test_device_properties(single_device):
    devices = await create_devices_from_messages(single_device)
    device_id, device = list(devices.items())[0]

    assert (
        device.get_value(
            IpsoPath(
                object_name="device",
                object_instance_id="0",
                resource_name="model_number",
            )
        )
        is not None
    )
    assert (
        device.get_value(
            IpsoPath(
                object_name="device",
                object_instance_id="0",
                resource_name="serial_number",
            )
        )
        is not None
    )
    assert (
        device.get_value(
            IpsoPath(
                object_name="device",
                object_instance_id="0",
                resource_name="firmware_version",
            )
        )
        is not None
    )
    assert isinstance(
        device.get_value(
            IpsoPath(
                object_name="connection_status",
                object_instance_id="0",
                resource_name="online",
            )
        ),
        bool,
    )


@pytest.mark.asyncio
async def test_object_creation():
    object_data = {
        "resources": {
            "watering_timer_1": {"type": "vi", "access": "rw"},
            "valve_error_1": {"type": "vi", "access": "r"},
        },
    }

    obj = IpsoObject("lemonbeat", "0", object_data)

    assert obj.name == "lemonbeat"
    assert obj.object_instance_id == "0"
    assert len(obj.resources) == 2
    assert "watering_timer_1" in obj.resources
    assert "valve_error_1" in obj.resources


@pytest.mark.asyncio
async def test_resource_properties():
    resource_data = {
        "type": "vi",
        "access": "rw",
        "unit": "s",
        "description": "Duration in seconds",
    }

    resource = IpsoResource("duration", resource_data, "actuator", "0")

    assert resource.name == "duration"
    assert resource.object_name == "actuator"
    assert resource.type == "vi"
    assert resource.access == "rw"
    assert resource.unit == "s"
    assert resource.is_readable
    assert resource.is_writable


@pytest.mark.asyncio
async def test_resource_read_only():
    resource_data = {"type": "vb", "access": "r"}
    resource = IpsoResource("online", resource_data, "connection_status", "0")

    assert resource.is_readable
    assert not resource.is_writable


@pytest.mark.asyncio
async def test_resource_write_only():
    resource_data = {"type": "vi", "access": "w"}
    resource = IpsoResource("command", resource_data, "lemonbeat", "0")

    assert not resource.is_readable
    assert resource.is_writable


@pytest.mark.asyncio
async def test_device_set_resource(water_control_message):
    devices = await create_devices_from_messages(water_control_message)
    device_id, device = list(devices.items())[0]

    write_request_list = device.build_set_resource_obj(
        "lemonbeat", "0", "watering_timer_1", 2342
    )
    write_request = write_request_list.root[0]

    assert write_request.op == "write"
    assert write_request.entity.device == device_id
    assert str(write_request.entity.path) == "lemonbeat/0/watering_timer_1"
    assert write_request.payload is not None
    assert write_request.payload["vi"] == 2342


@pytest.mark.asyncio
async def test_device_model_name(single_device):
    devices = await create_devices_from_messages(single_device)
    device_id, device = list(devices.items())[0]

    assert (
        device.get_value(
            IpsoPath(
                object_name="device",
                object_instance_id="0",
                resource_name="device_type",
            )
        )
        is not None
    )


@pytest.mark.asyncio
async def test_update_data(update_event, single_device):
    devices = await create_devices_from_messages(single_device)
    device_id, device = list(devices.items())[0]

    device.update_data(update_event[0])

    updated_battery = device.get_value(
        IpsoPath(
            object_name="lemonbeat",
            object_instance_id="0",
            resource_name="battery_level",
        )
    )
    assert updated_battery == 65


@pytest.mark.asyncio
async def test_create_devices_from_data(water_control_json):
    devices = await create_devices_from_json(water_control_json)

    assert devices is not None
    assert len(devices) == 1

    assert "3034F8EE90126D400001737D" in devices
    device = devices["3034F8EE90126D400001737D"]
    assert device.id == "3034F8EE90126D400001737D"
    assert device.model_definition.name == "smart Water Control"
