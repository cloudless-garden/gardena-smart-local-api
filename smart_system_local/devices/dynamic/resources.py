"""Dynamic IPSO object and resource system."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ValueField(BaseModel):
    """Represents a value field in Smart System Local device data with timestamp."""

    vb: bool | None = None
    vs: str | None = None
    vi: int | None = None
    vo: str | None = None
    ai: list[int] | None = None
    vf: float | None = None
    vt: int | None = None
    ts: int | None = None
    as_: list[str] | None = Field(None, alias="as")

    @property
    def value(self) -> bool | str | int | float | list[int] | list[str] | None:
        """Extract the actual value from the field."""
        for v in (
            self.vb,
            self.vs,
            self.vi,
            self.vf,
            self.vo,
            self.ai,
            self.vt,
            self.as_,
        ):
            if v is not None:
                return v
        return None

    @property
    def timestamp(self) -> datetime | None:
        """Convert timestamp to datetime object."""
        return datetime.fromtimestamp(self.ts) if self.ts else None


class DynamicResource:
    """Represents a single resource within an IPSO object."""

    def __init__(
        self,
        name: str,
        resource_data: dict[str, Any],
        object_name: str,
        object_instance_id: str,
        resource_instance_id: int = 0,
    ):
        """Initialize a dynamic resource.

        Args:
            name: Resource name (e.g., "state", "available")
            resource_data: Resource definition from YAML
            object_name: Name of the parent object (e.g., "actuator")
            object_instance_id: Instance ID of the parent object (e.g., "0", "1")
            resource_instance_id: Instance ID of the resource (for array resources, default: 0)
        """
        self.name = name
        self.object_name = object_name
        self.object_instance_id = object_instance_id
        self.resource_instance_id = resource_instance_id
        self.type = resource_data.get("type")  # vb, vs, vi, etc.
        self.access = resource_data.get("access")  # r, rw, w, or None
        self.unit = resource_data.get("unit")
        self.description = resource_data.get("description")
        self.constraints = resource_data.get("constraints")

    @property
    def path(self) -> tuple[str, str, str]:
        """Get the path tuple to access this resource in raw device data."""
        return (self.object_name, self.object_instance_id, self.name)

    @property
    def is_readable(self) -> bool:
        """Check if this resource can be read."""
        return self.access in ("r", "rw") if self.access else False

    @property
    def is_writable(self) -> bool:
        """Check if this resource can be written."""
        return self.access in ("w", "rw") if self.access else False

    def get_value(self, raw_data: dict[str, Any]) -> Any | None:
        """Extract the value from raw device data.

        Args:
            raw_data: Raw device data dictionary

        Returns:
            The resource value, or None if not found
        """
        obj = raw_data
        for key in self.path:
            if not isinstance(obj, dict):
                return None
            obj = obj.get(key)
            if obj is None:
                return None

        if isinstance(obj, dict):
            return ValueField(**obj).value
        return obj

    def get_field(self, raw_data: dict[str, Any]) -> ValueField | None:
        """Extract the ValueField from raw device data.

        Args:
            raw_data: Raw device data dictionary

        Returns:
            ValueField object, or None if not found
        """
        obj = raw_data
        for key in self.path:
            if not isinstance(obj, dict):
                return None
            obj = obj.get(key)
            if obj is None:
                return None

        return ValueField(**obj) if isinstance(obj, dict) else None

    def __repr__(self) -> str:
        return f"DynamicResource({self.object_name}/{self.object_instance_id}/{self.name}, type={self.type}, access={self.access}, resource_instance_id={self.resource_instance_id})"


class DynamicObject:
    """Represents an IPSO object instance with its resources."""

    def __init__(
        self,
        name: str,
        object_instance_id: str,
        object_data: dict[str, Any],
    ):
        """Initialize a dynamic object.

        Args:
            name: Object name (e.g., "actuator", "device")
            object_instance_id: Instance ID (e.g., "0", "1")
            object_data: Object definition from YAML
        """
        self.name = name
        self.object_instance_id = object_instance_id
        self.object_id = object_data.get("object_id")
        self.object_urn = object_data.get("object_urn")
        self.object_version = object_data.get("object_version")
        self.mandatory = object_data.get("mandatory", False)
        self.multi_instance = object_data.get("multi_instance", False)

        # Create DynamicResource instances for all resources
        self.resources: dict[str, DynamicResource] = {}
        for resource_name, resource_data in object_data.get("resources", {}).items():
            self.resources[resource_name] = DynamicResource(
                resource_name, resource_data, name, object_instance_id
            )

    def get_resource(self, resource_name: str) -> DynamicResource | None:
        """Get a resource by name.

        Args:
            resource_name: Name of the resource

        Returns:
            DynamicResource if found, None otherwise
        """
        return self.resources.get(resource_name)

    def get_value(self, resource_name: str, raw_data: dict[str, Any]) -> Any | None:
        """Get a resource value from raw device data.

        Args:
            resource_name: Name of the resource
            raw_data: Raw device data dictionary

        Returns:
            The resource value, or None if not found
        """
        resource = self.get_resource(resource_name)
        return resource.get_value(raw_data) if resource else None

    def list_resources(self) -> list[str]:
        """Get list of all resource names in this object."""
        return list(self.resources.keys())

    def __repr__(self) -> str:
        return f"DynamicObject({self.name}[{self.object_instance_id}], {len(self.resources)} resources)"
