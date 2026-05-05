---
description: "Use when writing, reviewing, running, or debugging tests. Covers pytest for Python, Vitest and React Testing Library for React/TypeScript, the 75% coverage hard gate, edge case requirements, mocking rules, and the unified test command pattern."
applyTo: "src/**"
---

# Testing and Code Coverage Standards

---

## The Non-Negotiable Coverage Gate

**75% code coverage is a hard gate. Features do not ship below this threshold.**

Coverage MUST be measured and enforced on all four dimensions:

| Dimension  | Minimum |
| ---------- | ------- |
| Statements | 75%     |
| Branches   | 75%     |
| Functions  | 75%     |
| Lines      | 75%     |

CI MUST be configured to fail on coverage below 75% on any dimension. This is a floor, not a
target. Aim higher.

### Completion Gate for Coding Agents

- A task that changes any source file under `src/` is NOT complete until the relevant unified
  test command succeeds locally:
  - Backend changes: run `pytest` in the corresponding Python project directory.
  - Frontend changes: run `npm run test` in `src/app/`.
- Final task report MUST include the exact command executed and the resulting coverage summary.
- If linting or type-checking fails, the task is incomplete even if unit tests pass.
- If any coverage dimension is below 75%, continue implementation and testing until the gate is
  satisfied. Do not mark the task done.

### Repository Enforcement Requirements

- CI checks for test jobs MUST be required status checks on protected branches.
- Merges to `main` MUST be blocked when any test, lint, type-check, or coverage gate fails.
- Local instruction files guide behavior; branch protection and failing CI enforce behavior.

---

## Tests Ship With Code

- Test files MUST be created in the **same commit** as the implementation they test.
- MUST NOT submit a PR that adds, modifies, or removes implementation code without corresponding
  test changes.
- "I'll write the tests in a follow-up PR" is not acceptable.

### Test File Naming and Location

| Language         | Convention                                       | Location                                                  |
| ---------------- | ------------------------------------------------ | --------------------------------------------------------- |
| Python           | `test_<module>.py`                               | `src/api/<domain>/tests/` mirroring the package structure |
| React/TypeScript | `<ComponentName>.test.tsx` / `use<Hook>.test.ts` | Co-located with the source file                           |

---

## Python Testing (pytest)

- Use `pytest` as the sole test runner. MUST NOT use `unittest.TestCase` classes or the
  `unittest` runner.
- Use `pytest-asyncio` for all async test cases. Set `asyncio_mode = "auto"` in
  `pyproject.toml` so async test functions are recognized without explicit markers.
- Use **fixtures** for all shared setup. MUST NOT duplicate setup code across test functions.
- Use `@pytest.mark.parametrize` for testing multiple input variations of the same behavior.
  MUST NOT write separate test functions that differ only in their input values.
- Use `pytest-cov` for coverage. The test command MUST include `--cov-fail-under=75`.

### Unified Python Test Command

The command `pytest` (run from `src/api/`) MUST perform all of the following in sequence:

1. `ruff check src/` — linting (fails fast on lint errors)
2. `mypy src/` — type checking
3. pytest test execution
4. Coverage report with `--cov-fail-under=75`

Configure in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
addopts = "--cov=src/api --cov-report=term-missing --cov-fail-under=75"

[tool.coverage.report]
fail_under = 75
show_missing = true
```

---

## React / TypeScript Testing (Vitest + React Testing Library)

- Use **Vitest** as the test runner with `@testing-library/react` and
  `@testing-library/user-event`.
- Test **behavior**, not implementation. MUST NOT test internal state, ref values, private
  methods, or implementation details of a component.
- Prefer these element selectors (in priority order):
  1. `getByRole` — matches accessible semantics
  2. `getByLabelText` — matches form labels
  3. `getByText` — matches visible text
  4. `getByTestId` — ONLY as a last resort when no semantic selector is available
- Mock only at system boundaries (API calls via `msw`, external services). MUST NOT mock
  internal module functions or component internals.

### Unified React Test Command

The command `npm run test` (run from `src/app/`) MUST perform all of the following in sequence:

1. ESLint — linting (fails fast on lint errors)
2. TypeScript type check (`tsc --noEmit`)
3. Vitest test execution
4. Coverage report with threshold enforcement

Configure in `package.json`:

```json
{
  "scripts": {
    "test": "npm run lint && npm run typecheck && vitest run --coverage",
    "lint": "eslint src/ --max-warnings 0",
    "typecheck": "tsc --noEmit",
    "test:watch": "vitest"
  }
}
```

Configure coverage thresholds in `vite.config.ts`:

```typescript
test: {
  coverage: {
    provider: 'v8',
    thresholds: {
      statements: 75,
      branches: 75,
      functions: 75,
      lines: 75
    }
  }
}
```

---

## Edge Case Requirements

Every test suite MUST explicitly cover:

| Category           | Description                                                                  |
| ------------------ | ---------------------------------------------------------------------------- |
| Happy path         | Expected inputs produce expected outputs                                     |
| Empty / zero input | Empty string, empty array, zero, null, undefined                             |
| Boundary values    | Minimum and maximum of any allowed range; first and last of any sequence     |
| Invalid input      | Wrong type, out-of-range value, malformed data, missing required fields      |
| Error paths        | What happens when a dependency raises an exception or returns an error       |
| Authorization      | Unauthenticated → 401; authenticated but unauthorized → 403                  |
| Async edge cases   | Request timeout, partial failure in concurrent operations (where applicable) |

Edge case test names MUST be descriptive. The name MUST describe the scenario and the expected
outcome:

```
WRONG:  test_error_case
WRONG:  test_invalid_input
CORRECT: test_create_certificate_with_expired_token_returns_401
CORRECT: test_parse_pem_with_empty_string_raises_ValidationError
CORRECT: renders_error_state_when_api_returns_500
```

---

## Mocking Rules

- MUST mock all external I/O (HTTP calls, database, file system, clock) in **unit tests**.
- MUST use real implementations for **integration tests**. Integration tests MUST be clearly
  separated from unit tests (use pytest marks `@pytest.mark.unit` and `@pytest.mark.integration`,
  or separate directories).
- MUST NOT mock the module under test itself.
- For React, use Mock Service Worker (`msw`) to intercept API requests at the network level
  rather than mocking service functions directly.

---

## Test Quality — Inadequacy Checklist

A test is **inadequate** and MUST be rewritten if any of the following is true:

- It cannot fail — it will pass regardless of what the implementation does.
- It tests only the happy path with no error or edge case coverage.
- Its name does not describe what scenario is being tested.
- It has no assertions, or only `assert True` / `expect(true).toBe(true)`.
- It tests the test framework itself rather than the application code.
- It is so tightly coupled to implementation details that a valid refactor breaks it.

---

## Test Organization

```
src/api/
  auth/
    tests/
      __init__.py
      test_service.py        # unit tests for auth/service.py
      test_repository.py     # unit tests for auth/repository.py
      test_router.py         # integration tests for auth endpoints
      conftest.py            # fixtures scoped to auth domain

src/app/
  components/
    CertificateCard/
      CertificateCard.tsx
      CertificateCard.test.tsx   # co-located
  hooks/
    useCertificate.ts
    useCertificate.test.ts       # co-located
```
