---
description: "Use when adding, reviewing, or updating dependencies in package.json, pyproject.toml, or GitHub Actions workflow files. Enforces proactive upgrades to latest stable/secure versions and OSV.dev vulnerability verification before accepting any version."
applyTo: "src/**, .github/workflows/**"
---

# Dependency Update Rules

## Default Predisposition: Always Latest Stable

Prefer the **latest stable, secure version** of every dependency. This is the default
choice — not an exception that requires justification.

- Do not leave older versions in place without an explicit, written reason.
- Do not wait for Dependabot to flag outdated packages. Upgrade proactively whenever
  touching a manifest, even if the change that triggered the edit is unrelated.
- "Latest" means the latest **stable** release — not alpha, beta, rc, or dev tags —
  unless the project explicitly requires a pre-release.

---

## OSV.dev Security Check — Required Before Accepting Any Version

Before writing any version into a manifest (adding, updating, or knowingly leaving
it unchanged), query [OSV.dev](https://osv.dev) to confirm it has no known
vulnerabilities. The API is free, unauthenticated, and has no rate limits.

### Single-package query

```bash
# PyPI
curl -s -d '{"package": {"name": "fastapi", "ecosystem": "PyPI"}, "version": "0.115.12"}' \
  "https://api.osv.dev/v1/query" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('CLEAN' if not d.get('vulns') else d)"

# npm
curl -s -d '{"package": {"name": "react", "ecosystem": "npm"}, "version": "18.3.1"}' \
  "https://api.osv.dev/v1/query" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('CLEAN' if not d.get('vulns') else d)"

# GitHub Action (GIT ecosystem — use full repo URL as name, tag as version)
curl -s -d '{"package": {"name": "https://github.com/actions/checkout", "ecosystem": "GIT"}, "version": "v4.2.2"}' \
  "https://api.osv.dev/v1/query" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('CLEAN' if not d.get('vulns') else d)"
```

An empty `vulns` array (`{}` or `{"vulns": []}`) means the version is clean.

### Batch query (preferred when updating multiple packages at once)

```bash
curl -s -d '{
  "queries": [
    {"package": {"name": "fastapi",  "ecosystem": "PyPI"}, "version": "0.115.12"},
    {"package": {"name": "pydantic", "ecosystem": "PyPI"}, "version": "2.13.3"},
    {"package": {"name": "react",    "ecosystem": "npm"},  "version": "18.3.1"}
  ]
}' "https://api.osv.dev/v1/querybatch"
```

**If `vulns` is non-empty** for the chosen version: upgrade to the latest clean version.
If the latest version is itself vulnerable, surface the finding to the user before
proceeding — do not silently leave a known-vulnerable version in the manifest.

---

## Ecosystem Reference

| Manifest           | OSV ecosystem name              | How to find the latest version                                |
| ------------------ | ------------------------------- | ------------------------------------------------------------- |
| `pyproject.toml`   | `PyPI`                          | `pip index versions <pkg>` or https://pypi.org/project/<pkg>/ |
| `package.json`     | `npm`                           | `npm outdated` · `npm show <pkg> version`                     |
| GH Actions `uses:` | `GIT` (full repo URL as `name`) | GitHub releases page for each action repo                     |

---

## Per-Manifest Rules

### Python — `src/**/pyproject.toml`

- Pin runtime and dev dependencies to an exact version (`==`). Exact pins make builds
  reproducible and make version drift visible in diffs.
- When upgrading, set the pin to the latest stable, OSV-clean release.
- After any `pyproject.toml` change: `pip install -e '.[dev]'` then the full test suite.

### npm — `src/app/package.json`

- Use `^` (compatible minor/patch) for all packages — the existing convention.
- When a new **major** version is available, upgrade to it proactively rather than
  waiting for a Dependabot PR.
- After any `package.json` change: `npm install` then `npm run test`.

### GitHub Actions — `.github/workflows/*.yml`

- Pin to a **full commit SHA** (for example
  `actions/checkout@<40-char-sha> # v4.2.2`), not a mutable major alias (`@v4`).
- Release tags are mutable pointers; they are better than floating major aliases, but they are
  not fully reproducible. Use tag comments only as human-readable labels for the pinned SHA.
- For paired artifact steps, keep `actions/upload-artifact` and
  `actions/download-artifact` on the same major version.
- When a newer release tag exists for an action, update the pin to that tag's commit SHA.
- Use the full `https://github.com/<owner>/<repo>` URL as the `name` field in OSV queries.

---

## Decision Flow When Touching Any Manifest

```
editing a manifest file?
  └─ for each dep in scope:
       1. look up the latest stable version
       2. query OSV.dev → if vulns present, bump to a clean version
       3. write the clean, latest version into the manifest
       4. run the test suite to confirm nothing broke
```

## What NOT to Do

- Do not add a version below the latest stable without a comment in the manifest
  explaining why (e.g., a known incompatibility).
- Do not skip the OSV check on the assumption a well-known package is clean.
- Do not treat Dependabot as the primary upgrade process — it is a backup safety net.
- Do not use `>=` lower-bound-only constraints; they allow silent future upgrades
  that may introduce vulnerabilities.
