import { useState, type FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";

const base = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");

type Target = { target_id: string; uid: string | null; cluster: string; namespace: string; name: string };
type Report = { incident_id: string; trigger_id: string; investigation_request_id: string; reused: boolean; assessment: string };

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

  async function login(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try {
      const response = await fetch(`${base}/api/v1/session`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ secret }) });
      if (!response.ok) throw new Error(await detail(response));
      const session = await response.json() as { csrf_token: string };
      const targets = await fetch(`${base}/api/v1/incident-targets`, { credentials: "include" });
      if (!targets.ok) throw new Error(await detail(targets));
      const items = await targets.json() as Target[];
      setTarget(items[0] ?? null); setCsrf(session.csrf_token); setSecret("");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Unable to sign in"); }
    finally { setBusy(false); }
  }

  async function report(event: FormEvent) {
    event.preventDefault();
    if (!target?.uid) { setError("The sample Deployment UID is not configured."); return; }
    setBusy(true); setError(""); setResult(null);
    try {
      const response = await fetch(`${base}/api/v1/incidents`, {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf, "Idempotency-Key": crypto.randomUUID() },
        body: JSON.stringify({ target_id: target.target_id, target_uid: target.uid, symptom: "http_5xx_spike", summary, note: note || null }),
      });
      if (!response.ok) throw new Error(await detail(response));
      setResult(await response.json() as Report);
      await queryClient.invalidateQueries({ queryKey: ["incidents"] });
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Unable to report incident"); }
    finally { setBusy(false); }
  }

  return <section className="panel" aria-label="Report sample incident">
    <h2>Report sample incident</h2>
    {!csrf ? <form onSubmit={login}>
      <label>Local operator secret <input type="password" value={secret} onChange={event => setSecret(event.target.value)} required /></label>
      <button disabled={busy}>Sign in</button>
    </form> : <form onSubmit={report}>
      <p>Target: {target?.cluster}/{target?.namespace}/{target?.name} (UID: {target?.uid ?? "unconfigured"})</p>
      <label>Symptom summary <input value={summary} onChange={event => setSummary(event.target.value)} minLength={3} maxLength={800} required /></label>
      <label>Optional note <textarea value={note} onChange={event => setNote(event.target.value)} maxLength={2000} /></label>
      <button disabled={busy || !target?.uid}>Report incident</button>
    </form>}
    {error && <p role="alert">{error}</p>}
    {result && <p role="status">{result.reused ? "Report added to open incident" : "Incident reported"}. Awaiting evidence collection. Assessment: {result.assessment}. Incident ID: {result.incident_id}</p>}
  </section>;
}
