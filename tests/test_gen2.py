# SPDX-FileCopyrightText: 2026 GARDENA GmbH
#
# SPDX-License-Identifier: LGPL-3.0-or-later

import pytest
import pytest_asyncio

from gardena_smart_local_api.devices.gen2 import Gen2Device
from gardena_smart_local_api.devices.irrigation import (
    Gen2IrrigationControl,
    Gen2WaterControl,
)
from gardena_smart_local_api.devices.mowers import Gen2Mower
from gardena_smart_local_api.messages import IngressMessageList
from gardena_smart_local_api.model_loader import Gen2ModelDefinition, get_model_loader


@pytest.fixture
def gen2_device():
    return Gen2Device(
        id="3034F8319C02BF00000033FF",
        data={},
        model_definition=Gen2ModelDefinition(
            model_number="test-model", name="Test Gen2 Device"
        ),
    )


def test_radio_signal_strength_and_link_quality_unset(gen2_device):
    assert gen2_device.radio_signal_strength is None
    assert gen2_device.rf_link_quality is None


def test_radio_signal_strength_and_link_quality_from_event(gen2_device):
    # Values as reported by a real Gen2 water control (single valve).
    path = "connectivity_monitoring/0"
    event = IngressMessageList.model_validate_json(f"""
        [
          {{
            "entity": {{ "device": "{gen2_device.id}", "path": "{path}" }},
            "metadata": {{ "sequence": 1, "source": "lwm2mserver" }},
            "op": "update",
            "payload": {{
              "radio_signal_strength": {{ "ts": 1786352015, "vi": -73 }},
              "link_quality": {{ "ts": 1786352015, "vi": 2 }},
              "_urn": "urn:oma:lwm2m:x:28171"
            }}
          }}
        ]
        """)
    gen2_device.update_data(event.root[0])

    assert gen2_device.radio_signal_strength == -73
    assert gen2_device.rf_link_quality == 90


@pytest.mark.parametrize(
    ("level", "percent"), [(0, 20), (1, 50), (2, 90), (3, 0), (-1, 0)]
)
def test_rf_link_quality_maps_level_to_percent(gen2_device, level, percent):
    event = IngressMessageList.model_validate_json(f"""
        [
          {{
            "entity": {{
              "device": "{gen2_device.id}",
              "path": "connectivity_monitoring/0"
            }},
            "metadata": {{ "sequence": 1, "source": "lwm2mserver" }},
            "op": "update",
            "payload": {{ "link_quality": {{ "ts": 1786352015, "vi": {level} }} }}
          }}
        ]
        """)
    gen2_device.update_data(event.root[0])

    assert gen2_device.rf_link_quality == percent


def test_build_refresh_rf_link_quality_obj(gen2_device):
    request_list = gen2_device.build_refresh_rf_link_quality_obj()
    request = request_list.root[0]

    assert request.op == "execute"
    assert request.entity.device == gen2_device.id
    assert request.entity.service == "lwm2mserver"
    assert request.entity.path.object_name == "sg_common"
    assert request.entity.path.object_instance_id == "0"
    assert request.entity.path.resource_name == "measure_rf_link"


@pytest.fixture
def gen2_water_control():
    return Gen2WaterControl(
        id="3034F8319C02BF00000033FF",
        data={},
        model_definition=Gen2ModelDefinition(
            model_number="test-model", name="Test Gen2 Water Control"
        ),
    )


def _temperature_event(device, value):
    event = IngressMessageList.model_validate_json(f"""
        [
          {{
            "entity": {{ "device": "{device.id}", "path": "temperature/0" }},
            "metadata": {{ "sequence": 1, "source": "lwm2mserver" }},
            "op": "update",
            "payload": {{ "sensor_value": {{ "ts": 1786352015, "vf": {value} }} }}
          }}
        ]
        """)
    return event.root[0]


def test_frost_warning_unset_without_temperature(gen2_water_control):
    assert gen2_water_control.has_frost_warning is None


@pytest.mark.parametrize(
    ("temperature", "frost"),
    [(-3.5, True), (3.62, True), (4.999, True), (5.0, False), (18.83, False)],
)
def test_frost_warning_derived_from_temperature(gen2_water_control, temperature, frost):
    gen2_water_control.update_data(_temperature_event(gen2_water_control, temperature))

    assert gen2_water_control.has_frost_warning is frost


SCHEDULE_RESOURCES = (
    "start_offset_from",
    "start_offset_seconds",
    "end_offset_from",
    "end_offset_seconds",
    "repetition_type",
    "repetition_value",
    "actuator",
    "pre_offset",
)


def _schedule_event(device, instance_id, free=False):
    """A schedule slot as the gateway reports it, `free` as left by a delete."""
    values = {
        "start_offset_seconds": 32400,
        "end_offset_seconds": 34200,
        "repetition_type": 1,
        "repetition_value": 129,
    }
    payload = {}
    for resource_name in SCHEDULE_RESOURCES:
        value = 0 if free else values.get(resource_name, 0)
        payload[resource_name] = {"ts": 1795435725, "vi": value}
    event = IngressMessageList.model_validate(
        [
            {
                "entity": {"device": device.id, "path": f"schedule/{instance_id}"},
                "metadata": {"sequence": 1, "source": "lwm2mserver"},
                "op": "update",
                "payload": payload,
            }
        ]
    )
    return event.root[0]


@pytest_asyncio.fixture(
    params=[("2812", Gen2WaterControl), ("469", Gen2IrrigationControl)],
    ids=["water_control", "irrigation_control"],
)
async def gen2_irrigation_device(request):
    model_number, device_class = request.param
    model_definition = (await get_model_loader()).get_model(model_number)
    return device_class(
        id="3034F8319C02BF00000033FF", data={}, model_definition=model_definition
    )


def test_no_schedules(gen2_irrigation_device):
    assert gen2_irrigation_device.schedule_count == 0
    with pytest.raises(ValueError, match="no schedules"):
        gen2_irrigation_device.build_clear_schedules_obj()


def test_free_schedule_slots_are_not_counted(gen2_irrigation_device):
    gen2_irrigation_device.update_data(
        _schedule_event(gen2_irrigation_device, 0, free=True)
    )
    gen2_irrigation_device.update_data(
        _schedule_event(gen2_irrigation_device, 1, free=True)
    )

    assert gen2_irrigation_device.schedule_count == 0
    with pytest.raises(ValueError, match="no schedules"):
        gen2_irrigation_device.build_clear_schedules_obj()


def test_schedule_count(gen2_irrigation_device):
    gen2_irrigation_device.update_data(_schedule_event(gen2_irrigation_device, 0))
    gen2_irrigation_device.update_data(
        _schedule_event(gen2_irrigation_device, 1, free=True)
    )
    gen2_irrigation_device.update_data(_schedule_event(gen2_irrigation_device, 3))

    assert gen2_irrigation_device.schedule_count == 2


def test_build_clear_schedules_frees_every_used_slot(gen2_irrigation_device):
    gen2_irrigation_device.update_data(_schedule_event(gen2_irrigation_device, 0))
    gen2_irrigation_device.update_data(
        _schedule_event(gen2_irrigation_device, 1, free=True)
    )
    gen2_irrigation_device.update_data(_schedule_event(gen2_irrigation_device, 3))

    requests = gen2_irrigation_device.build_clear_schedules_obj().root

    free_slot = {}
    for resource_name in SCHEDULE_RESOURCES:
        free_slot[resource_name] = {"vi": 0}
    assert len(requests) == 1
    request = requests[0]
    assert request.op == "write"
    assert str(request.entity.path) == "schedule"
    assert request.entity.device == gen2_irrigation_device.id
    assert request.entity.service == "lwm2mserver"
    assert request.payload == {"0": free_slot, "3": free_slot}


def test_schedule_count_drops_once_a_slot_is_freed(gen2_irrigation_device):
    gen2_irrigation_device.update_data(_schedule_event(gen2_irrigation_device, 0))
    assert gen2_irrigation_device.schedule_count == 1

    gen2_irrigation_device.update_data(
        _schedule_event(gen2_irrigation_device, 0, free=True)
    )

    assert gen2_irrigation_device.schedule_count == 0


def test_gen2_mower_has_no_schedule_support():
    assert not hasattr(Gen2Mower, "schedule_count")
    assert not hasattr(Gen2Mower, "build_clear_schedules_obj")


def test_build_write_object_rejects_unknown_instance(gen2_irrigation_device):
    with pytest.raises(ValueError, match="not found"):
        gen2_irrigation_device.build_write_object_obj(
            "schedule", {"0": {"repetition_type": 0}}
        )


def test_build_write_object_rejects_unknown_resource(gen2_irrigation_device):
    gen2_irrigation_device.update_data(_schedule_event(gen2_irrigation_device, 0))

    with pytest.raises(ValueError, match="not found"):
        gen2_irrigation_device.build_write_object_obj(
            "schedule", {"0": {"no_such_resource": 0}}
        )
