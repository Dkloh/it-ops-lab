# Portfolio and interview materials

## Website description (100–150 words)

IT Ops Lab is a local-first troubleshooting workspace that connects application
logs, diagnostic findings and network observations. I built a Python/FastAPI backend
with SQLAlchemy, SQLite and Alembic, then added a React/TypeScript dashboard for
service inventory, JSONL uploads, SQL-backed search and incident investigation.
Three deterministic rules detect recurring timeouts, authentication failures and
database connection errors, retaining links to the supporting events. Registered
DNS, TCP and HTTP/HTTPS checks record historical observations with public-address
validation, verified TLS and bounded connections. A synthetic retail POS incident
provides a repeatable offline demonstration without real credentials or customer
data. Automated backend and frontend tests cover validation, persistence, failure
handling and interface workflows. The project demonstrates practical support
engineering: separating symptoms from causes, investigating across protocol layers,
and communicating conclusions with evidence and explicit limitations.

## Resume bullets

- Built a FastAPI troubleshooting API with Pydantic validation, bounded JSONL ingestion,
  SQL-backed filtering and a React/TypeScript operations dashboard.
- Designed relational SQLite storage and Alembic migrations for services, logs,
  findings and network history, enforcing foreign keys, uniqueness and atomic writes.
- Implemented three deterministic diagnostic rules with inclusive rolling windows,
  reproducible historical runs and deduplicated supporting-event associations.
- Added DNS, TCP and HTTP/HTTPS observations with public-address validation, pinned
  connections, TLS hostname verification, deadlines and structured failure results.
- Validated the project with 261 backend tests, 17 frontend tests and Chromium
  investigation workflows using synthetic data and mocked external operations.

These describe a portfolio implementation, not user adoption, business savings,
production incident response or a deployed monitoring service.

## Technical talking points

- **Motivation:** support work needs a consistent way to move from a reported symptom
  to searchable evidence and a testable hypothesis. The POS sample makes that concrete.
- **Architecture:** one modular FastAPI application; React is a client, not a second
  business-logic backend. Routes, validation, domain operations and transport are separate.
- **Database:** batches retain ingestion outcomes; normalized events support SQL
  filtering. Runs/findings preserve historical analysis; the join table records evidence.
- **Rules:** phrase/severity matching plus inclusive rolling windows; unions retain all
  justified events without counting overlap twice. Version 1.0.0 is stored with each run.
- **Networking:** DNS resolution, TCP connection establishment and HTTP/TLS are different
  observations. A successful step does not establish health at every higher layer.
- **Security:** public-only targets, all-answer validation, pinned peers, verified TLS,
  no redirects or credentials. No authentication/authorization means localhost only.
- **Testing:** pure engine cases, temporary migrated SQLite integration tests, mocked
  socket/HTTP failure paths, Fetch component tests and browser workflow checks.
- **Trade-offs:** SQLite simplifies local setup; phrase rules are explainable but
  context-limited; bounded synchronous execution avoids worker infrastructure.
- **Future considerations:** identity/authorization and deployment design first;
  retention, query measurement and incident integrations depend on a real workload.
  None of these are claimed as implemented.

## Two-minute spoken demonstration

| Time | Screen and suggested narration |
| --- | --- |
| 0:00–0:20 | Overview: “This is a local support investigation workspace. These counts and recent records come from SQLite. The data is a synthetic POS incident.” |
| 0:20–0:45 | Logs, ERROR filter: “There are three database timeouts. I can narrow the batch/time range and open the original event and metadata.” |
| 0:45–1:10 | Diagnostics/evidence: “Two rules flag the same three events. The finding keeps IDs, UTC times and suggested checks, so I can show exactly what supports it.” |
| 1:10–1:35 | Network history: “These DNS, TCP and HTTP results are simulated and recorded separately. The disabled demo targets prevent accidental live checks. Different observation times do not establish one cause.” |
| 1:35–2:00 | Architecture/tests: “FastAPI is the boundary; SQLAlchemy handles persistence; the rule engine is pure Python. Tests cover failure paths and evidence integrity. This has no auth or public deployment, so those would need a separate design.” |

Use a fresh seeded file and open the relevant tabs beforehand. Keep implementation
details available for questions instead of spending the whole demonstration in code.

## Five likely interview questions

**1. How would you investigate the POS database timeouts?**

I would scope ERROR events to the service, batch and UTC interval, compare repeated
messages and retrieve the supporting IDs. The sample shows three timeouts and later
recovery. I would check database/upstream availability, reachability, pool usage and
configuration. Later simulated connectivity results do not prove the historical cause.

**2. How does the database protect the evidence?**

Foreign keys tie findings to runs and events; the association table's composite key
prevents duplicate evidence. A unique run/rule constraint prevents accidental duplicate
findings. One transaction commits a run, findings and associations together, and tests
inject failures to verify rollback preserves earlier records.

**3. Why might DNS succeed while the application fails?**

DNS only maps a name to addresses. TCP may still fail because of routing, filtering or
a closed listener. TCP success can coexist with TLS problems or HTTP 500. Even HTTP
200 says little about SQL credentials, connection-pool pressure or a particular checkout
transaction. I would distinguish the protocol stage and observation time.

**4. How do you reduce SSRF and DNS rebinding risk?**

Targets must be registered. The application validates every resolved IPv4/IPv6 address
and rejects unsafe answers. Connections use an approved numeric IP; HTTP verifies its
peer and keeps the original hostname for TLS, with redirects disabled. That controls
application-level resolution/connection behavior, not external NAT or a compromised OS.

**5. Would you deploy it publicly today?**

No. It has no identity or authorization and currently uses development servers. Public
hosting would need those controls, CSRF/Origin protections, egress policy, operational
ownership and a data/privacy model. I kept that limitation explicit rather than treating
localhost binding or passing tests as production readiness.

## Suggested GitHub metadata (owner-applied)

Description: **Local-first application and network troubleshooting workspace with
FastAPI, SQL-backed logs, evidence-linked diagnostics and a React dashboard.**

Topics: `python`, `fastapi`, `sqlalchemy`, `sqlite`, `react`, `typescript`,
`log-analysis`, `network-diagnostics`, `application-support`, `portfolio-project`.

Repository visibility and metadata were not changed. Before advertising source reuse,
choose a license deliberately; this release does not invent a license grant or author
identity. After reviewing/merging the PR, the owner can optionally tag the tested commit
and publish portfolio materials. No tag, GitHub Release or deployment is created here.
