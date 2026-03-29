import pytest

from gardena_smart_local_api.resources import ValueField


@pytest.mark.parametrize(
    "plain, serialized",
    [
        ([0], '{"ai":["0=0"]}'),
        ([1], '{"ai":["0=1"]}'),
        ([1, 2], '{"ai":["0=1,1=2"]}'),
    ],
)
def test_value_field_serialize_ai(plain, serialized):
    vf = ValueField(ai=plain)
    assert vf.model_dump_json(exclude_none=True) == serialized


@pytest.mark.parametrize(
    "plain, serialized",
    [
        ([0], '{"ai":["0=0"]}'),
        ([1], '{"ai":["0=1"]}'),
        ([1, 2], '{"ai":["0=1,1=2"]}'),
    ],
)
def test_value_field_deserialize_ai(plain, serialized):
    vf = ValueField.model_validate_json(serialized)
    assert vf.ai == plain


@pytest.mark.parametrize(
    "plain, serialized",
    [
        ([""], '{"as":["0=\'\'"]}'),
        (["one"], '{"as":["0=\'one\'"]}'),
        (["one", "two"], "{\"as\":[\"0='one',1='two'\"]}"),
        (["a,b"], '{"as":["0=\'a,b\'"]}'),
        (["a,b", "c"], "{\"as\":[\"0='a,b',1='c'\"]}"),
    ],
)
def test_value_field_serialize_as(plain, serialized):
    vf = ValueField(as_=plain)
    assert vf.model_dump_json(exclude_none=True) == serialized


@pytest.mark.parametrize(
    "plain, serialized",
    [
        ([""], '{"as":["0=\'\'"]}'),
        (["one"], '{"as":["0=\'one\'"]}'),
        (["one", "two"], "{\"as\":[\"0='one',1='two'\"]}"),
        (["a,b"], '{"as":["0=\'a,b\'"]}'),
        (["a,b", "c"], "{\"as\":[\"0='a,b',1='c'\"]}"),
    ],
)
def test_value_field_deserialize_as(plain, serialized):
    vf = ValueField.model_validate_json(serialized)
    assert vf.as_ == plain
