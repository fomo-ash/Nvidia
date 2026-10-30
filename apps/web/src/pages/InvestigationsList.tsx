import { useQuery } from "@tanstack/react-query";
import { NavLink } from "react-router-dom";
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
  });

  if (!isAuthenticated) {
    return (
      <section className="panel" aria-label="Sign in required">
        <h1>Investigations</h1>
        <p className="sub">Evidence collection and AI diagnosis runs.</p>
        <div className="state state-muted">
          <p>An operator session is required to inspect investigations.</p>
          <p>Please authenticate using the <b>Sign In</b> button in the sidebar.</p>
        </div>
      </section>
    );
  }

  return (
    <>
      <h1>Investigations</h1>
      <p className="sub">Evidence collection and AI diagnosis runs.</p>
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
          {query.data && query.data.length > 0 ? (
            <div className="table-responsive">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Status</th>
                    <th>Assessment</th>
                    <th>Summary</th>
                    <th>Created</th>
                    <th>Incident</th>
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
                        <code>{item.result?.assessment ?? "unassessed"}</code>
                      </td>
                      <td>
                        <b>{item.summary || "Investigation run"}</b>
                        {item.result?.gaps && item.result.gaps.length > 0 && (
                          <small className="cell-sub">
                            Gaps: {item.result.gaps.join(", ")}
                          </small>
                        )}
                      </td>
                      <td>
                        <time dateTime={item.created_at}>
                          {new Date(item.created_at).toLocaleString()}
                        </time>
                      </td>
                      <td>
                        {item.incident_id ? (
                          <NavLink to={`/incidents/${item.incident_id}`}>
                            View incident
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
