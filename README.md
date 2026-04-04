# Python library for GARDENA smart local API

Enables controlling and monitoring GARDENA smart devices in the local network, without going through the cloud.

## Supported Devices

| Device                        | Article Number                         | Model (EAN suffix) |
| ----------------------------- | -------------------------------------- | ------------------ |
| smart Sensor                  | 19030-20                               | 18845              |
| smart Sensor II               | 19040-20                               | 19040              |
| smart Water Control           | 19031-20                               | 18869              |
| smart Water Control           | 19033-20                               | 2812               |
| smart Dual Water Control      | 19034-20                               | 2814               |
| smart Pipeline Water Control  | 19050-20                               | 2826               |
| smart Irrigation Control      | 19035-20                               | 469                |
| smart Power Adapter           | 19095-20                               | 35279              |
| smart SILENO                  | 19060-20, 19060-60                     | 6146               |
| smart SILENO+                 | 19061-20, 19061-60, 19064-60, 19065-60 | 6146               |
| smart SILENO city             | 19066-20, 19069-20                     | 29694              |
| smart SILENO life             | 19113-20, 19114-20, 19115-20           | 29694              |
| smart SILENO city (with LONA) | 19602-66, 19603-60, 19605-60           | 53988              |
| smart SILENO life (with LONA) | 19701-60, 19702-60, 19703-66, 19704-60 | 53988              |

## Installation

```txt
pip install gardena-smart-local-api
```

## Using the Library

Have a look at our [example code][examples].

You can run the examples from within the repository as follows:

```txt
uv sync --group examples
uv run gardena_smart_local_api/examples/irrigation.py --help
```

[examples]: https://github.com/cloudless-garden/gardena-smart-local-api/tree/main/gardena_smart_local_api/examples

## Contributing

### Commits

Try to keep commits reviewable, i.e. they should only contain one logical change and generally not be too big.

As we use rebase to integrate pull requests, clean commits matter. Use commands like `git commit --amend`,
`git commit --fixup ...` and `git rebase --interactive ...` to rework your commits. Should this be too advanced for you,
just push temporary commits and when review is done, run e.g.:

```txt
git fetch
git rebase origin/main
git reset origin/main
git commit --all
git push --force-with-lease
```

For the commit message(s), follow [these guidelines][commits]. If you are unsure how to formulate your commit messages,
look at `git log` for inspiration.

[commits]: https://cbea.ms/git-commit/

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
