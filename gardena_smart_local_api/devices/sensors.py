from ..messages import EgressMessageList
from ..resources import IpsoPath
from .gen1 import Gen1BatteryMixin, Gen1Device, Gen1FrostWarningMixin, Gen1IdentifyMixin


class _Sensor(Gen1Device, Gen1BatteryMixin, Gen1IdentifyMixin, Gen1FrostWarningMixin):
    def build_refresh_soil_moisture_obj(self) -> EgressMessageList:
        return self.build_command_obj(self.get_command("measure_soil_moisture"))


class Sensor1(_Sensor):
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

    def build_refresh_temperature_obj(self) -> EgressMessageList:
        return self.build_command_obj(self.get_command("measure_ambient_temperature"))

    def build_refresh_light_obj(self) -> EgressMessageList:
        return self.build_command_obj(self.get_command("measure_light"))


class Sensor2(_Sensor):
    @property
    def temperature(self) -> int | None:
        value = self.get_value(
            IpsoPath(
                object_name="lemonbeat",
                object_instance_id="0",
                resource_name="soil_temperature",
            )
        )
        if isinstance(value, int):
            return value
        return None

    @property
    def soil_moisture(self) -> int | None:
        value = self.get_value(
            IpsoPath(
                object_name="lemonbeat",
                object_instance_id="0",
                resource_name="soil_moisture",
            )
        )
        if isinstance(value, int):
            return value
        return None

    def build_refresh_temperature_obj(self) -> EgressMessageList:
        return self.build_command_obj(self.get_command("measure_soil_temperature"))
