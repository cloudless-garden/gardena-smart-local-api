"""Dynamic device builder for creating devices from YAML model definitions."""
import uuid
from functools import cached_property
from typing import Any

from pydantic import Field

from ..base import BaseDevice
from ...model_loader import ModelDefinition, get_model_loader
from .resources import DynamicObject


class DynamicDevice(BaseDevice):
    """Dynamically generated device based on YAML model definition."""

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
            raise ValueError(f"Expected exactly one device in payload, got {len(payload)}")

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
    def _extract_model_number(device_data: dict[str, Any]) -> str | None:
        """Extract model number from device data."""
        try:
            return device_data["device"]["0"]["model_number"]["vs"]
        except (KeyError, TypeError):
            return None

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
                result[object_name]["0"] = DynamicObject(
                    object_name, "0", object_data
                )
        return result

    def get_object(self, object_name: str, instance_id: str = "0") -> DynamicObject | None:
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
    ) -> dict[str, Any]:
        """Build a write request to set a resource value.

        Args:
            object_name: Name of the object
            instance_id: Instance ID
            resource_name: Name of the resource
            value: Value to set

        Returns:
            Dictionary containing the write request structure

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

        return {
            "request-id": str(uuid.uuid4()),
            "op": "write",
            "entity": {"device": self.id, "path": path},
            "payload": payload,
            "metadata": {},
        }

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
