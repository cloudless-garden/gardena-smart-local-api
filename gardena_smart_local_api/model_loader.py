import asyncio
from pathlib import Path
from typing import Any, Literal

import yaml
from aiofile import async_open
from pydantic import BaseModel, Field

DEFAULT_SCHEMA_DIR = Path(__file__).parent / "schema"


class BaseModelDefinition(BaseModel):
    model_number: str
    name: str
    description: str | None = None
    objects: dict[str, dict[str, Any]] = Field(default_factory=dict)

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(model_number={self.model_number!r}, "
            f"name={self.name!r})"
        )


class Gen1ModelDefinition(BaseModelDefinition):
    protocol: Literal["gen1"] = "gen1"
    commands: dict[str, int] = Field(default_factory=dict)


class Gen2ModelDefinition(BaseModelDefinition):
    protocol: Literal["gen2"] = "gen2"


PROTOCOL_MAP = {
    "gen1": Gen1ModelDefinition,
    "gen2": Gen2ModelDefinition,
}

ModelDefinition = Gen1ModelDefinition | Gen2ModelDefinition


class ModelLoader:
    def __init__(self, schema_dir: Path | str = DEFAULT_SCHEMA_DIR):
        self.schema_dir = Path(schema_dir)
        if not self.schema_dir.is_dir():
            raise FileNotFoundError(f"Schema directory not found: {self.schema_dir}")

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

        model_files = await asyncio.to_thread(
            lambda: sorted(self.schema_dir.glob("*.yaml"))
        )
        for model_file in model_files:
            model_number = model_file.stem.split("_")[0]
            async with async_open(model_file, mode="r") as f:
                data = yaml.safe_load(await f.read())
            self._models[model_number] = self.parse_model_definition(model_number, data)

        self._loaded = True

    def get_model(self, model_number: str | int) -> ModelDefinition | None:
        return self._models.get(str(model_number))


_loader_cache: dict[Path, ModelLoader] = {}


async def get_model_loader(schema_dir: Path | str = DEFAULT_SCHEMA_DIR) -> ModelLoader:
    path = Path(schema_dir).resolve()

    if path not in _loader_cache:
        loader = ModelLoader(path)
        await loader.load()
        _loader_cache[path] = loader

    return _loader_cache[path]
