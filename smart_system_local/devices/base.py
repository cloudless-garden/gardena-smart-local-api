"""Base device classes and utilities for Smart System Local devices."""

import uuid
from datetime import datetime
from enum import Enum, IntEnum
from typing import Any

from pydantic import BaseModel, Field

from .messages import Entity, Request


def merge_enums(name: str, *enums: type[Enum]) -> type[Enum]:
    """Merge multiple Enum classes into a single Enum."""
    members = {}
    for enum in enums:
        for member in enum:
            if member.name in members:
                raise ValueError(f"Duplicate enum member: {member.name}")
            members[member.name] = member.value
    return Enum(name, members)


class DeviceCommand(IntEnum):
    """Base class for all device command enums.

    All device-specific Command enums should inherit from this class
    to ensure type safety when using the build_command method.
    """


class IpsoPath(Enum):
    """Base class for all device value path enums.

    Each value is a tuple of (path_parts...) defining where the value
    is located in the device's raw data structure. Can be used for
    both getting and setting values.
    """


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


class BaseDevice(BaseModel):
    """Base class for all Smart System Local devices with common properties."""

    id: str
    raw: dict[str, Any] = Field(repr=False)

    def get_value(self, *path: str | IpsoPath) -> Any | None:
        """Get a device value using path components or an IpsoPath enum.

        Args:
            path: Either individual path components as strings, or a single IpsoPath enum.

        Returns:
            The value from the device's raw data, or None if not found.

        Example:
            >>> device.get_value("lemonbeat", "0", "light")
            850
            >>> device.get_value(Sensor.Value.LIGHT)
            850
        """
        # If single argument and it's an IpsoPath, extract its value tuple
        path_parts: tuple[str, ...]
        if len(path) == 1 and hasattr(path[0], "value"):
            path_parts = path[0].value  # type: ignore[attr-defined]
        else:
            path_parts = tuple(
                str(p) if isinstance(p, str) else str(p.value) for p in path
            )

        # Navigate through nested dict and extract value from ValueField
        obj: Any = self.raw
        for key in path_parts:
            if not isinstance(obj, dict):
                return None
            obj = obj.get(key)
        if isinstance(obj, dict):
            return ValueField(**obj).value
        return obj

    def get_field(self, *path: str) -> ValueField | None:
        """Navigate through nested dict and return ValueField object."""
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

    def build_command(self, command: DeviceCommand) -> Request:
        """Build a Lemonbeat command JSON structure.

        Args:
            command: A DeviceCommand IntEnum value representing the command code.

        Returns:
            A dictionary containing the command structure ready to be sent
            to the Lemonbeat API.

        Example:
            >>> # Using a command from a dynamically built Command enum
            >>> device.build_command(device.Command.PARK_UNTIL_NEXT_TASK)
            Request(
                request_id="2a8166c5-d60f-4ddd-8735-29aa3661a128",
                op="write",
                entity=Entity(device="device_id", path="lemonbeat/0/command"),
                payload={"vi": 3},
                metadata={}
            )
        """
        return Request(
            request_id=str(uuid.uuid4()),
            op="write",
            entity=Entity(device=self.id, path="lemonbeat/0/command"),
            payload={"vi": command.value},
        )

    def write_value(
        self, path: "IpsoPath", value: int | str | bool | float
    ) -> Request:
        """Build a value write JSON structure.

        Args:
            path: An IpsoPath enum value - a tuple of path components.
            value: The value to set (int, str, bool, or float).

        Returns:
            A dictionary containing the write structure ready to be sent
            to the Lemonbeat API.

        Example:
            >>> # Using a value from a dynamically built Value enum
            >>> device.write_value(device.Value.POWER_TIMER, 3600)
            Request(
                request_id="2a8166c5-d60f-4ddd-8735-29aa3661a128",
                op="write",
                entity=Entity(device="device_id", path="lemonbeat/0/power_timer"),
                payload={"vi": 3600},
                metadata={}
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

        # Build the path from the enum tuple
        path_str = "/".join(path.value)

        return Request(
            request_id=str(uuid.uuid4()),
            op="write",
            entity=Entity(device=self.id, path=path_str),
            payload=payload,
        )

    def read_value(self, path: "IpsoPath") -> Request:
        """Build a value read request JSON structure.

        Args:
            path: An IpsoPath enum value - a tuple of path components.

        Returns:
            A dictionary containing the read request structure ready to be sent
            to the Lemonbeat API.

        Example:
            >>> # Using a value from a dynamically built Value enum
            >>> device.read_value(device.Value.POWER_TIMER)
            Request(
                request_id="2a8166c5-d60f-4ddd-8735-29aa3661a128",
                op="read",
                entity=Entity(device="device_id", path="lemonbeat/0/power_timer"),
                metadata={}
            )
        """
        # Build the path from the enum tuple
        path_str = "/".join(path.value)

        return Request(
            request_id=str(uuid.uuid4()),
            op="read",
            entity=Entity(device=self.id, path=path_str),
        )