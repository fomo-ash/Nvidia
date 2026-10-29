import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import LiveProposalReview from "./LiveProposalReview";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); sessionStorage.clear(); });

it("prepares an exact proposal and records deliberate approval without claiming recovery", async () => {
  sessionStorage.setItem("fixproof_csrf", "csrf-test");
  vi.stubGlobal("crypto", { randomUUID: () => "review-key" });
  let proposalCreated = false;
  let approved = false;
  const proposal = {
    id: "proposal-1", investigation_id: "run-1", status: "proposed",
    target: "local-kind/fixproof-demo/sample-api", proposal_hash: "a".repeat(64),
    expires_at: "2026-10-30T00:00:00Z", evidence: [{ id: "evidence-1", source: "prometheus", content_hash: "b".repeat(64) }],
    parameters: { uid: "sample-uid", resource_version: "101", expected_bad_template_hash: "b".repeat(64), desired_good_template_hash: "c".repeat(64), verification_plan: "Fresh measurements" },
  };
  const fetch = vi.fn(async (url: string, options?: RequestInit) => {
    if (options?.method === "POST") {
      if (url.endsWith("/proposals")) proposalCreated = true;
      if (url.endsWith("/approve")) approved = true;
      return { ok: true, status: 201, json: async () => ({ ...proposal, status: approved ? "approved" : "proposed" }) };
    }
    return { ok: true, status: 200, json: async () => proposalCreated ? [{ ...proposal, status: approved ? "approved" : "proposed" }] : [] };
  });
  vi.stubGlobal("fetch", fetch);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><LiveProposalReview incidentId="incident-1" investigationId="run-1" eligible /></QueryClientProvider>);
  fireEvent.click(await screen.findByRole("button", { name: "Prepare exact proposal" }));
  expect(await screen.findByText(/Observed faulty template SHA-256/)).toBeTruthy();
  expect(screen.getByText(/sample-uid/)).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Approve exact proposal" }));
  expect(await screen.findByText(/Status:/)).toBeTruthy();
  expect(approved).toBe(true);
  expect(screen.getByText(/Recovery is reported only after fresh rollout/)).toBeTruthy();
  const approvalCall = fetch.mock.calls.find(([url]) => url.endsWith("/approve"));
  expect(approvalCall?.[1]).toMatchObject({
    credentials: "include",
    headers: { "X-CSRF-Token": "csrf-test", "Idempotency-Key": "review-key" },
    body: JSON.stringify({ proposal_hash: "a".repeat(64) }),
  });
});
