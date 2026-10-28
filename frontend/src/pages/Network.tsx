import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import { useAction, useResource } from "../hooks/useResource";
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
import type { CheckType, TargetInput } from "../types";
export function NetworkPage() {
  const [params, setParams] = useSearchParams();
  const service = params.get("service_id") || "";
  const target = params.get("target_id") || "";
  const result = params.get("result_id") || "";
  const [offset, setOffset] = useState(0);
  const [targetOffset, setTargetOffset] = useState(0);
  const [version, setVersion] = useState(0);
  const [kind, setKind] = useState<CheckType>("DNS");
  const [scheme, setScheme] = useState<"http" | "https">("https");
  const [port, setPort] = useState("443");
  const targets = useResource(
    `targets:${service}:${targetOffset}:${version}`,
    (s) => api.targets(service, targetOffset, s),
    !!service,
  );
  const history = useResource(
    `results:${target}:${offset}:${version}`,
    (s) => api.results(target, offset, s),
    !!target,
  );
  const detail = useResource(
    "result:" + result,
    (s) => api.result(result, s),
    !!result,
  );
  const create = useAction();
  const check = useAction();
  const [notice, setNotice] = useState("");
  const selected = targets.data?.find((t) => String(t.id) === target);
  return (
    <>
      <Header
        title="Network checks"
        description="Observe DNS, TCP and HTTP connectivity for explicitly registered targets."
      />
      <p className="notice">
        Public destinations only. Private, loopback, link-local and reserved
        addresses are blocked. Checks run only when you click Run.
      </p>
      <ServiceSelector
        value={service}
        onChange={(v) => {
          setParams(v ? { service_id: v } : {});
          setOffset(0);
          setTargetOffset(0);
          setNotice("");
        }}
      />
      <div className="two-columns">
        <Panel title="Registered targets">
          <State {...targets} empty={targets.data?.length === 0} />
          {targets.data?.map((t) => (
            <button
              key={t.id}
              className={`history-item ${String(t.id) === target ? "selected" : ""}`}
              onClick={() => {
                setParams({ service_id: service, target_id: String(t.id) });
                setOffset(0);
              }}
            >
              <strong>{t.name}</strong> · {t.check_type}
              <br />
              {t.host}
              {t.port ? `:${t.port}` : ""} ·{" "}
              {t.enabled ? "Enabled" : "Disabled"}
            </button>
          ))}
          {targets.data && (
            <Pagination
              offset={targetOffset}
              count={targets.data.length}
              onChange={setTargetOffset}
            />
          )}
          <button
            disabled={!selected?.enabled || check.busy}
            onClick={() =>
              check.execute(
                (s) => api.check(target, s),
                (value) => {
                  setVersion((v) => v + 1);
                  setOffset(0);
                  setParams({
                    service_id: service,
                    target_id: target,
                    result_id: String(value.id),
                  });
                  setNotice(
                    `Check recorded: ${value.outcome}${value.error_code ? " · " + value.error_code : ""}`,
                  );
                },
              )
            }
          >
            {check.busy ? "Checking…" : "Run selected check"}
          </button>
          <ErrorState error={check.error} />
          <p role="status">{notice}</p>
          <p className="muted">
            A successful HTTP response does not prove every application
            component is healthy.
          </p>
        </Panel>
        <Panel title="Register target">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const form = e.currentTarget;
              const data = new FormData(form);
              const payload: TargetInput = {
                name: String(data.get("name")).trim(),
                check_type: kind,
                host: String(data.get("host")).trim(),
                enabled: data.get("enabled") === "on",
              };
              if (kind !== "DNS") payload.port = Number(port);
              if (kind === "HTTP") {
                payload.scheme = scheme;
                payload.path = String(data.get("path"));
              }
              create.execute(
                (s) => api.createTarget(service, payload, s),
                (value) => {
                  setVersion((v) => v + 1);
                  setTargetOffset(0);
                  setParams({
                    service_id: service,
                    target_id: String(value.id),
                  });
                  setNotice(
                    `Target ${value.name} registered. No check has run.`,
                  );
                  form.reset();
                },
              );
            }}
          >
            <label>
              Name
              <input name="name" required maxLength={100} />
            </label>
            <label>
              Check type
              <select
                aria-label="Check type"
                value={kind}
                onChange={(e) => {
                  setKind(e.target.value as CheckType);
                  setScheme("https");
                  setPort("443");
                }}
              >
                {["DNS", "TCP", "HTTP"].map((t) => (
                  <option key={t}>{t}</option>
                ))}
              </select>
            </label>
            <label>
              Host
              <input
                name="host"
                required
                maxLength={253}
                placeholder="example.com"
              />
            </label>
            {kind === "HTTP" && (
              <label>
                Scheme
                <select
                  aria-label="Scheme"
                  value={scheme}
                  onChange={(e) => {
                    setScheme(e.target.value as "http" | "https");
                    setPort(e.target.value === "https" ? "443" : "80");
                  }}
                >
                  <option>https</option>
                  <option>http</option>
                </select>
              </label>
            )}
            {kind !== "DNS" && (
              <label>
                Port
                <input
                  type="number"
                  min="1"
                  max="65535"
                  required
                  value={port}
                  onChange={(e) => setPort(e.target.value)}
                />
              </label>
            )}
            {kind === "HTTP" && (
              <label>
                Path
                <input name="path" required defaultValue="/" maxLength={2048} />
              </label>
            )}
            <label className="checkbox">
              <input name="enabled" type="checkbox" defaultChecked />
              Enabled
            </label>
            <button disabled={!service || create.busy}>
              {create.busy ? "Saving…" : "Create target"}
            </button>
            <ErrorState error={create.error} />
          </form>
        </Panel>
      </div>
      {target && (
        <Panel title="Observation history">
          <State {...history} empty={history.data?.length === 0} />
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Observed at</th>
                  <th>Outcome</th>
                  <th>Detail</th>
                  <th>HTTP</th>
                  <th>Duration</th>
                  <th>Result</th>
                </tr>
              </thead>
              <tbody>
                {history.data?.map((r) => (
                  <tr key={r.id}>
                    <td>
                      <Time value={r.checked_at} />
                    </td>
                    <td>
                      <Badge value={r.outcome} />
                    </td>
                    <td>
                      {r.error_code?.replaceAll("_", " ") ||
                        "Successful observation"}
                    </td>
                    <td>{r.status_code ?? "—"}</td>
                    <td>{r.duration_ms} ms</td>
                    <td>
                      <button
                        className="text-button"
                        onClick={() =>
                          setParams((prev) => {
                            const next = new URLSearchParams(prev);
                            next.set("result_id", String(r.id));
                            return next;
                          })
                        }
                      >
                        #{r.id}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination
            offset={offset}
            count={history.data?.length || 0}
            onChange={setOffset}
          />
        </Panel>
      )}
      {result && (
        <Panel title={`Observation #${result}`}>
          <State {...detail} />
          {detail.data && (
            <>
              <Badge value={detail.data.outcome} />
              <p>
                <Time value={detail.data.checked_at} /> ·{" "}
                {detail.data.duration_ms} ms ·{" "}
                {detail.data.error_code || "Successful observation"}
              </p>
              <Json value={detail.data.details_json} />
            </>
          )}
        </Panel>
      )}
    </>
  );
}
