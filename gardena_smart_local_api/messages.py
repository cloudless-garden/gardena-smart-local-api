import uuid
from typing import Literal

from pydantic import BaseModel, Field, RootModel, ValidationError

from .resources import IpsoPath

EventOp = Literal["update", "overwrite", "delete"]


class Entity(BaseModel):
    path: IpsoPath
    service: str | None = None
    device: str | None = None


class Request(BaseModel):
    entity: Entity
    op: str
    payload: dict | None = None
    request_id: str | None = Field(default_factory=lambda: str(uuid.uuid4()))

    def __str__(self) -> str:
        return self.model_dump_json(exclude_none=True)


class EgressMessageList(RootModel[list[Request]]):
    def __add__(self, other: "EgressMessageList") -> "EgressMessageList":
        return EgressMessageList(self.root + other.root)

    def __str__(self) -> str:
        return self.model_dump_json(exclude_none=True)

    def __iter__(self):
        return iter(self.root)

    def __len__(self):
        return len(self.root)

    def __getitem__(self, index):
        return self.root[index]

    def __setitem__(self, index, value):
        self.root[index] = value

    def __delitem__(self, index):
        del self.root[index]


class ErrorMetadata(BaseModel):
    error_source: str


class ErrorMessage(BaseModel):
    payload: dict = Field(default_factory=dict)
    metadata: ErrorMetadata
    success: Literal[False]

    @property
    def error_message(self) -> str:
        return self.payload.get("vs", "Unknown error")

    @property
    def error_source(self) -> str:
        return self.metadata.error_source


class Event(BaseModel):
    payload: dict = Field(default_factory=dict)
    entity: Entity
    op: EventOp


class Reply(BaseModel):
    payload: dict = Field(default_factory=dict)
    entity: Entity
    request_id: str
    success: bool


def validate_message(data: dict) -> Event | Reply | ErrorMessage:
    """Validate incoming message data and return as ErrorMessage, Reply, or Event.

    Args:
        data: The raw message data as a dictionary
    Returns:
        An instance of ErrorMessage, Reply, or Event depending on the message type
    Raises:
        ValueError: If the data does not conform to any of the Message schemas
    """
    for message_cls in (Event, Reply, ErrorMessage):
        try:
            return message_cls.model_validate(data)
        except ValidationError:
            continue

    raise ValueError("Invalid message format")


class IngressMessageList(RootModel[list[Event | Reply | ErrorMessage]]):
    @classmethod
    def model_validate(cls, obj, **kwargs):
        if isinstance(obj, list):
            obj = [
                validate_message(item) if isinstance(item, dict) else item
                for item in obj
            ]
        return super().model_validate(obj, **kwargs)

    def __add__(self, other: "IngressMessageList") -> "IngressMessageList":
        return IngressMessageList(self.root + other.root)

    def __str__(self) -> str:
        return self.model_dump_json(exclude_none=True)

    def __iter__(self):
        return iter(self.root)

    def __len__(self):
        return len(self.root)

    def __getitem__(self, index):
        return self.root[index]

    def __setitem__(self, index, value):
        self.root[index] = value

    def __delitem__(self, index):
        del self.root[index]
