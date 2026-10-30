import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import { AuthProvider } from "./context/AuthContext";
import type { components } from "./services/schema";

const dashboard: components["schemas"]["DashboardOut"] = {
  open_incidents: 2,
  mode: "deterministic-demo",
  cost_autopsy: {
    mode: "synthetic", currency: "USD", current_period: "2026-10", previous_period: "2026-09",
    total_cost: 2450, previous_total: 1200, change: 1250, change_percent: 104.17,
    drivers: [], estimated_savings: { amount: 525, assumption: "Assume 25% reduction.", formula: "2100 × 0.25" },
  },
};

function mount(path = "/", authenticated = false) {
  if (authenticated) {
    sessionStorage.setItem("fixproof_csrf", "mock-csrf-token");
  } else {
    sessionStorage.removeItem("fixproof_csrf");
  }
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <AuthProvider>
        <MemoryRouter initialEntries={[path]}>
          <App />
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
}

afterEach(() => { cleanup(); vi.unstubAllGlobals(); sessionStorage.clear(); });

describe("operations console", () => {
  it("shows loading then API-backed costs with explicit sample and estimate labels", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => dashboard }));
    mount("/", true);
    expect(screen.getByRole("status").textContent).toContain("Loading");
    expect(await screen.findByText("$2,450.00")).toBeTruthy();
    expect(screen.getByText("$525.00")).toBeTruthy();
    expect(screen.getByRole("status").textContent).toContain("Synthetic billing data");
    expect(screen.getByText("2100 × 0.25")).toBeTruthy();
  });

  it("shows an incident API failure and lets the operator retry", async () => {
    const fetch = vi.fn()
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce({ ok: true, json: async () => [] });
    vi.stubGlobal("fetch", fetch);
    mount("/incidents");
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.queryByText(/No incidents yet/)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText(/No incidents yet/)).toBeTruthy();
  });

  it("renders real incident fields returned by the API", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => [
      { id: "incident-1", title: "Worker latency spike", severity: "high", status: "open" },
    ] }));
    mount("/incidents");
    expect(await screen.findByText("Worker latency spike")).toBeTruthy();
    expect(screen.getByText("high")).toBeTruthy();
  });

  it("signs in and reports the registered target as unassessed", async () => {
    const fetch = vi.fn(async (url: string, options?: RequestInit) => ({ ok: true, status: 200, json: async () => {
      if (url.endsWith("/incidents") && options?.method === "POST") return reportResponse;
      if (url.endsWith("/session")) return { csrf_token: "csrf-test" };
      if (url.endsWith("/incident-targets")) return [{ target_id: "local-kind/fixproof-demo/sample-api", uid: "uid-1", cluster: "local-kind", namespace: "fixproof-demo", name: "sample-api" }];
      return [];
    } }));
    const reportResponse = { incident_id: "incident-1", trigger_id: "trigger-1", investigation_request_id: "request-1", reused: false, assessment: "unassessed" };
    vi.stubGlobal("fetch", fetch);
    vi.stubGlobal("crypto", { randomUUID: () => "test-key" });
    mount("/incidents");
    await screen.findByText(/No incidents yet/);
    fireEvent.change(screen.getByLabelText("Local operator secret"), { target: { value: "local-secret" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByText(/UID: uid-1/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Report incident" }));
    expect(await screen.findByText(/Awaiting evidence collection/)).toBeTruthy();
    expect(screen.getByText(/reporting is not detection or confirmation/)).toBeTruthy();
    expect((fetch.mock.calls as unknown as [string, unknown][]).find(([, options]) => (options as { method?: string } | undefined)?.method === "POST" && (options as { headers?: { "Idempotency-Key"?: string } }).headers?.["Idempotency-Key"] === "test-key")?.[1]).toMatchObject({ credentials: "include", headers: { "X-CSRF-Token": "csrf-test", "Idempotency-Key": "test-key" } });
  });

  it("reuses a pending report key after a dropped response", async () => {
    const keys: string[] = [];
    let attempts = 0;
    const uuid = vi.fn().mockReturnValueOnce("retry-key-one").mockReturnValue("retry-key-two");
    vi.stubGlobal("crypto", { randomUUID: uuid });
    vi.stubGlobal("fetch", vi.fn(async (url: string, options?: RequestInit) => {
      if (url.endsWith("/incidents") && options?.method === "POST") {
        keys.push((options.headers as Record<string, string>)["Idempotency-Key"]);
        if (++attempts === 1) throw new Error("network dropped");
        return { ok: true, status: 201, json: async () => ({ incident_id: "incident-1", reused: false }) };
      }
      return { ok: true, status: 200, json: async () => url.endsWith("/session") ? { csrf_token: "csrf-test" } : url.endsWith("/incident-targets") ? [{ target_id: "local-kind/fixproof-demo/sample-api", uid: "uid-1", cluster: "local-kind", namespace: "fixproof-demo", name: "sample-api" }] : [] };
    }));
    mount("/incidents");
    fireEvent.change(screen.getByLabelText("Local operator secret"), { target: { value: "local-secret" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    await screen.findByText(/UID: uid-1/);
    fireEvent.click(screen.getByRole("button", { name: "Report incident" }));
    expect(await screen.findByText("network dropped")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Report incident" }));
    await screen.findByText(/Incident reported/);
    expect(keys).toEqual(["retry-key-one", "retry-key-one"]);
    expect(uuid).toHaveBeenCalledTimes(1);
  });

  it("shows a recoverable overview error and unknown-route fallback", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    mount("/", true);
    expect(await screen.findByRole("alert")).toBeTruthy();
    cleanup();
    mount("/missing");
    expect(screen.getByRole("heading", { name: "Page not found" })).toBeTruthy();
  });
});
