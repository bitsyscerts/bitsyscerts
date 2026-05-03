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

Under `src/api/<domain>/`, create:

- `__init__.py` — exports only, no implementation code
- `models.py` — Pydantic models (if this module has data structures crossing boundaries)
- `<module_name>.py` — implementation (MUST be ≤200 lines)
- `exceptions.py` — domain-specific exception classes (if applicable)

MUST NOT place implementation code in `__init__.py`.

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

Create `src/api/<domain>/tests/test_<module_name>.py`:

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

Run the following and confirm all pass before declaring complete:

```bash
ruff check src/api/<domain>/
ruff format --check src/api/<domain>/
mypy src/api/<domain>/
pytest src/api/<domain>/tests/ --cov=src/api/<domain> --cov-fail-under=75
```

Report the coverage percentages and confirm all checks pass.
