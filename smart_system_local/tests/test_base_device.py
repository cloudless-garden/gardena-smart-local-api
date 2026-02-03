"""Tests for BaseDevice methods that return Request objects."""

import pytest
import uuid

from smart_system_local.devices.base import BaseDevice, DeviceCommand, IpsoPath
from smart_system_local.devices.messages import Request, Entity


# Test fixtures and helper classes
class SampleCommand(DeviceCommand):
    """Test commands for testing."""

    START = 1
    STOP = 2
    PARK = 3


class SampleValue(IpsoPath):
    """Test value paths for testing."""

    POWER_TIMER = ("lemonbeat", "0", "power_timer")
    STATE = ("actuator", "0", "state")
    ENABLED = ("actuator", "0", "enabled")
    TEMPERATURE = ("sensor", "0", "temperature")


@pytest.fixture
def sample_device():
    """Create a sample device for testing."""
    device_data = {
        "device": {
            "0": {
                "model_number": {"vs": "469"},
                "serial_number": {"vs": "12345678"},
                "manufacturer": {"vs": "GARDENA"},
            }
        },
        "lemonbeat": {
            "0": {
                "power_timer": {"vi": 3600},
                "software_version": {"vs": "1.2.3"},
            }
        },
        "actuator": {
            "0": {
                "state": {"vi": 1},
                "enabled": {"vb": True},
            }
        },
        "sensor": {
            "0": {
                "temperature": {"vf": 23.5},
            }
        },
    }
    return BaseDevice(id="test_device_123", raw=device_data)


class TestBuildCommand:
    """Tests for build_command method."""

    @pytest.mark.asyncio
    async def test_build_command_creates_request(self, sample_device):
        """Test that build_command returns a Request object."""
        request = sample_device.build_command(SampleCommand.START)

        assert isinstance(request, Request)

    @pytest.mark.asyncio
    async def test_build_command_has_correct_operation(self, sample_device):
        """Test that build_command creates a write operation."""
        request = sample_device.build_command(SampleCommand.START)

        assert request.op == "write"

    @pytest.mark.asyncio
    async def test_build_command_has_correct_entity(self, sample_device):
        """Test that build_command has correct entity."""
        request = sample_device.build_command(SampleCommand.START)

        assert request.entity is not None
        assert request.entity.device == "test_device_123"
        assert request.entity.path == "lemonbeat/0/command"

    @pytest.mark.asyncio
    async def test_build_command_has_correct_payload(self, sample_device):
        """Test that build_command has correct payload with command value."""
        request = sample_device.build_command(SampleCommand.START)

        assert request.payload is not None
        assert "vi" in request.payload
        assert request.payload["vi"] == SampleCommand.START.value

    @pytest.mark.asyncio
    async def test_build_command_different_commands(self, sample_device):
        """Test that different commands produce different payloads."""
        request1 = sample_device.build_command(SampleCommand.START)
        request2 = sample_device.build_command(SampleCommand.PARK)

        assert request1.payload["vi"] == SampleCommand.START.value
        assert request2.payload["vi"] == SampleCommand.PARK.value
        assert request1.payload["vi"] != request2.payload["vi"]

    @pytest.mark.asyncio
    async def test_build_command_has_request_id(self, sample_device):
        """Test that build_command generates a request_id."""
        request = sample_device.build_command(SampleCommand.START)

        assert request.request_id is not None
        # Verify it's a valid UUID
        uuid.UUID(request.request_id)

    @pytest.mark.asyncio
    async def test_build_command_unique_request_ids(self, sample_device):
        """Test that each call generates a unique request_id."""
        request1 = sample_device.build_command(SampleCommand.START)
        request2 = sample_device.build_command(SampleCommand.START)

        assert request1.request_id != request2.request_id


class TestWriteValue:
    """Tests for write_value method."""

    @pytest.mark.asyncio
    async def test_write_value_int_creates_request(self, sample_device):
        """Test that write_value returns a Request object for integer values."""
        request = sample_device.write_value(SampleValue.POWER_TIMER, 7200)

        assert isinstance(request, Request)

    @pytest.mark.asyncio
    async def test_write_value_has_correct_operation(self, sample_device):
        """Test that write_value creates a write operation."""
        request = sample_device.write_value(SampleValue.POWER_TIMER, 7200)

        assert request.op == "write"

    @pytest.mark.asyncio
    async def test_write_value_int_has_correct_payload(self, sample_device):
        """Test that write_value creates correct payload for integer."""
        request = sample_device.write_value(SampleValue.POWER_TIMER, 7200)

        assert request.payload is not None
        assert "vi" in request.payload
        assert request.payload["vi"] == 7200

    @pytest.mark.asyncio
    async def test_write_value_bool_has_correct_payload(self, sample_device):
        """Test that write_value creates correct payload for boolean."""
        request = sample_device.write_value(SampleValue.ENABLED, False)

        assert request.payload is not None
        assert "vb" in request.payload
        assert request.payload["vb"] is False

    @pytest.mark.asyncio
    async def test_write_value_float_has_correct_payload(self, sample_device):
        """Test that write_value creates correct payload for float."""
        request = sample_device.write_value(SampleValue.TEMPERATURE, 25.5)

        assert request.payload is not None
        assert "vf" in request.payload
        assert request.payload["vf"] == 25.5

    @pytest.mark.asyncio
    async def test_write_value_string_has_correct_payload(self, sample_device):
        """Test that write_value creates correct payload for string."""
        # Create a string-type path for testing
        class StringPath(IpsoPath):
            NAME = ("device", "0", "name")

        request = sample_device.write_value(StringPath.NAME, "My Device")

        assert request.payload is not None
        assert "vs" in request.payload
        assert request.payload["vs"] == "My Device"

    @pytest.mark.asyncio
    async def test_write_value_has_correct_entity(self, sample_device):
        """Test that write_value has correct entity path."""
        request = sample_device.write_value(SampleValue.POWER_TIMER, 7200)

        assert request.entity is not None
        assert request.entity.device == "test_device_123"
        assert request.entity.path == "lemonbeat/0/power_timer"

    @pytest.mark.asyncio
    async def test_write_value_different_paths(self, sample_device):
        """Test that different paths produce different entity paths."""
        request1 = sample_device.write_value(SampleValue.POWER_TIMER, 7200)
        request2 = sample_device.write_value(SampleValue.STATE, 2)

        assert request1.entity.path == "lemonbeat/0/power_timer"
        assert request2.entity.path == "actuator/0/state"

    @pytest.mark.asyncio
    async def test_write_value_has_request_id(self, sample_device):
        """Test that write_value generates a request_id."""
        request = sample_device.write_value(SampleValue.POWER_TIMER, 7200)

        assert request.request_id is not None
        # Verify it's a valid UUID
        uuid.UUID(request.request_id)

    @pytest.mark.asyncio
    async def test_write_value_unique_request_ids(self, sample_device):
        """Test that each call generates a unique request_id."""
        request1 = sample_device.write_value(SampleValue.POWER_TIMER, 7200)
        request2 = sample_device.write_value(SampleValue.POWER_TIMER, 7200)

        assert request1.request_id != request2.request_id

    @pytest.mark.asyncio
    async def test_write_value_unsupported_type_raises_error(self, sample_device):
        """Test that write_value raises TypeError for unsupported types."""
        with pytest.raises(TypeError, match="Unsupported value type"):
            sample_device.write_value(SampleValue.POWER_TIMER, [1, 2, 3])

    @pytest.mark.asyncio
    async def test_write_value_bool_true(self, sample_device):
        """Test writing True boolean value."""
        request = sample_device.write_value(SampleValue.ENABLED, True)

        assert request.payload["vb"] is True

    @pytest.mark.asyncio
    async def test_write_value_zero_int(self, sample_device):
        """Test writing zero as integer."""
        request = sample_device.write_value(SampleValue.POWER_TIMER, 0)

        assert request.payload["vi"] == 0


class TestReadValue:
    """Tests for read_value method."""

    @pytest.mark.asyncio
    async def test_read_value_creates_request(self, sample_device):
        """Test that read_value returns a Request object."""
        request = sample_device.read_value(SampleValue.POWER_TIMER)

        assert isinstance(request, Request)

    @pytest.mark.asyncio
    async def test_read_value_has_correct_operation(self, sample_device):
        """Test that read_value creates a read operation."""
        request = sample_device.read_value(SampleValue.POWER_TIMER)

        assert request.op == "read"

    @pytest.mark.asyncio
    async def test_read_value_has_correct_entity(self, sample_device):
        """Test that read_value has correct entity path."""
        request = sample_device.read_value(SampleValue.POWER_TIMER)

        assert request.entity is not None
        assert request.entity.device == "test_device_123"
        assert request.entity.path == "lemonbeat/0/power_timer"

    @pytest.mark.asyncio
    async def test_read_value_no_payload(self, sample_device):
        """Test that read_value has no payload."""
        request = sample_device.read_value(SampleValue.POWER_TIMER)

        # Read operations typically don't have a payload
        assert request.payload is None

    @pytest.mark.asyncio
    async def test_read_value_different_paths(self, sample_device):
        """Test that different paths produce different entity paths."""
        request1 = sample_device.read_value(SampleValue.POWER_TIMER)
        request2 = sample_device.read_value(SampleValue.STATE)

        assert request1.entity.path == "lemonbeat/0/power_timer"
        assert request2.entity.path == "actuator/0/state"

    @pytest.mark.asyncio
    async def test_read_value_has_request_id(self, sample_device):
        """Test that read_value generates a request_id."""
        request = sample_device.read_value(SampleValue.POWER_TIMER)

        assert request.request_id is not None
        # Verify it's a valid UUID
        uuid.UUID(request.request_id)

    @pytest.mark.asyncio
    async def test_read_value_unique_request_ids(self, sample_device):
        """Test that each call generates a unique request_id."""
        request1 = sample_device.read_value(SampleValue.POWER_TIMER)
        request2 = sample_device.read_value(SampleValue.POWER_TIMER)

        assert request1.request_id != request2.request_id

    @pytest.mark.asyncio
    async def test_read_value_complex_path(self, sample_device):
        """Test reading value with complex path."""
        request = sample_device.read_value(SampleValue.TEMPERATURE)

        assert request.entity.path == "sensor/0/temperature"


class TestRequestsIntegration:
    """Integration tests for Request-returning methods."""

    @pytest.mark.asyncio
    async def test_all_methods_return_request_objects(self, sample_device):
        """Test that all three methods return Request objects."""
        cmd_req = sample_device.build_command(SampleCommand.START)
        write_req = sample_device.write_value(SampleValue.POWER_TIMER, 7200)
        read_req = sample_device.read_value(SampleValue.POWER_TIMER)

        assert isinstance(cmd_req, Request)
        assert isinstance(write_req, Request)
        assert isinstance(read_req, Request)

    @pytest.mark.asyncio
    async def test_all_methods_have_unique_request_ids(self, sample_device):
        """Test that all methods generate unique request IDs."""
        cmd_req = sample_device.build_command(SampleCommand.START)
        write_req = sample_device.write_value(SampleValue.POWER_TIMER, 7200)
        read_req = sample_device.read_value(SampleValue.POWER_TIMER)

        request_ids = {cmd_req.request_id, write_req.request_id, read_req.request_id}
        assert len(request_ids) == 3  # All unique

    @pytest.mark.asyncio
    async def test_all_methods_have_correct_device_id(self, sample_device):
        """Test that all methods use the correct device ID."""
        cmd_req = sample_device.build_command(SampleCommand.START)
        write_req = sample_device.write_value(SampleValue.POWER_TIMER, 7200)
        read_req = sample_device.read_value(SampleValue.POWER_TIMER)

        assert cmd_req.entity.device == "test_device_123"
        assert write_req.entity.device == "test_device_123"
        assert read_req.entity.device == "test_device_123"

    @pytest.mark.asyncio
    async def test_requests_can_be_serialized_to_dict(self, sample_device):
        """Test that Request objects can be serialized to dict."""
        cmd_req = sample_device.build_command(SampleCommand.START)
        write_req = sample_device.write_value(SampleValue.POWER_TIMER, 7200)
        read_req = sample_device.read_value(SampleValue.POWER_TIMER)

        # Pydantic models have model_dump method
        cmd_dict = cmd_req.model_dump()
        write_dict = write_req.model_dump()
        read_dict = read_req.model_dump()

        assert isinstance(cmd_dict, dict)
        assert isinstance(write_dict, dict)
        assert isinstance(read_dict, dict)

        # Verify structure
        assert "op" in cmd_dict
        assert "entity" in cmd_dict
        assert "payload" in cmd_dict

    @pytest.mark.asyncio
    async def test_request_entity_structure(self, sample_device):
        """Test that Entity objects have the correct structure."""
        request = sample_device.build_command(SampleCommand.START)

        assert hasattr(request.entity, "path")
        assert hasattr(request.entity, "device")
        assert isinstance(request.entity, Entity)
