from ..messages import EgressMessageList
from ..resources import IpsoPath
from .gen1 import Gen1BatteryPoweredGen1Device


class Gen1WaterControl(Gen1BatteryPoweredGen1Device):
    def build_set_watering_timer_obj(self, seconds: int) -> EgressMessageList:
        """Set the watering timer.

        Args:
            seconds: Duration of watering in seconds.

        Returns:
            EgressMessageList ready to be sent to the local GARDENA smart API.

        Example:
            >>> Gen1WaterControl(...).build_set_watering_timer_obj(3600)
            EgressMessageList([
                Request(
                    request_id="2a8166c5-d60f-4ddd-8735-29aa3661a128",
                    op="write",
                    entity=Entity(
                        device="device_id",
                        path=IpsoPath(
                            object_name="lemonbeat",
                            object_instance_id="0",
                            resource_name="watering_timer_1"
                        ),
                        service="lemonbeatd"
                    ),
                    payload={"vi": 3600}
                )
            ])
        """
        return self.build_write_value_obj(
            IpsoPath(
                object_name="lemonbeat",
                object_instance_id="0",
                resource_name="watering_timer_1",
            ),
            seconds,
        )

    def build_stop_watering_obj(self) -> EgressMessageList:
        return self.build_set_watering_timer_obj(0)

    @property
    def watering_timer(self) -> int | None:
        value = self.get_value(
            IpsoPath(
                object_name="lemonbeat",
                object_instance_id="0",
                resource_name="watering_timer_1",
            )
        )
        if isinstance(value, int):
            return value
        return None

    @property
    def is_opened(self) -> bool | None:
        value = self.watering_timer
        if value is not None:
            return value > 0
        return None

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

    @property
    def has_frost_warning(self) -> bool | None:
        value = self.get_value(
            IpsoPath(
                object_name="lemonbeat",
                object_instance_id="0",
                resource_name="frost_warning",
            )
        )
        if isinstance(value, int):
            return bool(value)
        return None

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
