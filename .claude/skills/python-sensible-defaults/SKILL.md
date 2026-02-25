---
name: python-sensible-defaults
description: >
  Apply when working on any Python project. Enforces sensible default tool choices
  (uv, ruff, pytest, pydantic, pydantic-settings, fastapi) and a strict TDD workflow.
  Run ruff check and format after every code change.
---

# Python Sensible Defaults

These are the default tool choices and workflow rules for all Python projects.
Apply them automatically unless the project already uses a conflicting tool or
the user explicitly opts out.

---

## Default Toolchain

| Concern | Tool |
|---|---|
| Package & project management | `uv` |
| Linting & formatting | `ruff` |
| Testing | `pytest` |
| Data validation & modelling | `pydantic` |
| Configuration / env vars | `pydantic-settings` |
| HTTP API framework | `fastapi` |

Never suggest pip, Poetry, black, flake8, isort, mypy, or dataclasses as
alternatives unless the user explicitly asks. Prefer these defaults even when
starting from scratch.

---

## Workflow Rules

### Test-Driven Development (TDD)
- Write a failing test **before** writing any implementation code.
- The test must fail for the right reason (not an import error or a syntax error).
- Write the minimum implementation to make the test pass.
- Refactor only after the test is green.
- No production code exists without a corresponding test.

### After every code change, run:
```bash
uv run ruff check .
uv run ruff format .
```

Fix all ruff errors before considering a change complete. Do not leave linting
errors unresolved and move on.

---

## Quick-Reference Commands

```bash
# Add a dependency
uv add <package>

# Add a dev dependency
uv add --dev <package>

# Run tests
uv run pytest

# Run a single test
uv run pytest path/to/test_file.py::TestClass::test_method

# Lint
uv run ruff check .

# Format
uv run ruff format .

# Lint + format in one pass
uv run ruff check . && uv run ruff format .
```
