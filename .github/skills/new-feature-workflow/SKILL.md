---
name: new-feature-workflow
description: "Multi-step workflow for implementing any new feature, endpoint, or component. Use when starting new work of any size. Enforces: decomposition plan via the Planner agent FIRST, explicit user approval before any code is written, bottom-up implementation with tests alongside each unit, coverage gate before completion, and a security audit of all new files."
argument-hint: "Describe the feature to implement"
---

# New Feature Workflow

This skill enforces the project's most fundamental mandate: **Decomposition First**. No
implementation code is written until the design is understood, decomposed, and explicitly
approved. This is not optional. It applies to every feature regardless of perceived size.

---

## When to Use

- Starting any new feature (no matter how small it seems)
- Adding a new API endpoint
- Adding a new React page or major component
- Adding a new Python module, service, or package
- Any work that will result in more than one new file

---

## The Workflow

### Step 1 — Decompose (MANDATORY — cannot be skipped)

Invoke the `planner` agent with the feature description as input.

The Planner will:
- Search the codebase for reusable units
- Produce a complete unit breakdown (components, hooks, modules, services)
- Confirm every unit has a single-sentence responsibility
- Validate that every unit fits within size limits (≤200 lines per file, ≤20 lines per function)
- Determine the build order (leaves first)
- Produce a test plan for each unit

**Do not proceed past this step until the Planner's output is presented.**

---

### Step 2 — Plan Approval (MANDATORY — cannot be skipped)

Present the Planner's output in full and ask explicitly:

> "Does this decomposition plan look correct? Are there any units that should be further
> decomposed, merged, or removed before we begin implementation?"

**MUST NOT write any implementation code until the user responds with explicit approval.**

If the user requests changes, update the plan and present it again. Repeat until approved.

---

### Step 3 — Bottom-Up Implementation

Implement units in the exact build order determined in Step 1. For each unit:

1. **Create the implementation file.**
2. **Create the test file immediately** — in the same step, not after. MUST NOT move on to
   the next unit while the test file for the current unit is missing.
3. **Run the tests for this unit** and confirm they pass before moving to the next unit.
4. **Confirm linting and type checking pass** for this unit before moving on.

MUST NOT move to a composite or aggregate unit until all of its dependencies have been
implemented, tested, and verified.

---

### Step 4 — Integration

Once all leaf units are implemented and tested:

1. Implement composite components and services, assembled from the tested leaves.
2. Write integration-level tests (endpoint tests, page-level component tests).
3. Run the full test suite:
   - Python: `pytest` from `src/api/` (includes lint + type check + coverage)
   - React: `npm run test` from `src/app/` (includes lint + type check + coverage)

---

### Step 5 — Coverage Gate

Run the full coverage report. MUST verify **all four dimensions** before proceeding:

| Dimension  | Required |
|------------|----------|
| Statements | ≥ 75%    |
| Branches   | ≥ 75%    |
| Functions  | ≥ 75%    |
| Lines      | ≥ 75%    |

If any dimension is below 75%, identify the uncovered code, write the missing tests, and
re-run coverage. MUST NOT proceed to Step 6 until all four dimensions pass.

---

### Step 6 — Security Checkpoint

Invoke the `security-auditor` agent on all newly created and modified files.

If any **Critical** or **High** findings are reported:
- They MUST be remediated before the feature is considered complete.
- After remediation, re-run the test suite to confirm nothing broke.
- Re-invoke the security auditor on the remediated files to confirm the findings are resolved.

Medium, Low, and Informational findings MUST be logged (as GitHub issues or in-code TODO
comments with a tracking reference) but do not block completion.

---

### Step 7 — Completion Checklist

Confirm every item before declaring the feature complete:

- [ ] All new files are ≤200 lines
- [ ] All new functions are ≤20 lines
- [ ] All linting passes: `ruff check` (Python) and/or `npm run lint` (React/TS)
- [ ] All type checks pass: `mypy` (Python) and/or `tsc --noEmit` (TypeScript)
- [ ] Coverage ≥75% on all four dimensions
- [ ] No Critical or High security findings from the Security Auditor
- [ ] All public functions and classes have docstrings / JSDoc comments
- [ ] No hardcoded secrets, credentials, or environment-specific values in any file
- [ ] `.env.example` updated if any new environment variables were introduced
- [ ] All new API endpoints have explicit Pydantic request and response models
- [ ] All new React components have explicit TypeScript prop interfaces
