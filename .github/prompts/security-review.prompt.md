---
description: "Perform a read-only OWASP security audit of a file, module, endpoint, or component. Maps findings to OWASP Top 10 (2021) and OWASP API Top 10 (2023) with severity ratings, evidence, and concrete remediation code examples."
agent: "agent"
tools: [read, search]
argument-hint: "Path to audit, e.g. 'src/api/auth/router.py' or 'src/app/components/LoginForm'"
---

Perform a security audit of: **${input}**

This is a **read-only** audit. MUST NOT modify any files. MUST NOT suggest code changes inline
— all remediation is provided as examples in the report only.

---

## Audit Scope

Review the specified code against:

1. OWASP Top 10 (2021): A01 through A10
2. OWASP API Top 10 (2023): API1 through API10
3. Project security rules: [security.instructions.md](../.github/instructions/security.instructions.md)

---

## For Each Finding, Report

- **OWASP ID** — e.g., A03, API1
- **Severity** — Critical / High / Medium / Low / Informational
- **Location** — file path and line number
- **Description** — what the vulnerability is and why it matters
- **Evidence** — the exact code that demonstrates the issue
- **Remediation** — concrete corrected code example

---

## Severity Definitions

| Severity | Meaning |
|----------|---------|
| Critical | Direct exploitability; data breach or full system compromise is possible (e.g., SQL injection, authentication bypass, hardcoded credentials) |
| High | Significant risk with likely real-world impact (e.g., missing authorization check, sensitive data in response, no rate limiting on auth endpoint) |
| Medium | Risk under specific conditions (e.g., overly broad CORS, missing security headers, verbose error messages) |
| Low | Defense-in-depth improvement (e.g., missing `httpOnly` flag, no CSP header) |
| Informational | Best practice improvement with minimal direct risk |

---

## Required Report Format

```
## Security Audit Report: <target>
Audit Date: <today>

### Executive Summary
<2–3 sentences: overall security posture, most critical issues found>

### Findings Summary
| ID | OWASP | Severity | Brief Description |
|----|-------|----------|-------------------|

### Detailed Findings

#### FINDING-001 · <Short Title>
- **OWASP**: <ID> — <Name>
- **Severity**: <level>
- **Location**: `<file>:<line>`
- **Description**: <explanation>
- **Evidence**:
  ```<language>
  <vulnerable code>
  ```
- **Remediation**:
  ```<language>
  <corrected code>
  ```

### Passed Controls
<List OWASP IDs that were reviewed and found to be correctly implemented>

### Not Applicable
<List OWASP IDs that do not apply to the audited code, with a one-line reason>
```

If no findings exist, explicitly state:
**"No findings — all reviewed OWASP controls are correctly implemented in this file."**

MUST NOT omit the "Passed Controls" and "Not Applicable" sections — a complete audit accounts
for every control, not only the failures.
