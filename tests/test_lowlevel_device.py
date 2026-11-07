# SPDX-FileCopyrightText: 2026 GARDENA GmbH
#
# SPDX-License-Identifier: LGPL-3.0-or-later

import copy
from typing import Any, cast

import pytest

from gardena_smart_local_api.devices import (
    create_devices_from_json,
    create_devices_from_messages,
)
from gardena_smart_local_api.devices.device import (
    Device,
    DeviceMap,
    _value_to_payload,
    build_discovery_obj,
    build_inclusion_obj,
)
from gardena_smart_local_api.messages import Entity, Event
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


def test_value_to_payload_int_list():
    assert _value_to_payload([1, 2, 3]) == {"ai": ["0=1,1=2,2=3"]}


def test_value_to_payload_str_list():
    assert _value_to_payload(["a", "b"]) == {"as": ["0='a',1='b'"]}


def test_value_to_payload_empty_list_raises():
    with pytest.raises(TypeError, match="Empty list"):
        _value_to_payload([])


def test_value_to_payload_unsupported_list_type_raises():
    with pytest.raises(TypeError, match="Unsupported list value type"):
        _value_to_payload(cast(Any, [1.5, 2.5]))


def test_value_to_payload_unsupported_scalar_type_raises():
    with pytest.raises(TypeError, match="Unsupported value type"):
        _value_to_payload(cast(Any, None))


@pytest.mark.asyncio
async def test_from_raw_missing_model_number_raises():
    with pytest.raises(ValueError, match="Could not extract model_number"):
        await Device._from_raw({"some-id": {"device": {"0": {}}}})


@pytest.mark.asyncio
async def test_from_raw_unknown_model_returns_none():
    device = await Device._from_raw(
        {"some-id": {"device": {"0": {"model_number": {"vs": "unknown-model-number"}}}}}
    )
    assert device is None


@pytest.mark.asyncio
async def test_update_data_empty_payload_is_noop(water_control):
    before = copy.deepcopy(water_control.data)
    water_control.update_data(
        Event(
            entity=Entity(
                path=IpsoPath(object_name="lemonbeat", object_instance_id="0"),
                device=water_control.id,
            ),
            op="update",
            payload={},
        )
    )
    assert water_control.data == before


@pytest.mark.asyncio
async def test_update_data_overwrite_replaces_object(water_control):
    water_control.update_data(
        Event(
            entity=Entity(
                path=IpsoPath(object_name="lemonbeat", object_instance_id="0"),
                device=water_control.id,
            ),
            op="overwrite",
            payload={"battery_level": {"vi": 50}},
        )
    )
    assert water_control.data["lemonbeat"]["0"] == {"battery_level": {"vi": 50}}


@pytest.mark.asyncio
async def test_get_field(water_control):
    field = water_control.get_field(
        IpsoPath(
            object_name="lemonbeat",
            object_instance_id="0",
            resource_name="battery_level",
        )
    )
    assert field is not None
    assert field.value is not None


@pytest.mark.asyncio
async def test_get_field_missing_returns_none(water_control):
    field = water_control.get_field(
        IpsoPath(
            object_name="lemonbeat", object_instance_id="0", resource_name="unknown"
        )
    )
    assert field is None


@pytest.mark.asyncio
async def test_get_value_mid_path_non_dict_returns_none(water_control):
    water_control.data["lemonbeat"] = "not a dict"
    assert (
        water_control.get_value(
            IpsoPath(object_name="lemonbeat", object_instance_id="0", resource_name="x")
        )
        is None
    )


@pytest.mark.asyncio
async def test_get_field_mid_path_non_dict_returns_none(water_control):
    water_control.data["lemonbeat"] = "not a dict"
    assert (
        water_control.get_field(
            IpsoPath(object_name="lemonbeat", object_instance_id="0", resource_name="x")
        )
        is None
    )


@pytest.mark.asyncio
async def test_get_object_instance_ids_single_instance(water_control):
    assert water_control.get_object_instance_ids("device") == ["0"]


@pytest.mark.asyncio
async def test_build_set_resource_obj_unknown_object_raises(water_control):
    with pytest.raises(ValueError, match="not found"):
        water_control.build_set_resource_obj("unknown_object", "0", "x", 1)


@pytest.mark.asyncio
async def test_build_set_resource_obj_unknown_resource_raises(water_control):
    with pytest.raises(ValueError, match="not found"):
        water_control.build_set_resource_obj("device", "0", "unknown_resource", 1)


@pytest.mark.asyncio
async def test_build_set_resource_obj_not_writable_raises(water_control):
    with pytest.raises(ValueError, match="not writable"):
        water_control.build_set_resource_obj("device", "0", "model_number", "x")


@pytest.mark.asyncio
async def test_device_manufacturer_and_versions(water_control):
    assert water_control.manufacturer == "Gardena"
    assert water_control.software_version == "2.5.0"
    assert water_control.hardware_version == "0.3.5"


@pytest.mark.asyncio
async def test_build_exclusion_obj(water_control):
    request = water_control.build_exclusion_obj().root[0]

    assert request.op == "execute"
    assert request.entity.path.object_name == "device"
    assert request.entity.path.resource_name == "factory_reset"


@pytest.mark.asyncio
async def test_build_refresh_online_status_obj(water_control):
    request = water_control.build_refresh_online_status_obj().root[0]

    assert request.op == "read"
    assert request.entity.path.object_name == "connection_status"
    assert request.entity.path.resource_name == "online"


@pytest.mark.asyncio
async def test_firmware_update_state(water_control):
    assert str(water_control.firmware_update_state) == "idle"

    request = water_control.build_refresh_firmware_update_state_obj().root[0]
    assert request.op == "read"
    assert request.entity.path.object_name == "firmware_update"
    assert request.entity.path.resource_name == "state"


@pytest.mark.asyncio
async def test_firmware_update_result(water_control):
    assert water_control.firmware_update_result is not None

    request = water_control.build_refresh_firmware_update_result_obj().root[0]
    assert request.op == "read"
    assert request.entity.path.object_name == "firmware_update"
    assert request.entity.path.resource_name == "update_result"


@pytest.mark.asyncio
async def test_is_online_invalid_value_returns_none(water_control):
    water_control.update_data(
        Event(
            entity=Entity(
                path=IpsoPath(
                    object_name="connection_status",
                    object_instance_id="0",
                    resource_name="online",
                ),
                device=water_control.id,
            ),
            op="overwrite",
            payload={"vi": 3},
        )
    )
    assert water_control.is_online is None


@pytest.mark.asyncio
async def test_firmware_update_state_unknown_value_returns_none(water_control):
    water_control.update_data(
        Event(
            entity=Entity(
                path=IpsoPath(
                    object_name="firmware_update",
                    object_instance_id="0",
                    resource_name="state",
                ),
                device=water_control.id,
            ),
            op="overwrite",
            payload={"vi": 999},
        )
    )
    assert water_control.firmware_update_state is None


@pytest.mark.asyncio
async def test_firmware_update_result_unknown_value_returns_none(water_control):
    water_control.update_data(
        Event(
            entity=Entity(
                path=IpsoPath(
                    object_name="firmware_update",
                    object_instance_id="0",
                    resource_name="update_result",
                ),
                device=water_control.id,
            ),
            op="overwrite",
            payload={"vi": 999},
        )
    )
    assert water_control.firmware_update_result is None


@pytest.mark.asyncio
async def test_available_firmware_version_empty_is_none(water_control):
    assert water_control.available_firmware_version is None
    assert water_control.available_software_version is None

    request = water_control.build_refresh_available_firmware_version_obj().root[0]
    assert request.op == "read"
    assert request.entity.path.object_name == "firmware_update"
    assert request.entity.path.resource_name == "pkg_version"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("pkg_version", "expected_software_version"),
    [
        ("SwPkg-4.0", "4.0"),
        ("1.6.1-beta-3", "3"),
        ("unparsable", "unparsable"),
    ],
)
async def test_available_software_version_parsing(
    water_control, pkg_version, expected_software_version
):
    water_control.update_data(
        Event(
            entity=Entity(
                path=IpsoPath(
                    object_name="firmware_update",
                    object_instance_id="0",
                    resource_name="pkg_version",
                ),
                device=water_control.id,
            ),
            op="update",
            payload={"vs": pkg_version},
        )
    )
    assert water_control.available_firmware_version == pkg_version
    assert water_control.available_software_version == expected_software_version


@pytest.mark.asyncio
async def test_build_install_firmware_update_obj(water_control):
    request = water_control.build_install_firmware_update_obj().root[0]

    assert request.op == "execute"
    assert request.entity.path.object_name == "firmware_update"
    assert request.entity.path.resource_name == "update"
    assert request.payload is None


@pytest.mark.asyncio
async def test_device_repr(water_control):
    representation = repr(water_control)
    assert water_control.id in representation
    assert water_control.model_definition.name in representation


@pytest.mark.asyncio
async def test_device_map(water_control):
    device_map = DeviceMap({water_control.id: water_control})
    other_map = DeviceMap({"other-id": water_control})

    combined = device_map + other_map
    assert len(combined) == 2
    assert water_control.id in combined
    assert combined[water_control.id] is water_control

    combined["another-id"] = water_control
    assert "another-id" in combined
    del combined["another-id"]
    assert "another-id" not in combined

    assert set(iter(combined)) == {water_control.id, "other-id"}
    assert water_control.id in device_map.__str__()


def test_build_discovery_obj():
    requests = build_discovery_obj().root
    assert len(requests) == 2
    assert {r.entity.service for r in requests} == {"lemonbeatd", "lwm2mserver"}
    assert all(r.op == "read" for r in requests)


def test_build_inclusion_obj():
    request = build_inclusion_obj("lemonbeatd", "5").root[0]

    assert request.op == "execute"
    assert request.entity.service == "lemonbeatd"
    assert request.entity.path.object_name == "includable_device"
    assert request.entity.path.object_instance_id == "5"
    assert request.entity.path.resource_name == "include"
