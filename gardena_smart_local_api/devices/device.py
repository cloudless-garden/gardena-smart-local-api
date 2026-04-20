from collections.abc import MutableMapping
from functools import cached_property
from typing import Any, ClassVar, cast

from pydantic import BaseModel, Field, RootModel

from ..messages import EgressMessageList, Entity, Event, Request
from ..model_loader import ModelDefinition, get_model_loader
from ..resources import VALUE_TYPES, IpsoObject, IpsoPath, ValueField
from ..utils import deep_merge_dict, delete_nested_key


def _value_to_payload[T: VALUE_TYPES](value: T) -> dict[str, T]:
    SCALAR_TYPE_MAP = {
        bool: "vb",
        int: "vi",
        float: "vf",
        str: "vs",
        bytes: "vo",
    }

    if isinstance(value, list):
        if len(value) == 0:
            raise TypeError("Empty list")
        if isinstance(value[0], int):
            return ValueField(ai=cast(list[int], value)).model_dump(exclude_none=True)
        elif isinstance(value[0], str):
            return ValueField(as_=cast(list[str], value)).model_dump(exclude_none=True)
        else:
            raise TypeError(f"Unsupported list value type: {type(value[0])}")
    else:
        key = SCALAR_TYPE_MAP.get(type(value))
        if key is None:
            raise TypeError(f"Unsupported value type: {type(value)}")
        return ValueField(**{key: cast(Any, value)}).model_dump(exclude_none=True)


class Device(BaseModel):
    id: str
    data: dict[str, Any] = Field(repr=False)
    model_definition: ModelDefinition = Field()
    service: ClassVar[str] = ""

    @classmethod
    async def _from_raw(cls, device_data: dict[str, Any]) -> "Device | None":
        device_id, device_data = next(iter(device_data.items()))

        model_number: str | None = (
            device_data.get("device", {}).get("0", {}).get("model_number", {}).get("vs")
        )
        if model_number is None:
            raise ValueError("Could not extract model_number from device data")

        model_loader = await get_model_loader()
        model_definition = model_loader.get_model(model_number)
        if model_definition is None:
            return None

        return cls(
            id=device_id,
            data=device_data,
            model_definition=model_definition,
        )

    def update_data(self, event: Event) -> None:
        if event.op == "delete":
            delete_nested_key(self.data, event.entity.path)
            return

        if not event.payload:
            return

        nested: dict[str, Any] = event.payload
        for key in reversed(list(event.entity.path.segments)):
            nested = {key: nested}

        if event.op == "update":
            deep_merge_dict(self.data, nested)
        elif event.op == "overwrite":
            delete_nested_key(self.data, event.entity.path)
            deep_merge_dict(self.data, nested)

    def get_value(self, path: IpsoPath) -> VALUE_TYPES | None:
        obj = self.data
        for key in path.segments:
            if not isinstance(obj, dict):
                return None
            obj = obj.get(key)
        if isinstance(obj, dict):
            return ValueField(**obj).value
        return obj

    def get_field(self, path: IpsoPath) -> ValueField | None:
        obj = self.data

        for key in path.segments:
            if not isinstance(obj, dict):
                return None
            obj = obj.get(key)
        return ValueField(**obj) if isinstance(obj, dict) else None

    def build_write_value_obj(
        self, path: IpsoPath, value: VALUE_TYPES
    ) -> EgressMessageList:
        payload = _value_to_payload(value)

        return EgressMessageList(
            [
                Request(
                    op="write",
                    entity=Entity(device=self.id, path=path, service=self.service),
                    payload=payload,
                )
            ]
        )

    def build_read_value_obj(self, path: IpsoPath) -> EgressMessageList:
        return EgressMessageList(
            [
                Request(
                    op="read",
                    entity=Entity(device=self.id, path=path, service=self.service),
                )
            ]
        )

    def build_execute_obj(
        self, path: IpsoPath, value: VALUE_TYPES | None
    ) -> EgressMessageList:
        payload = _value_to_payload(value) if value is not None else None
        return EgressMessageList(
            [
                Request(
                    op="execute",
                    entity=Entity(device=self.id, path=path, service=self.service),
                    payload=payload,
                )
            ]
        )

    @cached_property
    def objects(self) -> dict[str, dict[str, IpsoObject]]:
        result: dict[str, dict[str, IpsoObject]] = {}
        for object_name, object_data in self.model_definition.objects.items():
            multi_instance = object_data.get("multi_instance", False)
            result[object_name] = {}

            if multi_instance:
                if object_name in self.data:
                    for object_instance_id in self.data[object_name].keys():
                        result[object_name][object_instance_id] = IpsoObject(
                            object_name, object_instance_id, object_data
                        )
            else:
                result[object_name]["0"] = IpsoObject(object_name, "0", object_data)
        return result

    def get_object(self, object_name: str, instance_id: str = "0") -> IpsoObject | None:
        """Get a object by name and instance ID.

        Args:
            object_name: Name of the object (e.g., "actuator", "device")
            instance_id: Instance ID (default: "0")

        Returns:
            DynamicObject if found, None otherwise
        """
        return self.objects.get(object_name, {}).get(instance_id)

    def get_object_instance_ids(self, object_name: str) -> list[str]:
        """Get list of all instance IDs for an object.

        Args:
            object_name: Name of the object

        Returns:
            List of instance ID strings
        """
        return [k for k in self.objects.get(object_name, {}).keys() if k != "_urn"]

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
        return obj.get_value(resource_name, self.data) if obj else None

    def build_set_resource_obj(
        self,
        object_name: str,
        instance_id: str | int,
        resource_name: str,
        value: Any,
    ) -> EgressMessageList:
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

        payload = _value_to_payload(value)
        path = IpsoPath(
            object_name=object_name,
            object_instance_id=str(instance_id),
            resource_name=resource_name,
        )

        return EgressMessageList(
            [
                Request(
                    op="write",
                    entity=Entity(device=self.id, path=path, service=self.service),
                    payload=payload,
                )
            ]
        )

    def build_exclusion_obj(self) -> EgressMessageList:
        return EgressMessageList(
            [
                Request(
                    op="execute",
                    entity=Entity(
                        device=self.id,
                        path=IpsoPath(
                            object_name="device",
                            object_instance_id="0",
                            resource_name="factory_reset",
                        ),
                        service=self.service,
                    ),
                )
            ]
        )

    @property
    def is_online(self) -> bool | None:
        value = self.get_value(
            IpsoPath(
                object_name="connection_status",
                object_instance_id="0",
                resource_name="online",
            )
        )
        if isinstance(value, bool):
            return value
        return None

    def build_refresh_online_status_obj(self) -> EgressMessageList:
        return self.build_read_value_obj(
            IpsoPath(
                object_name="connection_status",
                object_instance_id="0",
                resource_name="online",
            )
        )

    @property
    def serial_number(self) -> str | None:
        value = self.get_value(
            IpsoPath(
                object_name="device",
                object_instance_id="0",
                resource_name="serial_number",
            )
        )
        return str(value) if value else None

    @property
    def manufacturer(self) -> str | None:
        value = self.get_value(
            IpsoPath(
                object_name="device",
                object_instance_id="0",
                resource_name="manufacturer",
            )
        )
        return str(value) if value else None

    @property
    def software_version(self) -> str | None:
        value = self.get_value(
            IpsoPath(
                object_name="device",
                object_instance_id="0",
                resource_name="software_version",
            )
        )
        return str(value) if value else None

    @property
    def hardware_version(self) -> str | None:
        value = self.get_value(
            IpsoPath(
                object_name="device",
                object_instance_id="0",
                resource_name="hardware_version",
            )
        )
        return str(value) if value else None

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(id={self.id!r}, "
            f"model={self.model_definition.name!r})"
        )


class DeviceMap(RootModel[dict[str, Device]], MutableMapping):
    def __add__(self, other: "DeviceMap") -> "DeviceMap":
        return DeviceMap(self.root | other.root)

    def __str__(self) -> str:
        return self.model_dump_json(exclude_none=True)

    def __getitem__(self, key: str) -> Device:
        return self.root[key]

    def __setitem__(self, key: str, value: Device) -> None:
        self.root[key] = value

    def __delitem__(self, key: str) -> None:
        del self.root[key]

    def __iter__(self):
        return iter(self.root.keys())

    def __len__(self) -> int:
        return len(self.root)


def build_discovery_obj() -> EgressMessageList:
    return EgressMessageList(
        [
            Request(
                op="read",
                entity=Entity(
                    service="lemonbeatd", path=IpsoPath(object_name="devices")
                ),
            ),
            Request(
                op="read",
                entity=Entity(
                    service="lwm2mserver", path=IpsoPath(object_name="devices")
                ),
            ),
        ]
    )


def build_inclusion_obj(service: str, instance_id: str) -> EgressMessageList:
    return EgressMessageList(
        [
            Request(
                op="execute",
                entity=Entity(
                    service=service,
                    path=IpsoPath(
                        object_name="includable_device",
                        object_instance_id=instance_id,
                        resource_name="include",
                    ),
                ),
            )
        ]
    )
