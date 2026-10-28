import type { ReactNode } from "react";
import { api } from "../api/client";
import { useResource } from "../hooks/useResource";
import { useState } from "react";
export function Header({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <header className="page-header">
      <p className="eyebrow">OPERATIONS WORKSPACE</p>
      <h1>{title}</h1>
      <p>{description}</p>
    </header>
  );
}
export function Badge({ value }: { value: string }) {
  let tone = ["success", "completed", "INFO", "healthy"].includes(value)
    ? "good"
    : ["ERROR", "CRITICAL", "HIGH", "failure", "rejected"].includes(value)
      ? "bad"
      : ["WARNING", "MEDIUM", "partial"].includes(value)
        ? "warn"
        : "neutral";
  return <span className={`badge ${tone}`}>{value.replaceAll("_", " ")}</span>;
}
export function ErrorState({ error }: { error?: string }) {
  return error ? (
    <div role="alert" className="error">
      {error}
    </div>
  ) : null;
}
export function State({
  loading,
  error,
  empty = false,
}: {
  loading: boolean;
  error?: string;
  empty?: boolean;
}) {
  return (
    <>
      {loading && (
        <p role="status" className="notice">
          Loading records…
        </p>
      )}
      <ErrorState error={error} />
      {!loading && !error && empty && (
        <p className="empty">
          No records found. Choose a service or upload sample logs to begin.
        </p>
      )}
    </>
  );
}
export function Panel({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="panel">
      <h2>{title}</h2>
      {children}
    </section>
  );
}
export function Pagination({
  offset,
  limit = 50,
  total,
  count,
  onChange,
}: {
  offset: number;
  limit?: number;
  total?: number;
  count: number;
  onChange: (offset: number) => void;
}) {
  return (
    <nav className="pagination" aria-label="Pagination">
      <span>
        {count ? `${offset + 1}–${offset + count}` : "No rows"}
        {total !== undefined ? ` of ${total}` : ""}
      </span>
      <button
        disabled={offset === 0}
        onClick={() => onChange(Math.max(0, offset - limit))}
      >
        Previous
      </button>
      <button
        disabled={total !== undefined ? offset + count >= total : count < limit}
        onClick={() => onChange(offset + limit)}
      >
        Next
      </button>
    </nav>
  );
}
export function ServiceSelector({
  value,
  onChange,
}: {
  value: string;
  onChange: (value: string) => void;
}) {
  const [offset, setOffset] = useState(0);
  const state = useResource("selector" + offset, (s) =>
    api.services(offset, s),
  );
  return (
    <div className="selector">
      <label>
        Service
        <select
          aria-label="Service"
          value={value}
          onChange={(e) => onChange(e.target.value)}
        >
          <option value="">Choose a service</option>
          {value && !state.data?.some((s) => String(s.id) === value) && (
            <option value={value}>Selected service #{value}</option>
          )}
          {state.data?.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name} · {s.environment}
            </option>
          ))}
        </select>
      </label>
      <State {...state} />
      {(offset > 0 || state.data?.length === 50) && (
        <Pagination
          offset={offset}
          count={state.data?.length || 0}
          onChange={setOffset}
        />
      )}
    </div>
  );
}
export function Json({ value }: { value: unknown }) {
  return <pre>{JSON.stringify(value, null, 2)}</pre>;
}
export function Time({ value }: { value: string | null }) {
  return value ? (
    <time dateTime={value}>{value.replace("T", " ").replace("Z", " UTC")}</time>
  ) : (
    <span>Unavailable</span>
  );
}
