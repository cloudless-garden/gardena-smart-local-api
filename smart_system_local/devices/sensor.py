"""High-level API for Gardena Sensor devices."""

from smart_system_local.model_loader import LemonbeatModelDefinition

from .dynamic.device_builder import DynamicDevice
from .messages import Request


class Sensor:
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

    def __init__(self, device: DynamicDevice):
        """Initialize Sensor with a DynamicDevice.

        Args:
            device: A DynamicDevice instance representing the sensor

        Raises:
            ValueError: If device is not a Lemonbeat protocol device or not a Sensor model
        """
        if not isinstance(device.model_definition, LemonbeatModelDefinition):
            raise ValueError(
                f"Sensor requires a Lemonbeat device, got {device.model_definition.protocol}"
            )
        if device.model_definition.model_number != "18845":
            raise ValueError(
                f"Sensor requires model 18845, got {device.model_definition.model_number}"
            )
        self._device = device
        # workaround ty checker limitation
        self._model: LemonbeatModelDefinition = device.model_definition

    @property
    def id(self) -> str:
        """Device ID."""
        return self._device.id

    @property
    def is_online(self) -> bool:
        """Check if device is currently online."""
        return self._device.is_online

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

    # Diagnostic Information

    @property
    def device_type(self) -> str | None:
        """Type of the device."""
        return self._device.device_type

    @property
    def firmware_version(self) -> str | None:
        """Current firmware version."""
        return self._device.firmware_version

    @property
    def hardware_version(self) -> str | None:
        """Hardware version."""
        return self._device.get_value("device", "0", "hardware_version")

    @property
    def manufacturer(self) -> str | None:
        """Manufacturer name."""
        return self._device.manufacturer

    @property
    def model_number(self) -> str | None:
        """Model number or identifier."""
        return self._device.model_number

    @property
    def serial_number(self) -> str | None:
        """Serial number."""
        return self._device.serial_number

    @property
    def software_version(self) -> str | None:
        """Current software version."""
        return self._device.software_version

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
        cmd = self._model.commands.get("measure_soil_moisture")
        if cmd is None:
            raise ValueError(
                "Command 'measure_soil_moisture' not available for this device"
            )
        return self._device.build_command(cmd)

    def measure_soil_temperature(self) -> Request:
        """Trigger a soil temperature measurement.

        Returns:
            Request to send via WebSocket to trigger the measurement
        """
        cmd = self._model.commands.get("measure_soil_temperature")
        if cmd is None:
            raise ValueError(
                "Command 'measure_soil_temperature' not available for this device"
            )
        return self._device.build_command(cmd)

    def measure_light(self) -> Request:
        """Trigger a light intensity measurement.

        Returns:
            Request to send via WebSocket to trigger the measurement
        """
        cmd = self._model.commands.get("measure_light")
        if cmd is None:
            raise ValueError("Command 'measure_light' not available for this device")
        return self._device.build_command(cmd)

    def measure_ambient_temperature(self) -> Request:
        """Trigger an ambient temperature measurement.

        Returns:
            Request to send via WebSocket to trigger the measurement
        """
        cmd = self._model.commands.get("measure_ambient_temperature")
        if cmd is None:
            raise ValueError(
                "Command 'measure_ambient_temperature' not available for this device"
            )
        return self._device.build_command(cmd)

    def measure_battery(self) -> Request:
        """Trigger a battery level measurement.

        Returns:
            Request to send via WebSocket to trigger the measurement
        """
        cmd = self._model.commands.get("measure_battery")
        if cmd is None:
            raise ValueError("Command 'measure_battery' not available for this device")
        return self._device.build_command(cmd)

    def measure_rf_link(self) -> Request:
        """Trigger an RF link quality measurement.

        Returns:
            Request to send via WebSocket to trigger the measurement
        """
        cmd = self._model.commands.get("measure_rf_link")
        if cmd is None:
            raise ValueError("Command 'measure_rf_link' not available for this device")
        return self._device.build_command(cmd)

    def measure_all(self) -> list[Request]:
        """Trigger all sensor measurements.

        Returns:
            List of Requests to send via WebSocket to trigger all measurements
        """
        return [
            self.measure_soil_moisture(),
            self.measure_soil_temperature(),
            self.measure_light(),
            self.measure_ambient_temperature(),
            self.measure_battery(),
            self.measure_rf_link(),
        ]

    def force_report(self) -> Request:
        """Force the device to report all current values.

        Returns:
            Request to send via WebSocket to force reporting
        """
        cmd = self._model.commands.get("force_report")
        if cmd is None:
            raise ValueError("Command 'force_report' not available for this device")
        return self._device.build_command(cmd)

    def reboot(self) -> Request:
        """Reboot the device.

        Returns:
            Request to send via WebSocket to reboot the device
        """
        cmd = self._model.commands.get("reboot")
        if cmd is None:
            raise ValueError("Command 'reboot' not available for this device")
        return self._device.build_command(cmd)

    @property
    def raw(self) -> dict:
        """Access the underlying raw device data."""
        return self._device.raw

    def __repr__(self) -> str:
        """Return string representation of the sensor."""
        return (
            f"Sensor(id={self.id!r}, "
            f"model={self.model_number}, "
            f"online={self.is_online})"
        )
