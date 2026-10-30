import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "../context/AuthContext";
import InvestigationsList from "./InvestigationsList";
import ApprovalsList from "./ApprovalsList";
import AuditEventsList from "./AuditEventsList";
import CostAutopsyView from "./CostAutopsyView";

function renderWithProviders(ui: React.ReactNode, authenticated = true) {
  if (authenticated) {
    sessionStorage.setItem("fixproof_csrf", "mock-csrf-token");
  } else {
    sessionStorage.removeItem("fixproof_csrf");
  }
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <AuthProvider>
        <MemoryRouter>{ui}</MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

describe("secondary pages suite", () => {
  it("renders InvestigationsList with unauthenticated guidance when not logged in", () => {
    renderWithProviders(<InvestigationsList />, false);
    expect(screen.getByText(/An operator session is required to inspect investigations/)).toBeTruthy();
  });

  it("renders InvestigationsList with loaded investigations", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => [
          {
            id: "inv-1",
            status: "completed",
            summary: "Analyzed pod logs and metrics",
            created_at: "2026-10-30T10:00:00Z",
            result: { assessment: "active", gaps: [] },
            incident_id: "inc-1",
          },
        ],
      })
    );
    renderWithProviders(<InvestigationsList />, true);
    expect(await screen.findByText("Analyzed pod logs and metrics")).toBeTruthy();
    expect(screen.getByText("completed")).toBeTruthy();
    expect(screen.getByText("View incident")).toBeTruthy();
  });

  it("renders ApprovalsList with recorded decision", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => [
          {
            id: "appr-1",
            decision: "approved",
            actor: "operator-admin",
            proposal_hash: "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
            created_at: "2026-10-30T10:05:00Z",
            recommendation_id: "rec-1",
            recommendation_version: 1,
            expires_at: null,
          },
        ],
      })
    );
    renderWithProviders(<ApprovalsList />, true);
    expect(await screen.findByText("approved")).toBeTruthy();
    expect(screen.getByText("operator-admin")).toBeTruthy();
    expect(screen.getByText(/abcdef1234567890/)).toBeTruthy();
  });

  it("renders AuditEventsList with append-only entries", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => [
          {
            id: "audit-1",
            entity_type: "recommendation",
            entity_id: "rec-1",
            action: "approved",
            actor: "operator-admin",
            created_at: "2026-10-30T10:05:00Z",
            details: { reason: "Manual approval granted" },
          },
        ],
      })
    );
    renderWithProviders(<AuditEventsList />, true);
    expect(await screen.findByText("recommendation")).toBeTruthy();
    expect(screen.getByText("approved")).toBeTruthy();
    expect(screen.getByText("operator-admin")).toBeTruthy();
    expect(screen.getByText(/1 detail fields/)).toBeTruthy();
  });

  it("renders CostAutopsyView with drivers and savings formula", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => [
          {
            id: "cost-1",
            created_at: "2026-10-30T10:00:00Z",
            current_period: "2026-10",
            previous_period: "2026-09",
            currency: "USD",
            total_cost: 3200,
            previous_total: 2100,
            change: 1100,
            change_percent: 52.38,
            drivers: [],
            estimated_savings: {
              amount: 600,
              assumption: "Assume standard pod reduction.",
              formula: "2400 × 0.25",
            },
          },
        ],
      })
    );
    renderWithProviders(<CostAutopsyView />, true);
    expect((await screen.findAllByText("$3,200.00")).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("$600.00").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/2400 × 0.25/)).toBeTruthy();
  });
});
