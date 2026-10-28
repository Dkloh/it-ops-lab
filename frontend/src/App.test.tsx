import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";
import App from "./App";
import { api, request } from "./api/client";
const service = {
  id: 1,
  name: "Retail POS",
  environment: "demo",
  description: "Store application",
  created_at: "2026-10-27T13:00:00Z",
};
const batch = {
  id: 1,
  service_id: 1,
  filename: "pos.jsonl",
  status: "completed",
  accepted_count: 3,
  rejected_count: 0,
  created_at: service.created_at,
};
const event = {
  id: 3,
  service_id: 1,
  batch_id: 1,
  occurred_at: service.created_at,
  severity: "ERROR",
  message: "Database connection timed out <script>bad()</script>",
  source: "pos-api",
  metadata: { attempt: 1 },
};
const finding = {
  id: 1,
  run_id: 1,
  rule_code: "REPEATED_TIMEOUTS",
  severity: "HIGH",
  summary: "Repeated timeouts",
  explanation: "Observed evidence",
  suggested_action: "Check upstream connectivity",
  first_seen_at: service.created_at,
  last_seen_at: service.created_at,
  event_count: 3,
  event_ids: [3],
};
const run = {
  id: 1,
  batch_id: 1,
  service_id: 1,
  ruleset_version: "1.0.0",
  status: "completed",
  started_at: service.created_at,
  finished_at: service.created_at,
  finding_count: 1,
  findings: [finding],
};
const target = {
  id: 1,
  service_id: 1,
  name: "Public HTTPS",
  check_type: "HTTP",
  host: "example.com",
  port: 443,
  scheme: "https",
  path: "/",
  enabled: true,
  created_at: service.created_at,
};
const result = {
  id: 1,
  target_id: 1,
  outcome: "failure",
  duration_ms: 3000,
  error_code: "TIMEOUT",
  status_code: null,
  details_json: { host: "example.com" },
  checked_at: service.created_at,
};
const calls: { path: string; init: RequestInit }[] = [];
let handler: (path: string, init: RequestInit) => unknown;
beforeEach(() => {
  calls.length = 0;
  handler = (path, init) => {
    if (path === "/dashboard")
      return {
        service_count: 1,
        event_count: 3,
        error_count: 3,
        warning_count: 0,
        latest_findings: [],
        recent_observations: [],
      };
    if (path.startsWith("/services?")) return [service];
    if (path === "/services" && init.method === "POST") return service;
    if (path === "/services/1") return service;
    if (path.includes("/log-batches") && init.method === "POST") return batch;
    if (path.startsWith("/services/1/log-batches"))
      return { items: [batch], total: 1, offset: 0, limit: 50 };
    if (path.includes("/log-batches/1/diagnostic-runs"))
      return init.method === "POST"
        ? run
        : { items: [run], total: 1, offset: 0, limit: 50 };
    if (path.startsWith("/log-events/summary"))
      return {
        total: 3,
        by_severity: { ERROR: 3 },
        by_service: [],
        earliest: service.created_at,
        latest: service.created_at,
      };
    if (path === "/log-events/3") return event;
    if (path.startsWith("/log-events?") || path === "/log-events")
      return { items: [event], total: 101, offset: 0, limit: 50 };
    if (path === "/diagnostic-runs/1") return run;
    if (path === "/findings/1")
      return { ...finding, batch_id: 1, service_id: 1, evidence: [event] };
    if (path.includes("/check-targets") && path.startsWith("/services/1"))
      return init.method === "POST" ? target : [target];
    if (path.includes("/check-targets/1/runs") || path === "/check-results/1")
      return result;
    if (path.includes("/check-targets/1/results")) return [result];
    if (path.includes("/errors")) return [];
    return [];
  };
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init: RequestInit = {}) => {
      const path = String(url).replace("/api/v1", "");
      calls.push({ path, init });
      return new Response(JSON.stringify(handler(path, init)), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }),
  );
});
function open(path = "/") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}
it("navigates from overview to service inventory", async () => {
  open();
  expect(await screen.findByText("Registered services")).toBeVisible();
  fireEvent.click(screen.getByRole("link", { name: "Services" }));
  expect(
    await screen.findByRole("button", { name: "Retail POS" }),
  ).toBeVisible();
});
it("creates a service and displays its details", async () => {
  open("/services");
  fireEvent.change(screen.getByLabelText("Name"), {
    target: { value: "Retail POS" },
  });
  fireEvent.change(screen.getByLabelText("Environment"), {
    target: { value: "demo" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Create service" }));
  expect(await screen.findByText("Service Retail POS created.")).toBeVisible();
  expect(calls.find((c) => c.path === "/services")?.init.body).toContain(
    "Retail POS",
  );
});
it("preserves URL log filters and performs server pagination", async () => {
  open("/logs?service_id=1&severity=ERROR");
  await screen.findByText(event.message);
  expect(
    calls.some(
      (c) =>
        c.path.includes("severity=ERROR") && c.path.includes("service_id=1"),
    ),
  ).toBe(true);
  fireEvent.click(screen.getAllByRole("button", { name: "Next" })[0]);
  await waitFor(() =>
    expect(calls.some((c) => c.path.includes("offset=50"))).toBe(true),
  );
});
it("debounces message searches and clears filters", async () => {
  open("/logs");
  await screen.findByText(event.message);
  fireEvent.change(screen.getByLabelText("Message substring"), {
    target: { value: "timeout" },
  });
  await waitFor(() =>
    expect(calls.some((c) => c.path.includes("message=timeout"))).toBe(true),
  );
  fireEvent.click(screen.getByRole("button", { name: "Clear filters" }));
  expect(screen.getByLabelText("Message substring")).toHaveValue("");
});
it("shows escaped event messages and formatted metadata", async () => {
  const { container } = open("/logs?event_id=3");
  expect(await screen.findByText(/"attempt": 1/)).toBeVisible();
  expect(container.querySelector("script")).toBeNull();
});
it("uploads raw JSONL bytes with filename and service", async () => {
  open("/logs?service_id=1");
  const file = new File(["{}\n"], "demo.jsonl", { type: "text/plain" });
  await userEvent.upload(screen.getByLabelText("JSONL file"), file);
  fireEvent.submit(
    screen.getByRole("button", { name: "Upload logs" }).closest("form")!,
  );
  expect(await screen.findByText(/3 accepted/)).toBeVisible();
  const call = calls.find((c) => c.path.includes("filename=demo.jsonl"));
  expect(call?.init.body).toBe(file);
  expect(call?.init.headers).toEqual({
    "Content-Type": "application/x-ndjson",
  });
});
it("runs diagnostics only by explicit action and shows evidence", async () => {
  open("/diagnostics?service_id=1&batch_id=1");
  await screen.findByText(/pos.jsonl/);
  expect(calls.filter((c) => c.init.method === "POST")).toHaveLength(0);
  fireEvent.click(screen.getByRole("button", { name: "Run diagnostics" }));
  fireEvent.click(
    await screen.findByRole("button", { name: "Inspect evidence #1" }),
  );
  expect(await screen.findByText(event.message)).toBeVisible();
  expect(
    calls.some(
      (c) =>
        c.path === "/log-batches/1/diagnostic-runs" && c.init.method === "POST",
    ),
  ).toBe(true);
});
it.each(["DNS", "TCP", "HTTP"])(
  "submits the type-specific %s target",
  async (kind) => {
    open("/network?service_id=1");
    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "Probe" },
    });
    fireEvent.change(screen.getByLabelText("Host"), {
      target: { value: "example.com" },
    });
    fireEvent.change(screen.getByLabelText("Check type"), {
      target: { value: kind },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create target" }));
    await screen.findByText(/registered. No check has run/);
    const payload = JSON.parse(
      String(
        calls.find(
          (c) =>
            c.path === "/services/1/check-targets" && c.init.method === "POST",
        )?.init.body,
      ),
    );
    expect(payload.check_type).toBe(kind);
    if (kind === "DNS") {
      expect(payload).not.toHaveProperty("port");
      expect(payload).not.toHaveProperty("path");
    }
    if (kind === "TCP") {
      expect(payload.port).toBe(443);
      expect(payload).not.toHaveProperty("scheme");
    }
    if (kind === "HTTP") {
      expect(payload.scheme).toBe("https");
      expect(payload.path).toBe("/");
    }
  },
);
it("views history and runs a selected check explicitly", async () => {
  open("/network?service_id=1&target_id=1&result_id=1");
  await screen.findByRole("button", { name: /Public HTTPS/ });
  expect((await screen.findAllByText(/3000 ms/))[0]).toBeVisible();
  expect(calls.filter((c) => c.path.endsWith("/runs"))).toHaveLength(0);
  fireEvent.click(screen.getByRole("button", { name: "Run selected check" }));
  await screen.findByText(/Check recorded: failure/);
});
it("shows API errors and does not fabricate totals", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async () =>
        new Response(JSON.stringify({ detail: "Database unavailable" }), {
          status: 503,
        }),
    ),
  );
  open();
  expect((await screen.findAllByRole("alert"))[0]).toHaveTextContent(
    "Database unavailable",
  );
  expect(screen.getAllByText("—")).toHaveLength(4);
});
it("shows loading and empty states", async () => {
  const original = handler;
  handler = (path, init) =>
    path.startsWith("/services?") ? [] : original(path, init);
  open("/services");
  expect(
    screen
      .getAllByRole("status")
      .some((e) => e.textContent?.includes("Loading")),
  ).toBe(true);
  expect(await screen.findByText(/No records found/)).toBeVisible();
});
it("handles invalid server responses and validation messages", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response("<html>unexpected</html>", { status: 502 })),
  );
  await expect(request("/services")).rejects.toThrow("unexpected response");
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            detail: [{ loc: ["body", "name"], msg: "Required" }],
          }),
          { status: 422 },
        ),
    ),
  );
  await expect(
    api.createService({ name: "", environment: "dev", description: null }),
  ).rejects.toThrow("name: Required");
});
it("cancels requests when filters change or unmount", async () => {
  const signals: AbortSignal[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((_url, init) => {
      signals.push(init.signal);
      return new Promise(() => {});
    }),
  );
  const page = open("/logs");
  fireEvent.change(screen.getByLabelText("Severity"), {
    target: { value: "ERROR" },
  });
  await waitFor(() => expect(signals.some((s) => s.aborted)).toBe(true));
  page.unmount();
  expect(signals.every((s) => s.aborted)).toBe(true);
});
it("handles malformed response objects without losing navigation", async () => {
  vi.spyOn(console, "error").mockImplementation(() => {});
  handler = () => ({ unexpected: true });
  open();
  expect(await screen.findByRole("alert")).toHaveTextContent("unexpected data");
  expect(screen.getByRole("link", { name: "Services" })).toBeVisible();
});
it("enforces the API timeout", async () => {
  vi.useFakeTimers();
  try {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        (_url, init) =>
          new Promise((_resolve, reject) =>
            init.signal.addEventListener("abort", () =>
              reject(new DOMException("Aborted", "AbortError")),
            ),
          ),
      ),
    );
    const pending = expect(request("/services")).rejects.toThrow("timed out");
    await vi.advanceTimersByTimeAsync(15001);
    await pending;
  } finally {
    vi.useRealTimers();
  }
});
