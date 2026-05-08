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
