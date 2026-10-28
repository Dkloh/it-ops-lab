import type {
  Batch,
  Event,
  FindingDetail,
  IngestionError,
  Overview,
  Page,
  Result,
  Run,
  RunItem,
  Service,
  Summary,
  Target,
  TargetInput,
} from "../types";
const base = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");
const configuredTimeout = Number(import.meta.env.VITE_API_TIMEOUT_MS);
const timeoutMs =
  Number.isFinite(configuredTimeout) &&
  configuredTimeout >= 1000 &&
  configuredTimeout <= 60000
    ? configuredTimeout
    : 15000;
export class ApiError extends Error {}
export async function request<T>(
  path: string,
  init: RequestInit = {},
  signal?: AbortSignal,
): Promise<T> {
  const controller = new AbortController();
  const cancel = () => controller.abort();
  signal?.addEventListener("abort", cancel, { once: true });
  if (signal?.aborted) controller.abort();
  const timer = setTimeout(cancel, timeoutMs);
  try {
    const response = await fetch(base + "/api/v1" + path, {
      ...init,
      signal: controller.signal,
      credentials: "omit",
    });
    const data: unknown = await response.json().catch(() => {
      throw new ApiError("The server returned an unexpected response.");
    });
    if (!response.ok) {
      const detail = (data as { detail?: unknown })?.detail;
      const message =
        typeof detail === "string"
          ? detail
          : Array.isArray(detail)
            ? detail
                .map(
                  (item: { loc?: unknown[]; msg?: string }) =>
                    `${item.loc?.slice(1).join(".") || "Request"}: ${item.msg || "Invalid value"}`,
                )
                .join("; ")
            : `Request failed (${response.status}).`;
      throw new ApiError(message);
    }
    if (data === null || typeof data !== "object")
      throw new ApiError("The server returned unexpected data.");
    return data as T;
  } catch (error) {
    if (signal?.aborted) throw new DOMException("Cancelled", "AbortError");
    if (controller.signal.aborted)
      throw new ApiError(
        "Request timed out. Refresh to check whether an operation completed.",
      );
    if (error instanceof ApiError) throw error;
    throw new ApiError(
      "Unable to reach the API. Check that FastAPI is running.",
    );
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", cancel);
  }
}
export function query(values: Record<string, string | number | undefined>) {
  const p = new URLSearchParams();
  Object.entries(values).forEach(([k, v]) => {
    if (v !== undefined && v !== "") p.set(k, String(v));
  });
  return p.size ? "?" + p.toString() : "";
}
const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});
export const api = {
  overview: (signal?: AbortSignal) =>
    request<Overview>("/dashboard", {}, signal),
  services: (offset = 0, signal?: AbortSignal) =>
    request<Service[]>("/services" + query({ offset, limit: 50 }), {}, signal),
  service: (id: string, signal?: AbortSignal) =>
    request<Service>("/services/" + id, {}, signal),
  createService: (
    body: { name: string; environment: string; description: string | null },
    signal?: AbortSignal,
  ) => request<Service>("/services", json(body), signal),
  events: (p: Record<string, string | number>, signal?: AbortSignal) =>
    request<Page<Event>>("/log-events" + query(p), {}, signal),
  event: (id: string, signal?: AbortSignal) =>
    request<Event>("/log-events/" + id, {}, signal),
  summary: (p: Record<string, string>, signal?: AbortSignal) =>
    request<Summary>("/log-events/summary" + query(p), {}, signal),
  upload: (service: string, file: File, signal?: AbortSignal) =>
    request<Batch>(
      `/services/${service}/log-batches` + query({ filename: file.name }),
      {
        method: "POST",
        headers: { "Content-Type": "application/x-ndjson" },
        body: file,
      },
      signal,
    ),
  errors: (id: string, offset = 0, signal?: AbortSignal) =>
    request<IngestionError[]>(
      `/log-batches/${id}/errors` + query({ offset, limit: 50 }),
      {},
      signal,
    ),
  batches: (service: string, offset = 0, signal?: AbortSignal) =>
    request<Page<Batch>>(
      `/services/${service}/log-batches` + query({ offset, limit: 50 }),
      {},
      signal,
    ),
  runs: (batch: string, offset = 0, signal?: AbortSignal) =>
    request<Page<RunItem>>(
      `/log-batches/${batch}/diagnostic-runs` + query({ offset, limit: 50 }),
      {},
      signal,
    ),
  run: (id: string, signal?: AbortSignal) =>
    request<Run>("/diagnostic-runs/" + id, {}, signal),
  diagnose: (batch: string, signal?: AbortSignal) =>
    request<Run>(
      `/log-batches/${batch}/diagnostic-runs`,
      { method: "POST" },
      signal,
    ),
  finding: (id: string, signal?: AbortSignal) =>
    request<FindingDetail>("/findings/" + id, {}, signal),
  targets: (service: string, offset = 0, signal?: AbortSignal) =>
    request<Target[]>(
      `/services/${service}/check-targets` + query({ offset, limit: 50 }),
      {},
      signal,
    ),
  createTarget: (service: string, body: TargetInput, signal?: AbortSignal) =>
    request<Target>(`/services/${service}/check-targets`, json(body), signal),
  check: (id: string, signal?: AbortSignal) =>
    request<Result>(`/check-targets/${id}/runs`, { method: "POST" }, signal),
  results: (id: string, offset = 0, signal?: AbortSignal) =>
    request<Result[]>(
      `/check-targets/${id}/results` + query({ offset, limit: 50 }),
      {},
      signal,
    ),
  result: (id: string, signal?: AbortSignal) =>
    request<Result>("/check-results/" + id, {}, signal),
};
