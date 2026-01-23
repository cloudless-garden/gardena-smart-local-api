from pathlib import Path
from typing import Any, Literal

from aiofile import async_open
from pydantic import BaseModel, Field
import yaml

DEFAULT_PATH = Path(__file__).parent / "schema" / "device_models.yaml"


class BaseModelDefinition(BaseModel):
    model_number: str
    name: str
    type: str
    description: str | None = None
    objects: dict[str, dict[str, Any]] = Field(default_factory=dict)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(model_number={self.model_number!r}, name={self.name!r}, type={self.type!r})"


class LemonbeatModelDefinition(BaseModelDefinition):
    protocol: Literal["lemonbeat"] = "lemonbeat"
    commands: dict[str, int] = Field(default_factory=dict)


class Lwm2mModelDefinition(BaseModelDefinition):
    protocol: Literal["lwm2m"] = "lwm2m"


ModelDefinition = LemonbeatModelDefinition | Lwm2mModelDefinition


def parse_model_definition(model_number: str, data: dict[str, Any]) -> ModelDefinition:
    """Parse raw YAML data into the appropriate ModelDefinition subclass."""
    protocol = data.get("protocol")
    if protocol == "lemonbeat":
        return LemonbeatModelDefinition(model_number=model_number, **data)
    elif protocol == "lwm2m":
        return Lwm2mModelDefinition(model_number=model_number, **data)
    else:
        raise ValueError(f"Unknown protocol: {protocol}")


class ModelLoader:
    """Loads and caches device models from YAML files."""

    def __init__(self, yaml_path: Path | str = DEFAULT_PATH):
        """Initialize the model loader.

        Args:
            yaml_path: Path to device_models.yaml. If None, uses default location.
        """
        self.yaml_path = Path(yaml_path)
        if not self.yaml_path.exists():
            raise FileNotFoundError(f"Device models file not found: {self.yaml_path}")

        self._types: dict[str, str] = {}
        self._models: dict[str, ModelDefinition] = {}
        self._loaded = False

    async def load(self) -> None:
        if self._loaded:
            return

        async with async_open(self.yaml_path, mode="r") as f:
            content = await f.read()

        data = yaml.safe_load(content)
        self._types = data.get("types", {})
        self._models = {
            model_number: parse_model_definition(model_number, model_data)
            for model_number, model_data in data.get("models", {}).items()
        }
        self._loaded = True

    @property
    def types(self) -> dict[str, str]:
        """Get resource type definitions."""
        return self._types

    def get_model(self, model_number: str) -> ModelDefinition | None:
        """Get a model definition by model number."""
        return self._models.get(model_number)

    def get_model_by_type(self, device_type: str) -> list[ModelDefinition]:
        """Get all models matching a device type."""
        return [m for m in self._models.values() if m.type == device_type]

    def list_models(self) -> list[ModelDefinition]:
        """Get all available model definitions."""
        return list(self._models.values())


_loader_cache: dict[Path, ModelLoader] = {}

async def get_model_loader(yaml_path: Path | str = DEFAULT_PATH) -> ModelLoader:
    path = Path(yaml_path).resolve()

    if path not in _loader_cache:
        loader = ModelLoader(path)
        await loader.load()
        _loader_cache[path] = loader

    return _loader_cache[path]

