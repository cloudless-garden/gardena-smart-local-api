from typing import ClassVar

from pydantic import Field

from ..messages import EgressMessageList, Entity, Request
from ..model_loader import Gen1ModelDefinition
from ..resources import IpsoPath
from .device import Device


class Gen1Device(Device):
    model_definition: Gen1ModelDefinition = Field()
    service: ClassVar[str] = "lemonbeatd"

    def get_command(self, name: str) -> int:
        return self.model_definition.commands[name]

    def build_command_obj(self, command: int) -> EgressMessageList:
        """Build a Gen1 command JSON structure.

        Args:
            command: Command code as int.

        Returns:
            EgressMessageList ready to be sent to the local GARDENA smart API.

        Example:
            >>> build_command_obj(3)
            EgressMessageList([
                Request(
                    op="write",
                    entity=Entity(
                        device="device_id",
                        path="lemonbeat/0/command",
                        service="lemonbeatd"
                    ),
                    payload={"vi": 3}
                )
            ])
        """
        request = Request(
            op="write",
            entity=Entity(
                device=self.id,
                path=IpsoPath(
                    object_name="lemonbeat",
                    object_instance_id="0",
                    resource_name="command",
                ),
                service=self.service,
            ),
            payload={"vi": command},
        )
        return EgressMessageList([request])

    @property
    def is_online(self) -> bool | None:
        value = self.get_value(
            IpsoPath(
                object_name="connection_status",
                object_instance_id="0",
                resource_name="online",
            )
        )
        if isinstance(value, bool):
            return value
        return None

    def build_reload_online_status_obj(self) -> EgressMessageList:
        return self.build_read_value_obj(
            IpsoPath(
                object_name="connection_status",
                object_instance_id="0",
                resource_name="online",
            )
        )

    @property
    def serial_number(self) -> str | None:
        value = self.get_value(
            IpsoPath(
                object_name="device",
                object_instance_id="0",
                resource_name="serial_number",
            )
        )
        return str(value) if value else None

    @property
    def manufacturer(self) -> str | None:
        value = self.get_value(
            IpsoPath(
                object_name="device",
                object_instance_id="0",
                resource_name="manufacturer",
            )
        )
        return str(value) if value else None

    @property
    def rf_link_quality(self) -> int | None:
        value = self.get_value(
            IpsoPath(
                object_name="lemonbeat",
                object_instance_id="0",
                resource_name="rf_link_quality",
            )
        )
        if isinstance(value, int):
            return value
        return None

    def build_reload_rf_link_quality_obj(self) -> EgressMessageList:
        return self.build_read_value_obj(
            IpsoPath(
                object_name="lemonbeat",
                object_instance_id="0",
                resource_name="rf_link_quality",
            )
        )

    @property
    def rf_link_state(self) -> int | None:
        value = self.get_value(
            IpsoPath(
                object_name="lemonbeat",
                object_instance_id="0",
                resource_name="rf_link_state",
            )
        )
        if isinstance(value, int):
            return value
        return None

    def build_reload_rf_link_state_obj(self) -> EgressMessageList:
        return self.build_command_obj(self.get_command("measure_rf_link"))

    @property
    def software_version(self) -> str | None:
        value = self.get_value(
            IpsoPath(
                object_name="device",
                object_instance_id="0",
                resource_name="software_version",
            )
        )
        return str(value) if value else None

    @property
    def hardware_version(self) -> str | None:
        value = self.get_value(
            IpsoPath(
                object_name="device",
                object_instance_id="0",
                resource_name="hardware_version",
            )
        )
        return str(value) if value else None


class Gen1BatteryPoweredGen1Device(Gen1Device):
    @property
    def battery_level(self) -> float | None:
        value = self.get_value(
            IpsoPath(
                object_name="lemonbeat",
                object_instance_id="0",
                resource_name="battery_level",
            )
        )
        if isinstance(value, (int, float)):
            return float(value)
        return None

    def build_reload_battery_level_obj(self) -> EgressMessageList:
        return self.build_command_obj(self.get_command("measure_battery"))


class WaterControl(Gen1BatteryPoweredGen1Device):
    def build_set_watering_timer_obj(self, seconds: int) -> EgressMessageList:
        """Set the watering timer.

        Args:
            seconds: Duration of watering in seconds.

        Returns:
            EgressMessageList ready to be sent to the local GARDENA smart API.

        Example:
            >>> WaterControl(...).build_set_watering_timer_obj(3600)
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
    def ambient_temperature(self) -> int | None:
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
