from ..messages import EgressMessageList
from ..resources import IpsoPath
from .gen1 import Gen1Device, Gen1IdentifyMixin


class PowerAdapter(Gen1IdentifyMixin, Gen1Device):
    @property
    def power_timer(self) -> int | None:
        value = self.get_value(
            IpsoPath(
                object_name="lemonbeat",
                object_instance_id="0",
                resource_name="power_timer",
            )
        )
        if isinstance(value, int):
            return value
        return None

    @property
    def is_output_enabled(self) -> bool | None:
        if (value := self.power_timer) is not None:
            return value != 0
        return None

    def build_enable_output_obj(self, seconds: int) -> EgressMessageList:
        return self.build_write_value_obj(
            IpsoPath(
                object_name="lemonbeat",
                object_instance_id="0",
                resource_name="power_timer",
            ),
            seconds,
        )

    def build_disable_output_obj(self) -> EgressMessageList:
        return self.build_enable_output_obj(0)
