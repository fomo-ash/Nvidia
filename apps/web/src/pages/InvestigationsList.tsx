import { useQuery } from "@tanstack/react-query";
import { NavLink } from "react-router-dom";
import { ExternalLink } from "lucide-react";
import { api } from "../services/api";
import { useAuth } from "../context/AuthContext";
import type { components } from "../services/schema";

type Investigation = components["schemas"]["InvestigationOut"];

export default function InvestigationsList() {
  const { isAuthenticated } = useAuth();
  const query = useQuery({
    queryKey: ["investigations-list"],
    queryFn: ({ signal }) => api("/api/v1/investigations", { signal }),
    enabled: isAuthenticated,
    refetchInterval: 5000,
  });

  if (!isAuthenticated) {
    return (
      <section className="panel" aria-label="Sign in required">
        <div className="page-header">
          <h1>Investigations</h1>
          <p className="sub">Evidence collection and AI diagnosis runs.</p>
        </div>
        <div className="state state-muted">
          <p>An operator session is required to inspect investigations.</p>
          <p>Please authenticate using the <b>Sign In</b> button in the sidebar.</p>
        </div>
      </section>
    );
  }

  return (
    <>
      <div className="page-header">
        <h1>Investigations</h1>
        <p className="sub">Evidence collection, retained metric observations, and advisory AI diagnosis runs.</p>
      </div>

      {query.isPending ? (
        <p role="status">Loading investigations…</p>
      ) : query.isError ? (
        <div role="alert" className="state">
          <p>Unable to load investigations.</p>
          <button className="secondary" onClick={() => void query.refetch()}>
            Retry
          </button>
        </div>
      ) : (
        <section className="panel" aria-label="Investigations list">
          <h2>Active & Completed Runs</h2>
          {query.data && query.data.length > 0 ? (
            <div className="table-responsive">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Status</th>
                    <th>Assessment</th>
                    <th>Summary</th>
                    <th>Created</th>
                    <th>Associated Incident</th>
                  </tr>
                </thead>
                <tbody>
                  {query.data.map((item: Investigation) => (
                    <tr key={item.id}>
                      <td>
                        <span className={`badge badge-${item.status}`}>
                          {item.status}
                        </span>
                      </td>
                      <td>
                        <code className="mono">{item.result?.assessment ?? "unassessed"}</code>
                      </td>
                      <td>
                        <b>{item.summary || "Investigation run"}</b>
                        {item.result?.gaps && item.result.gaps.length > 0 && (
                          <small className="cell-sub" style={{ color: "var(--color-warning)" }}>
                            Gaps: {item.result.gaps.join(", ")}
                          </small>
                        )}
                      </td>
                      <td>
                        <time dateTime={item.created_at} className="mono" style={{ fontSize: "12px" }}>
                          {new Date(item.created_at).toLocaleString()}
                        </time>
                      </td>
                      <td>
                        {item.incident_id ? (
                          <NavLink
                            to={`/incidents/${item.incident_id}`}
                            style={{ display: "inline-flex", alignItems: "center", gap: "4px" }}
                          >
                            View incident <ExternalLink size={12} />
                          </NavLink>
                        ) : (
                          <span className="state-muted">—</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="state-muted">
              No investigations have been executed yet. Report an incident to trigger an investigation.
            </p>
          )}
        </section>
      )}
    </>
  );
}
