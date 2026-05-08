from typing import ClassVar, Protocol

from pydantic import Field

from ..model_loader import Gen2ModelDefinition
from ..resources import VALUE_TYPES, IpsoPath
from .device import Device


class _DeviceProtocol(Protocol):
    """Used to satisfy the type checker."""

    def get_value(self, path: IpsoPath) -> VALUE_TYPES | None: ...


class Gen2BatteryMixin:
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


class Gen2ChargingCyclesMixin:
    @property
    def charging_cycles(self: _DeviceProtocol) -> int | None:
        value = self.get_value(
            IpsoPath(
                object_name="statistics",
                object_instance_id="0",
                resource_name="number_of_charging_cycles",
            )
        )
        if isinstance(value, int):
            return int(value)
        return None


class Gen2CuttingTimeMixin:
    @property
    def cutting_time(self: _DeviceProtocol) -> int | None:
        value = self.get_value(
            IpsoPath(
                object_name="statistics",
                object_instance_id="0",
                resource_name="total_cutting_time",
            )
        )
        if isinstance(value, int):
            return int(value)
        return None


class Gen2RunningTimeMixin:
    @property
    def running_time(self: _DeviceProtocol) -> int | None:
        value = self.get_value(
            IpsoPath(
                object_name="statistics",
                object_instance_id="0",
                resource_name="total_running_time",
            )
        )
        if isinstance(value, int):
            return int(value)
        return None


class Gen2CollisionsMixin:
    @property
    def collisions(self: _DeviceProtocol) -> int | None:
        value = self.get_value(
            IpsoPath(
                object_name="statistics",
                object_instance_id="0",
                resource_name="number_of_collisions",
            )
        )
        if isinstance(value, int):
            return int(value)
        return None


class Gen2Device(Device):
    model_definition: Gen2ModelDefinition = Field()
    service: ClassVar[str] = "lwm2mserver"
