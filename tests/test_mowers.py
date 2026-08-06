# SPDX-FileCopyrightText: 2026 GARDENA GmbH
#
# SPDX-License-Identifier: LGPL-3.0-or-later

from base64 import b64encode

import pytest

from gardena_smart_local_api.devices.gen1 import Gen1BatteryMixin
from gardena_smart_local_api.devices.gen2 import Gen2BatteryMixin
from gardena_smart_local_api.devices.mowers import (
    Gen1Mower1,
    Gen1Mower2,
    Gen1MowerPosition,
    Gen2Mower,
    MowerState,
)
from gardena_smart_local_api.model_loader import Gen1ModelDefinition


def _set_gen1_status(mower, status: int | None) -> None:
    mower.data["lemonbeat"]["0"]["status"] = {"vi": status}


def _set_gen1_position(mower, data: bytes) -> None:
    mower.data["lemonbeat"]["0"]["position"] = {"vo": b64encode(data).decode()}


def _set_gen2_activity(mower, activity: int | None) -> None:
    mower.data["mower_app"]["0"]["activity"] = {"vi": activity}


def _set_gen2_state(mower, state: int | None) -> None:
    mower.data["mower_app"]["0"]["state"] = {"vi": state}


@pytest.fixture
def mower_gen1():
    return Gen1Mower1(
        id="3034F8319C02BF00000033FF",
        data={},
        model_definition=Gen1ModelDefinition(model_number="29694", name="Test Mower"),
    )


@pytest.mark.asyncio
async def test_mower_gen1_lona_is_mower(mower_gen1_lona):
    assert isinstance(mower_gen1_lona, Gen1Mower2)
    assert isinstance(mower_gen1_lona, Gen1BatteryMixin)


@pytest.mark.asyncio
async def test_mower_gen1_lona_serial_number(mower_gen1_lona):
    assert mower_gen1_lona.serial_number == "202211111111"


@pytest.mark.asyncio
async def test_mower_gen1_lona_is_online(mower_gen1_lona):
    assert mower_gen1_lona.is_online is True


@pytest.mark.asyncio
async def test_mower_gen1_lona_battery_level(mower_gen1_lona):
    assert mower_gen1_lona.battery_level == 72


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (0, MowerState.PAUSED),  # PAUSED
        (1, MowerState.MOWING),  # OK_CUTTING_AUTO
        (2, MowerState.RETURNING),  # OK_SEARCHING_CS
        (3, MowerState.CHARGING),  # OK_CHARGING
        (4, MowerState.LEAVING),  # OK_LEAVING_CS
        (5, MowerState.PAUSED),  # WAIT_SOFTWARE_DOWNLOAD
        (6, MowerState.PAUSED),  # WAIT_POWER_UP
        (7, MowerState.PARKED),  # PARKED_WEEK_TIMER
        (8, MowerState.PARKED),  # PARKED_BY_USER
        (9, MowerState.PAUSED),  # OFF_MAIN_SWITCH
        (10, MowerState.PAUSED),  # WAIT_STOP_PRESSED
        (11, MowerState.UNKNOWN),  # UNKNOWN
        (12, MowerState.ERROR),  # ERROR
        (13, MowerState.ERROR),  # ERROR_POWER_UP
        (14, MowerState.PAUSED),  # WAIT
        (15, MowerState.MOWING),  # OK_CUTTING_MANUAL
        (16, MowerState.PARKED),  # PARKED_AUTOTIMER
        (17, MowerState.PARKED),  # PARKED_DAY_LIMIT
        (18, MowerState.PARKED),  # PARKED_FROST
        (99, MowerState.UNKNOWN),  # not a known status
        (None, MowerState.UNKNOWN),  # reported as null
    ],
)
async def test_mower_gen1_lona_state(mower_gen1_lona, status, expected):
    _set_gen1_status(mower_gen1_lona, status)
    assert mower_gen1_lona.state == expected


@pytest.mark.asyncio
async def test_mower_gen1_lona_state_is_unknown_when_not_reported(mower_gen1_lona):
    del mower_gen1_lona.data["lemonbeat"]["0"]["status"]
    assert mower_gen1_lona.state == MowerState.UNKNOWN


@pytest.mark.asyncio
async def test_mower_gen1_lona_position(mower_gen1_lona):
    position = mower_gen1_lona.position
    assert position is not None

    assert position.gnss_latitude == pytest.approx(47.3636)
    assert position.gnss_longitude == pytest.approx(8.5126)
    assert position.gnss_horizontal_accuracy == 2500
    assert position.compass_heading == pytest.approx(225.0)
    assert position.compass_is_calibrated is True
    assert position.latitude == pytest.approx(47.3637)
    assert position.longitude == pytest.approx(8.5127)
    assert position.heading == pytest.approx(224.8)
    assert position.lona_is_ready is True


@pytest.mark.asyncio
async def test_mower_gen1_lona_position_update_event(
    mower_gen1_lona, mower_gen1_lona_position_update_event
):
    mower_gen1_lona.update_data(mower_gen1_lona_position_update_event[0])

    position = mower_gen1_lona.position
    assert position is not None
    assert position.gnss_latitude == pytest.approx(47.363723)
    assert position.gnss_longitude == pytest.approx(8.512062)
    assert position.gnss_horizontal_accuracy == 500
    assert position.compass_heading == pytest.approx(230.0)
    assert position.compass_is_calibrated is False
    assert position.latitude == pytest.approx(47.363723)
    assert position.longitude == pytest.approx(8.512062)
    assert position.heading is None
    assert position.lona_is_ready is False


@pytest.mark.asyncio
async def test_mower_gen1_lona_position_is_none_when_truncated(mower_gen1_lona):
    _set_gen1_position(mower_gen1_lona, bytes(25))
    assert mower_gen1_lona.position is None


@pytest.mark.asyncio
async def test_mower_gen1_lona_position_is_none_when_not_reported(mower_gen1_lona):
    del mower_gen1_lona.data["lemonbeat"]["0"]["position"]
    assert mower_gen1_lona.position is None


def test_mower_gen1_position_from_bytes_requires_26_bytes():
    with pytest.raises(ValueError):
        Gen1MowerPosition.model_validate(bytes(27))


@pytest.mark.asyncio
async def test_mower_gen1_lona_build_start_mowing_obj(mower_gen1_lona):
    request = mower_gen1_lona.build_start_mowing_obj(300, 12).root[0]

    assert request.op == "write"
    assert request.entity.device == mower_gen1_lona.id
    assert request.entity.service == "lemonbeatd"
    assert request.entity.path.object_name == "lemonbeat"
    assert request.entity.path.object_instance_id == "0"
    assert request.entity.path.resource_name == "mower_timer_with_distance"
    # 12 meters from the charging station, then 300 seconds
    assert request.payload == {"vo": "AAwAAAEs"}


@pytest.mark.asyncio
async def test_mower_gen1_lona_build_start_mowing_obj_default_distance(mower_gen1_lona):
    request = mower_gen1_lona.build_start_mowing_obj(300).root[0]

    assert request.payload == {"vo": "AAAAAAEs"}


@pytest.mark.asyncio
async def test_mower_gen1_lona_build_stop_mowing_obj(mower_gen1_lona):
    request = mower_gen1_lona.build_stop_mowing_obj().root[0]

    assert request.op == "write"
    assert request.entity.device == mower_gen1_lona.id
    assert request.entity.path.object_name == "lemonbeat"
    assert request.entity.path.object_instance_id == "0"
    assert request.entity.path.resource_name == "action_paused_until_1"
    # 2042-12-31 22:00
    assert request.payload == {"vo": "+gcMHxYA"}


@pytest.mark.asyncio
async def test_mower_gen1_lona_build_start_position_reporting_obj(mower_gen1_lona):
    request = mower_gen1_lona.build_start_position_reporting_obj(60).root[0]

    assert request.op == "write"
    assert request.entity.device == mower_gen1_lona.id
    assert request.entity.path.object_name == "lemonbeat"
    assert request.entity.path.object_instance_id == "0"
    assert request.entity.path.resource_name == "position_timer"
    assert request.payload == {"vi": 60}


def test_mower_gen1_state_is_unknown_without_data(mower_gen1):
    assert mower_gen1.state == MowerState.UNKNOWN


def test_mower_gen1_build_start_mowing_obj(mower_gen1):
    request = mower_gen1.build_start_mowing_obj(300).root[0]

    assert request.op == "write"
    assert request.entity.device == mower_gen1.id
    assert request.entity.service == "lemonbeatd"
    assert request.entity.path.object_name == "lemonbeat"
    assert request.entity.path.object_instance_id == "0"
    assert request.entity.path.resource_name == "mower_timer"
    assert request.payload == {"vi": 300}


def test_mower_gen1_build_stop_mowing_obj(mower_gen1):
    request = mower_gen1.build_stop_mowing_obj().root[0]

    assert request.op == "write"
    assert request.entity.path.resource_name == "action_paused_until_1"
    assert request.payload == {"vo": "+gcMHxYA"}


@pytest.mark.asyncio
async def test_mower_gen2_is_mower(mower_gen2):
    assert isinstance(mower_gen2, Gen2Mower)
    assert isinstance(mower_gen2, Gen2BatteryMixin)


@pytest.mark.asyncio
async def test_mower_gen2_serial_number(mower_gen2):
    assert mower_gen2.serial_number == "00001111"


@pytest.mark.asyncio
async def test_mower_gen2_is_online(mower_gen2):
    assert mower_gen2.is_online is True


@pytest.mark.asyncio
async def test_mower_gen2_battery_level(mower_gen2):
    assert mower_gen2.battery_level == 85


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("activity", "expected"),
    [
        (1, MowerState.CHARGING),  # CHARGING
        (2, MowerState.LEAVING),  # GOING_OUT
        (3, MowerState.MOWING),  # MOWING
        (4, MowerState.RETURNING),  # GOING_HOME
        (5, MowerState.PARKED),  # PARKED
        (6, MowerState.UNKNOWN),  # STOPPED_IN_GARDEN
        (99, MowerState.UNKNOWN),  # not a known activity
        (None, MowerState.UNKNOWN),  # reported as null
    ],
)
async def test_mower_gen2_state(mower_gen2, activity, expected):
    _set_gen2_activity(mower_gen2, activity)
    assert mower_gen2.state == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("state", "expected"),
    [
        (2, MowerState.UNKNOWN),  # STOPPED
        (3, MowerState.ERROR),  # FATAL_ERROR
        (5, MowerState.PAUSED),  # PAUSED
        (8, MowerState.ERROR),  # ERROR
    ],
)
async def test_mower_gen2_state_without_activity(mower_gen2, state, expected):
    _set_gen2_activity(mower_gen2, 0)  # NONE
    _set_gen2_state(mower_gen2, state)
    assert mower_gen2.state == expected


@pytest.mark.asyncio
async def test_mower_gen2_position(mower_gen2):
    position = mower_gen2.position
    assert position is not None
    assert position.latitude == pytest.approx(47.2385238)
    assert position.longitude == pytest.approx(8.5364685)
    assert position.accuracy == 500
    assert position.heading == pytest.approx(235.6)
    assert position.heading_accuracy == pytest.approx(50.0)


@pytest.mark.asyncio
async def test_mower_gen2_position_update_event(
    mower_gen2, mower_gen2_position_update_event
):
    mower_gen2.update_data(mower_gen2_position_update_event[0])

    position = mower_gen2.position
    assert position is not None
    assert position.latitude == pytest.approx(47.363723)
    assert position.longitude == pytest.approx(8.512062)
    assert position.accuracy == 500
    assert position.heading == pytest.approx(235.6)
    assert position.heading_accuracy == pytest.approx(50.0)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "resource_name",
    [
        "position__latitude",
        "position__longitude",
        "position__accuracy",
        "position__heading",
        "position__heading_accuracy",
    ],
)
async def test_mower_gen2_position_is_none_when_incomplete(mower_gen2, resource_name):
    del mower_gen2.data["smart_system_mower_api"]["0"][resource_name]
    assert mower_gen2.position is None


@pytest.mark.asyncio
async def test_mower_gen2_build_start_mowing_obj(mower_gen2):
    request = mower_gen2.build_start_mowing_obj(300).root[0]

    assert request.op == "execute"
    assert request.entity.device == mower_gen2.id
    assert request.entity.service == "lwm2mserver"
    assert request.entity.path.object_name == "smart_system_mower_api"
    assert request.entity.path.object_instance_id == "0"
    assert request.entity.path.resource_name == "manual_start"
    assert request.payload == {"as": ["0='300'"]}


@pytest.mark.asyncio
async def test_mower_gen2_build_start_mowing_obj_in_zone(mower_gen2):
    request = mower_gen2.build_start_mowing_obj(300, 2).root[0]

    assert request.op == "execute"
    assert request.entity.device == mower_gen2.id
    assert request.entity.path.object_name == "smart_system_mower_api"
    assert request.entity.path.object_instance_id == "0"
    assert request.entity.path.resource_name == "manual_start_in_zone"
    assert request.payload == {"as": ["0='300',1='2'"]}


@pytest.mark.asyncio
async def test_mower_gen2_build_stop_mowing_obj(mower_gen2):
    request = mower_gen2.build_stop_mowing_obj().root[0]

    assert request.op == "execute"
    assert request.entity.device == mower_gen2.id
    assert request.entity.path.object_name == "smart_system_mower_api"
    assert request.entity.path.object_instance_id == "0"
    assert request.entity.path.resource_name == "park_until_further_notice"
    assert request.payload is None


@pytest.mark.asyncio
async def test_mower_gen2_build_pause_mowing_obj(mower_gen2):
    request = mower_gen2.build_pause_mowing_obj().root[0]

    assert request.op == "execute"
    assert request.entity.device == mower_gen2.id
    assert request.entity.path.object_name == "mower_app"
    assert request.entity.path.object_instance_id == "0"
    assert request.entity.path.resource_name == "pause"
    assert request.payload is None


@pytest.mark.asyncio
@pytest.mark.parametrize("seconds", [60, 3600])
async def test_mower_gen2_build_start_position_reporting_obj(mower_gen2, seconds):
    request = mower_gen2.build_start_position_reporting_obj(seconds).root[0]

    assert request.op == "execute"
    assert request.entity.device == mower_gen2.id
    assert request.entity.path.object_name == "smart_system_mower_api"
    assert request.entity.path.object_instance_id == "0"
    assert request.entity.path.resource_name == "start_position_timer"
    assert request.payload == {"as": [f"0='{seconds}',1='3'"]}


@pytest.mark.asyncio
async def test_mower_gen2_build_start_position_reporting_obj_too_short(mower_gen2):
    with pytest.raises(ValueError, match="greater than or equal to 60"):
        mower_gen2.build_start_position_reporting_obj(59)


@pytest.mark.asyncio
async def test_mower_gen2_build_start_position_reporting_obj_too_long(mower_gen2):
    with pytest.raises(ValueError, match="less than or equal to 3600"):
        mower_gen2.build_start_position_reporting_obj(3601)
