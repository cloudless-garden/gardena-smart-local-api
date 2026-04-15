from typing import ClassVar, Protocol

from pydantic import Field

from ..model_loader import Gen2ModelDefinition
from ..resources import VALUE_TYPES, IpsoPath
from .device import Device


class _DeviceProtocol(Protocol):
    """Used to satisfy the type checker."""

    def get_value(self, path: IpsoPath) -> VALUE_TYPES | None: ...


class Gen2BatteryMixin:
    """Mixin for battery-powered gen2 GARDENA smart devices."""

    @property
    def battery_level(self: _DeviceProtocol) -> float | None:
        value = self.get_value(
            IpsoPath(
                object_name="device",
                object_instance_id="0",
                resource_name="battery_level",
            )
        )
        if isinstance(value, (int, float)):
            return float(value)
        return None


class Gen2Device(Device):
    """Base class for gen2 GARDENA smart devices."""

    model_definition: Gen2ModelDefinition = Field()
    service: ClassVar[str] = "lwm2mserver"
