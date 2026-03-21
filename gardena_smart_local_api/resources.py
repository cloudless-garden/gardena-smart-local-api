from base64 import b64decode, b64encode
from collections.abc import Iterator
from datetime import datetime
from typing import Annotated, Any

from pydantic import (
    BaseModel,
    BeforeValidator,
    PlainSerializer,
    model_serializer,
    model_validator,
)


def _parse_opaque(v: object) -> bytes | None:
    if v is None:
        return None
    if isinstance(v, (bytes, bytearray)):
        return bytes(v)
    if isinstance(v, str):
        return b64decode(v)
    raise ValueError(f"Expected bytes or base64 string, got {type(v)}")


type Opaque = Annotated[
    bytes,
    BeforeValidator(_parse_opaque),
    PlainSerializer(lambda v: b64encode(v).decode(), return_type=str),
]


type VALUE_TYPES = bool | int | float | str | Opaque


class ValueField(BaseModel):
    vb: bool | None = None
    vs: str | None = None
    vi: int | None = None
    vo: Opaque | None = None
    vf: float | None = None
    vt: int | None = None
    ts: int | None = None

    @property
    def value(self) -> VALUE_TYPES | None:
        return next(
            (
                getattr(self, field)
                for field in ValueField.model_fields
                if field != "ts" and getattr(self, field) is not None
            ),
            None,
        )

    @property
    def timestamp(self) -> datetime | None:
        return datetime.fromtimestamp(self.ts) if self.ts else None


class IpsoPath(BaseModel):
    object_name: str | None = None
    object_instance_id: str | None = None
    resource_name: str | None = None
    resource_instance_id: int | None = None

    @model_validator(mode="before")
    @classmethod
    def validate_from_string(cls, data: Any) -> Any:
        """Allow deserialization from string path like 'devices/12345/resource/0'."""
        if isinstance(data, str):
            parts = data.split("/")
            result = {}
            if len(parts) >= 1 and parts[0]:
                result["object_name"] = parts[0]
            if len(parts) >= 2 and parts[1]:
                result["object_instance_id"] = parts[1]
            if len(parts) >= 3 and parts[2]:
                result["resource_name"] = parts[2]
            if len(parts) >= 4 and parts[3]:
                try:
                    result["resource_instance_id"] = int(parts[3])
                except ValueError:
                    pass
            return result
        return data

    @model_serializer
    def serialize_model(self):
        return str(self)

    @property
    def segments(self) -> Iterator[str]:
        if self.object_name is not None:
            yield self.object_name
        if self.object_instance_id is not None:
            yield self.object_instance_id
        if self.resource_name is not None:
            yield self.resource_name
        if self.resource_instance_id is not None:
            yield str(self.resource_instance_id)

    def __str__(self) -> str:
        return "/".join(self.segments)


class IpsoResource:
    def __init__(
        self,
        name: str,
        resource_data: dict[str, Any],
        object_name: str,
        object_instance_id: str,
        resource_instance_id: int | None = None,
    ):
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
    def path(self) -> IpsoPath:
        return IpsoPath(
            object_name=self.object_name,
            object_instance_id=self.object_instance_id,
            resource_name=self.name,
            resource_instance_id=self.resource_instance_id,
        )

    @property
    def is_readable(self) -> bool:
        return self.access in ("r", "rw") if self.access else False

    @property
    def is_writable(self) -> bool:
        return self.access in ("w", "rw") if self.access else False

    def get_value(self, raw_data: dict[str, Any]) -> Any | None:
        obj = raw_data

        for key in self.path.segments:
            if not isinstance(obj, dict):
                return None
            obj = obj.get(key)
            if obj is None:
                return None

        if isinstance(obj, dict):
            return ValueField(**obj).value
        return obj

    def get_field(self, raw_data: dict[str, Any]) -> ValueField | None:
        obj = raw_data
        for key in self.path.segments:
            if not isinstance(obj, dict):
                return None
            obj = obj.get(key)
            if obj is None:
                return None

        return ValueField(**obj) if isinstance(obj, dict) else None

    def __repr__(self) -> str:
        return (
            f"IpsoResource({self.object_name}/{self.object_instance_id}/{self.name}, "
            f"type={self.type}, access={self.access}, "
            f"resource_instance_id={self.resource_instance_id})"
        )


class IpsoObject:
    def __init__(
        self,
        name: str,
        object_instance_id: str,
        object_data: dict[str, Any],
    ):
        self.name = name
        self.object_instance_id = object_instance_id
        self.object_id = object_data.get("object_id")
        self.object_urn = object_data.get("object_urn")
        self.object_version = object_data.get("object_version")
        self.mandatory = object_data.get("mandatory", False)
        self.multi_instance = object_data.get("multi_instance", False)

        self.resources: dict[str, IpsoResource] = {}
        for resource_name, resource_data in object_data.get("resources", {}).items():
            self.resources[resource_name] = IpsoResource(
                resource_name, resource_data, name, object_instance_id
            )

    def get_resource(self, resource_name: str) -> IpsoResource | None:
        return self.resources.get(resource_name)

    def get_value(self, resource_name: str, raw_data: dict[str, Any]) -> Any | None:
        resource = self.get_resource(resource_name)
        return resource.get_value(raw_data) if resource else None

    def list_resources(self) -> list[str]:
        return list(self.resources.keys())

    def __repr__(self) -> str:
        return (
            f"IpsoObject({self.name}[{self.object_instance_id}], "
            f"{len(self.resources)} resources)"
        )
