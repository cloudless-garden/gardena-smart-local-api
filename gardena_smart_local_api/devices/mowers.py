from ..messages import EgressMessageList
from ..resources import IpsoPath
from .gen1 import Gen1BatteryPoweredDevice


class Gen1Mower(Gen1BatteryPoweredDevice):
    """
    For now, only mowers with model number 53988 are supported
    """

    def build_start_mowing_obj(
        self, meters_from_cs: int, seconds: int
    ) -> EgressMessageList:
        """Start mowing from given starting point, for given duration.

        Args:
            meters_from_cs: Distance from the charging station in meters
                            (0: default starting point).
            seconds: Duration in seconds (0: park until next schedule).

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
