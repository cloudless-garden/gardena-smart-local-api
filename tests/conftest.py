# SPDX-FileCopyrightText: 2026 GARDENA GmbH
#
# SPDX-License-Identifier: LGPL-3.0-or-later

import json
from pathlib import Path

import pytest
import pytest_asyncio

from gardena_smart_local_api.devices import create_devices_from_messages
from gardena_smart_local_api.messages import Entity, Event, IngressMessageList
from gardena_smart_local_api.resources import IpsoPath


def build_delete_event(device_id: str, resource_path: str) -> Event:
    """Build a delete Event for a single resource, e.g. "lemonbeat/0/power_timer"."""
    return Event(
        entity=Entity(path=IpsoPath.model_validate(resource_path), device=device_id),
        op="delete",
    )


@pytest.fixture
def update_event_json():
    data_file = Path(__file__).parent / "data" / "update_event.json"
    with open(data_file) as f:
        return f.read()


@pytest.fixture
def update_event(update_event_json):
    return IngressMessageList.model_validate_json(update_event_json)


@pytest.fixture
def single_device_json():
    data_file = Path(__file__).parent / "data" / "single_device.json"
    with open(data_file) as f:
        json_data = json.load(f)[:1]
        return json.dumps(json_data)


@pytest.fixture
def single_device(single_device_json):
    return IngressMessageList.model_validate_json(single_device_json)


@pytest.fixture
def water_control_json():
    data_file = Path(__file__).parent / "data" / "water_control.json"
    with open(data_file) as f:
        return f.read()


@pytest.fixture
def water_control_message(water_control_json):
    return IngressMessageList.model_validate_json(water_control_json)


@pytest_asyncio.fixture
async def water_control(water_control_message):
    return list((await create_devices_from_messages(water_control_message)).values())[0]


@pytest.fixture
def water_control_and_update_event(water_control_message, update_event):
    return water_control_message + update_event


@pytest.fixture
def unknown_device_json():
    data_file = Path(__file__).parent / "data" / "unknown_device.json"
    with open(data_file) as f:
        return f.read()


@pytest.fixture
def unknown_device(unknown_device_json):
    return IngressMessageList.model_validate_json(unknown_device_json)


@pytest.fixture
def sensor1_json():
    data_file = Path(__file__).parent / "data" / "sensor1.json"
    with open(data_file) as f:
        return f.read()


@pytest.fixture
def sensor1_message(sensor1_json):
    return IngressMessageList.model_validate_json(sensor1_json)


@pytest_asyncio.fixture
async def sensor1(sensor1_message):
    return list((await create_devices_from_messages(sensor1_message)).values())[0]


@pytest.fixture
def sensor1_update_event_json():
    data_file = Path(__file__).parent / "data" / "sensor1_update_event.json"
    with open(data_file) as f:
        return f.read()


@pytest.fixture
def sensor1_update_event(sensor1_update_event_json):
    return IngressMessageList.model_validate_json(sensor1_update_event_json)


@pytest.fixture
def sensor1_and_update_event(sensor1_message, sensor1_update_event):
    return sensor1_message + sensor1_update_event


@pytest.fixture
def sensor2_json():
    data_file = Path(__file__).parent / "data" / "sensor2.json"
    with open(data_file) as f:
        return f.read()


@pytest.fixture
def sensor2_message(sensor2_json):
    return IngressMessageList.model_validate_json(sensor2_json)


@pytest_asyncio.fixture
async def sensor2(sensor2_message):
    return list((await create_devices_from_messages(sensor2_message)).values())[0]


@pytest.fixture
def sensor2_update_event_json():
    data_file = Path(__file__).parent / "data" / "sensor2_update_event.json"
    with open(data_file) as f:
        return f.read()


@pytest.fixture
def sensor2_update_event(sensor2_update_event_json):
    return IngressMessageList.model_validate_json(sensor2_update_event_json)


@pytest.fixture
def sensor2_and_update_event(sensor2_message, sensor2_update_event):
    return sensor2_message + sensor2_update_event


@pytest.fixture
def power_adapter_json():
    data_file = Path(__file__).parent / "data" / "power_adapter.json"
    with open(data_file) as f:
        return f.read()


@pytest.fixture
def power_adapter_message(power_adapter_json):
    return IngressMessageList.model_validate_json(power_adapter_json)


@pytest_asyncio.fixture
async def power_adapter(power_adapter_message):
    return list((await create_devices_from_messages(power_adapter_message)).values())[0]


@pytest.fixture
def power_adapter_update_event_json():
    data_file = Path(__file__).parent / "data" / "power_adapter_update_event.json"
    with open(data_file) as f:
        return f.read()


@pytest.fixture
def power_adapter_update_event(power_adapter_update_event_json):
    return IngressMessageList.model_validate_json(power_adapter_update_event_json)


@pytest.fixture
def epp_json():
    data_file = Path(__file__).parent / "data" / "epp.json"
    with open(data_file) as f:
        return f.read()


@pytest.fixture
def epp_message(epp_json):
    return IngressMessageList.model_validate_json(epp_json)


@pytest_asyncio.fixture
async def epp(epp_message):
    return list((await create_devices_from_messages(epp_message)).values())[0]


@pytest.fixture
def mower_gen1_lona_json():
    data_file = Path(__file__).parent / "data" / "mower_gen1_lona.json"
    with open(data_file) as f:
        return f.read()


@pytest.fixture
def mower_gen1_lona_message(mower_gen1_lona_json):
    return IngressMessageList.model_validate_json(mower_gen1_lona_json)


@pytest_asyncio.fixture
async def mower_gen1_lona(mower_gen1_lona_message):
    return (
        list((await create_devices_from_messages(mower_gen1_lona_message)).values())
    )[0]


@pytest.fixture
def mower_gen2_json():
    data_file = Path(__file__).parent / "data" / "mower_gen2.json"
    with open(data_file) as f:
        return f.read()


@pytest.fixture
def mower_gen2_message(mower_gen2_json):
    return IngressMessageList.model_validate_json(mower_gen2_json)


@pytest_asyncio.fixture
async def mower_gen2(mower_gen2_message):
    return list((await create_devices_from_messages(mower_gen2_message)).values())[0]


@pytest.fixture
def mower_gen1_lona_position_update_event_json():
    data_file = (
        Path(__file__).parent / "data" / "mower_gen1_lona_position_update_event.json"
    )
    with open(data_file) as f:
        return f.read()


@pytest.fixture
def mower_gen1_lona_position_update_event(mower_gen1_lona_position_update_event_json):
    return IngressMessageList.model_validate_json(
        mower_gen1_lona_position_update_event_json
    )


@pytest.fixture
def mower_gen2_position_update_event_json():
    data_file = Path(__file__).parent / "data" / "mower_gen2_position_update_event.json"
    with open(data_file) as f:
        return f.read()


@pytest.fixture
def mower_gen2_position_update_event(mower_gen2_position_update_event_json):
    return IngressMessageList.model_validate_json(mower_gen2_position_update_event_json)
