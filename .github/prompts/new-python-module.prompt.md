---
description: "Scaffold a new Python package or module following all project standards: domain-driven package layout, type hints, docstrings, ruff/mypy compliance, and a co-located pytest test file with ≥75% coverage."
agent: "agent"
argument-hint: "Module name and purpose, e.g. 'certificate chain parser'"
---

Scaffold a new Python module for: **${input}**

Follow every step below in order. Do not skip steps or reorder them.

---

## Step 1 — Decompose First

Before writing any code:

1. State the single responsibility of this module in one sentence.
2. List every function and class the module needs. For each one, confirm it fits in ≤20 lines.
   If any unit is larger, decompose it further until all units are ≤20 lines.
3. Identify which units are leaves (no internal dependencies) and which are composite.
4. Confirm no file will exceed 200 lines before writing anything.

Present this decomposition and wait for confirmation before proceeding.

---

## Step 2 — Create the Package Structure

Determine which sub-project this module belongs to:

- **`src/api/<domain>/`** — REST API logic (routers, services, repositories, Pydantic models)
- **`src/ctpool/ctpool/`** — CT ingestion workers, CLI commands, DB schema, pruning logic

**For `src/api/<domain>/`, create:**

- `__init__.py` — exports only, no implementation code
- `models.py` — Pydantic models (if this module has data structures crossing boundaries)
- `<module_name>.py` — implementation (MUST be ≤200 lines)
- `exceptions.py` — domain-specific exception classes (if applicable)

**For `src/ctpool/ctpool/`, create:**

- `<module_name>.py` — implementation (MUST be ≤200 lines); follow the existing
  `_cli_*_impl.py` naming convention for CLI command implementations
- If defining new DB models or queries, co-locate with the relevant domain module
  (e.g., `prune_queries.py` alongside `_cli_prune_storage_profile_impl.py`)

MUST NOT place implementation code in `__init__.py` in either sub-project.

---

## Step 3 — Implement

- Every function MUST have complete type annotations on all parameters and the return value.
- Every public function and class MUST have a one-line docstring.
- Complex functions MUST have a Google-style docstring with `Args:`, `Returns:`, `Raises:`.
- No function exceeds 20 lines. No file exceeds 200 lines.
- All I/O MUST be async.
- Use domain-specific exception classes — MUST NOT raise `ValueError` or `Exception` from
  business logic.

---

## Step 4 — Create the Test File

Create the test file in the correct location:

- `src/api/<domain>/tests/test_<module_name>.py` for API modules
- `src/ctpool/tests/test_<module_name>.py` for ctpool modules

(Replace `<module_name>` with the actual module name.)

- Use pytest fixtures for all shared setup — no duplicated setup code.
- Use `@pytest.mark.parametrize` for input variations.
- MUST cover ALL of these cases:
  - [ ] Happy path — expected input produces expected output
  - [ ] Empty / zero input
  - [ ] Boundary values (min/max of any range)
  - [ ] Invalid input (wrong type, out-of-range, malformed)
  - [ ] Error paths (exception raised by dependency)
- Test names MUST describe the scenario and outcome:
  `test_<function>_with_<condition>_<expected_result>`
- Coverage MUST reach ≥75% on all four dimensions.

---

## Step 5 — Verify

Run the following for the relevant sub-project and confirm all pass before declaring complete:

```bash
# For src/api/ modules:
cd /workspaces/bitsyscerts/src/api
ruff check --fix certsapi/ tests/ && ruff format certsapi/ tests/
ruff check certsapi/ tests/ && ruff format --check certsapi/ tests/
mypy certsapi/
pytest tests/ --cov=certsapi --cov-fail-under=75

# For src/ctpool/ modules:
cd /workspaces/bitsyscerts/src/ctpool
ruff check --fix ctpool/ tests/ && ruff format ctpool/ tests/
ruff check ctpool/ tests/ && ruff format --check ctpool/ tests/
mypy ctpool/
pytest tests/ --cov=ctpool --cov-fail-under=75
```

Report the coverage percentages and confirm all checks pass.
