import { useQuery } from "@tanstack/react-query";
import { api } from "../services/api";
import { useAuth } from "../context/AuthContext";
import type { components } from "../services/schema";

type AuditEvent = components["schemas"]["AuditEventOut"];

export default function AuditEventsList() {
  const { isAuthenticated } = useAuth();
  const query = useQuery({
    queryKey: ["audit-events-list"],
    queryFn: ({ signal }) => api("/api/v1/audit-events", { signal }),
    enabled: isAuthenticated,
  });

  if (!isAuthenticated) {
    return (
      <section className="panel" aria-label="Sign in required">
        <h1>Audit history</h1>
        <p className="sub">Immutable append-only record of all incident actions and executions.</p>
        <div className="state state-muted">
          <p>An operator session is required to view the audit log.</p>
          <p>Please authenticate using the <b>Sign In</b> button in the sidebar.</p>
        </div>
      </section>
    );
  }

  return (
    <>
      <h1>Audit history</h1>
      <p className="sub">Immutable append-only record of all incident actions and executions.</p>
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
          {query.data && query.data.length > 0 ? (
            <div className="table-responsive">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Timestamp</th>
                    <th>Entity</th>
                    <th>Action</th>
                    <th>Actor</th>
                    <th>Details</th>
                  </tr>
                </thead>
                <tbody>
                  {query.data.map((item: AuditEvent) => (
                    <tr key={item.id}>
                      <td>
                        <time dateTime={item.created_at}>
                          {new Date(item.created_at).toLocaleString()}
                        </time>
                      </td>
                      <td>
                        <b>{item.entity_type}</b>
                      </td>
                      <td>
                        <span className="badge badge-action">{item.action}</span>
                      </td>
                      <td>
                        <code>{item.actor}</code>
                      </td>
                      <td>
                        {item.details && Object.keys(item.details).length > 0 ? (
                          <details>
                            <summary>Inspect details</summary>
                            <pre className="audit-detail-pre">
                              {JSON.stringify(item.details, null, 2)}
                            </pre>
                          </details>
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
            <p className="state-muted">No audit events recorded yet.</p>
          )}
        </section>
      )}
    </>
  );
}
