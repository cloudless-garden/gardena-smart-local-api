# SPDX-FileCopyrightText: 2026 GARDENA GmbH
#
# SPDX-License-Identifier: LGPL-3.0-or-later

import base64

import pytest

from gardena_smart_local_api.utils.schedules import (
    Gen1OffsetPoint,
    Gen1ScheduleCycle,
    Gen1Weekday,
    ScheduleEntry,
    SunScheduleEntry,
    TimeOffset,
    gen1_schedule_config_to_base64,
    gen1_sun_schedule_config_to_base64,
    parse_gen1_schedule_config,
    parse_gen1_sun_schedule_config,
)

SCHEDULE_CONFIG_B64 = "BX8GMh4ABAJ/BAoFAAQEfwYZGQABA38GABkAAAB/BAAFAAABfwQFBQAB"
SUN_SCHEDULE_CONFIG_B64 = "YD6gWAH/P6AZoB0B/z9wEnAWAf8/AA/gDwH/PyAh4CMB/z8="

# Real schedule_config payloads captured from gateways, one per device type.
SCHEDULE_CONFIG_B64_BY_DEVICE = {
    "power_adapter": (
        "GAgXAAUAACIIFxQFAAAECBcoBQAABRAAAQUAABkQABQFAAAWEAAoBQAAFBABAAUAABAQ"
        "ARQFAAASEAEoBQAAGhACAAUAAAwQAhQFAAAVEAIoBQAACBADAAUAACAQAxQFAAABEAMo"
        "BQAAHRAEAAUAACMQBBQFAAAGEAQoBQAACxAFAAUAAAAQBRQFAAAbEAUoBQAADhAGAAUA"
        "AAMQBhQFAAAKEAYoBQAADxAHAAUAABcQBxQFAAAeEAcoBQAABxAUAAUAAB8QFBQFAAAC"
        "EBQoBQAAExAVAAUAABEQFRQFAAAhEBUoBQAADRAWAAUAAAkQFhQFAAAcEBYoBQAA"
    ),
    "automatic_pump": (
        "gH8LHgUAAIF/CygFAACCAQsyBQAAg38MAAUAAIQBDAoFAACFAQwUBQAAhgEMHgUAAId/"
        "DCgFAACIAQwyBQAAiX8NAAUAAIoBDQoFAACLfw0UBQAAjAENHgUAAI1/DSgFAACOAQ0y"
        "BQAAj38OAAUAAJABDgoFAACRfw4UBQAAkn8OKAoAAJN/DwAFAACUAQ8KBQAAlX8PFAUA"
        "AJYBDx4FAACXfw8oBQAAmAEPMgUAAJl/EAAFAACaARAKBQAAm38QFAUAAJwBEB4FAACd"
        "fxAoBQAAngEQMgUAAJ9/EQAKAACgAREPBQAAoQERGQQAAA=="
    ),
    "robotic_lawnmower": (
        "AAEIALgBAAEBFAB4AAACAggAuAEAAwIUAHgAAAQECAC4AQAFBBQAeAAABggIALgBAAcI"
        "FAB4AAAIEAgAuAEACRAUAHgAAAogCAC4AQALIBQAeAAADEAIALgBAA1AFAB4AAA="
    ),
    "water_control": (
        "gH8AAAEAAIF/AB4BAACCfwUAAQAAg38FHgEAAIR/BgABAACFfwYeAQAAhn8HAAEAAId/"
        "Bx4BAACIfwgAAQAAiX8IHgEAAIp/CQABAACLfwkeAQAAjH8KAAEAAI1/Ch4BAACOfwsA"
        "AQAAj38LHgEAAJB/DAABAACRfwweAQAAkn8NAAEAAJN/DR4BAACUfw4AAQAAlX8OHgEA"
        "AJZ/DwABAACXfxEAAQAAmH8RHgEAAJl/Eh4BAACafxMAAQAAm38THgEAAJx/FAABAACd"
        "fxQeAQAAnn8VAAEAAJ9/FR4BAACgfxYAAQAAoX8WHgEAAKJ/FwABAACjfxceAQAA"
    ),
    "irrigation_control": (
        "gD4HAAMAAIF/CgADAACCfwsAAwAAg38MAAMAAIR/DQADAACFfw4AAwAAhn8PAAMAAId/"
        "EAADAACIfxEAAwAAiX8SAAMAAIp/EwADAACLPgcKAwABjH8KCgMAAY1/CwoDAAGOPgwK"
        "BAABj38NCgMAAZA+DgoEAAGRPhAKBAABkn8SCgMAAZM+EwoEAAGUPgcUBAAClT4KFAQA"
        "ApY+DBQEAAKXPg4UBAACmD4QFAQAApk+ExQEAAKaPgceBAADmz4KHgQAA5w+DB4EAAOd"
        "Pg4eBAADnj4QHgQAA58+Ex4EAAOgPggAHgAEoT4UAB4ABKI+CAAeAAWjPhQAHgAF"
    ),
}


def test_schedule_entry_from_bytes():
    weekdays = Gen1Weekday.MONDAY | Gen1Weekday.WEDNESDAY | Gen1Weekday.FRIDAY
    data = bytes([1, weekdays, 6, 30, 45, 0, 0])
    entry = ScheduleEntry.from_bytes(data)
    assert entry == ScheduleEntry(
        schedule_id=1,
        weekdays=Gen1Weekday.MONDAY | Gen1Weekday.WEDNESDAY | Gen1Weekday.FRIDAY,
        start_hour=6,
        start_minute=30,
        duration_minutes=45,
        action=0,
    )


def test_schedule_entry_from_bytes_wrong_size():
    with pytest.raises(ValueError, match="7 bytes"):
        ScheduleEntry.from_bytes(bytes(6))


def test_parse_schedule_config_multiple_entries():
    entry_one = bytes([0, Gen1Weekday.SUNDAY, 8, 0, 30, 0, 0])
    entry_two = bytes([1, Gen1Weekday.SATURDAY, 18, 15, 15, 0, 1])
    entries = parse_gen1_schedule_config(entry_one + entry_two)
    assert entries == [
        ScheduleEntry(0, Gen1Weekday.SUNDAY, 8, 0, 30, 0),
        ScheduleEntry(1, Gen1Weekday.SATURDAY, 18, 15, 15, action=1),
    ]


def test_parse_schedule_config_empty():
    assert parse_gen1_schedule_config(b"") == []


def test_parse_schedule_config_invalid_length():
    with pytest.raises(ValueError, match="multiple of 7"):
        parse_gen1_schedule_config(bytes(8))


def test_parse_schedule_config_real_gateway_payload():
    config = base64.b64decode(SCHEDULE_CONFIG_B64)
    entries = parse_gen1_schedule_config(config)
    assert entries == [
        ScheduleEntry(5, Gen1Weekday(0x7F), 6, 50, 30, action=4),
        ScheduleEntry(2, Gen1Weekday(0x7F), 4, 10, 5, action=4),
        ScheduleEntry(4, Gen1Weekday(0x7F), 6, 25, 25, action=1),
        ScheduleEntry(3, Gen1Weekday(0x7F), 6, 0, 25, action=0),
        ScheduleEntry(0, Gen1Weekday(0x7F), 4, 0, 5, action=0),
        ScheduleEntry(1, Gen1Weekday(0x7F), 4, 5, 5, action=1),
    ]


def test_schedule_config_to_base64_round_trip():
    entries = parse_gen1_schedule_config(base64.b64decode(SCHEDULE_CONFIG_B64))
    assert gen1_schedule_config_to_base64(entries) == SCHEDULE_CONFIG_B64


@pytest.mark.parametrize("device", sorted(SCHEDULE_CONFIG_B64_BY_DEVICE))
def test_schedule_config_to_base64_round_trip_real_devices(device):
    config_b64 = SCHEDULE_CONFIG_B64_BY_DEVICE[device]
    entries = parse_gen1_schedule_config(base64.b64decode(config_b64))
    assert gen1_schedule_config_to_base64(entries) == config_b64


def test_sun_schedule_entry_from_bytes_wrong_size():
    with pytest.raises(ValueError, match="7 bytes"):
        SunScheduleEntry.from_bytes(bytes(6))


def test_parse_sun_schedule_config_invalid_length():
    with pytest.raises(ValueError, match="multiple of 7"):
        parse_gen1_sun_schedule_config(bytes(8))


def test_parse_sun_schedule_config_real_gateway_payload():
    config = base64.b64decode(SUN_SCHEDULE_CONFIG_B64)
    entries = parse_gen1_sun_schedule_config(config)
    assert entries == [
        SunScheduleEntry(
            start=TimeOffset(Gen1OffsetPoint.MIDNIGHT, 998),
            stop=TimeOffset(Gen1OffsetPoint.MIDNIGHT, 1418),
            weekdays=Gen1Weekday(0x7F),
            cycle=Gen1ScheduleCycle.CYCLE_14D,
            action_id=0,
            flag=False,
        ),
        SunScheduleEntry(
            start=TimeOffset(Gen1OffsetPoint.MIDNIGHT, 410),
            stop=TimeOffset(Gen1OffsetPoint.MIDNIGHT, 474),
            weekdays=Gen1Weekday(0x7F),
            cycle=Gen1ScheduleCycle.CYCLE_14D,
            action_id=0,
            flag=False,
        ),
        SunScheduleEntry(
            start=TimeOffset(Gen1OffsetPoint.MIDNIGHT, 295),
            stop=TimeOffset(Gen1OffsetPoint.MIDNIGHT, 359),
            weekdays=Gen1Weekday(0x7F),
            cycle=Gen1ScheduleCycle.CYCLE_14D,
            action_id=0,
            flag=False,
        ),
        SunScheduleEntry(
            start=TimeOffset(Gen1OffsetPoint.MIDNIGHT, 240),
            stop=TimeOffset(Gen1OffsetPoint.MIDNIGHT, 254),
            weekdays=Gen1Weekday(0x7F),
            cycle=Gen1ScheduleCycle.CYCLE_14D,
            action_id=0,
            flag=False,
        ),
        SunScheduleEntry(
            start=TimeOffset(Gen1OffsetPoint.MIDNIGHT, 530),
            stop=TimeOffset(Gen1OffsetPoint.MIDNIGHT, 574),
            weekdays=Gen1Weekday(0x7F),
            cycle=Gen1ScheduleCycle.CYCLE_14D,
            action_id=0,
            flag=False,
        ),
    ]


def test_sun_schedule_config_to_base64_round_trip():
    entries = parse_gen1_sun_schedule_config(base64.b64decode(SUN_SCHEDULE_CONFIG_B64))
    assert gen1_sun_schedule_config_to_base64(entries) == SUN_SCHEDULE_CONFIG_B64
