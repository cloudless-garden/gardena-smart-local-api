# Contributing

## Discussions

For questions, ideas for larger changes, or to connect with other community members, use [GitHub Discussions][discussions]. This is also a good place for people implementing the GARDENA Smart local protocol in other languages to discuss the protocol, get help, and share their solutions.

## Reporting Bugs

Before reporting a bug, please search existing [issues] to avoid duplicates.

When reporting a bug, include:

- A clear and descriptive title
- Steps to reproduce the problem
- What you expected to happen and what actually happened
- The version of this library you are using
- Your Python version and OS

## Feature Requests

Feature requests are welcome. Please search existing [issues] first to see if it has already been suggested.

When opening a feature request, describe:

- The problem you are trying to solve
- Your proposed solution or the behavior you would like to see
- Any alternatives you have considered

## Pull Requests

Pull requests are the preferred way to contribute code changes. For significant changes, open an issue first to discuss the approach before investing time in an implementation.

[issues]: https://github.com/cloudless-garden/gardena-smart-local-api/issues
[discussions]: https://github.com/cloudless-garden/gardena-smart-local-api/discussions

## Commits

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

## Linting

```txt
uv sync --all-groups
uv run ruff check
uv run ruff format --check
uv run ty check
```

## Running Tests

```txt
uv sync --group test
uv run python -m pytest
```

## AI Usage

AI assistance (e.g. GitHub Copilot, Claude, ChatGPT) is welcome, but follow these guidelines:

- **Mark AI-generated code** in the commit message or PR description, e.g. `Generated with Claude`.
- **Review before submitting** — do not paste AI output directly into a PR without reading and understanding it. You are responsible for what you submit.
- **Verify correctness** — AI tools can produce plausible-looking but incorrect code. Check logic, edge cases, and consistency with the rest of the codebase.
- **Keep commits clean** — the same commit quality standards apply regardless of how the code was written.

## Building the Docs

```txt
uv sync --group docs
uv run sphinx-build docs docs/_build/html
```

Then open `docs/_build/html/index.html` in a browser.
