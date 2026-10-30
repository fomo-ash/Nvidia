import { useState } from "react";
import { NavLink, Route, Routes, useParams, useLocation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  LayoutDashboard,
  AlertTriangle,
  Search,
  CheckCircle2,
  DollarSign,
  ScrollText,
  Menu,
  X,
  ShieldCheck,
  ChevronRight,
} from "lucide-react";
import { api } from "./services/api";
import IncidentReport, { IncidentProgress } from "./IncidentReport";
import OperatorSessionBar from "./components/OperatorSessionBar";
import InvestigationsList from "./pages/InvestigationsList";
import ApprovalsList from "./pages/ApprovalsList";
import AuditEventsList from "./pages/AuditEventsList";
import CostAutopsyView from "./pages/CostAutopsyView";
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
        <div className="page-header">
          <h1>Operations overview</h1>
          <p className="sub">Evidence-led infrastructure reliability & autonomous remediation.</p>
        </div>
        <div className="state state-muted">
          <p>An operator session is required to inspect live cluster status and metrics.</p>
          <p>Please click <b>Sign In</b> in the sidebar to authenticate with your operator secret.</p>
        </div>
      </section>
    );
  }

  if (query.isPending) return <p role="status">Loading operational data...</p>;
  if (query.isError) {
    return (
      <div role="alert" className="state">
        <p>Unable to reach FixProof API.</p>
        <button className="secondary" onClick={() => void query.refetch()}>
          Retry
        </button>
      </div>
    );
  }

  const data = query.data;
  const costs = data.cost_autopsy;

  return (
    <>
      <div className="page-header">
        <h1>Operations overview</h1>
        <p className="sub">Evidence-led infrastructure reliability & autonomous remediation.</p>
      </div>

      <p role="status" className="state-muted" style={{ marginBottom: "16px" }}>
        API connected · <span className="mono">{data.mode}</span> · Synthetic billing data
      </p>

      <section className="grid">
        <article>
          <span>Open incidents</span>
          <strong>{data.open_incidents}</strong>
        </article>
        <article>
          <span>{costs.current_period} sample cost</span>
          <strong>{usd.format(costs.total_cost)}</strong>
        </article>
        <article>
          <span>Change from {costs.previous_period}</span>
          <strong>
            {usd.format(costs.change)} (
            {costs.change_percent === null ? "no baseline" : `${costs.change_percent}%`}
            )
          </strong>
        </article>
      </section>

      <section className="panel">
        <h2>Cloud Cost Autopsy</h2>
        <p>
          Estimated savings: <b>{usd.format(costs.estimated_savings.amount)}</b>.
        </p>
        <p className="state-muted">{costs.estimated_savings.assumption}</p>
        <p>
          <small>{costs.estimated_savings.formula}</small>
        </p>
      </section>
    </>
  );
}

function Incidents() {
  const query = useQuery({
    queryKey: ["incidents"],
    queryFn: ({ signal }) => api("/api/v1/incidents", { signal }),
  });

  return (
    <>
      <div className="page-header">
        <h1>Incidents</h1>
        <p className="sub">Cluster degradation reports, evidence collection, and remediation status.</p>
      </div>

      <IncidentReport />

      {query.isPending ? (
        <p role="status">Loading incidents...</p>
      ) : query.isError ? (
        <div role="alert" className="state">
          <p>Unable to load incidents.</p>
          <button className="secondary" onClick={() => void query.refetch()}>
            Retry
          </button>
        </div>
      ) : (
        <section className="panel" aria-label="Incident history list">
          <h2>Recorded Incidents</h2>
          {query.data.length ? (
            <div className="table-responsive">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Title</th>
                    <th>Severity</th>
                    <th>Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {query.data.map(item => (
                    <tr key={item.id}>
                      <td><b>{item.title}</b></td>
                      <td><span className={`badge badge-${item.severity}`}>{item.severity}</span></td>
                      <td><span className={`badge badge-${item.status}`}>{item.status}</span></td>
                      <td><NavLink to={`/incidents/${item.id}`}>View investigation</NavLink></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="state-muted">No incidents yet. Seed the local demo to load an example.</p>
          )}
        </section>
      )}
    </>
  );
}

function IncidentDetails() {
  const { incidentId } = useParams();
  return (
    <>
      <div className="page-header">
        <h1>Incident details</h1>
        <p className="sub">
          <NavLink to="/incidents">← Back to incidents list</NavLink>
        </p>
      </div>
      {incidentId && <IncidentProgress incidentId={incidentId} />}
    </>
  );
}

export default function App() {
  const links = [["/", "Overview"], ["/incidents", "Incidents"], ["/investigations", "Investigations"], ["/approvals", "Approvals"], ["/audit", "Audit"]];
  return <div className="shell">
    <aside>
      <div className="brand">FIX<span>PROOF</span></div><p>Local operations assistant</p>
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
