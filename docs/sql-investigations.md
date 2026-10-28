# SQL investigations with SQLite

These queries match the actual schema: `services` joins `log_batches` through
`log_batches.service_id`, and batches join `log_events` through `log_events.batch_id`.
`occurred_at` is stored as naive UTC; interpret all times below as UTC. Queries
are read-only and return bounded results. The automated suite executes every SQL
block against a migrated temporary database containing synthetic POS and auth logs.

To explore locally, open the configured database with a SQLite client (for example,
`sqlite3 it_ops_lab.db` if that optional CLI is installed), or use a SQLAlchemy
connection in Python. Use bound parameters for user-supplied inputs, not SQL string
interpolation. The literal values below are reproducible teaching examples.

## 1. Retrieve the latest ERROR events

Question: What failures happened most recently, and which service produced them?

```sql
SELECT e.id, s.name, s.environment, e.occurred_at, e.severity, e.message
FROM log_events AS e
JOIN log_batches AS b ON b.id = e.batch_id
JOIN services AS s ON s.id = b.service_id
WHERE e.severity = 'ERROR'
ORDER BY e.occurred_at DESC, e.id DESC
LIMIT 50;
```

The JOINs connect each event to its service without duplicating events, since each
batch has exactly one service. WHERE limits severity; ORDER BY uses ID to break
timestamp ties; LIMIT caps returned rows. `log_search.search_events` uses the same
batch JOIN, severity predicate, and deterministic ordering. Its response returns
service ID; this teaching query adds the service name through another JOIN.

## 2. Count events grouped by severity

Question: Is the dataset mostly normal activity, warnings, or failures?

```sql
SELECT severity, COUNT(*) AS event_count
FROM log_events
GROUP BY severity
ORDER BY severity;
```

GROUP BY creates one group per severity and COUNT counts rows in each group. The
API's `summarize_events` performs this aggregate in SQL after applying service,
batch, and time predicates. It also supplies zero counts for absent severity
levels, whereas this standalone query only returns levels present in the table.
There are five supported severity levels, so the grouped result is naturally small.

## 3. Find services with the highest error counts

Question: Which services need attention first?

```sql
SELECT s.id AS service_id, s.name, s.environment, COUNT(*) AS error_count
FROM log_events AS e
JOIN log_batches AS b ON b.id = e.batch_id
JOIN services AS s ON s.id = b.service_id
WHERE e.severity IN ('ERROR', 'CRITICAL')
GROUP BY s.id, s.name, s.environment
ORDER BY error_count DESC, s.id ASC
LIMIT 100;
```

JOINs identify the owning service; WHERE includes both error and critical events.
GROUP BY service counts each service's failures. ORDER BY ranks the counts, with
service ID as a tie-breaker. The summary API uses the same JOIN/GROUP BY structure
but counts all matching severities and orders services by ID; it does not provide
an error-only ranking endpoint. Search with `severity=ERROR` retrieves the supporting
events. The API severity filter accepts one level per request.

## 4. Search for a specific failure message

Question: Are repeated database timeouts supporting the incident report?

```sql
SELECT e.id, b.service_id, e.batch_id, e.occurred_at, e.message
FROM log_events AS e
JOIN log_batches AS b ON b.id = e.batch_id
WHERE lower(e.message) LIKE '%database connection timed out%' ESCAPE '/'
ORDER BY e.occurred_at DESC, e.id DESC
LIMIT 50;
```

WHERE performs a case-insensitive substring search for this fixed phrase. The
SQLAlchemy implementation uses `icontains(..., autoescape=True)` with a bound
parameter: user-supplied `%`, `_`, and `/` are escaped and treated literally. The
outer `%` characters added by SQLAlchemy implement substring matching. SQLite's
built-in `lower` provides ASCII case folding; Unicode case folding is not supported
by this implementation. A leading wildcard requires scanning candidate messages;
other filters should narrow large investigations first.

## 5. Count errors over time with hourly grouping

Question: When did errors cluster, and were they still appearing after recovery?

```sql
SELECT strftime('%Y-%m-%dT%H:00:00Z', occurred_at) AS hour_utc,
       COUNT(*) AS error_count
FROM log_events
WHERE severity IN ('ERROR', 'CRITICAL')
GROUP BY strftime('%Y-%m-%dT%H:00:00Z', occurred_at)
ORDER BY hour_utc ASC
LIMIT 100;
```

`strftime` places UTC timestamps into hourly buckets. WHERE restricts failures;
GROUP BY builds the buckets and COUNT counts failures per hour. Missing hours are
omitted rather than filled with zeros. The result returns the earliest 100 occupied
hours. Narrow the time range for a long-lived database. This is a learning query,
not an additional endpoint: the summary API uses SQL aggregates for totals and
minimum/maximum timestamps, and search accepts inclusive time bounds to investigate
a specific hour. Both approaches keep aggregation/filtering in SQLite.

## Indexes and query trade-offs

The Milestone 4 migration adds:

- `(batch_id, occurred_at)` for batch queries, including service queries that first
  locate batches through the existing `log_batches.service_id` index. It replaces
  the redundant single-column `log_events.batch_id` index because its leading
  column supports the same lookup and foreign-key checks.
- `(severity, occurred_at)` for severity equality followed by time range/order.
- `(occurred_at)` for global newest-first searches and time-only investigations.
  The composite indexes cannot efficiently provide global time order when their
  leading batch/severity column is unconstrained.

SQLite secondary indexes include the integer rowid (the event ID), supporting the
ID tie-breaker when scanning a single indexed range in reverse. Joining multiple
batches or some filter combinations may still require a temporary sort. Aggregate
counts can scan all matching index entries. Message substring searches do not use
a conventional message index, so none is added. Each index adds disk usage and
write work during ingestion; these three correspond to implemented query patterns.
Use `EXPLAIN QUERY PLAN` on representative data before adding more indexes. The
migration changes indexes only and its downgrade restores the original batch index.
