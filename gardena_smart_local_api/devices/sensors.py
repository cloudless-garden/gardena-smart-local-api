from ..messages import EgressMessageList
from ..resources import IpsoPath
from .gen1 import Gen1BatteryPoweredDevice


class Sensor1(Gen1BatteryPoweredDevice):
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

    def build_reload_temperature_obj(self) -> EgressMessageList:
        return self.build_command_obj(self.get_command("measure_ambient_temperature"))

    @property
    def light(self) -> int | None:
        value = self.get_value(
            IpsoPath(
                object_name="lemonbeat",
                object_instance_id="0",
                resource_name="light",
            )
        )
        if isinstance(value, int):
            return value
        return None

    def build_reload_light_obj(self) -> EgressMessageList:
        return self.build_command_obj(self.get_command("measure_light"))

    @property
    def soil_moisture(self) -> int | None:
        value = self.get_value(
            IpsoPath(
                object_name="lemonbeat",
                object_instance_id="0",
                resource_name="soil_humidity",
            )
        )
        if isinstance(value, int):
            return value
        return None

    def build_reload_soil_moisture_obj(self) -> EgressMessageList:
        return self.build_command_obj(self.get_command("measure_soil_moisture"))

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
