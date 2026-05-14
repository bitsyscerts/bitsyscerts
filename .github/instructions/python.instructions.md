---
description: "Use when creating or modifying Python files (.py). Enforces PEP-8, ruff linting and formatting, mandatory type hints, FastAPI patterns including explicit Pydantic models and Depends() injection, async-first I/O, domain-driven package structure, and docstring requirements."
applyTo: "**/*.py"
---

# Python Coding Standards

---

> **STOP — MANDATORY LAST STEP BEFORE EVERY TASK COMPLETE**
>
> After **every** edit to any `.py` file you MUST run the two commands below (for the
> relevant sub-project) and confirm zero violations before calling `task_complete` or
> saying you are finished. This is not optional. Skipping it causes pre-commit failures
> for the user on 100% of commits that touch Python files.
>
> ```bash
> # src/ctpool changes:
> cd /workspaces/bitsyscerts/src/ctpool && source /workspaces/bitsyscerts/.venv/bin/activate && ruff check --fix ctpool/ tests/ && ruff format ctpool/ tests/ && ruff check ctpool/ tests/
>
> # src/api changes:
> cd /workspaces/bitsyscerts/src/api && source /workspaces/bitsyscerts/.venv/bin/activate && ruff check --fix certsapi/ tests/ && ruff format certsapi/ tests/ && ruff check certsapi/ tests/
> ```
>
> The most common failure is **I001 — unsorted imports**, which `ruff check --fix`
> resolves automatically. There is no excuse for skipping this step.

---

## Style and Formatting

- ALL Python code MUST comply with PEP-8 in full.
- `ruff` is the enforced linter and formatter. Every file MUST pass `ruff check` and
  `ruff format` with zero warnings before it is considered complete.
- Maximum line length: **88 characters** (ruff/Black default).
- Imports MUST be ordered: standard library → third-party → local. Use ruff's import sorting
  (`I` rule set). MUST NOT mix import groups.
- MUST NOT use wildcard imports (`from module import *`). Every imported name must be explicit.

---

## Type Hints

- ALL functions and methods MUST have complete type annotations on every parameter and on the
  return value. No unannotated function signatures.
- MUST NOT use `Any` from `typing` unless interacting with a third-party library that cannot be
  typed. Every use of `Any` MUST have an inline comment explaining exactly why it cannot be
  avoided.
- Use `TypeAlias`, `TypeVar`, and `Protocol` for reusable type patterns. Prefer these over
  repeating complex union types.
- Pydantic `BaseModel` subclasses MUST be used for all structured data passed across module
  boundaries. MUST NOT pass raw `dict` objects between service and repository layers.

---

## Package and Module Structure

- `__init__.py` files MUST contain only re-exports of the module's public API. MUST NOT contain
  implementation code, business logic, or class definitions.
- No file exceeds **200 lines** (see decomposition rules).
- Package structure follows the **domain**, not the technical layer:

```
src/api/
  <domain>/
    __init__.py         # public exports only
    models.py           # Pydantic request/response models
    router.py           # FastAPI router — route definitions only
    service.py          # business logic — no direct DB access
    repository.py       # DB access — no business logic
    dependencies.py     # FastAPI Depends() factories
    exceptions.py       # domain-specific exception classes
    tests/
      test_service.py
      test_repository.py
      test_router.py
```

- MUST NOT create catch-all modules. The following names are **prohibited**:
  `utils.py`, `helpers.py`, `misc.py`, `common.py`, `shared.py` (unless the file is
  domain-scoped, e.g., `token_utils.py`, `date_helpers.py`).

---

## FastAPI Patterns

- Every router MUST be defined in its own `router.py` and registered via
  `app.include_router()` in the application factory. MUST NOT define routes directly on `app`.
- MUST define an explicit Pydantic request model for every request body. MUST NOT accept
  unvalidated `dict` or `Body(...)` parameters.
- MUST define an explicit Pydantic response model for every endpoint via the `response_model`
  parameter. MUST NOT use `response_model=None` or return raw dicts from endpoints.
- Use `Depends()` for all dependency injection: database sessions, current user, configuration,
  service instances, repository instances.
- MUST NOT instantiate service or repository classes directly inside endpoint functions. All
  dependencies MUST be injected via `Depends()`.
- Background tasks MUST use FastAPI's `BackgroundTasks` or a proper task queue (Celery, ARQ,
  Dramatiq). MUST NOT use `asyncio.create_task()` for fire-and-forget work in production.

---

## Async

- ALL I/O operations MUST be `async`. MUST NOT call synchronous blocking I/O (file reads,
  network calls, database queries) from inside an `async` function.
- Use `asyncpg` directly or SQLAlchemy with the `asyncio` extension for all database access.
- MUST NOT use `time.sleep()` inside an async context. Use `asyncio.sleep()`.
- MUST NOT call `asyncio.run()` from within a function that is already executing in an async
  context (this causes a runtime error and indicates a design flaw).
- Concurrent tasks MUST use `asyncio.gather()` or `asyncio.TaskGroup` with proper exception
  handling.

---

## Error Handling

- MUST NOT use bare `except:` or `except Exception:` without either re-raising or logging the
  full exception with context.
- MUST define domain-specific exception classes in `exceptions.py` for each domain package.
  MUST NOT raise generic `ValueError`, `RuntimeError`, or `Exception` from business logic.
- FastAPI exception handlers MUST be registered at the application level for each custom
  exception type, mapping domain exceptions to appropriate HTTP status codes.
- Exception messages MUST be safe for logging (no passwords, tokens, or PII in exception
  messages).

---

## Docstrings

- All public functions, classes, and modules MUST have a one-line docstring stating their
  single responsibility.
- Functions with non-obvious behavior, complex parameters, or multiple return paths MUST have
  a full Google-style docstring with `Args:`, `Returns:`, and `Raises:` sections.
- `__init__.py` files MUST have a module-level docstring listing what the package exports and
  what domain it covers.

---

## Configuration and Environment

- MUST NOT hardcode configuration values (database URLs, hostnames, feature flags, timeouts).
- Use Pydantic `BaseSettings` (from `pydantic-settings`) for all application configuration.
  Settings are loaded from environment variables with type validation.
- The settings class MUST be a singleton instantiated once and injected via `Depends()`.

---

## Database

- Use SQLAlchemy (async) with `asyncpg` as the driver.
- All database models MUST be defined using SQLAlchemy's declarative ORM.
- Database models (ORM) and API models (Pydantic) MUST be separate classes. MUST NOT use ORM
  models directly as Pydantic response models.
- Migrations MUST be managed with Alembic. MUST NOT modify the database schema manually.

---

## Definition of Done — MANDATORY GATE

After **every** edit to a Python file — no matter how small — MUST run the auto-fix
and check commands below **before** declaring the task complete or handing back to the
user. Do not ask whether to run them. Do not skip them. A response that does not
include a passing terminal run is incomplete.

**Step 1 — Always auto-fix first (run unconditionally after every Python edit):**

```
# For files changed under src/api/
cd /workspaces/bitsyscerts/src/api && source /workspaces/bitsyscerts/.venv/bin/activate && ruff check --fix certsapi/ tests/ && ruff format certsapi/ tests/

# For files changed under src/ctpool/
cd /workspaces/bitsyscerts/src/ctpool && source /workspaces/bitsyscerts/.venv/bin/activate && ruff check --fix ctpool/ tests/ && ruff format ctpool/ tests/
```

**Step 2 — Then verify zero violations remain:**

```
# For files changed under src/api/
cd /workspaces/bitsyscerts/src/api && ruff check certsapi/ tests/ && ruff format --check certsapi/ tests/

# For files changed under src/ctpool/
cd /workspaces/bitsyscerts/src/ctpool && ruff check ctpool/ tests/ && ruff format --check ctpool/ tests/
```

If Step 2 still reports violations after Step 1, fix them manually, then re-run Step 2
until it is clean. Only then declare the task complete.

The most common violation is **I001 (unsorted imports)**. It is always auto-fixable.
Running `ruff check --fix` before handing back prevents 100% of pre-commit import
failures.
