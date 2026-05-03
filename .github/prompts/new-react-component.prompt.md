---
description: "Scaffold a new React component with TypeScript, Mantine, an Error Boundary, a Suspense/skeleton loading state, and a co-located Vitest + React Testing Library test file with ≥75% coverage."
agent: "agent"
argument-hint: "Component name and purpose, e.g. 'CertificateCard — displays a certificate summary row'"
---

Scaffold a new React component for: **${input}**

Follow every step below in order. Do not skip steps or reorder them.

---

## Step 1 — Decompose First

Before writing any code:

1. State the single responsibility of this component in one sentence.
2. List every sub-component, custom hook, and service call this component needs.
   If it fetches data, manages form state, AND renders content, those are three separate
   concerns — extract accordingly.
3. Confirm no file will exceed 200 lines before writing anything.
4. Identify which units are leaves (no internal dependencies) and build those first.

Present this decomposition and wait for confirmation before proceeding.

---

## Step 2 — Create the Directory Structure

Under `src/app/components/<ComponentName>/`:

- `<ComponentName>.tsx` — primary component (MUST be ≤200 lines)
- `<ComponentName>.test.tsx` — Vitest + React Testing Library tests
- `types.ts` — TypeScript prop interfaces and local types (only if needed)

If a custom hook is needed, create it at `src/app/hooks/use<HookName>.ts` with a co-located
`use<HookName>.test.ts`.

---

## Step 3 — Implement

- All props MUST have an explicit TypeScript `interface`. MUST NOT use `any`.
- MUST use Mantine components exclusively — no raw HTML where Mantine provides an equivalent.
- MUST use Mantine theme tokens for all colors, spacing, and typography. MUST NOT hardcode
  CSS values.
- Wrap in an `<ErrorBoundary>` if the component fetches data or renders children that can fail.
- Add a `<Suspense>` boundary with a Mantine `<Skeleton>` placeholder for any async data.
  The skeleton MUST match the shape and approximate dimensions of the loaded content.
- MUST follow all React Rules of Hooks — no conditional or loop-based hook calls.

---

## Step 4 — Create the Test File

In `<ComponentName>.test.tsx`:

- Use `@testing-library/react` and `@testing-library/user-event`.
- Test behavior, not implementation. MUST NOT inspect internal state.
- Prefer selectors in this order: `getByRole`, `getByLabelText`, `getByText`. Use `getByTestId`
  only as a last resort.
- MUST cover ALL of these cases:
  - [ ] Renders correctly with valid props
  - [ ] Renders the skeleton/loading state
  - [ ] Renders the error fallback when the Error Boundary catches
  - [ ] Handles empty data (empty array, null, undefined props)
  - [ ] All user interactions that the component supports (clicks, form submissions, etc.)
- Coverage MUST reach ≥75% on all four dimensions.

---

## Step 5 — Verify

Run the following and confirm all pass before declaring complete:

```bash
npm run lint
npm run typecheck
vitest run --coverage src/app/components/<ComponentName>/
```

Report the coverage percentages and confirm all checks pass.
