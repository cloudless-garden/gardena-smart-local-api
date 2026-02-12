from gardena_smart_local_api.utils import deep_merge_dict


def test_deep_merge_dict_simple_merge():
    target = {"a": 1, "b": 2}
    source = {"c": 3, "d": 4}
    deep_merge_dict(target, source)
    assert target == {"a": 1, "b": 2, "c": 3, "d": 4}


def test_deep_merge_dict_overwrite_simple_value():
    target = {"a": 1, "b": 2}
    source = {"b": 3, "c": 4}
    deep_merge_dict(target, source)
    assert target == {"a": 1, "b": 3, "c": 4}


def test_deep_merge_dict_nested_merge():
    target = {"a": {"x": 1, "y": 2}, "b": 3}
    source = {"a": {"y": 3, "z": 4}, "c": 5}
    deep_merge_dict(target, source)
    assert target == {"a": {"x": 1, "y": 3, "z": 4}, "b": 3, "c": 5}


def test_deep_merge_dict_deeply_nested():
    target = {"a": {"b": {"c": 1, "d": 2}}}
    source = {"a": {"b": {"d": 3, "e": 4}}}
    deep_merge_dict(target, source)
    assert target == {"a": {"b": {"c": 1, "d": 3, "e": 4}}}


def test_deep_merge_dict_replace_dict_with_value():
    target = {"a": {"x": 1, "y": 2}}
    source = {"a": "simple value"}
    deep_merge_dict(target, source)
    assert target == {"a": "simple value"}


def test_deep_merge_dict_replace_value_with_dict():
    target = {"a": "simple value"}
    source = {"a": {"x": 1, "y": 2}}
    deep_merge_dict(target, source)
    assert target == {"a": {"x": 1, "y": 2}}


def test_deep_merge_dict_empty_source():
    target = {"a": 1, "b": 2}
    source = {}
    deep_merge_dict(target, source)
    assert target == {"a": 1, "b": 2}


def test_deep_merge_dict_empty_target():
    target = {}
    source = {"a": 1, "b": 2}
    deep_merge_dict(target, source)
    assert target == {"a": 1, "b": 2}


def test_deep_merge_dict_with_none_values():
    target = {"a": 1, "b": None}
    source = {"b": 2, "c": None}
    deep_merge_dict(target, source)
    assert target == {"a": 1, "b": 2, "c": None}


def test_deep_merge_dict_with_lists():
    target = {"a": [1, 2, 3]}
    source = {"a": [4, 5]}
    deep_merge_dict(target, source)
    assert target == {"a": [4, 5]}
