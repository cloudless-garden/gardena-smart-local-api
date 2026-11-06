# SPDX-FileCopyrightText: 2026 GARDENA GmbH
#
# SPDX-License-Identifier: LGPL-3.0-or-later

import pytest

from gardena_smart_local_api.devices.gen2 import Gen2Device
from gardena_smart_local_api.messages import IngressMessageList
from gardena_smart_local_api.model_loader import Gen2ModelDefinition


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
