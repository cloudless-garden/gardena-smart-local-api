# SPDX-FileCopyrightText: 2026 GARDENA GmbH
#
# SPDX-License-Identifier: LGPL-3.0-or-later

import pytest
import pytest_asyncio

from gardena_smart_local_api.devices.irrigation import (
    Gen1IrrigationControl,
    IrrigationControlValveError,
    WaterControlValveError,
)
from gardena_smart_local_api.messages import IngressMessageList
from gardena_smart_local_api.model_loader import Gen1ModelDefinition, get_model_loader


def _lemonbeat_update(device_id: str, resource_name: str, value: int):
    return IngressMessageList.model_validate_json(f"""
        [
          {{
            "entity": {{ "device": "{device_id}", "path": "lemonbeat/0" }},
            "metadata": {{ "sequence": 1, "source": "lemonbeatd" }},
            "op": "update",
            "payload": {{
              "{resource_name}": {{ "ts": 1774970419, "vi": {value} }},
              "_urn": "urn:oma:lwm2m:x:31000"
            }}
          }}
        ]
        """).root[0]


@pytest_asyncio.fixture
async def irrigation_control():
    loader = await get_model_loader()
    model_definition = loader.get_model("31653")
    assert isinstance(model_definition, Gen1ModelDefinition)
    return Gen1IrrigationControl(
        id="3034F8EE9012FFFF00001234",
        data={},
        model_definition=model_definition,
    )


@pytest.mark.asyncio
async def test_water_control_valve_error_none(water_control):
    assert water_control.get_valve_error() is WaterControlValveError.NONE


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (1, WaterControlValveError.VALVE_BROKEN),
        (2, WaterControlValveError.FROST_PREVENTS_STARTING),
        (3, WaterControlValveError.LOW_BATTERY_PREVENTS_STARTING),
        (4, WaterControlValveError.VALVE_POWER_SUPPLY_FAILED),
        (99, None),
    ],
)
async def test_water_control_valve_error(water_control, code, expected):
    water_control.update_data(
        _lemonbeat_update(water_control.id, "valve_error_1", code)
    )

    assert water_control.get_valve_error(0) is expected


@pytest.mark.asyncio
async def test_water_control_valve_error_invalid_valve(water_control):
    with pytest.raises(ValueError):
        water_control.get_valve_error(1)


@pytest.mark.asyncio
async def test_water_control_build_reset_all_valve_errors_obj(water_control):
    request = water_control.build_reset_all_valve_errors_obj().root[0]

    assert request.op == "write"
    assert request.entity.path.resource_name == "command"
    assert request.payload == {"vi": 36}


@pytest.mark.asyncio
async def test_irrigation_control_valve_error_maps_to_valve_id(irrigation_control):
    irrigation_control.update_data(
        _lemonbeat_update(irrigation_control.id, "valve_error_3", 2)
    )

    assert (
        irrigation_control.get_valve_error(2)
        is IrrigationControlValveError.VALVE_NOT_CONNECTED
    )
    assert irrigation_control.get_valve_error(0) is None


@pytest.mark.asyncio
async def test_irrigation_control_ignores_undocumented_valve_error_0(
    irrigation_control,
):
    irrigation_control.update_data(
        _lemonbeat_update(irrigation_control.id, "valve_error_0", 5)
    )

    for valve_id in irrigation_control.valve_ids:
        assert irrigation_control.get_valve_error(valve_id) is None


@pytest.mark.asyncio
async def test_irrigation_control_valve_error_invalid_valve(irrigation_control):
    with pytest.raises(ValueError):
        irrigation_control.get_valve_error(6)


@pytest.mark.asyncio
async def test_irrigation_control_build_reset_all_valve_errors_obj(
    irrigation_control,
):
    request = irrigation_control.build_reset_all_valve_errors_obj().root[0]

    assert request.op == "write"
    assert request.entity.path.resource_name == "command"
    assert request.payload == {"vi": 36}
