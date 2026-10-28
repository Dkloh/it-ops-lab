import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import { useAction, useDebounce, useResource } from "../hooks/useResource";
import {
  Badge,
  ErrorState,
  Header,
  Json,
  Panel,
  Pagination,
  ServiceSelector,
  State,
  Time,
} from "../components/Common";
import type { Batch } from "../types";
export function LogsPage() {
  const [params, setParams] = useSearchParams();
  const [message, setMessage] = useState(params.get("message") || "");
  const delayed = useDebounce(message);
  const key = params.toString();
  useEffect(() => {
    setMessage(params.get("message") || "");
  }, [params.get("message")]);
  useEffect(() => {
    if (delayed === (params.get("message") || "")) return;
    setParams(
      (previous) => {
        const next = new URLSearchParams(previous);
        if (delayed) next.set("message", delayed);
        else next.delete("message");
        next.delete("offset");
        return next;
      },
      { replace: true },
    );
  }, [delayed]);
  const update = (name: string, value: string) =>
    setParams((prev) => {
      const next = new URLSearchParams(prev);
      if (value) next.set(name, value);
      else next.delete(name);
      next.delete("offset");
      if (name !== "event_id") next.delete("event_id");
      return next;
    });
  const filterNames = [
    "service_id",
    "batch_id",
    "severity",
    "start_time",
    "end_time",
    "message",
    "offset",
    "limit",
  ];
  const filters = Object.fromEntries(
    filterNames.filter((n) => params.has(n)).map((n) => [n, params.get(n)!]),
  );
  const state = useResource("logs:" + key, (s) => api.events(filters, s));
  const summaryFilters = Object.fromEntries(
    ["service_id", "batch_id", "start_time", "end_time"]
      .filter((n) => params.has(n))
      .map((n) => [n, params.get(n)!]),
  );
  const summary = useResource(
    "summary:" + JSON.stringify(summaryFilters),
    (s) => api.summary(summaryFilters, s),
  );
  const eventId = params.get("event_id") || "";
  const detail = useResource(
    "event:" + eventId,
    (s) => api.event(eventId, s),
    !!eventId,
  );
  const service = params.get("service_id") || "";
  const upload = useAction();
  const [batch, setBatch] = useState<Batch>();
  const [localError, setLocalError] = useState("");
  const [errorOffset, setErrorOffset] = useState(0);
  const errors = useResource(
    `errors:${batch?.id}:${errorOffset}`,
    (s) => api.errors(String(batch?.id), errorOffset, s),
    !!batch?.rejected_count,
  );
  return (
    <>
      <Header
        title="Log explorer"
        description="Search normalized events. Filter times require a timezone; results are shown in UTC."
      />
      <Panel title="Search filters">
        <div className="filters">
          <ServiceSelector
            value={service}
            onChange={(v) => update("service_id", v)}
          />
          <label>
            Batch ID
            <input
              type="number"
              min="1"
              value={params.get("batch_id") || ""}
              onChange={(e) => update("batch_id", e.target.value)}
            />
          </label>
          <label>
            Severity
            <select
              aria-label="Severity"
              value={params.get("severity") || ""}
              onChange={(e) => update("severity", e.target.value)}
            >
              <option value="">All severities</option>
              {["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"].map((v) => (
                <option key={v}>{v}</option>
              ))}
            </select>
          </label>
          <label>
            Start timestamp
            <input
              placeholder="2026-10-27T13:00:00Z"
              value={params.get("start_time") || ""}
              onChange={(e) => update("start_time", e.target.value)}
            />
          </label>
          <label>
            End timestamp
            <input
              placeholder="2026-10-27T14:00:00Z"
              value={params.get("end_time") || ""}
              onChange={(e) => update("end_time", e.target.value)}
            />
          </label>
          <label>
            Message substring
            <input
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              maxLength={8000}
            />
          </label>
          <label>
            Rows per page
            <select
              aria-label="Rows per page"
              value={params.get("limit") || "50"}
              onChange={(e) => update("limit", e.target.value)}
            >
              {[25, 50, 100].map((n) => (
                <option key={n}>{n}</option>
              ))}
            </select>
          </label>
        </div>
        <button
          className="secondary"
          onClick={() => {
            setMessage("");
            setParams({});
          }}
        >
          Clear filters
        </button>
      </Panel>
      <Panel title="Severity summary">
        <p className="muted">
          Service, batch and time filters only; severity and message filters
          apply to the table below.
        </p>
        <State {...summary} />
        {summary.data && (
          <>
            <div className="summary">
              {Object.entries(summary.data.by_severity).map(
                ([level, count]) => (
                  <span key={level}>
                    <Badge value={level} /> {count}
                  </span>
                ),
              )}
            </div>
            <p>
              {summary.data.total} events ·{" "}
              <Time value={summary.data.earliest} /> —{" "}
              <Time value={summary.data.latest} />
            </p>
          </>
        )}
      </Panel>
      <Panel title="Matching events">
        <State {...state} empty={state.data?.items.length === 0} />
        {state.data && (
          <>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Timestamp</th>
                    <th>Severity</th>
                    <th>Service</th>
                    <th>Source</th>
                    <th>Message</th>
                    <th>Event</th>
                  </tr>
                </thead>
                <tbody>
                  {state.data.items.map((event) => (
                    <tr key={event.id}>
                      <td>
                        <Time value={event.occurred_at} />
                      </td>
                      <td>
                        <Badge value={event.severity} />
                      </td>
                      <td>{event.service_id}</td>
                      <td>{event.source || "—"}</td>
                      <td className="message">{event.message}</td>
                      <td>
                        <button
                          className="text-button"
                          onClick={() => update("event_id", String(event.id))}
                        >
                          #{event.id}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination
              {...state.data}
              count={state.data.items.length}
              onChange={(offset) =>
                setParams((prev) => {
                  const next = new URLSearchParams(prev);
                  next.set("offset", String(offset));
                  return next;
                })
              }
            />
          </>
        )}
      </Panel>
      {eventId && (
        <Panel title={`Event #${eventId}`}>
          <State {...detail} />
          {detail.data && (
            <>
              <p className="message">{detail.data.message}</p>
              <Time value={detail.data.occurred_at} />
              <h3>Metadata</h3>
              <Json value={detail.data.metadata} />
            </>
          )}
        </Panel>
      )}
      <Panel title="Upload JSON Lines">
        <p>
          Choose a service above, then a UTF-8 .jsonl file up to 1 MiB. Files
          are sent as raw bytes.
        </p>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            setLocalError("");
            const file = (
              e.currentTarget.elements.namedItem("file") as HTMLInputElement
            ).files?.[0];
            if (!service || !file) {
              setLocalError("Select a service and a JSONL file.");
              return;
            }
            if (
              !file.name.toLowerCase().endsWith(".jsonl") ||
              file.size > 1048576
            ) {
              setLocalError("Use a .jsonl file no larger than 1 MiB.");
              return;
            }
            upload.execute(
              (s) => api.upload(service, file, s),
              (value) => {
                setBatch(value);
                setErrorOffset(0);
              },
            );
          }}
        >
          <label>
            JSONL file
            <input name="file" type="file" accept=".jsonl" required />
          </label>
          <button disabled={!service || upload.busy}>
            {upload.busy ? "Uploading…" : "Upload logs"}
          </button>
          <ErrorState error={localError || upload.error} />
        </form>
        {batch && (
          <div role="status">
            <p>
              <Badge value={batch.status} /> {batch.accepted_count} accepted ·{" "}
              {batch.rejected_count} rejected
            </p>
            <Link
              to={`/logs?service_id=${batch.service_id}&batch_id=${batch.id}`}
            >
              View uploaded batch logs
            </Link>{" "}
            ·{" "}
            <Link
              to={`/diagnostics?service_id=${batch.service_id}&batch_id=${batch.id}`}
            >
              Analyze this batch
            </Link>
          </div>
        )}
        {!!batch?.rejected_count && (
          <>
            <h3>Ingestion errors</h3>
            <State {...errors} />
            <ul>
              {errors.data?.map((e) => (
                <li key={e.line_number}>
                  Line {e.line_number}: {e.reason}
                </li>
              ))}
            </ul>
            <Pagination
              offset={errorOffset}
              count={errors.data?.length || 0}
              total={batch.rejected_count}
              onChange={setErrorOffset}
            />
          </>
        )}
      </Panel>
    </>
  );
}
