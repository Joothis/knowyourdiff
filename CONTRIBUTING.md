# Contributing

Thanks for helping! Beginners are especially welcome.

## Setup

```bash
uv sync
uv run pre-commit install   # optional: runs ruff and mypy before each commit
uv run pytest
```

## Ground rules

- **Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/)**
  (`feat:`, `fix:`, `docs:`, `test:`, `chore:`). Releases and the changelog are generated from them.
- **Tests run offline.** No test may call a real LLM or the network.
- **Golden files.** Ranking output for the fixture cases in `tests/fixtures/cases/` is pinned in
  `tests/golden/`. If you change the risk scorer on purpose, regenerate with
  `uv run pytest --update-golden` and explain the change in your PR.
- **Never run repository-controlled code.** Any new git call goes through `knowyourdiff.git`.

## Good first issues

Look for the `good first issue` label: new language adapters for code context, new risk signals,
and fixture cases are all small, self-contained changes.
