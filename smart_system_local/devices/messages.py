from pydantic import BaseModel


class Entity(BaseModel):
    """Entity information in Smart System Local responses."""

    path: str = ""
    service: str | None = None
    device: str | None = None


class ResponseMetadata(BaseModel):
    """Metadata for Smart System Local API responses."""

    sequence: int | None = None
    source: str | None = None
    error_source: str | None = None


class Request(BaseModel):
    """Request to Smart System Local API."""

    entity: Entity
    op: str
    payload: dict | None = None
    request_id: str | None = None


class Event(BaseModel):
    """Event received from Smart System Local API."""

    entity: Entity | None = None
    metadata: ResponseMetadata | None = None
    op: str | None = None
    payload: dict | None = None


class Response(BaseModel):
    """Response from a Smart System Local command execution."""

    request_id: str
    success: bool | None = None
    entity: Entity | None = None
    metadata: ResponseMetadata | None = None
    payload: dict | None = None

    @property
    def device_id(self) -> str | None:
        """Get the device ID from the entity."""
        return self.entity.device if self.entity else None

    @property
    def command_path(self) -> str | None:
        """Get the command path from the entity."""
        return self.entity.path if self.entity else None

    @property
    def sequence(self) -> int | None:
        """Get the sequence number from metadata."""
        return self.metadata.sequence if self.metadata else None

    @property
    def source(self) -> str | None:
        """Get the source from metadata."""
        return self.metadata.source if self.metadata else None

    @property
    def error_source(self) -> str | None:
        """Get the error source from metadata."""
        return self.metadata.error_source if self.metadata else None
