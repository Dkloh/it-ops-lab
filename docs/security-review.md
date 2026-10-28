# Security review — portfolio release

Reviewed 2026-10-28. This is a source/configuration review and bounded test/audit
record, not penetration testing, a compliance assessment, or a security guarantee.
The application has **no authentication or authorization** and must not be exposed
publicly as-is. No public deployment, repository visibility change or history rewrite
was performed.

## Controls reviewed

| Area | Current behavior and evidence | Residual limit |
| --- | --- | --- |
| Destinations / SSRF | Registration validates bare hosts, types, ports and paths; runtime validates every IPv4/IPv6 DNS answer. Tests reject private, loopback, metadata, multicast, reserved and selected translation ranges. | Registered targets are trusted local configuration, not proof of destination ownership. Address registry data depends on Python. |
| DNS rebinding | TCP connects numerically. HTTP pins a validated address and verifies the OS-reported peer before TLS/request bytes, retaining original-host identity. Mixed unsafe answers fail closed. | No application can attest to external NAT/interception or a compromised OS/network stack. |
| TLS / redirects | `ssl.create_default_context()` retains certificate and hostname checks. No redirects, proxy configuration, cookies or authentication credentials are sent. | Proxy-only environments may fail. A valid TLS session does not prove application health. |
| Time / size bounds | DNS waiting and workers are bounded; TCP timeout is explicit; HTTP shares an I/O deadline, caps header reads and never consumes bodies. | OS resolution cannot be forcibly cancelled; two daemon workers can remain occupied until it finishes. |
| Request validation | Pydantic bodies/queries, constrained IDs, bounded uploads/pagination and type-specific target fields. | Not a user-permission boundary; there is no rate limiting or authorization. |
| Logs / UI | Parser handles untrusted input as data; no eval/shell execution. React renders messages and formatted JSON as text. No log storage in browser storage or telemetry. | Accepted logs and evidence can still contain secrets supplied by a user; use synthetic/sanitized data. URLs retain selected search filters. |
| SQL / persistence | SQLAlchemy binds parameters, escapes literal substring patterns, and uses database constraints/transactions. Foreign keys enabled. | Raw access to the local database is outside API protections; protect the file with OS permissions. |
| Errors / logging | Expected network failures use fixed codes without raw exceptions; generic 500 responses; SQL parameter values hidden. | Local server tracebacks and request paths still need careful handling before sharing logs. |
| Binding / browser | Vite and documented Uvicorn commands bind to 127.0.0.1. Vite proxies API requests; no wildcard CORS is configured. | Loopback is not authentication. There is no dedicated CSRF/Origin authorization gate on mutation endpoints; malicious local processes or browser-origin requests remain a concern. |
| Demo / repository | Explicit new-file seeding, no overwrite or symlink reuse, scoped mocks, disabled retained targets; DBs/builds/environments ignored. | Synthetic observations are not connectivity measurements; running another authorized target is a separate real action. |

The normal network implementation has no simulation flag or private-network bypass.
The seed script mocks operations only while populating a new file; it then disables
those demo targets before the ordinary API is started. Existing paths are refused
before any migration. Paths containing URL metacharacters are rejected to avoid
accidentally interpreting a filename as a different SQLite destination.

## Dependency audit results

Saved machine-readable reports:

- [npm, all dependencies](audits/npm-all.json): **0 known vulnerabilities**.
- [npm, runtime only](audits/npm-runtime.json): **0 known vulnerabilities**.
- [Python installed packages](audits/python.json): **0 known vulnerabilities** after
  the targeted packaging-tool update. The local editable `it-ops-lab` package is
  absent from PyPI and explicitly skipped; its source is covered by review/tests,
  not advisory matching.

The initial Python audit reported 12 advisory entries on pip 25.0.1 (six distinct
identifiers, with duplicates in the advisory feed): PYSEC-2026-1795, -1796, -2875,
-2876, -196 and -3721. Fix versions extend through 26.2. The development environment's
pip was updated specifically to **26.2.2**, then re-audited. Fresh setup instructions
require `pip>=26.2`. No forced npm fixes, broad package upgrades or TLS-verification
bypasses were used. No application runtime library changes were needed.

Audits match reported installed/locked versions against advisory data as of this
review. They do not detect every vulnerability, malicious dependency, license issue
or future advisory. Python runtime requirements remain version ranges; different
future installations can resolve differently. The frontend lockfile is committed.
The known whatwg-encoding deprecation is in jsdom test tooling, not a reported
vulnerability; Starlette emits an existing HTTPX test-client deprecation warning.

### Reproduce audits

From `frontend/`:

```powershell
npm ci
npm audit
npm audit --omit=dev
```

For Python, keep audit tooling isolated from application dependencies:

```powershell
py -3.12 -m venv .audit-venv
.\.audit-venv\Scripts\python.exe -m pip install --upgrade 'pip>=26.2'
.\.audit-venv\Scripts\python.exe -m pip install pip-audit
.\.audit-venv\Scripts\python.exe -m pip_audit --path .\.venv\Lib\site-packages
```

On Linux the equivalent path is `.venv/lib/python3.12/site-packages`; release auditing
used an isolated temporary tooling environment and pip-audit 2.10.1. Audits require
advisory/index access even though the incident demo and tests do not require live
connectivity to external application services. Never use `npm audit fix --force` as
an unreviewed release step.

## Sensitive-data inspection

Tracked paths and historical object names were checked for environment overrides,
private-key files and SQLite files; only the safe `.env.example` was tracked.
Source/configuration review found synthetic fixture values, not real credentials.
This is a limited inspection, not exhaustive secret scanning of every historical
blob. No sensitive history item was discovered and no history was rewritten.
Environment overrides, virtual environments, local SQLite variants, node_modules
and build outputs are ignored. Never paste secrets into Vite variables, sample logs,
portfolio screenshots, API error reports or committed environment files.

## Before any future public deployment

A separate reviewed deployment design would need identity, per-action/resource
authorization, CSRF/Origin protections, trusted-host validation, request/rate limits,
restricted egress and target administration, TLS termination, secret management,
protected data retention/backups, monitoring and dependency/update ownership.
Production static hosting must provide appropriate headers and SPA/API routing;
development reload servers are unsuitable. Revisit SQLite/concurrency and sensitive
log handling for that workload. These are prerequisites to evaluate, not implemented
features, deployment instructions or additional approved milestones.
