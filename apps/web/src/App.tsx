import { NavLink, Route, Routes, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "./services/api";
import IncidentReport, { IncidentProgress } from "./IncidentReport";
import OperatorSessionBar from "./components/OperatorSessionBar";
import { useAuth } from "./context/AuthContext";

const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });

function Overview() {
  const { isAuthenticated } = useAuth();
  const query = useQuery({
    queryKey: ["dashboard"],
    queryFn: ({ signal }) => api("/api/v1/dashboard/summary", { signal }),
    enabled: isAuthenticated,
  });

  if (!isAuthenticated) {
    return (
      <section className="panel" aria-label="Sign in required">
        <h1>Operations overview</h1>
        <p className="sub">Evidence-led operations.</p>
        <div className="state state-muted">
          <p>An operator session is required to inspect live cluster status and metrics.</p>
          <p>Please click <b>Sign In</b> in the sidebar or go to the <b>Incidents</b> tab to authenticate with your operator secret.</p>
        </div>
      </section>
    );
  }

  if (query.isPending) return <p role="status">Loading operational data...</p>;
  if (query.isError) return <div role="alert"><p>Unable to reach FixProof API.</p><button onClick={() => void query.refetch()}>Retry</button></div>;
  const data = query.data;
  const costs = data.cost_autopsy;
  return <>
    <h1>Operations overview</h1>
    <p className="sub">Evidence-led operations.</p>
    <p role="status">API connected · {data.mode} · Synthetic billing data</p>
    <section className="grid">
      <article><span>Open incidents</span><strong>{data.open_incidents}</strong></article>
      <article><span>{costs.current_period} sample cost</span><strong>{usd.format(costs.total_cost)}</strong></article>
      <article><span>Change from {costs.previous_period}</span><strong>{usd.format(costs.change)} ({costs.change_percent === null ? "no percentage baseline" : `${costs.change_percent}%`})</strong></article>
    </section>
    <section className="panel">
      <h2>Cloud Cost Autopsy</h2>
      <p>Estimated savings: <b>{usd.format(costs.estimated_savings.amount)}</b>.</p>
      <p>{costs.estimated_savings.assumption}</p>
      <p><small>{costs.estimated_savings.formula}</small></p>
      <small>Sample billing totals and estimated savings are separate.</small>
    </section>
  </>;
}

function Incidents() {
  const query = useQuery({
    queryKey: ["incidents"],
    queryFn: ({ signal }) => api("/api/v1/incidents", { signal }),
  });
  return <>
    <h1>Incidents</h1>
    <IncidentReport />
    {query.isPending ? <p role="status">Loading incidents...</p> :
      query.isError ? <div role="alert"><p>Unable to load incidents.</p><button onClick={() => void query.refetch()}>Retry</button></div> :
        <section className="panel">{query.data.length ? query.data.map(item =>
          <div className="row" key={item.id}><b>{item.title}</b><span className="badge">{item.severity}</span><span>{item.status}</span><NavLink to={`/incidents/${item.id}`}>View investigation</NavLink></div>,
        ) : <p>No incidents yet. Seed the local demo to load an example.</p>}</section>}
  </>;
}

function IncidentDetails() {
  const { incidentId } = useParams();
  return <><h1>Incident details</h1><p><NavLink to="/incidents">Back to reports and sign in</NavLink></p>{incidentId && <IncidentProgress incidentId={incidentId} />}</>;
}

function Placeholder({ title }: { title: string }) {
  return <><h1>{title}</h1><section className="panel"><p>This view is planned. The current demo supports incident investigation and approval through the API documentation.</p></section></>;
}

export default function App() {
  const links = [["/", "Overview"], ["/incidents", "Incidents"], ["/investigations", "Investigations"], ["/approvals", "Approvals"], ["/costs", "Cost Autopsy"], ["/audit", "Audit"]];
  return <div className="shell">
    <aside>
      <div className="brand">FIX<span>PROOF</span></div><p>Local operations assistant</p>
      <OperatorSessionBar />
      <nav aria-label="Main navigation">{links.map(([to, label]) => <NavLink key={to} to={to} end={to === "/"}>{label}</NavLink>)}</nav>
      <footer>Local operator console<br />Billing samples labeled synthetic</footer>
    </aside>
    <main><Routes>
      <Route path="/" element={<Overview />} />
      <Route path="/incidents" element={<Incidents />} />
      <Route path="/incidents/:incidentId" element={<IncidentDetails />} />
      <Route path="/investigations" element={<Placeholder title="Investigation timeline" />} />
      <Route path="/approvals" element={<Placeholder title="Remediation approval" />} />
      <Route path="/costs" element={<Placeholder title="Cloud Cost Autopsy" />} />
      <Route path="/audit" element={<Placeholder title="Audit history" />} />
      <Route path="*" element={<><h1>Page not found</h1><NavLink to="/">Return to overview</NavLink></>} />
    </Routes></main>
  </div>;
}
