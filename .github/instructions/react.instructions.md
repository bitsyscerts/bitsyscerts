---
description: "Use when creating or modifying TypeScript and TSX files in src/app/. Enforces React Rules of Hooks, mandatory Error Boundaries, Suspense with skeleton placeholders, Mantine component and theme token usage, explicit TypeScript interfaces, TanStack Query for server state, and accessibility requirements."
applyTo: "src/app/**"
---

# React / TypeScript / Mantine Standards

---

## File and Component Size

- Component files MUST NOT exceed **200 lines** (Robert C. Martin good threshold).
- If a component file approaches **150 lines**, evaluate immediately for extraction — do not
  wait until 200 is reached.
- A component file MUST export exactly **one** primary component. Secondary exports (types,
  sub-components) may exist only if they are tightly coupled and together keep the file under
  200 lines.

---

## Component Decomposition

- Every meaningful UI grouping MUST be its own component file. MUST NOT write inline JSX
  blocks longer than 5 elements inside a parent component without extracting them.
- **Pages** are composed exclusively of named components. A page file MUST NOT contain
  business logic, data transformation, or inline JSX beyond layout composition.
- Follow this construction order (bottom-up, per decomposition rules):
  1. Primitive UI components (buttons, inputs, badges)
  2. Domain components (CertificateCard, UserAvatar)
  3. Feature sections (CertificateList, LoginForm)
  4. Pages (composed from feature sections)

---

## Rules of Hooks

MUST follow all React Rules of Hooks without exception:

- MUST NOT call hooks conditionally (inside `if`, `switch`, ternary, or short-circuit `&&`).
- MUST NOT call hooks inside loops or nested functions.
- MUST NOT call hooks from non-React functions (only from function components and custom hooks).
- Custom hooks MUST:
  - Have names that start with `use`
  - Be defined in their own files under `src/app/hooks/`
  - Have a single responsibility, documented in a JSDoc comment
  - Have a co-located test file

---

## Error Boundaries

- MUST wrap every **page** in an Error Boundary.
- MUST wrap every major **feature section** (data grids, forms, charts, complex async content)
  in its own Error Boundary.
- Error Boundaries MUST display a user-friendly error message with a retry affordance.
  MUST NOT expose error stack traces, component names, or internal error details to the user.
- The project MUST maintain a reusable `<ErrorBoundary>` component at
  `src/app/components/ErrorBoundary/ErrorBoundary.tsx` with a configurable `fallback` prop.
  MUST NOT write one-off Error Boundary implementations inline.

---

## Suspense and Loading States

- ALL asynchronous data fetching MUST be paired with a Suspense boundary and a meaningful
  fallback.
- Suspense fallbacks MUST use **skeleton/shimmer placeholders** that match the shape of the
  loaded content. MUST NOT use a centered spinner as the sole loading indicator for a content
  area.
- Use Mantine's `Skeleton` component for content placeholders. Match the skeleton's dimensions
  to the target content as closely as possible.
- MUST NOT render blank areas, empty containers, or unhandled loading states. Every async data
  region has exactly three states handled: loading (skeleton), error (Error Boundary), and
  success (content).

---

## Mantine Usage

- MUST use Mantine component library for all UI elements. MUST NOT create custom implementations
  of components that Mantine provides (buttons, modals, notifications, forms, tables, etc.).
- MUST use **Mantine theme tokens** for all colors, spacing, font sizes, and border radii.
  MUST NOT hardcode CSS color values, pixel values for spacing, or font size numbers anywhere.
- Theme customization MUST be done exclusively in the central theme configuration file
  (`src/app/theme.ts` or equivalent). MUST NOT override theme values via inline `style` props
  at the component level.
- MUST use Mantine's `useForm` hook for all forms. MUST NOT use uncontrolled inputs, raw
  `useState` for form fields, or any other form library without explicit team agreement.
- Use Mantine's notification system for all user-facing feedback messages. MUST NOT use
  `alert()`, `confirm()`, or custom toast implementations.

---

## TypeScript

- MUST NOT use `any`. If a third-party type is unavailable or incomplete, use `unknown` and
  narrow the type explicitly with type guards or assertions before using the value.
- All component props MUST have an explicit TypeScript `interface`, defined either in the same
  file or in a co-located `types.ts`.
- API response types MUST be generated from or kept in sync with the backend Pydantic models.
  MUST NOT manually duplicate type definitions between the frontend and backend — pick one
  source of truth (e.g., generated OpenAPI types).
- MUST NOT use type assertions (`as SomeType`) without a comment explaining why the assertion
  is provably safe.

---

## Server State Management

- Server state (data from the API) MUST be managed with **TanStack Query** (React Query).
  MUST NOT manually manage `loading`, `error`, and `data` state variables for API calls with
  `useState` + `useEffect`.
- All API calls MUST be encapsulated in dedicated service functions in
  `src/app/services/<domain>.service.ts`. MUST NOT write `fetch()` or `axios` calls directly
  inside components or hooks.
- Query keys MUST be defined as constants in a co-located `queryKeys.ts` or within the service
  file. MUST NOT use inline string literals as query keys.

---

## Client State Management

- Prefer **local component state** for UI state that does not need to be shared.
- Lift state to the nearest common ancestor only when two or more sibling components must share
  it.
- For global client state (theme preferences, auth session, etc.), use React Context or
  **Zustand**. MUST NOT introduce Redux without explicit team agreement.

---

## Accessibility

- All interactive elements MUST have an accessible name via a visible label, `aria-label`, or
  `aria-labelledby`.
- All images MUST have `alt` text. Decorative images use `alt=""`.
- Keyboard navigation MUST work correctly for all interactive components (focus order, Enter/
  Space activation, Escape to close).
- Use Mantine's built-in accessibility props and patterns. MUST NOT override or remove Mantine's
  default ARIA attributes.
- Color MUST NOT be the only means of conveying information (provide a text or icon alternative).

---

## File Organization

```
src/app/
  components/
    ErrorBoundary/
      ErrorBoundary.tsx
      ErrorBoundary.test.tsx
    <ComponentName>/
      <ComponentName>.tsx
      <ComponentName>.test.tsx
      types.ts              # (only if needed)
  hooks/
    use<HookName>.ts
    use<HookName>.test.ts
  pages/
    <PageName>/
      <PageName>.tsx
      <PageName>.test.tsx
  services/
    <domain>.service.ts
    <domain>.service.test.ts
    queryKeys.ts
  types/
    api.ts                  # Generated or synced API response types
  theme.ts                  # Central Mantine theme configuration
  main.tsx                  # Application entry point only
  App.tsx                   # Router and top-level providers only
```

MUST NOT create files outside this structure without updating this document.
