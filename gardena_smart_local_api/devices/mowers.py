from ..messages import EgressMessageList
from ..resources import IpsoPath
from ._enums import _LowerNameEnum
from .gen1 import Gen1BatteryMixin, Gen1Device
from .gen2 import Gen2BatteryMixin, Gen2Device


class MowerState(_LowerNameEnum):
    UNKNOWN = 0
    PARKED = 1
    LEAVING = 2
    MOWING = 3
    PAUSED = 4
    RETURNING = 5
    CHARGING = 6
    ERROR = 7


class _Gen1MowerStatus(_LowerNameEnum):
    PAUSED = 0
    OK_CUTTING_AUTO = 1
    OK_SEARCHING_CS = 2
    OK_CHARGING = 3
    OK_LEAVING_CS = 4
    WAIT_SOFTWARE_DOWNLOAD = 5
    WAIT_POWER_UP = 6
    PARKED_WEEK_TIMER = 7
    PARKED_BY_USER = 8
    OFF_MAIN_SWITCH = 9
    WAIT_STOP_PRESSED = 10
    UNKNOWN = 11
    ERROR = 12
    ERROR_POWER_UP = 13
    WAIT = 14
    OK_CUTTING_MANUAL = 15
    PARKED_AUTOTIMER = 16
    PARKED_DAY_LIMIT = 17
    PARKED_FROST = 18


class _Gen2MowerState(_LowerNameEnum):
    OFF = 0
    WAIT_FOR_SAFETYPIN = 1
    STOPPED = 2
    FATAL_ERROR = 3
    PENDING_START = 4
    PAUSED = 5
    IN_OPERATION = 6
    RESTRICTED = 7
    ERROR = 8


class _Gen2MowerActivity(_LowerNameEnum):
    NONE = 0
    CHARGING = 1
    GOING_OUT = 2
    MOWING = 3
    GOING_HOME = 4
    PARKED = 5
    STOPPED_IN_GARDEN = 6


class _Gen1Mower(Gen1BatteryMixin, Gen1Device):
    """Robotic lawn mower base class"""

    @property
    def _status(self) -> _Gen1MowerStatus | None:
        value = self.get_value(
            IpsoPath(
                object_name="lemonbeat",
                object_instance_id="0",
                resource_name="status",
            )
        )
        if isinstance(value, int):
            try:
                return _Gen1MowerStatus(value)
            except ValueError:
                pass
        return None

    @property
    def state(self) -> MowerState:
        match self._status:
            case (
                _Gen1MowerStatus.PAUSED
                | _Gen1MowerStatus.PARKED_WEEK_TIMER
                | _Gen1MowerStatus.PARKED_BY_USER
                | _Gen1MowerStatus.PARKED_AUTOTIMER
                | _Gen1MowerStatus.PARKED_DAY_LIMIT
                | _Gen1MowerStatus.PARKED_FROST
                | _Gen1MowerStatus.WAIT_POWER_UP
                | _Gen1MowerStatus.OFF_MAIN_SWITCH
                | _Gen1MowerStatus.WAIT
            ):
                return MowerState.PARKED
            case _Gen1MowerStatus.OK_LEAVING_CS:
                return MowerState.LEAVING
            case _Gen1MowerStatus.OK_CUTTING_AUTO | _Gen1MowerStatus.OK_CUTTING_MANUAL:
                return MowerState.MOWING
            case _Gen1MowerStatus.OK_SEARCHING_CS:
                return MowerState.RETURNING
            case _Gen1MowerStatus.OK_CHARGING:
                return MowerState.CHARGING
            case _Gen1MowerStatus.ERROR | _Gen1MowerStatus.ERROR_POWER_UP:
                return MowerState.ERROR
        return MowerState.UNKNOWN

    def build_stop_mowing_obj(self) -> EgressMessageList:
        """Park until further notice.

        Returns:
            EgressMessageList ready to be sent to the local GARDENA smart API.
        """
        # A date far in the future (2042-12-31 22:00 > now + 65535 minutes)
        data = (2042).to_bytes(2, "little") + bytes([12, 31, 22, 0])

        return self.build_write_value_obj(
            IpsoPath(
                object_name="lemonbeat",
                object_instance_id="0",
                resource_name="action_paused_until_1",
            ),
            data,
        )


class Gen1Mower1(_Gen1Mower):
    """Robotic lawn mower"""

    def build_start_mowing_obj(self, seconds: int) -> EgressMessageList:
        """Start mowing for given duration.

        Args:
            seconds: Duration in seconds (0: park until next schedule).

        Returns:
            EgressMessageList ready to be sent to the local GARDENA smart API.
        """
        return self.build_write_value_obj(
            IpsoPath(
                object_name="lemonbeat",
                object_instance_id="0",
                resource_name="mower_timer",
            ),
            seconds,
        )


class Gen1Mower2(_Gen1Mower):
    """Robotic lawn mower with LONA"""

    def build_start_mowing_obj(
        self, seconds: int, meters_from_cs: int = 0
    ) -> EgressMessageList:
        """Start mowing from given starting point, for given duration.

        Args:
            seconds: Duration in seconds (0: park until next schedule).
            meters_from_cs: Distance from the charging station in meters
                            (0: default starting point).

        Returns:
            EgressMessageList ready to be sent to the local GARDENA smart API.
        """
        data = meters_from_cs.to_bytes(2, "big") + seconds.to_bytes(4, "big")

        return self.build_write_value_obj(
            IpsoPath(
                object_name="lemonbeat",
                object_instance_id="0",
                resource_name="mower_timer_with_distance",
            ),
            data,
        )


class Gen2Mower(Gen2BatteryMixin, Gen2Device):
    @property
    def _activity(self) -> _Gen2MowerActivity | None:
        value = self.get_value(
            IpsoPath(
                object_name="mower_app",
                object_instance_id="0",
                resource_name="activity",
            )
        )
        if isinstance(value, int):
            try:
                return _Gen2MowerActivity(value)
            except ValueError:
                pass
        return None

    @property
    def _state(self) -> _Gen2MowerState | None:
        value = self.get_value(
            IpsoPath(
                object_name="mower_app",
                object_instance_id="0",
                resource_name="state",
            )
        )
        if isinstance(value, int):
            try:
                return _Gen2MowerState(value)
            except ValueError:
                pass
        return None

    @property
    def state(self) -> MowerState:
        match self._activity:
            case _Gen2MowerActivity.PARKED:
                return MowerState.PARKED
            case _Gen2MowerActivity.GOING_OUT:
                return MowerState.LEAVING
            case _Gen2MowerActivity.MOWING:
                return MowerState.MOWING
            case _Gen2MowerActivity.GOING_HOME:
                return MowerState.RETURNING
            case _Gen2MowerActivity.CHARGING:
                return MowerState.CHARGING
            case _Gen2MowerActivity.NONE:
                match self._state:
                    case _Gen2MowerState.PAUSED:
                        return MowerState.PAUSED
                    case _Gen2MowerState.ERROR | _Gen2MowerState.FATAL_ERROR:
                        return MowerState.ERROR
        return MowerState.UNKNOWN

    def build_start_mowing_obj(
        self, seconds: int, zone: int | None = None
    ) -> EgressMessageList:
        """Start mowing for given duration.

        Args:
            seconds: Duration in seconds (0: park until next schedule).
            zone: An optional ID of the zone to mow in.

        Returns:
            EgressMessageList ready to be sent to the local GARDENA smart API.
        """
        resource_name = "manual_start"
        data = [str(seconds)]
        if zone is not None:
            resource_name = "manual_start_in_zone"
            data.append(str(zone))

        return self.build_execute_obj(
            IpsoPath(
                object_name="smart_system_mower_api",
                object_instance_id="0",
                resource_name=resource_name,
            ),
            data,
        )

    def build_stop_mowing_obj(self) -> EgressMessageList:
        """Park until further notice.

        Returns:
            EgressMessageList ready to be sent to the local GARDENA smart API.
        """
        return self.build_execute_obj(
            IpsoPath(
                object_name="smart_system_mower_api",
                object_instance_id="0",
                resource_name="park_until_further_notice",
            ),
            None,
        )

    def build_pause_mowing_obj(self) -> EgressMessageList:
        """Pause at current position.

        Returns:
            EgressMessageList ready to be sent to the local GARDENA smart API.
        """
        return self.build_execute_obj(
            IpsoPath(
                object_name="mower_app",
                object_instance_id="0",
                resource_name="pause",
            ),
            None,
        )
