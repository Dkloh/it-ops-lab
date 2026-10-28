# Portfolio release verification

Verified 2026-10-28 on Linux. The release starts from main's completed Milestone 7
(commit d7aae7b), preserves the application architecture, and adds documentation,
safer retained demo data, screenshots and release evidence. No deployment, visibility
change, authentication feature, new service or additional milestone is included.

## Executed checks

| Check | Actual result |
| --- | --- |
| Complete backend pytest suite | **261 passed**, including all 257 previous backend tests |
| Ruff lint / formatting | Passed |
| Frontend clean `npm ci` | Passed using committed lockfile |
| Vitest / Testing Library | **17 passed** under Vitest 5.0.5 |
| TypeScript validation | Passed |
| Prettier validation | Passed |
| Production frontend build | Passed; assets remain ignored, not deployed |
| `npm audit` | 0 known vulnerabilities |
| `npm audit --omit=dev` | 0 known vulnerabilities |
| Python pip-audit | 0 known vulnerabilities after targeted pip update; local editable project skipped |
| Alembic current / metadata check | `5d78151a73af (head)`; no pending model changes |
| Migration cycle / compatibility | Existing temporary-database tests passed for upgrade/downgrade/re-upgrade and preservation of earlier data |
| Retained demo / persistence | New file seeded; reopening retained 8 original events, two findings and three simulated observations |
| Demo protection | Existing file/symlink and URL-metacharacter paths refused; environment restored; retained targets disabled |
| Browser integration | Linux Chromium verified seeded views, fresh raw upload, search, diagnostics, evidence, disabled target creation and result history |
| Responsive / keyboard | All five routes fit a 390px viewport; skip navigation and labeled controls verified |
| Repository hygiene | Local environments, SQLite variants, environment overrides, node_modules and dist ignored; relative documentation links checked |

Browser viewing of seeded history produced no POST requests. Fresh browser actions
then appended another eight-event upload and diagnostic run; the disposable database
contained 16 events, four findings and three original network observations afterward.
Foreign-key checks remained clean and earlier records remained accessible. No live
external network measurement was made. Downloading packages and querying advisory
feeds for setup/audits are separate from application-network demonstrations.

The browser used the actual Vite proxy and ordinary FastAPI application, with no
runtime network mock installed in that server. Simulated observations had already
been seeded offline and their targets disabled. This verifies that reviewing those
records does not trigger a real check. Tests exercise expected real transport behavior
through controlled resolver/socket/httpcore mocks, including unsafe addresses,
peer mismatches, redirects, timeouts and TLS failures.

## Tested tool versions

| Component | Version |
| --- | --- |
| Python | 3.12.14 |
| Node / npm | 24.19.0 / 11.9.0 |
| FastAPI / Pydantic | 0.162.0 / 2.14.1 |
| SQLAlchemy / Alembic | 2.1.6 / 1.20.1 |
| HTTPX / httpcore | 0.28.1 / 1.0.9 |
| React / React Router | 19.3.1 / 7.18.5 |
| Vite / TypeScript | 7.3.7 / 5.9.3 |
| Vitest | 5.0.5 |
| pip / pip-audit | 26.2.2 / 2.10.1 |

These record the tested environment, not a promise that version ranges will always
resolve to the same packages. npm's lockfile is committed; Python has compatible
ranges and does not yet have a full transitive lockfile.

## Warnings and limits

- Starlette's test-client integration emits one existing HTTPX deprecation warning.
- npm clean installation reports deprecated whatwg-encoding in jsdom test tooling.
  Neither npm audit reports an advisory for the installed dependency tree.
- Python auditing initially reported old pip 25.0.1; the packaging tool was specifically
  updated to 26.2.2. Details, identifiers and final reports are in the security review.
- The editable project is not a public PyPI distribution and cannot be advisory-matched;
  source review/tests complement dependency auditing.
- Windows/PowerShell was not available. Commands use documented PowerShell syntax;
  equivalent Python/Node CLI and browser workflows were executed on Linux. The symlink-specific test explicitly skips on Windows when OS permission is unavailable;
  regular-file refusal remains separately tested. No Windows
  certification or full screen-reader audit is claimed.
- No user authentication/authorization, continuous monitoring, production alerting,
  incident-management integration, public deployment or production frontend hosting.
- Findings are batch-local phrase-rule observations, not confirmed causes. Network
  observations represent their own times and cannot establish historical causality.
- Public-only checks select one approved address without retries; proxy-only routing
  can fail. OS DNS workers are bounded but cannot be forcibly cancelled.

## Recheck before presenting

Use a new disposable demo path, then the root README's test/build/audit commands.
Review the current advisory reports rather than treating this dated result as permanent.
Screenshots were captured directly at ordinary desktop/mobile viewport sizes with
synthetic data. PNGs are approximately 104–186 KiB each, without source-image edits,
private infrastructure details, credentials or personal information.

## Owner's remaining manual choices

1. Review the feature PR/comparison and merge only after approval.
2. Apply the suggested GitHub description/topics if desired; visibility remains unchanged.
3. Choose a source license deliberately before advertising reuse rights.
4. Optionally tag the reviewed commit/create a GitHub Release and copy portfolio text
   and screenshots to a personal site. Neither tagging nor publication is performed here.
5. Keep the application local. Public hosting requires the separate controls described
   in the security review and is outside this release.
