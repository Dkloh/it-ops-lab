import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import { useAction, useResource } from "../hooks/useResource";
import {
  ErrorState,
  Header,
  Panel,
  Pagination,
  State,
} from "../components/Common";
export function ServicesPage() {
  const [params, setParams] = useSearchParams();
  const offset = Math.max(0, Number(params.get("offset")) || 0);
  const id = params.get("service_id") || "";
  const [version, setVersion] = useState(0);
  const state = useResource(`services:${offset}:${version}`, (s) =>
    api.services(offset, s),
  );
  const detail = useResource("service:" + id, (s) => api.service(id, s), !!id);
  const action = useAction();
  const [notice, setNotice] = useState("");
  return (
    <>
      <Header
        title="Service inventory"
        description="Register applications and keep investigation context close to the evidence."
      />
      <div className="two-columns">
        <Panel title="Registered services">
          <State {...state} empty={state.data?.length === 0} />
          {state.data && (
            <>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Service</th>
                      <th>Environment</th>
                      <th>Description</th>
                      <th>ID</th>
                      <th>Investigate</th>
                    </tr>
                  </thead>
                  <tbody>
                    {state.data.map((s) => (
                      <tr key={s.id}>
                        <td>
                          <button
                            className="text-button"
                            onClick={() =>
                              setParams({
                                offset: String(offset),
                                service_id: String(s.id),
                              })
                            }
                          >
                            {s.name}
                          </button>
                        </td>
                        <td>{s.environment}</td>
                        <td>{s.description || "—"}</td>
                        <td>{s.id}</td>
                        <td>
                          <Link to={`/logs?service_id=${s.id}`}>Logs</Link> ·{" "}
                          <Link to={`/network?service_id=${s.id}`}>
                            Network
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <Pagination
                offset={offset}
                count={state.data.length}
                onChange={(n) => setParams({ offset: String(n) })}
              />
            </>
          )}
        </Panel>
        <Panel title="Register service">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const form = e.currentTarget;
              const data = new FormData(form);
              action.execute(
                (s) =>
                  api.createService(
                    {
                      name: String(data.get("name")).trim(),
                      environment: String(data.get("environment")).trim(),
                      description: String(data.get("description")) || null,
                    },
                    s,
                  ),
                (created) => {
                  form.reset();
                  setVersion((v) => v + 1);
                  setParams({ service_id: String(created.id) });
                  setNotice(`Service ${created.name} created.`);
                },
              );
            }}
          >
            <label>
              Name
              <input name="name" required maxLength={100} />
            </label>
            <label>
              Environment
              <input
                name="environment"
                required
                maxLength={50}
                placeholder="development"
              />
            </label>
            <label>
              Description
              <textarea name="description" maxLength={2000} />
            </label>
            <button disabled={action.busy}>
              {action.busy ? "Creating…" : "Create service"}
            </button>
            <ErrorState error={action.error} />
            <p role="status">{notice}</p>
          </form>
        </Panel>
      </div>
      {id && (
        <Panel title="Service details">
          <State {...detail} />
          {detail.data && (
            <dl>
              <dt>Name</dt>
              <dd>{detail.data.name}</dd>
              <dt>Environment</dt>
              <dd>{detail.data.environment}</dd>
              <dt>Description</dt>
              <dd>{detail.data.description || "No description"}</dd>
            </dl>
          )}
        </Panel>
      )}
    </>
  );
}
