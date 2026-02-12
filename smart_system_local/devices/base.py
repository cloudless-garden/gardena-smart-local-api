"""Base device classes for high-level device API."""

from typing import ClassVar

from smart_system_local.model_loader import (
    LemonbeatModelDefinition,
    Lwm2mModelDefinition,
    ModelDefinition,
)

from .dynamic.device_builder import DynamicDevice
from .messages import Request


class BaseDevice:
    """Base class for high-level device wrappers.

    Provides common properties and basic functionality for all devices.
    Use protocol-specific subclasses (LemonbeatDevice, Lwm2mDevice) for
    protocol-specific features.
    """

    MODEL_NUMBERS: ClassVar[tuple[str, ...]] = ()

    def __init__(self, device: DynamicDevice):
        """Initialize BaseDevice with a DynamicDevice.

        Args:
            device: A DynamicDevice instance representing the device
        """
        self._device = device

    @property
    def id(self) -> str:
        """Device ID."""
        return self._device.id

    @property
    def is_online(self) -> bool:
        """Check if device is currently online."""
        return self._device.is_online

    @property
    def name(self) -> str | None:
        """Device name."""
        # Try common name locations
        name = self._device.get_value("sg_common", "0", "name")
        if name is None:
            # Try device object for some lwm2m devices
            name = self._device.get_value("device", "0", "name")
        return name

    @property
    def device_type(self) -> str | None:
        """Type of the device."""
        return self._device.device_type

    @property
    def model_number(self) -> str | None:
        """Model number or identifier."""
        return self._device.model_number

    @property
    def serial_number(self) -> str | None:
        """Serial number."""
        return self._device.serial_number

    @property
    def firmware_version(self) -> str | None:
        """Current firmware version."""
        return self._device.firmware_version

    @property
    def hardware_version(self) -> str | None:
        """Hardware version."""
        return self._device.get_value("device", "0", "hardware_version")

    @property
    def software_version(self) -> str | None:
        """Current software version."""
        return self._device.software_version

    @property
    def manufacturer(self) -> str | None:
        """Manufacturer name."""
        return self._device.manufacturer

    @property
    def model_definition(self) -> ModelDefinition:
        """Device model definition."""
        return self._device.model_definition

    @property
    def raw(self) -> dict:
        """Access the underlying raw device data."""
        return self._device.raw

    def __repr__(self) -> str:
        """Return string representation of the device."""
        return (
            f"{self.__class__.__name__}(id={self.id!r}, "
            f"model={self.model_number}, "
            f"online={self.is_online})"
        )


class LemonbeatDevice(BaseDevice):
    """Base class for Lemonbeat protocol devices.

    Provides validation and command execution support for Lemonbeat devices.
    """

    def __init__(self, device: DynamicDevice):
        """Initialize LemonbeatDevice with a DynamicDevice.

        Args:
            device: A DynamicDevice instance representing the device

        Raises:
            ValueError: If device is not a Lemonbeat protocol device
        """
        if not isinstance(device.model_definition, LemonbeatModelDefinition):
            raise ValueError(
                f"{self.__class__.__name__} requires a Lemonbeat device, "
                f"got {device.model_definition.protocol}"
            )
        super().__init__(device)
        # Store typed model for type checker
        self._model: LemonbeatModelDefinition = device.model_definition

    def build_command(self, command_name: str) -> Request:
        """Build a command request for this device.

        Args:
            command_name: Name of the command to execute

        Returns:
            Request to send via WebSocket to execute the command

        Raises:
            ValueError: If command is not available for this device
        """
        cmd = self._model.commands.get(command_name)
        if cmd is None:
            raise ValueError(
                f"Command {command_name!r} not available for this device. "
                f"Available commands: {list(self._model.commands.keys())}"
            )
        return self._device.build_command(cmd)


class Lwm2mDevice(BaseDevice):
    """Base class for LWM2M protocol devices.

    Provides validation for LWM2M devices.
    """

    def __init__(self, device: DynamicDevice):
        """Initialize Lwm2mDevice with a DynamicDevice.

        Args:
            device: A DynamicDevice instance representing the device

        Raises:
            ValueError: If device is not an LWM2M protocol device
        """
        if not isinstance(device.model_definition, Lwm2mModelDefinition):
            raise ValueError(
                f"{self.__class__.__name__} requires an LWM2M device, "
                f"got {device.model_definition.protocol}"
            )
        super().__init__(device)
        # Store typed model for type checker
        self._model: Lwm2mModelDefinition = device.model_definition


def create_device(device: DynamicDevice) -> BaseDevice:
    """Factory function to create the appropriate high-level device wrapper.

    Args:
        device: A DynamicDevice instance

    Returns:
        Appropriate device class instance (Sensor, etc.) or BaseDevice for unknown models
    """
    model_number = device.model_definition.model_number

    # Find all BaseDevice subclasses and check their MODEL_NUMBERS
    for subclass in _get_all_subclasses(BaseDevice):
        if model_number in subclass.MODEL_NUMBERS:
            return subclass(device)

    # No specific device class found, return generic BaseDevice
    return BaseDevice(device)


def _get_all_subclasses(cls):
    """Recursively get all subclasses of a class."""
    all_subclasses = []
    for subclass in cls.__subclasses__():
        all_subclasses.append(subclass)
        all_subclasses.extend(_get_all_subclasses(subclass))
    return all_subclasses
