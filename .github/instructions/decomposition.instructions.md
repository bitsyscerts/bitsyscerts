---
description: "Use when creating or modifying any source file under src/. Enforces decomposition-first design: problem analysis before coding, Robert C. Martin file and function size limits, Single Responsibility Principle, bottom-up build order, and intention-revealing naming."
applyTo: "src/**"
---

# Decomposition-First Rules

These rules apply to every file under `src/`. They are non-negotiable.

---

## Step Zero: Design Before Code

MUST complete all of the following before writing any implementation code:

1. State the single responsibility of the unit being created in **one sentence**. If you cannot
   do this, stop — the unit is too large and must be decomposed further.
2. List every logical sub-unit that could be independently unit tested. Each one MUST become its
   own function, class, or module/component.
3. Identify the dependency graph: which units depend on which. This determines the build order.
4. Confirm that no proposed unit will exceed the size limits below before writing a single line.

MUST NOT begin writing implementation code until this design step is complete. "We can refactor
later" is not an acceptable rationale for skipping decomposition.

---

## File Size Limits (Robert C. Martin, *Clean Code*)

| Lines      | Status     | Required Action |
|------------|------------|-----------------|
| ≤ 200      | Good       | No action needed — this is the target |
| 201 – 500  | Warning    | MUST add a comment block at the top of the file: what the consolidation rationale is and when it will be resolved |
| > 500      | **Defect** | MUST split the file immediately. No other work may proceed on this file until it is below 500 lines |

If a file approaches 200 lines during implementation, stop and extract — do not wait until the
limit is reached.

---

## Function and Method Size Limits (Robert C. Martin, *Clean Code*)

| Lines  | Status     | Required Action |
|--------|------------|-----------------|
| ≤ 20   | Good       | No action needed — this is the target |
| 21–50  | Warning    | MUST add an inline comment explaining why extraction is not yet possible |
| > 50   | **Defect** | MUST split the function before proceeding with any other work |

Functions longer than 20 lines are almost always doing more than one thing. Find the seam and
extract.

---

## Single Responsibility Principle

- Every **function** does exactly one thing. Its name MUST completely describe that one thing.
  A reader MUST understand the function's purpose without reading its body.
- Every **class or component** has exactly one reason to change. If the word "and" appears when
  describing its purpose, it has too many responsibilities.
- Every **module or package** has a cohesive domain. Cross-domain logic MUST be extracted to a
  shared, explicitly named module.

---

## Bottom-Up Build Order

MUST build in this sequence:

1. **Primitives and pure utilities** — standalone functions with zero internal project
   dependencies. These are built and fully tested first.
2. **Domain components** — single-purpose classes, hooks, or services built from primitives.
   Each is fully tested before the next level is started.
3. **Composite features and pages** — assembled from tested domain components.

MUST NOT write a page, service, or aggregate component before its constituent parts exist and
have passing tests. Scaffolding a top-level component with placeholder children is prohibited —
build the children first.

---

## Naming Rules

- Names MUST be **intention-revealing**. A reader must understand the unit's purpose without
  reading its body.
- No abbreviations except universally accepted ones (`id`, `url`, `api`, `dto`, `i`, `j`).
- No generic, catch-all names:

| Prohibited Name | Use Instead |
|-----------------|-------------|
| `utils.py` | `token_utils.py`, `date_utils.py` |
| `helpers.ts` | `certificate_helpers.ts` |
| `misc/` | a domain-named directory |
| `common/` | a domain-named shared module |
| `process_data()` | `parse_certificate_chain()` |
| `handleStuff()` | `submitLoginForm()` |
| `do_everything()` | split into named functions |

---

## Reuse Check

Before creating any new unit, MUST search the existing codebase for a unit that already covers
the same concern. Duplicating logic across modules is a defect. If a similar unit exists but does
not quite fit, extend or generalize it rather than duplicating it.

---

## What Good Looks Like

A well-decomposed Python module:
```
src/api/auth/
  __init__.py          # exports only
  models.py            # Pydantic models for this domain (≤200 lines)
  router.py            # FastAPI route definitions (≤200 lines)
  service.py           # business logic only, no DB access (≤200 lines)
  repository.py        # DB access only, no business logic (≤200 lines)
  dependencies.py      # FastAPI Depends() factories (≤200 lines)
  tests/
    test_service.py
    test_repository.py
    test_router.py
```

A well-decomposed React feature:
```
src/app/components/CertificateCard/
  CertificateCard.tsx        # primary component (≤200 lines)
  CertificateCard.test.tsx   # co-located tests
  types.ts                   # TypeScript interfaces
src/app/hooks/
  useCertificate.ts          # data-fetching hook (≤200 lines)
  useCertificate.test.ts
```
