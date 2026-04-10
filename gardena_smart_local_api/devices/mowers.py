from enum import Enum

from ..messages import EgressMessageList
from ..resources import IpsoPath
from .gen1 import Gen1BatteryMixin, Gen1Device


class Gen1MowerStatus(Enum):
    """Status of a gen1 robotic lawn mower."""

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

    def __str__(self):
        return self.name.lower()


class _Gen1Mower(Gen1Device, Gen1BatteryMixin):
    """Robotic lawn mower base class"""

    @property
    def status(self) -> Gen1MowerStatus | None:
        value = self.get_value(
            IpsoPath(
                object_name="lemonbeat",
                object_instance_id="0",
                resource_name="status",
            )
        )
        if isinstance(value, int):
            try:
                return Gen1MowerStatus(value)
            except ValueError:
                pass
        return None

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
    """GARDENA smart SILENO (19060-20), SILENO+ (19061-20),
    SILENO city (19066-20) and SILENO life (19113-20)."""

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
    """GARDENA smart SILENO city (19602-66) and SILENO life (19701-60) with LONA."""

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
