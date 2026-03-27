from typing import ClassVar

from pydantic import Field

from ..model_loader import Gen2ModelDefinition
from ..resources import IpsoPath
from .device import Device


class Gen2Device(Device):
    model_definition: Gen2ModelDefinition = Field()
    service: ClassVar[str] = "lwm2mserver"


class Gen2BatteryPoweredDevice(Gen2Device):
    @property
    def battery_level(self) -> float | None:
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
