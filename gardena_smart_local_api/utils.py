from typing import Any

from .resources import IpsoPath


def deep_merge_dict(target: dict[str, Any], source: dict[str, Any]) -> None:
    for key, value in source.items():
        if key in target and isinstance(target[key], dict) and isinstance(value, dict):
            deep_merge_dict(target[key], value)
        else:
            target[key] = value


def delete_nested_key(data: dict[str, Any], path: IpsoPath) -> None:
    segments = list(path.segments)
    if not segments:
        return
    # Track the chain of (parent_dict, key) so we can prune upward
    parents: list[tuple[dict[str, Any], str]] = []
    obj = data
    for key in segments[:-1]:
        if not isinstance(obj, dict):
            return
        parents.append((obj, key))
        obj = obj.get(key)
    if not isinstance(obj, dict):
        return
    obj.pop(segments[-1], None)
    # Prune empty parent dicts bottom-up
    for parent, key in reversed(parents):
        if isinstance(parent.get(key), dict) and not parent[key]:
            del parent[key]
        else:
            break
