"""High-level API for Gardena Sensor devices."""

from .base import LemonbeatDevice
from .messages import Request


class Sensor(LemonbeatDevice):
    """High-level API for Gardena Sensor device (model 18845).

    This class wraps a DynamicDevice and provides convenient access to
    sensor values and measurement triggers.

    Sensor Values:
        - ambient_temperature: Ambient air temperature in °C
        - battery_level: Battery level (0-100%)
        - light: Light intensity in lux
        - rf_link_quality: RF link quality (0-100%)
        - soil_humidity: Soil moisture (0-100%)
        - soil_temperature: Ground temperature in °C
        - frost_warning: Frost warning flag (1=frost, 0=no frost)

    Diagnostic Info:
        - device_type: Type of the device
        - firmware_version: Current firmware version
        - hardware_version: Hardware version
        - manufacturer: Manufacturer name
        - model_number: Model number
        - serial_number: Serial number
        - software_version: Current software version
        - utc_offset: UTC offset currently in effect

    Example:
        >>> sensor = Sensor(dynamic_device)
        >>> print(f"Soil humidity: {sensor.soil_humidity}%")
        >>> print(f"Temperature: {sensor.soil_temperature}°C")
        >>> # Trigger new measurements
        >>> request = sensor.measure_soil_moisture()
        >>> await websocket.send(request)
    """

    MODEL_NUMBERS = ("18845",)

    def __init__(self, device):
        """Initialize Sensor with a DynamicDevice.

        Args:
            device: A DynamicDevice instance representing the sensor

        Raises:
            ValueError: If device is not a Lemonbeat protocol device or not a Sensor model
        """
        super().__init__(device)
        if self.model_number not in self.MODEL_NUMBERS:
            raise ValueError(
                f"Sensor requires model {', '.join(self.MODEL_NUMBERS)}, "
                f"got {self.model_number}"
            )

    # Sensor Values

    @property
    def ambient_temperature(self) -> int | None:
        """Ambient air temperature in °C (-30 to 85°C)."""
        return self._device.get_value("lemonbeat", "0", "ambient_temperature")

    @property
    def battery_level(self) -> int | None:
        """Battery level percentage (0-100%, 100% is full)."""
        return self._device.get_value("lemonbeat", "0", "battery_level")

    @property
    def light(self) -> int | None:
        """Light intensity in lux (0-200000)."""
        return self._device.get_value("lemonbeat", "0", "light")

    @property
    def rf_link_quality(self) -> int | None:
        """RF link quality percentage (0-100%)."""
        return self._device.get_value("lemonbeat", "0", "rf_link_quality")

    @property
    def soil_humidity(self) -> int | None:
        """Soil moisture percentage (0-100%, mean weighted value)."""
        return self._device.get_value("lemonbeat", "0", "soil_humidity")

    @property
    def soil_humidity_raw(self) -> int | None:
        """Soil moisture percentage (0-100%, raw measured value)."""
        return self._device.get_value("lemonbeat", "0", "soil_humidity_raw_value")

    @property
    def soil_temperature(self) -> int | None:
        """Ground temperature in °C (-30 to 85°C)."""
        return self._device.get_value("lemonbeat", "0", "soil_temperature")

    @property
    def frost_warning(self) -> int | None:
        """Frost warning flag (1=frost below 5°C, 0=no frost)."""
        return self._device.get_value("lemonbeat", "0", "frost_warning")

    @property
    def error(self) -> int | None:
        """Error status (none, eeprom, brown_out)."""
        return self._device.get_value("lemonbeat", "0", "error")

    @property
    def utc_offset(self) -> str | None:
        """UTC offset currently in effect for device."""
        return self._device.get_value("device", "0", "utc_offset")

    # Measurement Triggers

    def measure_soil_moisture(self) -> Request:
        """Trigger a soil moisture measurement.

        Returns:
            Request to send via WebSocket to trigger the measurement
        """
        return self.build_command("measure_soil_moisture")

    def measure_soil_temperature(self) -> Request:
        """Trigger a soil temperature measurement.

        Returns:
            Request to send via WebSocket to trigger the measurement
        """
        return self.build_command("measure_soil_temperature")

    def measure_light(self) -> Request:
        """Trigger a light intensity measurement.

        Returns:
            Request to send via WebSocket to trigger the measurement
        """
        return self.build_command("measure_light")

    def measure_ambient_temperature(self) -> Request:
        """Trigger an ambient temperature measurement.

        Returns:
            Request to send via WebSocket to trigger the measurement
        """
        return self.build_command("measure_ambient_temperature")

    def measure_battery(self) -> Request:
        """Trigger a battery level measurement.

        Returns:
            Request to send via WebSocket to trigger the measurement
        """
        return self.build_command("measure_battery")

    def measure_rf_link(self) -> Request:
        """Trigger an RF link quality measurement.

        Returns:
            Request to send via WebSocket to trigger the measurement
        """
        return self.build_command("measure_rf_link")

    def measure_all(self) -> list[Request]:
        """Trigger all sensor measurements.

        Returns:
            List of Requests to send via WebSocket to trigger all measurements
        """
        commands = [
            "measure_soil_moisture",
            "measure_soil_temperature",
            "measure_light",
            "measure_ambient_temperature",
            "measure_battery",
            "measure_rf_link",
        ]
        return [self.build_command(cmd) for cmd in commands if cmd in self._model.commands]

    def force_report(self) -> Request:
        """Force the device to report all current values.

        Returns:
            Request to send via WebSocket to force reporting
        """
        return self.build_command("force_report")

    def reboot(self) -> Request:
        """Reboot the device.

        Returns:
            Request to send via WebSocket to reboot the device
        """
        return self.build_command("reboot")
