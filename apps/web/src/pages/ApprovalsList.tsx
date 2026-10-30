import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, XCircle } from "lucide-react";
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
    refetchInterval: 5000,
  });

  if (!isAuthenticated) {
    return (
      <section className="panel" aria-label="Sign in required">
        <div className="page-header">
          <h1>Remediation approvals</h1>
          <p className="sub">Human-in-the-loop review and cryptographic action authorization.</p>
        </div>
        <div className="state state-muted">
          <p>An operator session is required to inspect approvals.</p>
          <p>Please authenticate using the <b>Sign In</b> button in the sidebar.</p>
        </div>
      </section>
    );
  }

  return (
    <>
      <div className="page-header">
        <h1>Remediation approvals</h1>
        <p className="sub">Cryptographically signed operator authorizations binding proposal hashes to guarded cluster mutations.</p>
      </div>

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
          <h2>Authorization Decisions</h2>
          {query.data && query.data.length > 0 ? (
            <div className="table-responsive">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Decision</th>
                    <th>Approver / Operator</th>
                    <th>Proposal SHA-256</th>
                    <th>Recommendation ID</th>
                    <th>Decided At</th>
                  </tr>
                </thead>
                <tbody>
                  {query.data.map((item: Approval) => (
                    <tr key={item.id}>
                      <td>
                        <span className={`badge badge-${item.decision}`}>
                          {item.decision === "approved" ? (
                            <CheckCircle2 size={12} />
                          ) : (
                            <XCircle size={12} />
                          )}
                          {item.decision}
                        </span>
                      </td>
                      <td>
                        <b style={{ color: "var(--text-primary)" }}>{item.actor}</b>
                      </td>
                      <td>
                        <code className="mono" title={item.proposal_hash ?? "N/A"}>
                          {item.proposal_hash ? `${item.proposal_hash.slice(0, 16)}…` : "None"}
                        </code>
                      </td>
                      <td>
                        <code className="mono" style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                          {item.recommendation_id ? `${item.recommendation_id.slice(0, 8)}…` : "—"} (v{item.recommendation_version})
                        </code>
                      </td>
                      <td>
                        <time dateTime={item.created_at} className="mono" style={{ fontSize: "12px" }}>
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
