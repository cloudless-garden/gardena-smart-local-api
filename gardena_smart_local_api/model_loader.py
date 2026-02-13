from pathlib import Path
from typing import Any, Literal

import yaml
from aiofile import async_open
from pydantic import BaseModel, Field

DEFAULT_PATH = Path(__file__).parent / "schema" / "device_models.yaml"


class BaseModelDefinition(BaseModel):
    model_number: str
    name: str
    type: str
    description: str | None = None
    objects: dict[str, dict[str, Any]] = Field(default_factory=dict)

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(model_number={self.model_number!r}, "
            f"name={self.name!r}, type={self.type!r})"
        )


class Gen1ModelDefinition(BaseModelDefinition):
    protocol: Literal["gen1"] = "gen1"
    commands: dict[str, int] = Field(default_factory=dict)


PROTOCOL_MAP = {
    "gen1": Gen1ModelDefinition,
}

ModelDefinition = Gen1ModelDefinition


class ModelLoader:
    def __init__(self, yaml_path: Path | str = DEFAULT_PATH):
        self.yaml_path = Path(yaml_path)
        if not self.yaml_path.exists():
            raise FileNotFoundError(f"Device models file not found: {self.yaml_path}")

        self._types: dict[str, str] = {}
        self._models: dict[str, ModelDefinition] = {}
        self._loaded = False

    def parse_model_definition(
        self, model_number: str, data: dict[str, Any]
    ) -> ModelDefinition:
        protocol = data.get("protocol")
        if protocol in PROTOCOL_MAP:
            return PROTOCOL_MAP[protocol](model_number=model_number, **data)
        else:
            raise ValueError(f"Unknown protocol: {protocol}")

    async def load(self) -> None:
        if self._loaded:
            return

        async with async_open(self.yaml_path, mode="r") as f:
            content = await f.read()

        data = yaml.safe_load(content)
        self._types = data.get("types", {})
        self._models = {
            model_number: self.parse_model_definition(model_number, model_data)
            for model_number, model_data in data.get("models", {}).items()
        }
        self._loaded = True

    @property
    def types(self) -> dict[str, str]:
        return self._types

    def get_model(self, model_number: str | int) -> ModelDefinition | None:
        return self._models.get(str(model_number))


_loader_cache: dict[Path, ModelLoader] = {}


async def get_model_loader(yaml_path: Path | str = DEFAULT_PATH) -> ModelLoader:
    path = Path(yaml_path).resolve()

    if path not in _loader_cache:
        loader = ModelLoader(path)
        await loader.load()
        _loader_cache[path] = loader

    return _loader_cache[path]
