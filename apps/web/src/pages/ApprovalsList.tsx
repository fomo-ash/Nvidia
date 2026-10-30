import { useQuery } from "@tanstack/react-query";
import { api } from "../services/api";
import { useAuth } from "../context/AuthContext";
import type { components } from "../services/schema";

type Approval = components["schemas"]["ApprovalOut"];

export default function ApprovalsList() {
  const { isAuthenticated } = useAuth();
  const query = useQuery({
    queryKey: ["approvals-list"],
    queryFn: ({ signal }) => api("/api/v1/approvals", { signal }),
    enabled: isAuthenticated,
  });

  if (!isAuthenticated) {
    return (
      <section className="panel" aria-label="Sign in required">
        <h1>Remediation approvals</h1>
        <p className="sub">Human-in-the-loop review and cryptographic action authorization.</p>
        <div className="state state-muted">
          <p>An operator session is required to inspect approvals.</p>
          <p>Please authenticate using the <b>Sign In</b> button in the sidebar.</p>
        </div>
      </section>
    );
  }

  return (
    <>
      <h1>Remediation approvals</h1>
      <p className="sub">Human-in-the-loop review and cryptographic action authorization.</p>
      {query.isPending ? (
        <p role="status">Loading approvals…</p>
      ) : query.isError ? (
        <div role="alert" className="state">
          <p>Unable to load approvals.</p>
          <button className="secondary" onClick={() => void query.refetch()}>
            Retry
          </button>
        </div>
      ) : (
        <section className="panel" aria-label="Approvals list">
          {query.data && query.data.length > 0 ? (
            <div className="table-responsive">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Decision</th>
                    <th>Approver / Actor</th>
                    <th>Proposal Hash</th>
                    <th>Decided At</th>
                  </tr>
                </thead>
                <tbody>
                  {query.data.map((item: Approval) => (
                    <tr key={item.id}>
                      <td>
                        <span className={`badge badge-${item.decision}`}>
                          {item.decision}
                        </span>
                      </td>
                      <td>
                        <b>{item.actor}</b>
                      </td>
                      <td>
                        <code title={item.proposal_hash ?? "N/A"}>
                          {item.proposal_hash ? `${item.proposal_hash.slice(0, 16)}…` : "None"}
                        </code>
                      </td>
                      <td>
                        <time dateTime={item.created_at}>
                          {new Date(item.created_at).toLocaleString()}
                        </time>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="state-muted">
              No approval decisions recorded yet. Once an investigation generates a proposal, it can be reviewed and decided on the incident detail page.
            </p>
          )}
        </section>
      )}
    </>
  );
}
