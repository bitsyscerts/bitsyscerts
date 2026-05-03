---
description: "Use when creating or modifying any source file under src/. Enforces OWASP Top 10 (2021) and OWASP API Top 10 (2023). Covers input validation, output encoding, authentication, authorization, secrets management, parameterized queries, CORS, security headers, and error handling."
applyTo: "src/**"
---

# Security-First Rules

Security is a design constraint applied from line one. It is not a review step added after the
feature is built. Every item below MUST be addressed before code is considered correct. When in
doubt, the secure option is the correct option.

---

## OWASP Top 10 (2021) — Mandatory Compliance Checklist

Evaluate every applicable item when creating or modifying any file:

### A01 · Broken Access Control
- Every endpoint and every data access operation MUST enforce authorization explicitly.
- Default to **deny**. Access is granted by explicit permission, never by the absence of a check.
- MUST NOT trust client-supplied identity claims (user ID in request body, role in JWT payload
  without server-side verification).
- Direct Object References MUST be validated: confirm the requesting user owns or is authorized
  for the specific resource being accessed (see also API1).

### A02 · Cryptographic Failures
- MUST NOT store or transmit passwords, tokens, or PII in plain text.
- Passwords MUST be hashed with bcrypt or Argon2. MUST NOT use MD5, SHA-1, or unsalted SHA-256
  for password storage.
- All data in transit MUST use TLS. MUST NOT fall back to HTTP for any authenticated or
  sensitive endpoint.
- Encryption keys and secrets MUST NOT be hardcoded. See Secrets section below.

### A03 · Injection
- MUST use parameterized queries or an ORM for all database access. MUST NOT construct SQL
  statements by string concatenation or f-string formatting with user input.
- MUST NOT pass user input to shell commands, OS functions, or file path constructors without
  strict validation against an explicit allowlist.
- Input validation MUST use an **allowlist** (permitted values, patterns, ranges). Denylist
  validation is insufficient and MUST NOT be used as the sole defense.

### A04 · Insecure Design
- MUST threat-model every new feature before implementing it. Identify trust boundaries: what
  does this feature accept from untrusted sources? What can go wrong?
- MUST NOT implement workarounds, shortcuts, or temporary bypasses that circumvent security
  controls. "We'll fix it properly later" is not acceptable.

### A05 · Security Misconfiguration
- MUST NOT use default credentials anywhere.
- Debug mode and verbose error output MUST NOT be enabled in any production code path.
- Stack traces and internal error details MUST NOT be returned to API consumers.
- CORS origins MUST be an explicit allowlist. See CORS section below.

### A06 · Vulnerable and Outdated Components
- Pin all dependency versions. MUST NOT use unpinned `*` or `^latest` versions in production
  dependency manifests.
- Before introducing any new dependency, review its CVE history and maintenance status.

### A07 · Identification and Authentication Failures
- All authentication endpoints MUST have rate limiting applied.
- Access tokens MUST be short-lived (≤ 15 minutes). Refresh token rotation MUST be implemented.
- MUST NOT store session tokens or JWTs in `localStorage` or `sessionStorage`. Use httpOnly,
  Secure, SameSite=Strict cookies or in-memory storage only.
- Multi-factor authentication pathways MUST be designed without fallback to SMS-only where
  possible.

### A08 · Software and Data Integrity Failures
- Verify the integrity of data received from external sources before processing it.
- Use Content Security Policy headers on all HTML responses.
- MUST NOT deserialize untrusted data without schema validation.

### A09 · Security Logging and Monitoring Failures
- MUST log: authentication events (success and failure), access control failures, and input
  validation failures.
- MUST NOT log: passwords, tokens, API keys, session identifiers, or PII.
- Logs MUST include sufficient context to reconstruct the event (timestamp, user identity if
  known, resource, action, outcome).

### A10 · Server-Side Request Forgery (SSRF)
- MUST validate and allowlist all URLs used in server-initiated HTTP requests.
- MUST NOT allow user input to directly control the host, scheme, or path of outbound requests
  without strict validation.

---

## OWASP API Top 10 (2023) — Mandatory Compliance Checklist

### API1 · Broken Object Level Authorization
- Every API endpoint that accesses a specific resource MUST verify the requesting user is
  authorized for **that specific resource instance**, not just the resource type.
- MUST NOT rely on obscurity (e.g., opaque IDs) as an authorization control.

### API2 · Broken Authentication
- API keys and JWT tokens MUST be validated on every request — no caching of authorization
  decisions without a cache invalidation strategy.
- Token expiry MUST be enforced server-side. An expired token MUST be rejected regardless of
  client behavior.

### API3 · Broken Object Property Level Authorization
- API responses MUST use explicit Pydantic response models. MUST NOT return raw ORM objects,
  raw dict serializations, or SQLAlchemy models directly.
- Sensitive fields (internal IDs, hashed passwords, internal status codes, audit fields) MUST
  be explicitly excluded from response models.
- MUST NOT use `model.dict()` or `model.__dict__` as a response without a whitelist of
  permitted fields.

### API4 · Unrestricted Resource Consumption
- All list endpoints MUST have pagination with a maximum page size.
- Request body size limits MUST be set at the API server level.
- Rate limiting MUST be applied to all endpoints. Authentication and registration endpoints
  require stricter limits.
- Long-running operations MUST be asynchronous (return a job ID, not block the request).

### API5 · Broken Function Level Authorization
- Administrative, privileged, and management endpoints MUST have role-based access control
  distinct from standard user endpoints.
- MUST NOT rely solely on the URL structure to separate admin from user access — enforce roles
  in the authorization layer.

### API6 · Unrestricted Access to Sensitive Business Flows
- Sensitive business operations (account creation, certificate issuance, bulk exports) MUST be
  rate-limited and require verified identity.
- Automated abuse of business flows MUST be considered in the threat model.

### API7 · Server-Side Request Forgery
- See A10 above.

### API8 · Security Misconfiguration
- Automatic API documentation endpoints (Swagger UI, Scalar, Redoc) MUST be disabled or
  access-controlled in production environments.
- MUST NOT expose internal API routes, health check endpoints with sensitive data, or debug
  endpoints in production.

### API9 · Improper Inventory Management
- All API versions and routes MUST be documented.
- Deprecated routes MUST be removed — not left dormant and undocumented.
- MUST NOT silently deploy a new API version without updating documentation.

### API10 · Unsafe Consumption of APIs
- Validate and sanitize all data received from third-party APIs before use.
- MUST NOT assume third-party API responses conform to their documented schema without
  validation.

---

## Mandatory Implementation Rules

### Input Validation

- MUST validate ALL input at system boundaries: API entry points, form submissions, file
  uploads, message queue consumers.
- **Python/FastAPI**: Pydantic models are mandatory for all request bodies and query parameters.
  No naked `dict` parameters on endpoints.
- **React/TypeScript**: All form input MUST be validated with an explicit schema (Zod is the
  project standard). MUST NOT submit unvalidated form data to the API.
- Validation MUST use an allowlist (permitted values, patterns, character sets, numeric ranges).
  Denylist-only validation is insufficient.

### Output Encoding

- **React**: MUST use JSX rendering for all dynamic content — JSX encodes output automatically.
  MUST NOT use `dangerouslySetInnerHTML` unless the content has been sanitized with DOMPurify
  immediately before rendering.
- **Python/FastAPI**: MUST use Pydantic response models for all endpoint responses. MUST NOT
  return raw `dict` objects or serialized ORM instances without a whitelist model.

### Secrets and Configuration

- MUST NOT hardcode secrets, API keys, database connection strings, or credentials anywhere in
  source code — not even in comments.
- All secrets MUST come exclusively from environment variables at runtime.
- MUST maintain a `.env.example` file documenting every required environment variable with a
  placeholder value and a description.
- `.env` and any file containing real secrets MUST be listed in `.gitignore`. MUST verify this
  before every commit that touches environment configuration.

### Authentication and Sessions

- MUST NOT store JWT tokens or session data in `localStorage` or `sessionStorage`.
- Use httpOnly, Secure, SameSite=Strict cookies for session tokens.
- Implement token refresh flows: short-lived access tokens (≤ 15 minutes), longer-lived refresh
  tokens stored in httpOnly cookies.

### Database Access

- MUST use SQLAlchemy (async) or an equivalent ORM with parameterized queries.
- Raw string-concatenated SQL is a defect and MUST NOT appear anywhere in the codebase.
- Database error messages MUST NOT be surfaced to API consumers. Catch database exceptions,
  log them server-side with context, and return a generic error response.

### HTTP Security Headers

All API responses MUST include:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Strict-Transport-Security: max-age=31536000; includeSubDomains`
- `Content-Security-Policy` (configured per environment)

### CORS

- The CORS `Access-Control-Allow-Origin` header MUST use an explicit allowlist of permitted
  origins.
- `Access-Control-Allow-Origin: *` is **never** acceptable in a production environment or on
  any endpoint that handles authenticated requests.

### Error Handling

- API errors MUST return a structured error response: a client-safe message and an internal
  error code. Example: `{"error": "Certificate not found", "code": "CERT_404"}`.
- Stack traces MUST NOT be included in any API error response.
- All unexpected exceptions MUST be logged server-side with full context (request ID, user ID
  if available, timestamp, exception type, message, traceback).
- The response to the client for an unexpected exception MUST be generic: HTTP 500 with a
  reference code the user can provide to support.
