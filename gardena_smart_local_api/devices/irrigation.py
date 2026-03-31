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


class ValveError(Enum):
    NONE = 0
    PUMP_NOT_FILLED = 1
    CLEAN_GASKET = 2
    CLEAN_FINE_MESH = 3
    SMALL_LEAKAGE = 4

    def __str__(self):
        return self.name.lower()


class OperatingMode(Enum):
    SCHEDULED = 0
    AUTOMATIC = 1

    def __str__(self):
        return self.name.lower()


class PumpState(Enum):
    PUMP_IS_JUST_STARTING = 0
    WATER_IN_THE_PUMP_BODY = 1
    NO_WATER_IN_THE_PUMP_BODY = 2
    FLOW_AFTER_5S = 3
    NO_FLOW_AFTER_5S = 4

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


class Pump(Gen1IdentifyMixin, Gen1FrostWarningMixin, _Gen1Irrigation):
    @property
    def valve_count(self) -> int:
        return 1

    @property
    def valve_ids(self) -> list[int]:
        return [0]

    def build_close_all_valves_obj(self) -> EgressMessageList:
        return self.build_close_valve_obj(valve_id=0)

    @property
    def pump_mode(self) -> int | None:
        value = self.get_value(
            IpsoPath(
                object_name="lemonbeat",
                object_instance_id="0",
                resource_name="pump_mode",
            )
        )
        if isinstance(value, int):
            return value
        return None

    @property
    def pump_state(self) -> PumpState | None:
        value = self.get_value(
            IpsoPath(
                object_name="lemonbeat",
                object_instance_id="0",
                resource_name="pump_state",
            )
        )
        if isinstance(value, int):
            try:
                return PumpState(value)
            except ValueError:
                pass
        return None

    @property
    def is_running(self) -> bool | None:
        value = self.get_value(
            IpsoPath(
                object_name="lemonbeat",
                object_instance_id="0",
                resource_name="pump_on_off",
            )
        )
        if isinstance(value, int):
            return value != 0
        return None

    @property
    def outlet_pressure(self) -> float | None:
        value = self.get_value(
            IpsoPath(
                object_name="lemonbeat",
                object_instance_id="0",
                resource_name="outlet_pressure",
            )
        )
        if isinstance(value, (int, float)):
            return float(value)
        return None

    @property
    def outlet_pressure_max(self) -> float | None:
        value = self.get_value(
            IpsoPath(
                object_name="lemonbeat",
                object_instance_id="0",
                resource_name="outlet_pressure_max",
            )
        )
        if isinstance(value, (int, float)):
            return float(value)
        return None

    @property
    def outlet_temperature(self) -> int | None:
        value = self.get_value(
            IpsoPath(
                object_name="lemonbeat",
                object_instance_id="0",
                resource_name="outlet_temperature",
            )
        )
        if isinstance(value, int):
            return value
        return None

    @property
    def outlet_temperature_max(self) -> int | None:
        value = self.get_value(
            IpsoPath(
                object_name="lemonbeat",
                object_instance_id="0",
                resource_name="outlet_temperature_max",
            )
        )
        if isinstance(value, int):
            return value
        return None

    @property
    def outlet_temperature_min(self) -> int | None:
        value = self.get_value(
            IpsoPath(
                object_name="lemonbeat",
                object_instance_id="0",
                resource_name="outlet_temperature_min",
            )
        )
        if isinstance(value, int):
            return value
        return None

    @property
    def flow_rate(self) -> int | None:
        value = self.get_value(
            IpsoPath(
                object_name="lemonbeat",
                object_instance_id="0",
                resource_name="flow_rate",
            )
        )
        if isinstance(value, int):
            return value
        return None

    @property
    def flow_total(self) -> int | None:
        value = self.get_value(
            IpsoPath(
                object_name="lemonbeat",
                object_instance_id="0",
                resource_name="flow_total",
            )
        )
        if isinstance(value, int):
            return value
        return None

    @property
    def flow_since_last_reset(self) -> int | None:
        value = self.get_value(
            IpsoPath(
                object_name="lemonbeat",
                object_instance_id="0",
                resource_name="flow_since_last_reset",
            )
        )
        if isinstance(value, int):
            return value
        return None

    @property
    def operating_mode(self) -> OperatingMode | None:
        value = self.get_value(
            IpsoPath(
                object_name="lemonbeat",
                object_instance_id="0",
                resource_name="operating_mode",
            )
        )
        if isinstance(value, int):
            try:
                return OperatingMode(value)
            except ValueError:
                pass
        return None

    @property
    def turn_on_pressure(self) -> float | None:
        value = self.get_value(
            IpsoPath(
                object_name="lemonbeat",
                object_instance_id="0",
                resource_name="turn_on_pressure",
            )
        )
        if isinstance(value, (int, float)):
            return float(value)
        return None

    @property
    def dripping_alert(self) -> int | None:
        value = self.get_value(
            IpsoPath(
                object_name="lemonbeat",
                object_instance_id="0",
                resource_name="dripping_alert",
            )
        )
        if isinstance(value, int):
            return value
        return None

    @property
    def valve_error(self) -> ValveError | None:
        value = self.get_value(
            IpsoPath(
                object_name="lemonbeat",
                object_instance_id="0",
                resource_name="valve_error_1",
            )
        )
        if isinstance(value, int):
            try:
                return ValveError(value)
            except ValueError:
                pass
        return None

    def build_set_operating_mode_obj(self, mode: OperatingMode) -> EgressMessageList:
        return self.build_write_value_obj(
            IpsoPath(
                object_name="lemonbeat",
                object_instance_id="0",
                resource_name="operating_mode",
            ),
            mode.value,
        )

    def build_set_turn_on_pressure_obj(self, pressure: float) -> EgressMessageList:
        return self.build_write_value_obj(
            IpsoPath(
                object_name="lemonbeat",
                object_instance_id="0",
                resource_name="turn_on_pressure",
            ),
            pressure,
        )

    def build_set_dripping_alert_obj(self, timeout: int) -> EgressMessageList:
        return self.build_write_value_obj(
            IpsoPath(
                object_name="lemonbeat",
                object_instance_id="0",
                resource_name="dripping_alert",
            ),
            timeout,
        )

    def build_reset_flow_resettable_obj(self) -> EgressMessageList:
        return self.build_command_obj(self.get_command("reset_flow_resettable"))

    def build_reset_all_valve_errors_obj(self) -> EgressMessageList:
        return self.build_command_obj(self.get_command("reset_all_valve_errors"))

    def build_reset_outlet_temperature_min_max_obj(self) -> EgressMessageList:
        return self.build_command_obj(
            self.get_command("reset_outlet_temperature_min_max")
        )
