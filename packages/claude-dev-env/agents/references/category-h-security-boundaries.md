# Category H — Security boundaries

**What this category audits:** injection (SQL / command / template), path traversal, authentication and authorization bypass, secret and credential leakage, SSRF, CSRF, deserialization gadgets, file-upload validation — anything where untrusted input crosses a privilege boundary without proper sanitization.

**Examples of Category H findings:**
- User input concatenated into SQL rather than parameterized.
- File path joined from untrusted input without normalization or root containment.
- Token, password, or API key written to a log line.
- A `pickle.loads` call against attacker-controllable bytes.
- An HTTP redirect to a URL derived from a query parameter without an allowlist.

**Companion reference:** see `source-material-section-types.md`.

---

## Sub-bucket decomposition (Category H)

| ID | Axis name | Concrete checks |
|---|---|---|
| H1 | SQL injection | Parameterization vs string concatenation; ORM `raw()` usage; dynamic table/column names. |
| H2 | Command injection | `shell=True`, `os.system`, f-string into shell, PowerShell `-Command` with interpolated input. |
| H3 | Path traversal | User input joined to a base path without `realpath` + root containment check. |
| H4 | Authentication bypass | Missing auth checks; role checks bypassed via direct API; cookie / token validation gaps. |
| H5 | Authorization checks | Vertical (admin vs user) and horizontal (user A vs user B) access controls; IDOR vulnerabilities. |
| H6 | Secret / credential leakage | API keys / tokens / passwords in logs, errors, traces, env-dump endpoints, telemetry. |
| H7 | SSRF / external request validation | URL parameters not validated against allowlist; cloud metadata endpoint blocked? |
| H8 | CSRF / state-changing without token | POST/PUT/DELETE handlers without CSRF protection; same-origin assumptions. |
| H9 | Deserialization | `pickle.loads`, `yaml.load` (without SafeLoader), `eval` / `exec` against external input. |
| H10 | File upload / MIME validation | Trusted Content-Type from client; no extension allowlist; no magic-byte verification. |

---

## Reusable sample prompt template (Category H)

````
Audit [REPO/ARTIFACT] [TARGET ID] for **Category H only** (security boundaries). Skip A–G, I–K. Sub-bucket forced-exhaustion mode: Category H is decomposed into [N] sub-buckets below. Each sub-bucket REQUIRES at least one Shape A finding OR exactly one Shape B proof-of-absence with **at least 3 adversarial probes** specific to that sub-bucket. A sub-bucket returning neither is a protocol gap.

[ARTIFACT METADATA — including the trust model: who is the attacker, what input do they control?]
ID prefix: `find`.

## Source material ([N] files/sections, all lines in scope)

[INLINE THE FULL ARTIFACT HERE — do not ask the agent to fetch.]

## Sub-buckets (each requires Shape A finding OR Shape B with ≥3 adversarial probes)

**H1. SQL injection**
- Every SQL string built from external input — parameterized? Or string-concatenated?
- ORM `.raw()` / `.execute()` calls with user-supplied fragments.
- Dynamic identifiers (table/column) — must use whitelist, never interpolate.

**H2. Command injection**
- `subprocess.Popen(..., shell=True)` with any interpolated input.
- `os.system`, `os.popen` — never safe with untrusted input.
- f-strings building command-line strings (Bash, PowerShell, cmd) where input flows in.
- PowerShell `-Command` with `f"..."` interpolation — argv-based invocation is safer.

**H3. Path traversal**
- `os.path.join(base, user_input)` without subsequent `realpath` + ancestor check.
- File-serving handlers — input normalized and confined to a root?
- Archive extraction (`zipfile`, `tarfile`) — entries with `..` validated?

**H4. Authentication bypass**
- Endpoints / functions added in this diff — auth check present and correct?
- Token/session validation flows — expired, revoked, malformed token paths.

**H5. Authorization checks**
- Vertical: admin-only paths protected by role check?
- Horizontal: user A cannot access user B's resources via crafted ID (IDOR).
- API endpoints accepting `user_id` from request — verified against session?

**H6. Secret / credential leakage**
- Logs, error messages, exception stacktraces — do they include API keys, tokens, passwords?
- Environment dumps in error pages.
- Error messages that reveal internal paths or schema.

**H7. SSRF / external request validation**
- URL parameters fed into `requests.get` / `urllib.request` — allowlist or block?
- Cloud metadata endpoint (169.254.169.254) blocked at the application layer?
- DNS rebinding considered?

**H8. CSRF / state-changing without token**
- POST / PUT / PATCH / DELETE handlers — CSRF token verified?
- Same-origin assumptions explicit?

**H9. Deserialization**
- `pickle.loads`, `yaml.load(...)` (must use `SafeLoader`), `marshal.loads`, `eval`, `exec`.
- JSON decoders for arbitrary types (`json.loads(..., object_hook=...)`).

**H10. File upload / MIME validation**
- Content-Type trusted vs verified from magic bytes.
- Extension allowlist enforced post-rename.
- Path of stored upload — outside web root, no execute permission.

## Cross-bucket questions to answer at the end

Q1: Are there inputs that cross two boundaries (e.g., a path traversal input H3 that also lands in a SQL query H1)?
Q2: What's the worst injection / leakage hazard introduced by this artifact? Cite [file:line].
Q3: Which input vector is most fragile to a future API addition (e.g., a new endpoint that accepts the same parameter without re-validating)?

## Output

Lead: `Total: N (P0=N, P1=N, P2=N)`. For each sub-bucket [H1]–[HN], produce Shape A or Shape B (with ≥3 probes). Cross-bucket Q1–Q3 answers after the per-sub-bucket walk. Adversarial second pass: "assume your first pass missed at least 3 P0/P1 vulnerabilities across these [N] sub-buckets — find them." Open Questions section. Read-only. No edits, no commits.

Note: Category H findings tend toward P0/P1 since they're security-relevant — adjust the adversarial-pass quota severity accordingly.
````

For a literal worked example using PR #394, see `category-a-api-contracts.md`. Category H walks for that diff:
- H2: the test helper builds `f"(Get-Item '{path}').CreationTimeUtc = [DateTime]'{date_str}'"` and passes to `subprocess.run(["powershell", "-Command", ...])`. The `path` is from `tempfile.TemporaryDirectory` (locally trusted) but the f-string into a single-quoted PowerShell literal is fragile; if an attacker controlled the path they could break out of the literal with a single quote. Severity P2 in this context (test code, locally bounded).
- H3: `arguments.root` from CLI is passed to `os.walk` and `os.rmdir`. Path traversal isn't applicable since the script *is* the privileged process — it walks whatever is given. The trust assumption is "operator provides correct root."
- H6: no secrets / credentials handled.
