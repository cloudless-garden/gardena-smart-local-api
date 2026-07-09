# SPDX-FileCopyrightText: 2026 GARDENA GmbH
#
# SPDX-License-Identifier: LGPL-3.0-or-later

"""Parse and build the raw byte blobs Gen1 devices use for schedules.

Gen1 gateways expose schedules as opaque, base64-encoded byte blobs,
in one of two formats:

- `schedule_config`: fixed weekday + time-of-day + duration entries.
  Used by :class:`~gardena_smart_local_api.devices.Gen1WaterControl`,
  :class:`~gardena_smart_local_api.devices.Gen1IrrigationControl`, and
  :class:`~gardena_smart_local_api.devices.Pump`.
- `sun_schedule_config`: entries relative to sunrise/sunset.
  Used by :class:`~gardena_smart_local_api.devices.PowerAdapter`.

Gen2 devices (`Gen2WaterControl`, `Gen2IrrigationControl`, `Gen2Mower`, ...)
no longer use these lemonbeat paths and have a different schedule format
that this module does not (yet) support.
"""

from dataclasses import dataclass
from enum import IntEnum, IntFlag

SCHEDULE_ENTRY_SIZE = 7
SUN_SCHEDULE_ENTRY_SIZE = 7

# Bit position (0-6) -> weekday, as used in the sun_schedule_config recurrence field.
_RECURRENCE_DAY_ORDER = [
    "MONDAY",
    "TUESDAY",
    "WEDNESDAY",
    "THURSDAY",
    "FRIDAY",
    "SATURDAY",
    "SUNDAY",
]


class Weekday(IntFlag):
    SUNDAY = 0x01
    MONDAY = 0x02
    TUESDAY = 0x04
    WEDNESDAY = 0x08
    THURSDAY = 0x10
    FRIDAY = 0x20
    SATURDAY = 0x40


class OffsetPoint(IntEnum):
    MIDNIGHT = 0
    SUNRISE = 1
    SUNSET = 2


class ScheduleCycle(IntEnum):
    CYCLE_12D = 0
    CYCLE_14D = 1
    CYCLE_15D = 2


@dataclass
class ScheduleEntry:
    schedule_id: int
    weekdays: Weekday
    start_hour: int
    start_minute: int
    duration_minutes: int
    action: int

    @classmethod
    def from_bytes(cls, data: bytes) -> "ScheduleEntry":
        if len(data) != SCHEDULE_ENTRY_SIZE:
            raise ValueError(f"Schedule entry must be {SCHEDULE_ENTRY_SIZE} bytes")
        return cls(
            schedule_id=data[0],
            weekdays=Weekday(data[1]),
            start_hour=data[2],
            start_minute=data[3],
            duration_minutes=int.from_bytes(data[4:6], byteorder="little"),
            action=data[6],
        )


def parse_gen1_schedule_config(config: bytes) -> list[ScheduleEntry]:
    """Parse a Gen1 `schedule_config` byte blob into individual schedule entries."""
    if len(config) % SCHEDULE_ENTRY_SIZE != 0:
        raise ValueError(
            f"Schedule config length must be a multiple of {SCHEDULE_ENTRY_SIZE}"
        )
    return [
        ScheduleEntry.from_bytes(config[i : i + SCHEDULE_ENTRY_SIZE])
        for i in range(0, len(config), SCHEDULE_ENTRY_SIZE)
    ]


@dataclass
class TimeOffset:
    point: OffsetPoint
    minutes: int

    @classmethod
    def from_bytes(cls, data: bytes) -> "TimeOffset":
        raw = int.from_bytes(data, byteorder="little")
        return cls(point=OffsetPoint(raw & 0b11), minutes=raw >> 4)


@dataclass
class SunScheduleEntry:
    start: TimeOffset
    stop: TimeOffset
    weekdays: Weekday
    cycle: ScheduleCycle
    action_id: int
    flag: bool

    @classmethod
    def from_bytes(cls, data: bytes) -> "SunScheduleEntry":
        if len(data) != SUN_SCHEDULE_ENTRY_SIZE:
            raise ValueError(
                f"Sun schedule entry must be {SUN_SCHEDULE_ENTRY_SIZE} bytes"
            )
        mid = data[4]
        recurrence = int.from_bytes(data[5:7], byteorder="little")
        weekdays = Weekday(0)
        for bit, name in enumerate(_RECURRENCE_DAY_ORDER):
            if recurrence & (1 << bit) and recurrence & (1 << (bit + 7)):
                weekdays |= Weekday[name]
        return cls(
            start=TimeOffset.from_bytes(data[0:2]),
            stop=TimeOffset.from_bytes(data[2:4]),
            weekdays=weekdays,
            cycle=ScheduleCycle(mid & 0x0F),
            action_id=(mid & 0x70) >> 4,
            flag=bool(mid & 0x80),
        )


def parse_gen1_sun_schedule_config(config: bytes) -> list[SunScheduleEntry]:
    """Parse a Gen1 `sun_schedule_config` byte blob into individual schedule entries."""
    if len(config) % SUN_SCHEDULE_ENTRY_SIZE != 0:
        raise ValueError(
            f"Sun schedule config length must be a "
            f"multiple of {SUN_SCHEDULE_ENTRY_SIZE}"
        )
    return [
        SunScheduleEntry.from_bytes(config[i : i + SUN_SCHEDULE_ENTRY_SIZE])
        for i in range(0, len(config), SUN_SCHEDULE_ENTRY_SIZE)
    ]
