import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import { useAction, useResource } from "../hooks/useResource";
import {
  Badge,
  ErrorState,
  Header,
  Panel,
  Pagination,
  ServiceSelector,
  State,
  Time,
} from "../components/Common";
export function DiagnosticsPage() {
  const [params, setParams] = useSearchParams();
  const service = params.get("service_id") || "";
  const batch = params.get("batch_id") || "";
  const runId = params.get("run_id") || "";
  const finding = params.get("finding_id") || "";
  const [batchOffset, setBatchOffset] = useState(0);
  const [runOffset, setRunOffset] = useState(0);
  const [version, setVersion] = useState(0);
  const batches = useResource(
    `batches:${service}:${batchOffset}`,
    (s) => api.batches(service, batchOffset, s),
    !!service,
  );
  const runs = useResource(
    `runs:${batch}:${runOffset}:${version}`,
    (s) => api.runs(batch, runOffset, s),
    !!batch,
  );
  const run = useResource("run:" + runId, (s) => api.run(runId, s), !!runId);
  const detail = useResource(
    "finding:" + finding,
    (s) => api.finding(finding, s),
    !!finding,
  );
  const action = useAction();
  return (
    <>
      <Header
        title="Rule-based diagnostics"
        description="Find recurring patterns and inspect supporting evidence. Findings are investigation directions, not confirmed causes."
      />
      <Panel title="Investigation scope">
        <div className="filters">
          <ServiceSelector
            value={service}
            onChange={(v) => {
              setParams(v ? { service_id: v } : {});
              setBatchOffset(0);
              setRunOffset(0);
            }}
          />
          <label>
            Ingestion batch
            <select
              aria-label="Ingestion batch"
              disabled={!service}
              value={batch}
              onChange={(e) => {
                setParams({ service_id: service, batch_id: e.target.value });
                setRunOffset(0);
              }}
            >
              <option value="">Choose an uploaded batch</option>
              {batch &&
                !batches.data?.items.some((b) => String(b.id) === batch) && (
                  <option value={batch}>Selected batch #{batch}</option>
                )}
              {batches.data?.items.map((b) => (
                <option value={b.id} key={b.id}>
                  {b.filename} · #{b.id} · {b.accepted_count} events
                </option>
              ))}
            </select>
          </label>
        </div>
        <State {...batches} />
        {batches.data && (
          <Pagination
            {...batches.data}
            count={batches.data.items.length}
            onChange={setBatchOffset}
          />
        )}
        <button
          disabled={!batch || action.busy}
          onClick={() =>
            action.execute(
              (s) => api.diagnose(batch, s),
              (value) => {
                setParams({
                  service_id: service,
                  batch_id: batch,
                  run_id: String(value.id),
                });
                setVersion((v) => v + 1);
              },
            )
          }
        >
          {action.busy ? "Analyzing…" : "Run diagnostics"}
        </button>
        <ErrorState error={action.error} />
        <p role="status">
          {action.busy
            ? "Analysis in progress."
            : run.data
              ? `Run #${run.data.id} completed with ${run.data.finding_count} findings.`
              : ""}
        </p>
      </Panel>
      {batch && (
        <Panel title="Historical runs">
          <State {...runs} empty={runs.data?.items.length === 0} />
          {runs.data?.items.map((r) => (
            <button
              className="history-item"
              key={r.id}
              onClick={() =>
                setParams({
                  service_id: service,
                  batch_id: batch,
                  run_id: String(r.id),
                })
              }
            >
              Run #{r.id} · <Time value={r.started_at} /> · {r.finding_count}{" "}
              findings
            </button>
          ))}
          {runs.data && (
            <Pagination
              {...runs.data}
              count={runs.data.items.length}
              onChange={setRunOffset}
            />
          )}
        </Panel>
      )}
      {runId && (
        <Panel title={`Diagnostic run #${runId}`}>
          <State {...run} />
          {run.data && (
            <>
              <p>
                <Badge value={run.data.status} /> Ruleset{" "}
                {run.data.ruleset_version} ·{" "}
                <Time value={run.data.finished_at} />
              </p>
              {run.data.findings.length === 0 && (
                <p className="empty">
                  No diagnostic patterns detected in this batch.
                </p>
              )}
              {run.data.findings.map((f) => (
                <article className="finding" key={f.id}>
                  <Badge value={f.severity} />
                  <h3>{f.summary}</h3>
                  <code>{f.rule_code}</code>
                  <p>{f.explanation}</p>
                  <p>
                    {f.event_count} supporting events ·{" "}
                    <Time value={f.first_seen_at} /> —{" "}
                    <Time value={f.last_seen_at} />
                  </p>
                  <h4>Suggested investigation</h4>
                  <p>{f.suggested_action}</p>
                  <button
                    className="secondary"
                    onClick={() =>
                      setParams((prev) => {
                        const next = new URLSearchParams(prev);
                        next.set("finding_id", String(f.id));
                        return next;
                      })
                    }
                  >
                    Inspect evidence #{f.id}
                  </button>
                </article>
              ))}
            </>
          )}
        </Panel>
      )}
      {finding && (
        <Panel title="Supporting evidence">
          <State {...detail} />
          {detail.data && (
            <>
              <h3>{detail.data.summary}</h3>
              <p>
                Finding #{detail.data.id} · Run #{detail.data.run_id} ·{" "}
                {detail.data.event_count} events
              </p>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Event</th>
                      <th>Timestamp</th>
                      <th>Severity</th>
                      <th>Source</th>
                      <th>Message</th>
                    </tr>
                  </thead>
                  <tbody>
                    {detail.data.evidence.map((e) => (
                      <tr key={e.id}>
                        <td>{e.id}</td>
                        <td>
                          <Time value={e.occurred_at} />
                        </td>
                        <td>
                          <Badge value={e.severity} />
                        </td>
                        <td>{e.source || "—"}</td>
                        <td className="message">{e.message}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </Panel>
      )}
    </>
  );
}
