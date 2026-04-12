from abc import ABC, abstractmethod
from enum import Enum

from ..messages import EgressMessageList
from ..resources import IpsoPath
from .gen1 import Gen1BatteryMixin, Gen1Device, Gen1FrostWarningMixin, Gen1IdentifyMixin
from .gen2 import Gen2BatteryMixin, Gen2Device

# Used to indicate that the action was initiated through WebSocket API.
COMMAND_SOURCE = "18"

# Default to 30 minutes for safety
DEFAULT_WATERING_DURATION = 1800


class TimeslotState(Enum):
    IDLE = 0
    SCHEDULED = 1
    WILL_START = 2
    SKIPPED = 3
    UNUSED = 4
    RUNNING = 5
    STOPPED = 6
    ERROR = 7
    OVERWRITTEN = 8
    DONE = 9
    DELETED = 10
    REQUESTED = 11

    def __str__(self):
        return self.name.lower()


class _Gen1Irrigation(Gen1Device, ABC):
    @property
    @abstractmethod
    def valve_count(self) -> int: ...

    @property
    @abstractmethod
    def valve_ids(self) -> list[int]: ...

    def _build_set_watering_timer_obj(
        self, valve_id: int, seconds: int
    ) -> EgressMessageList:
        return self.build_write_value_obj(
            IpsoPath(
                object_name="lemonbeat",
                object_instance_id="0",
                resource_name=f"watering_timer_{valve_id + 1}",
            ),
            seconds,
        )

    def get_watering_timer(self, valve_id: int) -> int | None:
        value = self.get_value(
            IpsoPath(
                object_name="lemonbeat",
                object_instance_id="0",
                resource_name=f"watering_timer_{valve_id + 1}",
            )
        )
        if isinstance(value, int):
            return value
        return None

    def is_valve_open(self, valve_id: int = 0) -> bool | None:
        if valve_id not in self.valve_ids:
            raise ValueError(f"Invalid valve ID {valve_id}")
        value = self.get_watering_timer(valve_id)
        if value is not None:
            return value > 0
        return None

    def build_open_valve_obj(
        self, valve_id: int = 0, duration_seconds: int = DEFAULT_WATERING_DURATION
    ) -> EgressMessageList:
        if valve_id not in self.valve_ids:
            raise ValueError(f"Invalid valve ID {valve_id}")
        return self._build_set_watering_timer_obj(valve_id, duration_seconds)

    def build_close_valve_obj(self, valve_id: int = 0) -> EgressMessageList:
        if valve_id not in self.valve_ids:
            raise ValueError(f"Invalid valve ID {valve_id}")
        return self._build_set_watering_timer_obj(valve_id, 0)

    @abstractmethod
    def build_close_all_valves_obj(self) -> EgressMessageList: ...


class Gen1WaterControl(
    Gen1BatteryMixin, Gen1IdentifyMixin, Gen1FrostWarningMixin, _Gen1Irrigation
):
    @property
    def valve_count(self) -> int:
        return 1

    @property
    def valve_ids(self) -> list[int]:
        return [0]

    @property
    def button_config_time(self) -> int | None:
        value = self.get_value(
            IpsoPath(
                object_name="lemonbeat",
                object_instance_id="0",
                resource_name="button_config_time",
            )
        )
        if isinstance(value, int):
            return value
        return None

    @property
    def temperature(self) -> int | None:
        value = self.get_value(
            IpsoPath(
                object_name="lemonbeat",
                object_instance_id="0",
                resource_name="ambient_temperature",
            )
        )
        if isinstance(value, int):
            return value
        return None

    def build_close_all_valves_obj(self) -> EgressMessageList:
        return self.build_close_valve_obj()

    def build_read_button_config_time_obj(self) -> EgressMessageList:
        return self.build_read_value_obj(
            IpsoPath(
                object_name="lemonbeat",
                object_instance_id="0",
                resource_name="button_config_time",
            )
        )

    def build_set_button_config_time_obj(self, seconds: int) -> EgressMessageList:
        return self.build_write_value_obj(
            IpsoPath(
                object_name="lemonbeat",
                object_instance_id="0",
                resource_name="button_config_time",
            ),
            seconds,
        )


class Gen1IrrigationControl(Gen1IdentifyMixin, _Gen1Irrigation):
    @property
    def valve_count(self) -> int:
        return 6

    @property
    def valve_ids(self) -> list[int]:
        return list(range(6))

    def build_close_valve_obj(self, valve_id: int = 0) -> EgressMessageList:
        return self._build_set_watering_timer_obj(valve_id, 0)

    def build_close_all_valves_obj(self) -> EgressMessageList:
        return self.build_command_obj(self.get_command("close_all_valves"))


class _Gen2Irrigation(Gen2Device):
    @property
    def valve_count(self) -> int:
        return len(self.valve_ids)

    @property
    def valve_ids(self) -> list[int]:
        return list(map(int, self.get_object_instance_ids("actuator")))

    def build_open_valve_obj(
        self, valve_id: int = 0, duration_seconds: int = DEFAULT_WATERING_DURATION
    ) -> EgressMessageList:
        if valve_id not in self.valve_ids:
            raise ValueError(f"Invalid valve ID {valve_id}")
        return self.build_execute_obj(
            IpsoPath(
                object_name="actuator",
                object_instance_id=str(valve_id),
                resource_name="start",
            ),
            [COMMAND_SOURCE, str(duration_seconds)],
        )

    def build_close_valve_obj(self, valve_id: int = 0) -> EgressMessageList:
        if valve_id not in self.valve_ids:
            raise ValueError(f"Invalid valve ID {valve_id}")
        return self.build_execute_obj(
            IpsoPath(
                object_name="actuator",
                object_instance_id=str(valve_id),
                resource_name="stop",
            ),
            [COMMAND_SOURCE],
        )

    def build_close_all_valves_obj(self) -> EgressMessageList:
        return self.build_execute_obj(
            IpsoPath(
                object_name="sg_common",
                object_instance_id="0",
                resource_name="stop_all_actuators",
            ),
            [COMMAND_SOURCE],
        )

    def is_valve_open(self, valve_id: int = 0) -> bool | None:
        if valve_id not in self.valve_ids:
            raise ValueError(f"Invalid valve ID {valve_id}")
        return self.get_timeslot_state(valve_id) == TimeslotState.RUNNING

    def get_timeslot_state(self, timeslot_id: int) -> TimeslotState | None:
        value = self.get_value(
            IpsoPath(
                object_name="timeslot",
                object_instance_id=str(timeslot_id),
                resource_name="state",
            )
        )
        if isinstance(value, int):
            try:
                return TimeslotState(value)
            except ValueError:
                pass
        return None


class Gen2WaterControl(_Gen2Irrigation, Gen2BatteryMixin):
    pass


class Gen2IrrigationControl(_Gen2Irrigation):
    pass
