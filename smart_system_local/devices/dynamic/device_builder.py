"""Dynamic device builder for creating devices from YAML model definitions."""

import uuid
from enum import IntEnum
from functools import cached_property
from typing import Any, TYPE_CHECKING

from pydantic import BaseModel, Field

from ..messages import Entity, Request
from ...model_loader import ModelDefinition, get_model_loader
from .resources import DynamicObject

if TYPE_CHECKING:
    from .resources import ValueField


class DeviceCommand(IntEnum):
    """Base class for all device command enums.

    All device-specific Command enums should inherit from this class
    to ensure type safety when using the build_command method.
    """


class DynamicDevice(BaseModel):
    """Dynamically generated device based on YAML model definition."""

    id: str
    raw: dict[str, Any] = Field(repr=False)
    model_definition: ModelDefinition = Field()

    @classmethod
    async def from_raw(cls, raw_message: dict[str, Any]) -> "DynamicDevice":
        """Async factory to build a DynamicDevice from raw message data.

        Args:
            raw_message: Raw message with entity, metadata, and payload

        Returns:
            DynamicDevice instance

        Raises:
            ValueError: If data is invalid or model not found
        """
        payload = raw_message.get("payload") or raw_message

        if len(payload) != 1:
            raise ValueError(
                f"Expected exactly one device in payload, got {len(payload)}"
            )

        device_id, device_data = next(iter(payload.items()))

        model_number = cls._extract_model_number(device_data)
        if not model_number:
            raise ValueError("Could not extract model_number from device data")

        model_loader = await get_model_loader()
        model_definition = model_loader.get_model(model_number)
        if not model_definition:
            raise ValueError(f"Unknown model number: {model_number}")

        return cls(id=device_id, raw=device_data, model_definition=model_definition)

    @staticmethod
    def discover() -> Request:
        """Create a device discovery command for the Smart System Local API.

        Returns:
            Request to retrieve all devices from the lemonbeatd service.

        Example:
            >>> DynamicDevice.discover()
            Request(
                request_id="2a8166c5-d60f-4ddd-8735-29aa3661a128",
                op="read",
                entity=Entity(service="lemonbeatd", path="devices")
            )
        """
        return Request(
            request_id=str(uuid.uuid4()),
            op="read",
            entity=Entity(service="lemonbeatd", path="devices"),
        )

    @staticmethod
    def _extract_model_number(device_data: dict[str, Any]) -> str | None:
        """Extract model number from device data."""
        try:
            return device_data["device"]["0"]["model_number"]["vs"]
        except (KeyError, TypeError):
            return None

    def get_value(self, *path: str) -> Any | None:
        """Get a device value using path components.

        Args:
            path: Individual path components as strings.

        Returns:
            The value from the device's raw data, or None if not found.

        Example:
            >>> device.get_value("lemonbeat", "0", "light")
            850
        """
        from .resources import ValueField

        # Navigate through nested dict and extract value from ValueField
        obj: Any = self.raw
        for key in path:
            if not isinstance(obj, dict):
                return None
            obj = obj.get(key)
        if isinstance(obj, dict):
            return ValueField(**obj).value
        return obj

    def get_field(self, *path: str) -> "ValueField | None":
        """Navigate through nested dict and return ValueField object."""
        from .resources import ValueField

        obj = self.raw
        for key in path:
            if not isinstance(obj, dict):
                return None
            obj = obj.get(key)
        return ValueField(**obj) if isinstance(obj, dict) else None

    @property
    def is_online(self) -> bool:
        """Check if device is currently online."""
        return self.get_value("connection_status", "0", "online") or False

    @property
    def device_type(self) -> str | None:
        """Device type identifier."""
        return self.get_value("device", "0", "device_type")

    @property
    def model_number(self) -> str | None:
        """Model number of the device."""
        return self.get_value("device", "0", "model_number")

    @property
    def serial_number(self) -> str | None:
        """Serial number of the device."""
        return self.get_value("device", "0", "serial_number")

    @property
    def firmware_version(self) -> str | None:
        """Firmware version of the device."""
        return self.get_value("device", "0", "firmware_version")

    @property
    def software_version(self) -> str | None:
        """Software version of the device."""
        return self.get_value("lemonbeat", "0", "software_version")

    @property
    def manufacturer(self) -> str | None:
        """Manufacturer of the device."""
        return self.get_value("device", "0", "manufacturer")

    @property
    def rf_link_quality(self) -> int | None:
        """RF link quality indicator."""
        return self.get_value("lemonbeat", "0", "rf_link_quality")

    @property
    def error(self) -> int | None:
        """Current error code."""
        return self.get_value("lemonbeat", "0", "error")

    def build_command(self, command: int | DeviceCommand) -> Request:
        """Build a Lemonbeat command JSON structure.

        Args:
            command: Command code as int or DeviceCommand IntEnum value.

        Returns:
            Request ready to be sent to the Lemonbeat API.

        Example:
            >>> device.build_command(3)
            Request(
                request_id="2a8166c5-d60f-4ddd-8735-29aa3661a128",
                op="write",
                entity=Entity(device="device_id", path="lemonbeat/0/command"),
                payload={"vi": 3}
            )
        """
        cmd_value = command.value if isinstance(command, DeviceCommand) else command
        return Request(
            request_id=str(uuid.uuid4()),
            op="write",
            entity=Entity(device=self.id, path="lemonbeat/0/command"),
            payload={"vi": cmd_value},
        )

    def write_value(
        self, path_str: str, value: int | str | bool | float
    ) -> Request:
        """Build a value write JSON structure.

        Args:
            path_str: Path string (e.g., "lemonbeat/0/power_timer").
            value: The value to set (int, str, bool, or float).

        Returns:
            Request ready to be sent to the Lemonbeat API.

        Example:
            >>> device.write_value("lemonbeat/0/power_timer", 3600)
            Request(
                request_id="2a8166c5-d60f-4ddd-8735-29aa3661a128",
                op="write",
                entity=Entity(device="device_id", path="lemonbeat/0/power_timer"),
                payload={"vi": 3600}
            )
        """
        # Determine the appropriate payload key based on value type
        if isinstance(value, bool):
            payload = {"vb": value}
        elif isinstance(value, int):
            payload = {"vi": value}
        elif isinstance(value, float):
            payload = {"vf": value}
        elif isinstance(value, str):
            payload = {"vs": value}
        else:
            raise TypeError(f"Unsupported value type: {type(value)}")

        return Request(
            request_id=str(uuid.uuid4()),
            op="write",
            entity=Entity(device=self.id, path=path_str),
            payload=payload,
        )

    def read_value(self, path_str: str) -> Request:
        """Build a value read request JSON structure.

        Args:
            path_str: Path string (e.g., "lemonbeat/0/power_timer").

        Returns:
            Request ready to be sent to the Lemonbeat API.

        Example:
            >>> device.read_value("lemonbeat/0/power_timer")
            Request(
                request_id="2a8166c5-d60f-4ddd-8735-29aa3661a128",
                op="read",
                entity=Entity(device="device_id", path="lemonbeat/0/power_timer")
            )
        """
        return Request(
            request_id=str(uuid.uuid4()),
            op="read",
            entity=Entity(device=self.id, path=path_str),
        )

    @cached_property
    def objects(self) -> dict[str, dict[str, DynamicObject]]:
        """Build and cache DynamicObject instances from model definition."""
        result: dict[str, dict[str, DynamicObject]] = {}
        for object_name, object_data in self.model_definition.objects.items():
            multi_instance = object_data.get("multi_instance", False)
            result[object_name] = {}

            if multi_instance:
                if object_name in self.raw:
                    for object_instance_id in self.raw[object_name].keys():
                        result[object_name][object_instance_id] = DynamicObject(
                            object_name, object_instance_id, object_data
                        )
            else:
                result[object_name]["0"] = DynamicObject(object_name, "0", object_data)
        return result

    def get_object(
        self, object_name: str, instance_id: str = "0"
    ) -> DynamicObject | None:
        """Get a dynamic object by name and instance ID.

        Args:
            object_name: Name of the object (e.g., "actuator", "device")
            instance_id: Instance ID (default: "0")

        Returns:
            DynamicObject if found, None otherwise
        """
        return self.objects.get(object_name, {}).get(instance_id)

    def get_resource(
        self, object_name: str, instance_id: str | int, resource_name: str
    ) -> Any | None:
        """Get a resource value from the device.

        Args:
            object_name: Name of the object (e.g., "actuator")
            instance_id: Instance ID (e.g., "0" or 0)
            resource_name: Name of the resource (e.g., "state")

        Returns:
            The resource value, or None if not found
        """
        obj = self.get_object(object_name, str(instance_id))
        return obj.get_value(resource_name, self.raw) if obj else None

    def set_resource(
        self,
        object_name: str,
        instance_id: str | int,
        resource_name: str,
        value: Any,
    ) -> Request:
        """Build a write request to set a resource value.

        Args:
            object_name: Name of the object
            instance_id: Instance ID
            resource_name: Name of the resource
            value: Value to set

        Returns:
            Request to set the resource value

        Raises:
            ValueError: If resource is not writable or not found
        """
        obj = self.get_object(object_name, str(instance_id))
        if not obj:
            raise ValueError(f"Object {object_name}[{instance_id}] not found")

        resource = obj.get_resource(resource_name)
        if not resource:
            raise ValueError(
                f"Resource {resource_name} not found in {object_name}[{instance_id}]"
            )

        if not resource.is_writable:
            raise ValueError(
                f"Resource {object_name}/{instance_id}/{resource_name} is not writable"
            )

        # Determine payload type from value
        if isinstance(value, bool):
            payload = {"vb": value}
        elif isinstance(value, int):
            payload = {"vi": value}
        elif isinstance(value, float):
            payload = {"vf": value}
        elif isinstance(value, str):
            payload = {"vs": value}
        elif isinstance(value, list):
            if value and isinstance(value[0], int):
                payload = {"ai": value}
            else:
                payload = {"as": value}
        else:
            raise TypeError(f"Unsupported value type: {type(value)}")

        path = f"{object_name}/{instance_id}/{resource_name}"

        return Request(
            request_id=str(uuid.uuid4()),
            op="write",
            entity=Entity(device=self.id, path=path, service="lemonbeatd"),
            payload=payload,
        )

    def list_instances(self, object_name: str) -> list[str]:
        """Get list of all instance IDs for an object.

        Args:
            object_name: Name of the object

        Returns:
            List of instance ID strings
        """
        return list(self.objects.get(object_name, {}).keys())

    @property
    def device_name(self) -> str:
        """Get the device model name."""
        return self.model_definition.name

    @property
    def device_type_name(self) -> str:
        """Get the device type name."""
        return self.model_definition.type

    def __repr__(self) -> str:
        return f"DynamicDevice(id={self.id!r}, model={self.model_definition.name!r}, type={self.model_definition.type!r})"
