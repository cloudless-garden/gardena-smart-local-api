"""Tests for dynamic device system."""

import json
import pytest
from pathlib import Path

from smart_system_local.devices.messages import Response


@pytest.fixture
def lemonbeat_command_response():
    """Load lemonbeat command response from test data."""
    data_file = Path(__file__).parent / "data" / "lemonbeat_command_response.json"
    with open(data_file) as f:
        return json.load(f)


@pytest.mark.asyncio
async def test_parsing_response(lemonbeat_command_response):
    response = Response(**lemonbeat_command_response[0])
    assert response is not None
    assert response.success
    assert response.entity is not None
    assert response.device_id == "3034F8EE901267400000B333"
    assert response.payload is None
