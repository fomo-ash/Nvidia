import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import type { components } from "./services/schema";
import { VerificationSummary } from "./LiveProposalReview";

type Verification = components["schemas"]["VerificationOut"];

function verification(status: Verification["status"]): Verification {
  return {
    id: "verification-1", execution_id: "execution-1", actor: "operator", status,
    started_at: "2026-10-30T10:00:00Z", completed_at: "2026-10-30T10:01:00Z",
    observations: {
      reason: "Prometheus data was stale.",
      measurements: [{ name: "work_requests", value: 25, operator: "gte", threshold: 20, observed_at: "2026-10-30T10:00:30Z" }],
    },
  };
}

it("labels recovery as verified only for a passed measurement verdict", () => {
  const { rerender } = render(<VerificationSummary verification={verification("inconclusive")} />);
  expect(screen.getByRole("heading", { name: "Recovery inconclusive" })).toBeTruthy();
  expect(screen.queryByRole("heading", { name: "Recovery verified" })).toBeNull();
  expect(screen.getByText("Prometheus data was stale.")).toBeTruthy();

  rerender(<VerificationSummary verification={verification("passed")} />);
  expect(screen.getByRole("heading", { name: "Recovery verified" })).toBeTruthy();
  expect(screen.getByText("Fresh rollout, health, and traffic measurements passed.")).toBeTruthy();
  expect(screen.getByText("work_requests")).toBeTruthy();
});
