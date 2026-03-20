# Python library for GARDENA smart local API

Enables controlling and monitoring GARDENA smart devices in the local network, without going through the cloud.

## Supported Devices

| Model | Device |
|-------|--------|
| 18869 | Water Control |

## Installation

```txt
pip install gardena-smart-local-api
```

## Contributing

### Linting

```txt
uv sync --all-groups
uv run ruff check
uv run ruff format --check
uv run ty check
```

### Running Tests

```txt
uv sync --group test
uv run python -m pytest
```
