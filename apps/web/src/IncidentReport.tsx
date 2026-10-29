import { useRef, useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

const base = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");

import type { components } from "./services/schema";
import LiveInvestigation from "./LiveInvestigation";

type Target = components["schemas"]["IncidentTargetOut"];
type Report = components["schemas"]["ManualIncidentOut"];
type Trigger = components["schemas"]["IncidentTriggerOut"];
type Request = components["schemas"]["InvestigationRequestOut"];

async function detail(response: Response): Promise<string> {
  try { const body = await response.json() as { detail?: string }; return body.detail ?? `Request failed (${response.status})`; }
  catch { return `Request failed (${response.status})`; }
}

export default function IncidentReport() {
  const queryClient = useQueryClient();
  const [secret, setSecret] = useState("");
  const [csrf, setCsrf] = useState("");
  const [target, setTarget] = useState<Target | null>(null);
  const [summary, setSummary] = useState("Sample requests return 5xx");
  const [note, setNote] = useState("");
  const [result, setResult] = useState<Report | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const pendingReport = useRef<{ body: string; key: string } | null>(null);

  async function refreshTarget() {
    setBusy(true); setError("");
    try {
      const targets = await fetch(`${base}/api/v1/incident-targets`, { credentials: "include" });
      if (targets.status === 401) { setCsrf(""); sessionStorage.removeItem("fixproof_csrf"); setTarget(null); throw new Error("Your session expired. Sign in again to refresh the target."); }
      if (!targets.ok) throw new Error(await detail(targets));
      const items = await targets.json() as Target[];
      setTarget(items[0] ?? null);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Unable to refresh target"); }
    finally { setBusy(false); }
  }

  async function login(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try {
      const response = await fetch(`${base}/api/v1/session`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ secret }) });
      if (!response.ok) throw new Error(await detail(response));
      const session = await response.json() as { csrf_token: string };
      const targets = await fetch(`${base}/api/v1/incident-targets`, { credentials: "include" });
      if (!targets.ok) throw new Error(await detail(targets));
      const items = await targets.json() as Target[];
      setTarget(items[0] ?? null); setCsrf(session.csrf_token); sessionStorage.setItem("fixproof_csrf", session.csrf_token); setSecret("");
      await queryClient.invalidateQueries({ queryKey: ["incidents"] });
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Unable to sign in"); }
    finally { setBusy(false); }
  }

  async function report(event: FormEvent) {
    event.preventDefault();
    if (!target?.uid) { setError("The sample Deployment UID is not configured."); return; }
    setBusy(true); setError(""); setResult(null);
    try {
      const body = JSON.stringify({ target_id: target.target_id, target_uid: target.uid, symptom: "http_5xx_spike", summary, note: note || null });
      if (!pendingReport.current || pendingReport.current.body !== body) pendingReport.current = { body, key: crypto.randomUUID() };
      const response = await fetch(`${base}/api/v1/incidents`, {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf, "Idempotency-Key": pendingReport.current.key },
        body,
      });
      if (response.status === 401 || response.status === 403) { setCsrf(""); sessionStorage.removeItem("fixproof_csrf"); setTarget(null); throw new Error("Your session expired. Sign in again before reporting."); }
      if (response.status === 409) { await refreshTarget(); throw new Error("The registered target changed. Review the refreshed UID and submit again."); }
      if (!response.ok) throw new Error(await detail(response));
      setResult(await response.json() as Report);
      pendingReport.current = null;
      await queryClient.invalidateQueries({ queryKey: ["incidents"] });
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Unable to report incident"); }
    finally { setBusy(false); }
  }

  return <section className="panel" aria-label="Report sample incident">
    <h2>Report sample incident</h2>
    {!csrf ? <form onSubmit={login}>
      <p className="state state-muted">Sign in with the local operator secret to report the registered sample target.</p>
      <label>Local operator secret <input type="password" value={secret} onChange={event => setSecret(event.target.value)} required /></label>
      <button disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
    </form> : <form onSubmit={report}>
      <div className="target-summary"><div><span className="eyebrow">Signed in · operator session active</span><p>Target: {target?.cluster}/{target?.namespace}/{target?.name} (UID: {target?.uid ?? "unconfigured"})</p></div><button className="secondary" type="button" onClick={() => void refreshTarget()} disabled={busy}>Refresh target</button></div>
      <label>Symptom summary <input value={summary} onChange={event => setSummary(event.target.value)} minLength={3} maxLength={800} required /></label>
      <label>Optional note <textarea value={note} onChange={event => setNote(event.target.value)} maxLength={2000} /></label>
      <button disabled={busy || !target?.uid}>{busy ? "Submitting…" : "Report incident"}</button>
    </form>}
    {error && <p role="alert">{error}</p>}
    {result && <><p role="status">{result.reused ? "Report added to open incident" : "Incident reported"}. Awaiting evidence collection. Reports start <b>unassessed</b>; reporting is not detection or confirmation.</p><IncidentProgress incidentId={result.incident_id} /></>}
  </section>;
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${base}${path}`, { credentials: "include" });
  if (!response.ok) throw new Error(await detail(response));
  return response.json() as Promise<T>;
}

export function IncidentProgress({ incidentId }: { incidentId: string }) {
  const triggers = useQuery({ queryKey: ["incident-triggers", incidentId], queryFn: () => getJson<Trigger[]>(`/api/v1/incidents/${incidentId}/triggers`) });
  const requests = useQuery({ queryKey: ["investigation-requests", incidentId], queryFn: () => getJson<Request[]>(`/api/v1/incidents/${incidentId}/investigation-requests`), refetchInterval: 2000 });
  const retry = () => { void triggers.refetch(); void requests.refetch(); };
  const loading = triggers.isPending || requests.isPending;
  const failed = triggers.isError || requests.isError;
  if (loading) return <p className="state" role="status">Loading report history and investigation queue…</p>;
  if (failed) return <div className="state" role="alert"><p>Unable to load report progress.</p><button className="secondary" onClick={retry}>Retry progress</button></div>;
  const queue = requests.data ?? [];
  const history = triggers.data ?? [];
  return <section className="incident-progress" aria-label="Incident report progress">
    <h3>Report progress</h3>
    <LiveInvestigation incidentId={incidentId} />
    <div className="progress-grid">
      <div><span className="eyebrow">Investigation queue</span>{queue.length ? <ul>{queue.map(item => <li key={item.id}><span className={`queue-status queue-${item.status}`}>{item.status}</span><time>{new Date(item.created_at).toLocaleString()}</time></li>)}</ul> : <p className="state-muted">No investigation request has been queued yet.</p>}</div>
      <div><span className="eyebrow">Trigger history</span>{history.length ? <ul>{history.map(item => <li key={item.id}><b>{item.summary}</b><small>{item.source} report · {new Date(item.reported_at).toLocaleString()}</small>{item.note && <small>Note: {item.note}</small>}</li>)}</ul> : <p className="state-muted">No trigger history is available yet.</p>}</div>
    </div>
  </section>;
}
