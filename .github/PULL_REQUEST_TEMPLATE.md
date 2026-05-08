## Summary

<!-- One paragraph describing what this PR does and why. Link to the issue it resolves. -->

Closes #

---

## Type of Change

<!-- Check all that apply -->

- [ ] `feat` — New feature (non-breaking)
- [ ] `fix` — Bug fix (non-breaking)
- [ ] `perf` — Performance improvement (non-breaking)
- [ ] `refactor` — Code change with no functional effect
- [ ] `docs` — Documentation only
- [ ] `chore` — Tooling, dependencies, CI
- [ ] `BREAKING CHANGE` — Changes existing public behaviour

---

## What Changed

<!-- Bullet-point list of the concrete changes made. Be specific. -->

-
-

---

## Testing

- [ ] New unit tests written for all new code paths
- [ ] Existing tests updated where behaviour changed
- [ ] `pytest` passes locally (`cd src/api && pytest` and/or `cd src/ctpool && pytest`)
- [ ] `npm run test` passes locally (`cd src/app && npm run test`)
- [ ] Coverage remains ≥ 75% on all four dimensions (statements, branches, functions, lines)

<!-- Paste the coverage summary lines here if this PR affects coverage-sensitive paths -->

---

## Security Checklist

- [ ] All new API inputs are validated with Pydantic before use
- [ ] No raw SQL string concatenation (parameterised queries only)
- [ ] No secrets, credentials, or PII in source code or logs
- [ ] CORS, rate-limiting, and auth checks are unaffected (or intentionally updated)
- [ ] No new third-party dependencies with known CVEs (`pip-audit` / `npm audit` clean)

> [!CAUTION]
> If this PR touches authentication, authorisation, or data persistence, tag a maintainer
> for an OWASP review pass before requesting merge.

---

## Checklist

- [ ] Branch follows naming convention (`feat/`, `fix/`, `chore/`, `docs/`)
- [ ] Commits follow Conventional Commits format
- [ ] File sizes are within limits (no file > 500 lines, no function > 50 lines)
- [ ] Linting passes without suppressions added to make it pass
- [ ] Self-review completed — no debug prints, commented-out code, or TODO left behind
- [ ] PR description is complete (all sections above filled in)
