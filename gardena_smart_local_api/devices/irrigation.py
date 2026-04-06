from ..messages import EgressMessageList
from ..resources import IpsoPath
from .gen1 import Gen1BatteryPoweredDevice, IdentifyMixin
from .gen2 import Gen2BatteryMixin, Gen2Device

# Used to indicate that the action was initiated through WebSocket API.
COMMAND_SOURCE = "18"


class Gen1WaterControl(IdentifyMixin, Gen1BatteryPoweredDevice):
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


class _Gen2Irrigation(Gen2Device):
    @property
    def valve_count(self) -> int:
        return len(self.valve_ids)

    @property
    def valve_ids(self) -> list[int]:
        return list(map(int, self.get_object_instance_ids("actuator")))

    def build_open_valve_obj(
        self, valve_id: int, duration_seconds: int
    ) -> EgressMessageList:
        return self.build_execute_obj(
            IpsoPath(
                object_name="actuator",
                object_instance_id=str(valve_id),
                resource_name="start",
            ),
            [COMMAND_SOURCE, str(duration_seconds)],
        )

    def build_close_valve_obj(self, valve_id: int) -> EgressMessageList:
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


class Gen2WaterControl(_Gen2Irrigation, Gen2BatteryMixin):
    pass


class Gen2IrrigationControl(_Gen2Irrigation):
    pass
