import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";
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

function mount(path = "/") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}><App /></MemoryRouter></QueryClientProvider>);
}

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("operations console", () => {
  it("shows loading then API-backed costs with explicit sample and estimate labels", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => dashboard }));
    mount();
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

  it("shows a recoverable overview error and unknown-route fallback", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    mount();
    expect(await screen.findByRole("alert")).toBeTruthy();
    cleanup();
    mount("/missing");
    expect(screen.getByRole("heading", { name: "Page not found" })).toBeTruthy();
  });
});
