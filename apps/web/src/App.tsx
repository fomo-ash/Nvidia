import { NavLink, Route, Routes } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "./services/api";

const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });

function Overview() {
  const query = useQuery({
    queryKey: ["dashboard"],
    queryFn: ({ signal }) => api("/api/v1/dashboard/summary", { signal }),
  });
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
    {query.isPending ? <p role="status">Loading incidents...</p> :
      query.isError ? <div role="alert"><p>Unable to load incidents.</p><button onClick={() => void query.refetch()}>Retry</button></div> :
        <section className="panel">{query.data.length ? query.data.map(item =>
          <div className="row" key={item.id}><b>{item.title}</b><span className="badge">{item.severity}</span><span>{item.status}</span></div>,
        ) : <p>No incidents yet. Seed the local demo to load an example.</p>}</section>}
  </>;
}

function Placeholder({ title }: { title: string }) {
  return <><h1>{title}</h1><section className="panel"><p>This view is planned. The current demo supports incident investigation and approval through the API documentation.</p></section></>;
}

export default function App() {
  const links = [["/", "Overview"], ["/incidents", "Incidents"], ["/investigations", "Investigations"], ["/approvals", "Approvals"], ["/costs", "Cost Autopsy"], ["/audit", "Audit"]];
  return <div className="shell">
    <aside>
      <div className="brand">FIX<span>PROOF</span></div><p>Local operations assistant</p>
      <nav aria-label="Main navigation">{links.map(([to, label]) => <NavLink key={to} to={to} end={to === "/"}>{label}</NavLink>)}</nav>
      <footer>Local demo identity<br />Synthetic evidence and billing</footer>
    </aside>
    <main><Routes>
      <Route path="/" element={<Overview />} />
      <Route path="/incidents" element={<Incidents />} />
      <Route path="/investigations" element={<Placeholder title="Investigation timeline" />} />
      <Route path="/approvals" element={<Placeholder title="Remediation approval" />} />
      <Route path="/costs" element={<Placeholder title="Cloud Cost Autopsy" />} />
      <Route path="/audit" element={<Placeholder title="Audit history" />} />
      <Route path="*" element={<><h1>Page not found</h1><NavLink to="/">Return to overview</NavLink></>} />
    </Routes></main>
  </div>;
}
