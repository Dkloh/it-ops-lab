import { Link } from "react-router-dom";
import { api } from "../api/client";
import { useResource } from "../hooks/useResource";
import { Badge, Header, Panel, State, Time } from "../components/Common";
export function OverviewPage() {
  const state = useResource("overview", (s) => api.overview(s));
  const data = state.data;
  return (
    <>
      <Header
        title="Operations overview"
        description="A current view of persisted evidence across your services."
      />
      <State {...state} />
      <div className="metrics">
        {[
          ["Registered services", data?.service_count],
          ["Ingested events", data?.event_count],
          ["Errors + critical", data?.error_count],
          ["Warnings", data?.warning_count],
        ].map(([label, value]) => (
          <section key={label}>
            <p>{label}</p>
            <strong>{value ?? "—"}</strong>
          </section>
        ))}
      </div>
      <div className="two-columns">
        <Panel title="Latest diagnostic findings">
          {data && !data.latest_findings.length && (
            <p className="empty">No diagnostic findings yet.</p>
          )}
          {data?.latest_findings.map((f) => (
            <article className="activity" key={f.id}>
              <Badge value={f.severity} />
              <h3>
                <Link
                  to={`/diagnostics?service_id=${f.service_id}&run_id=${f.run_id}&finding_id=${f.id}`}
                >
                  {f.summary}
                </Link>
              </h3>
              <p>{f.rule_code}</p>
              <small>
                Recorded <Time value={f.recorded_at} />
              </small>
            </article>
          ))}
        </Panel>
        <Panel title="Recent network observations">
          {data && !data.recent_observations.length && (
            <p className="empty">No network checks have been recorded.</p>
          )}
          {data?.recent_observations.map((r) => (
            <article className="activity" key={r.id}>
              <Badge value={r.outcome} />
              <h3>
                <Link
                  to={`/network?service_id=${r.service_id}&target_id=${r.target_id}&result_id=${r.id}`}
                >
                  {r.target_name}
                </Link>
              </h3>
              <p>
                {r.error_code || "Successful observation"} · {r.duration_ms} ms
              </p>
              <small>
                <Time value={r.checked_at} />
              </small>
            </article>
          ))}
        </Panel>
      </div>
      <Panel title="Investigation workflow">
        <ol className="workflow">
          <li>
            <Link to="/services">Register your application</Link>
          </li>
          <li>
            <Link to="/logs">Upload and search its logs</Link>
          </li>
          <li>
            <Link to="/diagnostics">Review rule-based evidence</Link>
          </li>
          <li>
            <Link to="/network">Observe current connectivity</Link>
          </li>
        </ol>
        <p>
          Historical log errors and current network checks represent different
          observation times.
        </p>
      </Panel>
    </>
  );
}
