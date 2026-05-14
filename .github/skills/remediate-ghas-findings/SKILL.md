---
name: remediate-ghas-findings
description: "Fetch all open GitHub Advanced Security (GHAS) findings — code scanning, Dependabot, and secret scanning — and remediate each one. Targets alerts visible on the repository Security tab. Distinct from the OWASP security-auditor which reviews source code statically."
argument-hint: "Optionally scope to one alert type: 'code', 'dependabot', or 'secrets'. Defaults to all three."
---

# Remediate GHAS Findings

This skill drives end-to-end remediation of every open GitHub Advanced Security alert on the
repository. It fetches live findings from the GitHub API, triages them by type and severity,
applies code fixes or dependency updates, flags secrets for rotation, then verifies the fixes
before reporting completion.

---

## Scope

| Alert type | Source | What remediation looks like |
|---|---|---|
| **Code scanning** | CodeQL / third-party SAST tools | Edit source files to eliminate the flagged pattern |
| **Dependabot** | Dependency graph + advisory DB | Bump the vulnerable package in the manifest and lockfile |
| **Secret scanning** | GitHub secret patterns | Remove or replace the credential in source; prompt user to rotate |

This skill targets alerts shown on the **Security** tab of the GitHub repository. It does NOT
duplicate the OWASP source-code audit performed by the `security-auditor` agent.

---

## Prerequisites

- `gh` CLI is authenticated (`gh auth status` must pass).
- The calling agent has write access to source files.
- Determine repo coordinates before running any command:

```bash
# Derive from git remote — do not hard-code
gh repo view --json nameWithOwner -q .nameWithOwner
```

All subsequent commands use `$REPO` (e.g. `bitsyscerts/bitsyscerts`).

---

## The Workflow

---

### Step 1 — Fetch All Open Alerts (MANDATORY)

Run all three queries. Capture the raw JSON for use in subsequent steps. Filter to `state=open`
only — do not attempt to re-remediate already-dismissed or fixed alerts.

```bash
# Code scanning — open alerts only
gh api "repos/$REPO/code-scanning/alerts?state=open&per_page=100" | jq .

# Dependabot — open alerts only
gh api "repos/$REPO/dependabot/alerts?state=open&per_page=100" | jq .

# Secret scanning — open alerts only
gh api "repos/$REPO/secret-scanning/alerts?state=open&per_page=100" | jq .
```

If any command returns a 404 or a `{"message": "..."}` error object, note it and continue with
the alert types that did return data. A 404 on secret scanning means the feature is not enabled
— skip that category silently.

**Present a triage summary table to the user before proceeding:**

| # | Type | Severity | Rule / Package / Secret type | Location | Alert number |
|---|---|---|---|---|---|
| … | … | … | … | … | … |

Sort by: Critical > High > Medium > Low > Warning > Note.

**Do not begin remediation until the triage table has been presented.**

---

### Step 2 — User Confirmation (MANDATORY — cannot be skipped)

Ask explicitly:

> "The table above lists every open GHAS finding. Which of these would you like me to
> remediate? Reply 'all', list specific alert numbers, or reply with an alert type
> ('code', 'dependabot', 'secrets') to remediate just that category."

**MUST NOT modify any file until the user responds.**

---

### Step 3 — Remediate Code Scanning Alerts

For each approved code scanning alert:

1. **Read the alert detail:**
   ```bash
   gh api "repos/$REPO/code-scanning/alerts/$ALERT_NUMBER"
   ```
   Extract: `rule.id`, `rule.description`, `most_recent_instance.location` (file + line),
   `most_recent_instance.message.text`.

2. **Read the flagged file** at the reported line range (±20 lines for context).

3. **Apply a targeted fix** that eliminates the flagged pattern. Follow these rules:
   - Fix ONLY the reported location. Do not refactor surrounding code.
   - If the fix requires a new helper, create it as a separate file (≤200 lines).
   - After editing, confirm `ruff check --fix && ruff format && ruff check` pass (Python) or
     `npm run lint` passes (TypeScript/React) before moving to the next alert.
   - If the fix is non-trivial or the correct resolution is ambiguous, pause and ask the user
     before applying.

4. **Common CodeQL rules and their standard remediations:**

   | Rule ID | Common cause | Standard fix |
   |---|---|---|
   | `py/sql-injection` | String-formatted SQL | Use parameterised queries / SQLAlchemy ORM |
   | `py/clear-text-logging-sensitive-data` | Logging passwords/tokens | Redact before logging |
   | `py/path-injection` | `os.path.join` with user input | Validate and sanitise path components |
   | `py/incomplete-url-scheme-check` | `startswith("http")` bypass | Use `urllib.parse.urlparse` scheme check |
   | `js/xss` | Unsanitised `innerHTML` | Use `textContent` or a sanitisation library |
   | `js/sql-injection` | Template-literal SQL | Use parameterised queries |
   | `js/hardcoded-credentials` | Literal secret in source | Replace with environment variable |

5. After all code scanning fixes are applied, run the relevant test suite:
   - Python: `cd src/api && pytest` (or `cd src/ctpool && pytest`)
   - React: `cd src/app && npm run test`

   MUST NOT proceed to the next alert type if the test suite fails.

---

### Step 4 — Remediate Dependabot Alerts

For each approved Dependabot alert:

1. **Read the alert detail:**
   ```bash
   gh api "repos/$REPO/dependabot/alerts/$ALERT_NUMBER"
   ```
   Extract: `dependency.package.name`, `dependency.package.ecosystem`,
   `dependency.manifest_path`, `security_advisory.cvss.score`,
   `security_vulnerability.first_patched_version.identifier`.

2. **Determine the safe version** — use `first_patched_version` from the alert. If null, the
   advisory has no patched version yet; note this as unresolvable and skip.

3. **Apply the version bump** based on ecosystem:

   **Python (`pip` / `uv`)** — edit `pyproject.toml` or `requirements*.txt`:
   ```bash
   cd src/api   # or src/ctpool — check manifest_path
   uv add "package>=safe_version"
   # Then verify lockfile is regenerated
   ```

   **Node.js (`npm` / `pnpm`)** — edit `package.json`:
   ```bash
   cd src/app
   pnpm update package@safe_version
   # Confirm pnpm-lock.yaml is updated
   ```

4. After bumping, run a quick import/build smoke test:
   - Python: `python -c "import package_name"` inside the venv
   - Node: `pnpm run build` (or `tsc --noEmit` if no build step)

5. If the bump introduces a breaking change (the smoke test or test suite fails), note the
   conflict and ask the user how to proceed before moving on.

---

### Step 5 — Remediate Secret Scanning Alerts

> **Important:** BitsysCerts source code should never contain live credentials. These fixes
> are about removing the secret from source. The actual credential MUST be rotated in the
> external service — this skill cannot do that for you and will explicitly flag every secret
> that requires rotation.

For each approved secret scanning alert:

1. **Read the alert detail:**
   ```bash
   gh api "repos/$REPO/secret-scanning/alerts/$ALERT_NUMBER"
   ```
   Extract: `secret_type`, `secret_type_display_name`, `locations_url`.

2. **Fetch the location(s):**
   ```bash
   gh api "$LOCATIONS_URL"
   ```
   Extract file path, start/end line.

3. **Replace the literal secret** with a reference to an environment variable or secrets
   manager. Example patterns:

   ```python
   # Before (flagged)
   API_KEY = "sk-live-abc123..."

   # After (safe)
   import os
   API_KEY = os.environ["MY_SERVICE_API_KEY"]
   ```

   ```typescript
   // Before (flagged)
   const apiKey = "sk-live-abc123...";

   // After (safe)
   const apiKey = import.meta.env.VITE_MY_SERVICE_API_KEY;
   ```

4. **If the secret appears in a git-committed file that is still in history**, note that
   `git` history rewriting is required. Do NOT attempt `git filter-repo` or force-pushes
   autonomously — present the finding to the user with the exact command to run:
   ```
   ACTION REQUIRED: Secret found in git history.
   Run: git filter-repo --path <file> --invert-paths  (after rotation)
   Or use: gh secret set <NAME> to add the rotated value as a repository secret.
   ```

5. **Produce a rotation checklist** — one row per secret — to present at the end of Step 5:

   | Secret type | File | Line | Env var to set | External service to rotate in |
   |---|---|---|---|---|
   | … | … | … | … | … |

   Present this checklist to the user. MUST NOT dismiss the alert via the API — dismissal
   happens automatically when GitHub re-scans and no longer detects the pattern, or the user
   dismisses it manually after confirming rotation.

---

### Step 6 — Verify and Report

1. **Run linting** across all modified files:
   - Python: `ruff check --fix && ruff format && ruff check` (MUST be clean)
   - TypeScript: `cd src/app && npm run lint` (MUST be clean)

2. **Run the full test suite** for each sub-project that had files modified:
   - `cd src/api && pytest`
   - `cd src/ctpool && pytest`
   - `cd src/app && npm run test`

3. **Produce a final remediation report:**

   ```
   ## GHAS Remediation Report

   ### Code Scanning
   - Fixed: <N> alerts
   - Skipped (ambiguous): <list>
   - Remaining open: <list alert numbers>

   ### Dependabot
   - Bumped: <package@old → package@new> (×N)
   - Unresolvable (no patched version): <list>
   - Remaining open: <list alert numbers>

   ### Secret Scanning
   - Secrets removed from source: <N>
   - ⚠ Rotation required (see checklist above): <N>
   - Remaining open: <list alert numbers>

   ### Test Suite
   - All suites passing: yes / no (detail failures)
   - Linting clean: yes / no
   ```

4. If any Critical or High code scanning findings remain unresolved, surface them explicitly
   and block completion until the user either approves a manual fix or explicitly accepts the
   risk.

---

## What This Skill Does NOT Do

- Does NOT rewrite git history autonomously.
- Does NOT rotate credentials in external services.
- Does NOT dismiss alerts via the API on your behalf.
- Does NOT perform a general OWASP source-code audit (use `/security-review` for that).
- Does NOT modify files outside `src/`.
