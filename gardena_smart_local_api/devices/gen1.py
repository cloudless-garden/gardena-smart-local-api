from typing import ClassVar, Protocol

from pydantic import Field

from ..messages import EgressMessageList, Entity, Request
from ..model_loader import Gen1ModelDefinition
from ..resources import IpsoPath
from .device import Device


class _Gen1DeviceProtocol(Protocol):
    """Used to satisfy the type checker."""

    def build_command_obj(self, command: int) -> EgressMessageList: ...
    def get_command(self, name: str) -> int: ...


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

    def build_refresh_rf_link_quality_obj(self) -> EgressMessageList:
        return self.build_read_value_obj(
            IpsoPath(
                object_name="lemonbeat",
                object_instance_id="0",
                resource_name="rf_link_quality",
            )
        )

    @property
    def error(self) -> int | None:
        value = self.get_value(
            IpsoPath(
                object_name="lemonbeat",
                object_instance_id="0",
                resource_name="error",
            )
        )
        if isinstance(value, int):
            return value
        return None


class Gen1BatteryPoweredDevice(Gen1Device):
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

    def build_refresh_battery_level_obj(self) -> EgressMessageList:
        return self.build_command_obj(self.get_command("measure_battery"))


class IdentifyMixin:
    def build_identify_obj(self: _Gen1DeviceProtocol) -> EgressMessageList:
        return self.build_command_obj(self.get_command("hap_identify"))
