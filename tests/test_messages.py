import json
import uuid

import pytest
from pydantic import ValidationError

from gardena_smart_local_api.messages import (
    EgressMessageList,
    Entity,
    ErrorMessage,
    Event,
    IngressMessageList,
    Reply,
    Request,
)
from gardena_smart_local_api.resources import IpsoPath


def test_request_serialize():
    request = Request(
        op="write",
        entity=Entity(
            device="device_123",
            path=IpsoPath(
                object_name="lemonbeat",
                object_instance_id="0",
                resource_name="command",
            ),
            service="lemonbeatd",
        ),
        payload={"vi": 42},
        request_id="test-request-id",
    )

    json_str = request.model_dump_json(exclude_none=True)
    assert isinstance(json_str, str)

    parsed = json.loads(json_str)
    assert parsed["op"] == "write"
    assert parsed["entity"]["device"] == "device_123"
    assert parsed["entity"]["service"] == "lemonbeatd"
    assert parsed["entity"]["path"] == "lemonbeat/0/command"
    assert parsed["payload"] == {"vi": 42}
    assert parsed["request_id"] == "test-request-id"

    str_output = str(request)
    assert str_output == json_str


def test_request_deserialize():
    json_data = {
        "op": "read",
        "entity": {
            "device": "device_456",
            "path": "connection_status/0/online",
            "service": "lemonbeatd",
        },
        "request_id": "another-request-id",
    }

    request = Request.model_validate(json_data)
    assert request.op == "read"
    assert request.entity.device == "device_456"
    assert request.entity.service == "lemonbeatd"
    assert request.entity.path.object_name == "connection_status"
    assert request.entity.path.object_instance_id == "0"
    assert request.entity.path.resource_name == "online"
    assert request.payload is None
    assert request.request_id == "another-request-id"


def test_request_roundtrip():
    original = Request(
        op="write",
        entity=Entity(
            device="device_789",
            path=IpsoPath(
                object_name="lemonbeat",
                object_instance_id="0",
                resource_name="watering_timer_1",
            ),
        ),
        payload={"vi": 3600},
        request_id="roundtrip-test",
    )

    json_str = original.model_dump_json()

    restored = Request.model_validate_json(json_str)

    assert restored.op == original.op
    assert restored.entity.device == original.entity.device
    assert restored.entity.service == original.entity.service
    assert str(restored.entity.path) == str(original.entity.path)
    assert restored.payload == original.payload
    assert restored.request_id == original.request_id


def test_request_list_serialize():
    request1 = Request(
        op="read",
        entity=Entity(
            device="device_1",
            path=IpsoPath(
                object_name="connection_status",
                object_instance_id="0",
                resource_name="online",
            ),
            service="lemonbeatd",
        ),
        request_id="req-1",
    )

    request2 = Request(
        op="write",
        entity=Entity(
            device="device_2",
            path=IpsoPath(
                object_name="lemonbeat", object_instance_id="0", resource_name="command"
            ),
            service="lemonbeatd",
        ),
        payload={"vi": 5},
        request_id="req-2",
    )

    request_list = EgressMessageList([request1, request2])

    json_str = request_list.model_dump_json(exclude_none=True)
    assert isinstance(json_str, str)

    parsed = json.loads(json_str)
    assert isinstance(parsed, list)
    assert len(parsed) == 2
    assert parsed[0]["op"] == "read"
    assert parsed[0]["request_id"] == "req-1"
    assert parsed[1]["op"] == "write"
    assert parsed[1]["request_id"] == "req-2"
    assert parsed[1]["payload"] == {"vi": 5}

    str_output = str(request_list)
    assert str_output == json_str


def test_request_list_deserialize():
    json_data = [
        {
            "op": "read",
            "entity": {
                "device": "device_a",
                "path": "lemonbeat/0/rf_link_quality",
                "service": "lemonbeatd",
            },
            "request_id": "req-a",
        },
        {
            "op": "write",
            "entity": {
                "device": "device_b",
                "path": "lemonbeat/0/button_config_time",
                "service": "lemonbeatd",
            },
            "payload": {"vi": 300},
            "request_id": "req-b",
        },
    ]

    request_list = EgressMessageList.model_validate(json_data)
    assert len(request_list.root) == 2

    assert request_list.root[0].op == "read"
    assert request_list.root[0].entity.device == "device_a"
    assert str(request_list.root[0].entity.path) == "lemonbeat/0/rf_link_quality"
    assert request_list.root[0].payload is None

    assert request_list.root[1].op == "write"
    assert request_list.root[1].entity.device == "device_b"
    assert str(request_list.root[1].entity.path) == "lemonbeat/0/button_config_time"
    assert request_list.root[1].payload == {"vi": 300}


def test_request_list_roundtrip():
    request1 = Request(
        op="read",
        entity=Entity(
            device="dev_x",
            path=IpsoPath(
                object_name="device",
                object_instance_id="0",
                resource_name="serial_number",
            ),
        ),
        request_id="x-req-1",
    )

    request2 = Request(
        op="read",
        entity=Entity(
            device="dev_y",
            path=IpsoPath(
                object_name="device",
                object_instance_id="0",
                resource_name="manufacturer",
            ),
        ),
        request_id="y-req-2",
    )

    original = EgressMessageList([request1, request2])

    json_str = original.model_dump_json()

    restored = EgressMessageList.model_validate_json(json_str)

    for i, (orig_req, rest_req) in enumerate(
        zip(original.root, restored.root, strict=True)
    ):
        assert rest_req.op == orig_req.op, f"Request {i} op mismatch"
        assert rest_req.entity.device == orig_req.entity.device, (
            f"Request {i} device mismatch"
        )
        assert str(rest_req.entity.path) == str(orig_req.entity.path), (
            f"Request {i} path mismatch"
        )
        assert rest_req.payload == orig_req.payload, f"Request {i} payload mismatch"
        assert rest_req.request_id == orig_req.request_id, (
            f"Request {i} request_id mismatch"
        )


def test_request_list_addition():
    req1 = Request(
        op="read",
        entity=Entity(
            device="dev1",
            path=IpsoPath(
                object_name="device",
                object_instance_id="0",
                resource_name="serial_number",
            ),
        ),
        request_id="req1",
    )

    req2 = Request(
        op="read",
        entity=Entity(
            device="dev2",
            path=IpsoPath(
                object_name="device",
                object_instance_id="0",
                resource_name="manufacturer",
            ),
        ),
        request_id="req2",
    )

    req3 = Request(
        op="write",
        entity=Entity(
            device="dev3",
            path=IpsoPath(
                object_name="lemonbeat", object_instance_id="0", resource_name="command"
            ),
        ),
        payload={"vi": 1},
        request_id="req3",
    )

    list1 = EgressMessageList([req1, req2])
    list2 = EgressMessageList([req3])

    combined = list1 + list2

    assert isinstance(combined, EgressMessageList)
    assert len(combined.root) == 3
    assert combined.root[0].request_id == "req1"
    assert combined.root[1].request_id == "req2"
    assert combined.root[2].request_id == "req3"


def test_request_without_payload():
    request = Request(
        op="read",
        entity=Entity(
            device="device_no_payload",
            path=IpsoPath(
                object_name="device",
                object_instance_id="0",
                resource_name="serial_number",
            ),
        ),
        request_id="no-payload-req",
    )

    json_str = request.model_dump_json(exclude_none=True)
    parsed = json.loads(json_str)
    assert "payload" not in parsed

    restored = Request.model_validate_json(json_str)
    assert restored.payload is None


def test_request_auto_generated_id():
    request = Request(
        op="read",
        entity=Entity(
            device="device_auto_id",
            path=IpsoPath(
                object_name="device",
                object_instance_id="0",
                resource_name="serial_number",
            ),
        ),
    )

    assert request.request_id is not None
    assert uuid.UUID(request.request_id).version == 4

    # Each request gets a unique ID
    request2 = Request(
        op="read",
        entity=Entity(
            device="device_auto_id",
            path=IpsoPath(
                object_name="device",
                object_instance_id="0",
                resource_name="serial_number",
            ),
        ),
    )
    assert request.request_id != request2.request_id


def test_empty_request_list():
    empty_list = EgressMessageList([])

    assert len(empty_list.root) == 0

    json_str = empty_list.model_dump_json()
    assert json_str == "[]"

    restored = EgressMessageList.model_validate_json(json_str)
    assert len(restored.root) == 0


def test_message_list_deserialize_water_control_reply(water_control_message):
    assert len(water_control_message) == 1
    msg = water_control_message[0]
    assert isinstance(msg, Reply)
    assert msg.success is True
    assert msg.request_id == "2a8166c5-d60f-4ddd-8735-29aa3661a128"
    assert str(msg.entity.path) == "devices"


def test_message_list_deserialize_update_event(update_event):
    assert len(update_event) == 1
    msg = update_event[0]
    assert isinstance(msg, Event)
    assert msg.op == "update"
    assert msg.entity.device == "3034F8EE90126D400001737D"


def test_message_list_deserialize_combined(water_control_and_update_event):
    assert len(water_control_and_update_event) == 2
    assert isinstance(water_control_and_update_event[0], Reply)
    assert isinstance(water_control_and_update_event[1], Event)


def test_message_list_str_preserves_subtype_fields(water_control_and_update_event):
    parsed = json.loads(str(water_control_and_update_event))
    reply_json = parsed[0]
    assert "entity" in reply_json
    assert "success" in reply_json
    assert "request_id" in reply_json

    event_json = parsed[1]
    assert "entity" in event_json
    assert "op" in event_json


def test_message_list_model_validate_json_invalid_json():
    with pytest.raises(ValidationError):
        IngressMessageList.model_validate_json("not valid json")


def test_message_list_model_validate_json_not_a_list():
    with pytest.raises(ValidationError):
        IngressMessageList.model_validate_json('{"op": "update"}')


def test_message_list_model_validate_invalid_item():
    with pytest.raises(ValueError, match="Invalid message format"):
        IngressMessageList.model_validate([{"completely_unknown_field": 123}])


def test_message_list_deserialize_error_message():
    error_data = {
        "success": False,
        "metadata": {"error_source": "lemonbeatd"},
        "payload": {"vs": "device unreachable"},
    }
    message_list = IngressMessageList.model_validate([error_data])

    assert len(message_list.root) == 1
    msg = message_list.root[0]
    assert isinstance(msg, ErrorMessage)
    assert msg.success is False
    assert msg.error_source == "lemonbeatd"
    assert msg.error_message == "device unreachable"


def test_message_list_deserialize_error_message_default_error_text():
    error_data = {
        "success": False,
        "metadata": {"error_source": "lemonbeatd"},
        "payload": {},
    }
    msg = IngressMessageList.model_validate([error_data]).root[0]
    assert isinstance(msg, ErrorMessage)
    assert msg.error_message == "Unknown error"
