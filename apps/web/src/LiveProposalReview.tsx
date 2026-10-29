import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import type { components } from "./services/schema";

type Proposal = components["schemas"]["RecommendationOut"];
type Execution = components["schemas"]["ExecutionOut"];
type Verification = components["schemas"]["VerificationOut"];
const base = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");

async function message(response: Response) {
  try { return ((await response.json()) as { detail?: string }).detail ?? `Request failed (${response.status})`; }
  catch { return `Request failed (${response.status})`; }
}

export default function LiveProposalReview({ incidentId, investigationId, eligible }: {
  incidentId: string; investigationId: string; eligible: boolean;
}) {
  const client = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const query = useQuery({
    queryKey: ["live-proposals", incidentId],
    queryFn: async () => {
      const response = await fetch(`${base}/api/v1/incidents/${incidentId}/recommendations`, { credentials: "include" });
      if (!response.ok) throw new Error(await message(response));
      return response.json() as Promise<Proposal[]>;
    },
  });
  const proposal = query.data?.find(item => item.investigation_id === investigationId);
  const executions = useQuery({
    queryKey: ["live-executions", proposal?.id], enabled: Boolean(proposal),
    queryFn: async () => {
      const response = await fetch(`${base}/api/v1/executions?limit=100`, { credentials: "include" });
      if (!response.ok) throw new Error(await message(response));
      return (await response.json() as Execution[]).find(item => item.recommendation_id === proposal?.id) ?? null;
    },
    refetchInterval: 3000,
  });
  const execution = executions.data;
  const verification = useQuery({
    queryKey: ["live-verification", execution?.id], enabled: Boolean(execution),
    queryFn: async () => {
      const response = await fetch(`${base}/api/v1/executions/${execution!.id}/verification`, { credentials: "include" });
      if (response.status === 404) return null;
      if (!response.ok) throw new Error(await message(response));
      return response.json() as Promise<Verification>;
    },
    refetchInterval: 3000,
  });

  async function submit(path: string, body: object) {
    const csrf = sessionStorage.getItem("fixproof_csrf");
    if (!csrf) { setError("Sign in on the Incidents page before reviewing a proposal."); return; }
    setBusy(true); setError("");
    try {
      const response = await fetch(`${base}/api/v1${path}`, {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf, "Idempotency-Key": crypto.randomUUID() },
        body: JSON.stringify(body),
      });
      if (response.status === 401 || response.status === 403) {
        sessionStorage.removeItem("fixproof_csrf");
        throw new Error("Operator session expired. Sign in again.");
      }
      if (!response.ok) throw new Error(await message(response));
      await client.invalidateQueries({ queryKey: ["live-proposals", incidentId] });
      await client.invalidateQueries({ queryKey: ["live-executions"] });
      await client.invalidateQueries({ queryKey: ["live-verification"] });
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Unable to submit review"); }
    finally { setBusy(false); }
  }

  if (query.isPending) return <p role="status">Loading proposal review…</p>;
  if (query.isError) return <div role="alert">Unable to load proposals. <button onClick={() => void query.refetch()}>Retry proposals</button></div>;
  if (!proposal) return <section aria-label="Restore proposal">
    <h4>Restore proposal</h4>
    <p>No exact restore proposal has been created for this investigation.</p>
    {eligible && <button disabled={busy} onClick={() => void submit(`/incidents/${incidentId}/proposals`, { investigation_id: investigationId })}>Prepare exact proposal</button>}
    {error && <p role="alert">{error}</p>}
  </section>;
  const fields = proposal.parameters as Record<string, unknown>;
  return <section aria-label="Restore proposal">
    <h4>Exact restore proposal</h4>
    <p>Status: <b>{proposal.status}</b>. Model analysis is advisory; operator approval is recorded separately.</p>
    <dl>
      <dt>Target</dt><dd>{proposal.target} (UID: {String(fields.uid)})</dd>
      <dt>Observed resource version</dt><dd>{String(fields.resource_version)}</dd>
      <dt>Observed faulty template SHA-256</dt><dd><code>{String(fields.expected_bad_template_hash)}</code></dd>
      <dt>Trusted healthy template SHA-256</dt><dd><code>{String(fields.desired_good_template_hash)}</code></dd>
      <dt>Expires</dt><dd>{proposal.expires_at ? new Date(proposal.expires_at).toLocaleString() : "unknown"}</dd>
      <dt>Verification plan</dt><dd>{String(fields.verification_plan)}</dd>
      <dt>Proposal SHA-256</dt><dd><code>{proposal.proposal_hash}</code></dd>
    </dl>
    <p>Retained evidence: {proposal.evidence?.map(item => "id" in item ? <a key={item.id} href={`#evidence-${item.id}`}>{item.source} </a> : null)}</p>
    {proposal.status === "proposed" && proposal.proposal_hash && <div className="row">
      <button disabled={busy} onClick={() => void submit(`/recommendations/${proposal.id}/approve`, { proposal_hash: proposal.proposal_hash })}>Approve exact proposal</button>
      <button className="secondary" disabled={busy} onClick={() => void submit(`/recommendations/${proposal.id}/reject`, {})}>Reject proposal</button>
    </div>}
    {proposal.status === "approved" && !execution && <button disabled={busy || executions.isPending} onClick={() => void submit(`/recommendations/${proposal.id}/execute`, { proposal_hash: proposal.proposal_hash })}>Execute approved restore</button>}
    {execution && <section aria-label="Restore execution">
      <p>Execution: <b>{execution.status}</b>. {String(execution.result?.reason ?? "")}</p>
      {execution.status === "pending" && <button disabled={busy} onClick={() => void submit(`/executions/${execution.id}/reconcile`, {})}>Check uncertain outcome</button>}
      {execution.status === "succeeded" && !verification.data && <button disabled={busy || verification.isPending} onClick={() => void submit(`/executions/${execution.id}/verify`, {})}>Measure recovery</button>}
      {verification.data && <p>Recovery verification: <b>{verification.data.status}</b>.</p>}
    </section>}
    <p>Approval authorizes one exact restore attempt. Recovery is reported only after fresh rollout, probe, and traffic measurements pass.</p>
    {error && <p role="alert">{error}</p>}
  </section>;
}
