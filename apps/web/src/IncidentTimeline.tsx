import { useQuery } from "@tanstack/react-query";
import type { components } from "./services/schema";

type TimelineEvent = components["schemas"]["TimelineOut"];
const base = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");

async function getTimeline(incidentId: string): Promise<TimelineEvent[]> {
  const response = await fetch(`${base}/api/v1/incidents/${incidentId}/timeline`, { credentials: "include" });
  if (!response.ok) throw new Error("Unable to load incident timeline");
  return response.json() as Promise<TimelineEvent[]>;
}

function eventLabel(event: string) {
  return event.replaceAll("_", " ").replace(/\b\w/g, letter => letter.toUpperCase());
}

function eventDetail(details: Record<string, unknown>) {
  const reason = details.reason;
  if (typeof reason === "string") return reason;
  const status = details.status;
  if (typeof status === "string") return `Status: ${status}`;
  return null;
}

export default function IncidentTimeline({ incidentId }: { incidentId: string }) {
  const query = useQuery({
    queryKey: ["incident-timeline", incidentId],
    queryFn: () => getTimeline(incidentId),
    refetchInterval: 3000,
  });

  if (query.isPending) return <p className="state" role="status">Loading incident timeline…</p>;
  if (query.isError) return <div className="state" role="alert"><p>Unable to load the incident timeline.</p><button className="secondary" onClick={() => void query.refetch()}>Retry timeline</button></div>;
  if (!query.data?.length) return <section className="incident-timeline" aria-label="Incident timeline"><h3>Incident timeline</h3><p className="state-muted">No auditable lifecycle events are available yet.</p></section>;

  return <section className="incident-timeline" aria-label="Incident timeline">
    <h3>Incident timeline</h3>
    <p className="state-muted">Events are recorded by the API. A successful restore is not a verified recovery.</p>
    <ol>
      {query.data.map((item, index) => <li key={`${item.at}-${item.event}-${index}`}>
        <time dateTime={item.at}>{new Date(item.at).toLocaleString()}</time>
        <div><b>{eventLabel(item.event)}</b>{eventDetail(item.details) && <p>{eventDetail(item.details)}</p>}</div>
      </li>)}
    </ol>
  </section>;
}
