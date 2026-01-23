"""Tests for model loader."""

import pytest

from smart_system_local.model_loader import ModelDefinition, get_model_loader


@pytest.mark.asyncio
async def test_model_loader_initialization():
    """Test that model loader can be initialized."""
    # Use the default path
    loader = await get_model_loader()
    assert loader is not None
    assert loader.yaml_path.exists()


@pytest.mark.asyncio
async def test_model_loader_loads_models():
    """Test that models are loaded from YAML."""
    loader = await get_model_loader()
    models = loader.list_models()
    
    assert len(models) > 0
    assert all(isinstance(m, ModelDefinition) for m in models)


@pytest.mark.asyncio
async def test_model_loader_get_model_by_number():
    """Test getting a model by model number."""
    loader = await get_model_loader()
    
    # Model 469 should be Irrigation Control eco
    model = loader.get_model("469")
    assert model is not None
    assert model.model_number == "469"
    assert model.name == "Irrigation Control eco"
    assert model.type == "Irrigation Control eco"


@pytest.mark.asyncio
async def test_model_loader_get_model_by_type():
    """Test getting models by device type."""
    loader = await get_model_loader()
    
    mowers = loader.get_model_by_type("Mower CBT11")
    assert len(mowers) > 0
    assert all(m.type == "Mower CBT11" for m in mowers)


@pytest.mark.asyncio
async def test_model_definition_structure():
    """Test that model definition has expected structure."""
    loader = await get_model_loader()
    model = loader.get_model("469")
    
    assert model is not None
    assert hasattr(model, "objects")
    assert "actuator" in model.objects
    assert "resources" in model.objects["actuator"]
    assert "state" in model.objects["actuator"]["resources"]


@pytest.mark.asyncio
async def test_model_loader_caching():
    """Test that model loader caches results."""
    loader1 = await get_model_loader()
    loader2 = await get_model_loader()
    
    # Should return the same instance
    assert loader1 is loader2


@pytest.mark.asyncio
async def test_model_types():
    """Test that type definitions are loaded."""
    loader = await get_model_loader()
    types = loader.types
    
    assert "vb" in types
    assert types["vb"] == "bool"
    assert "vs" in types
    assert types["vs"] == "str"
    assert "vi" in types
    assert types["vi"] == "int"
