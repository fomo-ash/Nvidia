import { useQuery } from "@tanstack/react-query";
import type { components } from "./services/schema";
import LiveProposalReview from "./LiveProposalReview";
import IncidentChatDrawer from "./components/IncidentChatDrawer";

type Investigation = components["schemas"]["InvestigationOut"];
type Evidence = components["schemas"]["EvidenceItemOut"];
const base = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");

async function read<T>(path: string): Promise<T> {
  const response = await fetch(`${base}${path}`, { credentials: "include" });
  if (!response.ok) throw new Error("Unable to load investigation");
  return response.json() as Promise<T>;
}

export default function LiveInvestigation({ incidentId }: { incidentId: string }) {
  const query = useQuery({ queryKey: ["live-investigations", incidentId], queryFn: () => read<Investigation[]>(`/api/v1/incidents/${incidentId}/investigations`), refetchInterval: 2000 });
  const latest = query.data?.[0];
  const evidence = useQuery({ queryKey: ["live-evidence", latest?.id], enabled: Boolean(latest), queryFn: () => read<Evidence[]>(`/api/v1/investigations/${latest!.id}/evidence`), refetchInterval: 2000 });
  if (query.isPending) return <p role="status">Waiting for investigation status…</p>;
  if (query.isError) return <div role="alert">Unable to load investigation. <button onClick={() => void query.refetch()}>Retry investigation</button></div>;
  if (!latest) return <p>Awaiting evidence collection.</p>;
  const findings = latest.result?.analysis;
  return <section aria-label="Live investigation">
    <h3>Investigation: {latest.status}</h3>
    <p>Measured assessment: {latest.result?.assessment ?? "unassessed"}</p>
    <p>{latest.summary}</p>
    {latest.result?.gaps?.length ? <p role="status">Collection or analysis gaps: {latest.result.gaps.join(", ")}</p> : null}
    <h4>Source observations</h4>
    {evidence.isPending ? <p role="status">Loading observations…</p> : evidence.isError ? <div role="alert">Unable to load observations. <button onClick={() => void evidence.refetch()}>Retry observations</button></div> : evidence.data?.length ? evidence.data.map(item => <article id={`evidence-${item.id}`} key={item.id}>
      <b>{item.source}</b><p>{item.collection_error ?? item.fact}</p>
      <small>{new Date(item.observed_at).toLocaleString()} · {item.mode} · {item.id}</small>
      {!item.collection_error && <details><summary>Retained source data</summary><pre>{JSON.stringify(item.raw_data, null, 2)}</pre></details>}
    </article>) : <p>No observations retained yet.</p>}
    <h4>Model interpretation</h4>
    {findings ? <><p>{findings.analysis.summary}</p><small>{findings.provider} · {findings.model}</small>{(findings.analysis.gaps ?? []).length > 0 && <p>Model gaps: {(findings.analysis.gaps ?? []).join(", ")}</p>}{findings.analysis.hypotheses.map((finding, index) => <article key={index}><p>{finding.cause}</p><p>Uncertainty: {finding.uncertainty}</p><p>Supporting evidence: {finding.supporting_evidence_ids.map(id => <a key={id} href={`#evidence-${id}`}>{id} </a>)}</p>{(finding.contradicting_evidence_ids ?? []).length > 0 && <p>Contradicting evidence: {(finding.contradicting_evidence_ids ?? []).join(", ")}</p>}</article>)}</> : <p>Validated model analysis is not available. Review the source observations.</p>}
    <LiveProposalReview incidentId={incidentId} investigationId={latest.id} eligible={latest.status === "completed" && latest.result?.assessment === "active" && findings?.analysis.advisory_action === "restore_known_good_template"} />
    <p>Human review and an exact approval are required before the guarded restore.</p>
    <IncidentChatDrawer incidentId={incidentId} />
  </section>;
}
