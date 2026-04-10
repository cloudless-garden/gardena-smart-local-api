# SPDX-FileCopyrightText: 2026 GARDENA GmbH
#
# SPDX-License-Identifier: LGPL-3.0-or-later

from typing import ClassVar, Protocol

from pydantic import Field

from ..messages import EgressMessageList
from ..model_loader import Gen2ModelDefinition
from ..resources import VALUE_TYPES, IpsoPath
from .device import Device


class _DeviceProtocol(Protocol):
    """Used to satisfy the type checker."""

    def get_value(self, path: IpsoPath) -> VALUE_TYPES | None: ...

    def build_execute_obj(
        self, path: IpsoPath, value: VALUE_TYPES | None
    ) -> EgressMessageList: ...


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


class Gen2TemperatureMixin:
    @property
    def temperature(self: _DeviceProtocol) -> float | None:
        """
        All battery driven Gen2 water controls have an ambient temperature entity.

        The temperature is measured roughly every 31 minutes and every time the
        valve changes its state. Reports are sent when the temperature difference is
        greater than 2°C since the last report. Around the frost warning temperature of
        4.0°C (±0.25°C hysteresis), the update occurs also when the frost warning state
        changes.
        """
        value = self.get_value(
            IpsoPath(
                object_name="temperature",
                object_instance_id="0",
                resource_name="sensor_value",
            )
        )
        return value if isinstance(value, float) else None


class Gen2IdentifyMixin:
    def build_identify_obj(self: _DeviceProtocol) -> EgressMessageList:
        return self.build_execute_obj(
            IpsoPath(
                object_name="sg_common",
                object_instance_id="0",
                resource_name="identify",
            ),
            None,
        )


class Gen2Device(Device):
    """Base class for gen2 GARDENA smart devices."""

    # connectivity_monitoring is present in every known Gen2 model schema.
    model_definition: Gen2ModelDefinition = Field()
    service: ClassVar[str] = "lwm2mserver"

    @property
    def radio_signal_strength(self: _DeviceProtocol) -> int | None:
        """Signal strength in dBm, from the standard LwM2M connectivity object.

        Also refreshed by build_refresh_rf_link_quality_obj().
        """
        value = self.get_value(
            IpsoPath(
                object_name="connectivity_monitoring",
                object_instance_id="0",
                resource_name="radio_signal_strength",
            )
        )
        return value if isinstance(value, int) else None

    @property
    def rf_link_quality(self: _DeviceProtocol) -> int | None:
        value = self.get_value(
            IpsoPath(
                object_name="connectivity_monitoring",
                object_instance_id="0",
                resource_name="link_quality",
            )
        )
        return value if isinstance(value, int) else None

    def build_refresh_rf_link_quality_obj(self: _DeviceProtocol) -> EgressMessageList:
        return self.build_execute_obj(
            IpsoPath(
                object_name="sg_common",
                object_instance_id="0",
                resource_name="measure_rf_link",
            ),
            None,
        )
