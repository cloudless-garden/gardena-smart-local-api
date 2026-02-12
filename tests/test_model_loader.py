import pytest

from gardena_smart_local_api.model_loader import get_model_loader


@pytest.mark.asyncio
async def test_model_loader_initialization():
    # Use the default path
    loader = await get_model_loader()
    assert loader is not None
    assert loader.yaml_path.exists()


@pytest.mark.asyncio
async def test_model_loader_get_model_by_number():
    loader = await get_model_loader()

    model = loader.get_model("18869")
    assert model is not None
    assert model.model_number == "18869"
    assert model.name == "Water Control"
    assert model.type == "Water Control"


@pytest.mark.asyncio
async def test_model_definition_structure():
    loader = await get_model_loader()
    model = loader.get_model("18869")

    assert model is not None
    assert hasattr(model, "objects")
    assert "lemonbeat" in model.objects
    assert "resources" in model.objects["lemonbeat"]
    assert "watering_timer_1" in model.objects["lemonbeat"]["resources"]


@pytest.mark.asyncio
async def test_model_loader_caching():
    loader1 = await get_model_loader()
    loader2 = await get_model_loader()

    assert loader1 is loader2
