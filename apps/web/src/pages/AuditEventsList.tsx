import { useState, useMemo, Fragment } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search, Filter, ChevronDown, ChevronRight, Clock, User, Layers } from "lucide-react";
import { api } from "../services/api";
import { useAuth } from "../context/AuthContext";
import type { components } from "../services/schema";

type AuditEvent = components["schemas"]["AuditEventOut"];

export default function AuditEventsList() {
  const { isAuthenticated } = useAuth();
  const [search, setSearch] = useState("");
  const [filterAction, setFilterAction] = useState<string>("all");
  const [expandedRow, setExpandedRow] = useState<string | null>(null);

  const query = useQuery({
    queryKey: ["audit-events-list"],
    queryFn: ({ signal }) => api("/api/v1/audit-events", { signal }),
    enabled: isAuthenticated,
    refetchInterval: 5000,
  });

  const events = useQueryMemo(query.data ?? [], search, filterAction);

  if (!isAuthenticated) {
    return (
      <section className="panel" aria-label="Sign in required">
        <div className="page-header">
          <h1>Audit history</h1>
          <p className="sub">Immutable append-only record of all incident actions and executions.</p>
        </div>
        <div className="state state-muted">
          <p>An operator session is required to view the audit log.</p>
          <p>Please authenticate using the <b>Sign In</b> button in the sidebar.</p>
        </div>
      </section>
    );
  }

  return (
    <>
      <div className="page-header">
        <h1>Audit history</h1>
        <p className="sub">Cryptographically attested, append-only lifecycle operations and mutations.</p>
      </div>

      <div className="audit-toolbar">
        <div style={{ position: "relative", flex: "1", maxWidth: "340px" }}>
          <Search size={14} style={{ position: "absolute", left: "10px", top: "10px", color: "var(--text-muted)" }} />
          <input
            type="text"
            className="audit-search-input"
            style={{ paddingLeft: "32px" }}
            placeholder="Search by action, actor, or ID…"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <Filter size={14} className="state-muted" />
          <select
            value={filterAction}
            onChange={e => setFilterAction(e.target.value)}
            style={{ padding: "7px 10px", fontSize: "12.5px", width: "auto" }}
          >
            <option value="all">All actions</option>
            <option value="reported">Reported</option>
            <option value="report_added">Report added</option>
            <option value="proposed">Proposed</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
            <option value="executed">Executed</option>
            <option value="verified">Verified</option>
          </select>
        </div>
      </div>

      {query.isPending ? (
        <p role="status">Loading audit events…</p>
      ) : query.isError ? (
        <div role="alert" className="state">
          <p>Unable to load audit history.</p>
          <button className="secondary" onClick={() => void query.refetch()}>
            Retry
          </button>
        </div>
      ) : (
        <section className="panel" aria-label="Audit events list">
          {events.length > 0 ? (
            <div className="table-responsive">
              <table className="data-table">
                <thead>
                  <tr>
                    <th style={{ width: "40px" }}></th>
                    <th><Clock size={12} style={{ display: "inline", verticalAlign: "-1px", marginRight: "4px" }} />Timestamp</th>
                    <th><Layers size={12} style={{ display: "inline", verticalAlign: "-1px", marginRight: "4px" }} />Entity</th>
                    <th>Action</th>
                    <th><User size={12} style={{ display: "inline", verticalAlign: "-1px", marginRight: "4px" }} />Actor</th>
                    <th>Payload summary</th>
                  </tr>
                </thead>
                <tbody>
                  {events.map((item: AuditEvent) => {
                    const isExpanded = expandedRow === item.id;
                    const details = item.details || {};
                    const targetUid = typeof details.target_uid === "string" ? details.target_uid : null;
                    const proposalHash = typeof details.proposal_hash === "string" ? details.proposal_hash : null;
                    const triggerId = typeof details.trigger_id === "string" ? details.trigger_id : null;

                    return (
                      <Fragment key={item.id}>
                        <tr
                          onClick={() => setExpandedRow(isExpanded ? null : item.id)}
                          style={{ cursor: "pointer" }}
                        >
                          <td style={{ textAlign: "center", color: "var(--text-muted)" }}>
                            {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                          </td>
                          <td>
                            <time dateTime={item.created_at} className="mono" style={{ fontSize: "12px" }}>
                              {new Date(item.created_at).toLocaleString()}
                            </time>
                          </td>
                          <td>
                            <span style={{ fontWeight: 600, color: "var(--text-primary)" }}>{item.entity_type}</span>
                          </td>
                          <td>
                            <span className="badge badge-action">{item.action}</span>
                          </td>
                          <td>
                            <code className="mono">{item.actor}</code>
                          </td>
                          <td>
                            <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                              {targetUid && (
                                <span className="mono" title={`Target UID: ${targetUid}`} style={{ fontSize: "11px", color: "var(--text-secondary)" }}>
                                  target: {targetUid.slice(0, 8)}…
                                </span>
                              )}
                              {proposalHash && (
                                <span className="mono" title={`Proposal Hash: ${proposalHash}`} style={{ fontSize: "11px", color: "var(--accent-teal)" }}>
                                  hash: {proposalHash.slice(0, 8)}…
                                </span>
                              )}
                              {triggerId && (
                                <span className="mono" title={`Trigger: ${triggerId}`} style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                                  trig: {triggerId.slice(0, 8)}…
                                </span>
                              )}
                              {!targetUid && !proposalHash && !triggerId && (
                                <span className="state-muted" style={{ fontSize: "12px" }}>
                                  {Object.keys(details).length} detail fields
                                </span>
                              )}
                            </div>
                          </td>
                        </tr>

                        {isExpanded && (
                          <tr className="audit-expanded-row">
                            <td colSpan={6} style={{ background: "var(--bg-app)", padding: "12px 16px" }}>
                              <div className="audit-detail-wrapper">
                                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "8px" }}>
                                  <span className="eyebrow">Cryptographic Record & Payload</span>
                                  <span className="mono" style={{ fontSize: "11px", color: "var(--text-muted)" }}>ID: {item.id}</span>
                                </div>

                                <div className="audit-detail-grid">
                                  {Object.entries(details).map(([k, v]) => (
                                    <div key={k} className="audit-detail-item">
                                      <b>{k}:</b>
                                      <span>{typeof v === "object" ? JSON.stringify(v) : String(v)}</span>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            </td>
                          </tr>
                        )}
                      </Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="state-muted">
              {search || filterAction !== "all"
                ? "No audit records match the selected filter."
                : "No audit events recorded yet."}
            </p>
          )}
        </section>
      )}
    </>
  );
}

function useQueryMemo(items: AuditEvent[], search: string, filterAction: string) {
  return useMemo(() => {
    return items.filter(item => {
      if (filterAction !== "all" && item.action !== filterAction) return false;
      if (!search.trim()) return true;
      const q = search.toLowerCase();
      const inAction = item.action.toLowerCase().includes(q);
      const inActor = item.actor.toLowerCase().includes(q);
      const inEntity = item.entity_type.toLowerCase().includes(q);
      const inDetails = JSON.stringify(item.details || {}).toLowerCase().includes(q);
      return inAction || inActor || inEntity || inDetails;
    });
  }, [items, search, filterAction]);
}
