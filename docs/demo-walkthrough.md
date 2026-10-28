# Retail POS incident: repeatable, offline portfolio demonstration

The dataset is synthetic. Eight records include startup/success, three database
timeouts, one authentication warning and recovery. No customer data or credentials
are needed. The same API and SQLite schema are used in the demo and application.

## Prepare a new disposable workspace

Install the dependencies using the root README. From the repository root:

```powershell
.\.venv\Scripts\python.exe scripts/demo_network_diagnostics.py --database .\portfolio-demo.db
$demoPath = (Resolve-Path .\portfolio-demo.db).Path.Replace('\', '/')
$env:IT_OPS_DATABASE_URL = "sqlite:///$demoPath"
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --reload --host 127.0.0.1
```

In another terminal, `cd frontend`, `npm ci`, then `npm run dev`. Open the local Vite
page at `http://127.0.0.1:5173`. Both servers bind only to localhost. PowerShell syntax
is documented; release execution used equivalent Linux Python/Node commands.

This is the single retained-data seeding entry point. It creates the file exclusively,
refuses existing files/symlinks, accepts a plain `.db`/`.sqlite`/`.sqlite3` destination,
and rejects URL metacharacters in paths. The parent directory must exist. It never
opens the usual development database. If interrupted, preserve or inspect the new
partial file and choose another fresh filename; the script does not delete data.
Do not remove an existing file merely to silence its overwrite refusal.

Console output explicitly says SIMULATED and reports actual generated service,
batch and run IDs. Do not assume any ID value. Retained demo network targets are
**disabled** after recording their mocked observations. The normal API therefore
cannot accidentally rerun them against the internet. No safety checks are weakened.
To repeat, use `portfolio-demo-2.db` and point the backend to that new file. Without
`--database`, the existing short-lived console demonstration still uses a temporary
file and removes it when finished; that mode does not populate the dashboard.

## Walk through the evidence

1. **Overview:** expect one service, eight events, three errors and one warning.
   These are actual SQL counts, not UI constants. Two HIGH findings and three network
   observations already exist in this newly seeded file.
2. **Services:** select `retail-pos` / `simulated-demo`. Review its inventory entry.
   To demonstrate service creation, create another synthetic service/environment;
   the total will then increase, so original expected counts apply only to a fresh seed.
3. **Logs:** choose the POS service and its seeded batch. Filter severity ERROR.
   Expect three `Database connection timed out` records. Two share a timestamp and
   remain separate events with distinct IDs. Open one to inspect its metadata.
4. **Summary:** expect INFO 4, WARNING 1, ERROR 3, DEBUG/CRITICAL 0; the dataset spans
   13:00–14:00 UTC on 2026-10-27. Summary follows service/batch/time scope, separately
   labeled from the severity/message-filtered table.
5. **Diagnostics:** choose that service and batch. Open its historical run, or explicitly
   click Run diagnostics to create another run. Refresh never reruns analysis.
6. **Findings:** expect `REPEATED_TIMEOUTS` and `DATABASE_CONNECTION_ERRORS`, both HIGH,
   each supported by the same three ERROR IDs from 13:05–13:07 UTC. Inspect evidence
   and compare the IDs to the log search rather than assuming numeric values.
7. **Network Checks:** choose the POS service and review Simulated DNS/TCP/HTTP targets.
   Select each to review history. DNS succeeds, TCP records TIMEOUT, and HTTP records
   status 503 with HTTP_STATUS. The target labels, console output and disabled state
   identify the observations as simulated. All are new persisted rows, not browser mocks.
8. **Observation times:** check_results.checked_at reflects seeding time; the log
   timestamps are historical. These are not simultaneous observations of a real outage.

For a live upload demonstration, choose the existing service in Logs and upload
`samples/retail-pos.jsonl`. Expect eight accepted and zero rejected records, then
follow the batch-specific logs/Analyze links. This adds another batch; filter by it
to retain expected counts. Running diagnostics on it creates two HIGH findings again.
Uploading or analyzing again appends history rather than replacing earlier records.

## A defensible incident hypothesis

“The synthetic POS application logged three database connection timeouts between
13:05 and 13:07 UTC, followed by a recovery event at 13:10. Two deterministic rules
flagged those same events. I would investigate upstream/database availability,
network reachability and connection-pool limits. The later simulated TCP timeout
and HTTP 503 demonstrate how to record layer-specific observations, but cannot
prove what caused the earlier application failures.”

The authentication warning is insufficient for the five-event authentication rule.
A successful DNS lookup proves naming worked in that observation, not TCP or SQL
health. A 503 is an application response; a TCP timeout or TLS failure is a different
stage. Do not assert downtime, compromise or root cause without further evidence.

## Optional real checks and common problems

The portfolio demo requires **no external network calls**. If you separately want
real measurements, register a new enabled target for an authorized public destination
and explicitly click Run. That is a real operation, not the seeded simulation.
Private/loopback/metadata restrictions and verified TLS remain unchanged.

- Existing-file refusal: choose a new disposable filename; never overwrite a real DB.
- Empty dashboard: verify both the environment URL and server process point to the
  seeded file, not the default database. Frontend uses the localhost Vite proxy.
- Duplicate counts: re-uploads/reruns append records. Scope investigation to the
  intended batch/run, or seed a new disposable file for original counts.
- Zero findings: verify phrases, severity and accepted events; the original POS
  sample should yield exactly two rule findings, not an authentication finding.
- Disabled Run button for seeded targets: intentional. Review their history without
  contacting any service. Register a separate authorized target only for real checks.

For screenshots, use only synthetic records. Capture Overview, ERROR-filtered Logs,
Diagnostic findings/evidence and Network history. Repository screenshots were captured
through Chromium from seeded SQLite data; no source-image states were edited.
