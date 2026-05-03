---
description: "Scaffold a new FastAPI endpoint: security design first, Pydantic request/response models, service/repository separation, Depends() injection, authorization check, rate limiting consideration, and co-located pytest tests covering auth, validation, and happy path."
agent: "agent"
argument-hint: "Endpoint description, e.g. 'GET /certificates/{id} — returns a single certificate for the authenticated user'"
---

Scaffold a new FastAPI endpoint for: **${input}**

Follow every step below in order. Do not skip steps or reorder them.

---

## Step 1 — Security Design First

Before writing any code, answer every question below. Present answers and wait for confirmation.

| Question | Answer |
|----------|--------|
| What authentication is required? (JWT, API key, anonymous) | |
| What is the minimum required role or permission? | |
| Which specific resource is being accessed — is ownership/authorization checked per-object? (API1 BOLA) | |
| What inputs require validation? (path params, query params, body fields) | |
| What fields MUST NOT appear in the response? (passwords, internal IDs, audit fields) | |
| Does this endpoint need rate limiting? If so, what threshold? (API4/API6) | |
| Is there an SSRF risk from any URL or identifier passed by the client? (A10/API7) | |

---

## Step 2 — Define Pydantic Models

In `src/api/<domain>/models.py`:

- **Request model**: define with field validators (`@field_validator`) for all inputs.
  Validators MUST use an allowlist approach — reject anything not explicitly permitted.
- **Response model**: include ONLY the fields the client should receive. Explicitly exclude
  internal fields, hashed values, and audit columns.
- MUST NOT reuse ORM models as Pydantic models. They are always separate classes.

---

## Step 3 — Service Function

In `src/api/<domain>/service.py`:

- Business logic ONLY. MUST NOT make direct database calls.
- Receives domain objects, returns domain objects.
- Each function MUST be ≤20 lines. If it cannot be, decompose it.
- MUST use domain-specific exception classes for error cases — no generic `ValueError`.

---

## Step 4 — Repository Function

In `src/api/<domain>/repository.py`:

- Database access ONLY. MUST NOT contain business logic.
- Uses parameterized ORM queries (SQLAlchemy async). MUST NOT construct raw SQL strings.
- Each function MUST be ≤20 lines.

---

## Step 5 — Endpoint in Router

In `src/api/<domain>/router.py`:

- Use `Depends()` for ALL dependencies (db session, current user, service instance).
- Declare `response_model` explicitly — MUST NOT omit it or set it to `None`.
- Declare HTTP status codes for success AND all documented error cases.
- Apply authorization check as the first operation in the endpoint body (or via a Depends).
- Apply rate limiting decorator/middleware as required by Step 1 findings.

---

## Step 6 — Create Tests

In `src/api/<domain>/tests/`:

**`test_router.py`** — endpoint-level (integration) tests:
- [ ] Unauthenticated request returns 401
- [ ] Authenticated but unauthorized (wrong user/role) returns 403
- [ ] Valid request with valid data returns expected response and status code
- [ ] Resource not found returns 404
- [ ] Invalid path parameter type returns 422
- [ ] Invalid request body (missing required fields, out-of-range values) returns 422

**`test_service.py`** — unit tests for service functions:
- [ ] Happy path
- [ ] Dependency raises exception → service raises correct domain exception
- [ ] Edge cases specific to this business logic

Use pytest fixtures for auth tokens, database sessions, and test data.
Use `@pytest.mark.parametrize` for input validation variations.

---

## Step 7 — Verify

Run the following and confirm all pass before declaring complete:

```bash
ruff check src/api/<domain>/
mypy src/api/<domain>/
pytest src/api/<domain>/tests/ --cov=src/api/<domain> --cov-fail-under=75
```

Report the coverage percentages and confirm all checks pass.
