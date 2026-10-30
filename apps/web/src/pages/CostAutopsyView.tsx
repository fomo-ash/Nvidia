import { useQuery } from "@tanstack/react-query";
import { api } from "../services/api";
import { useAuth } from "../context/AuthContext";
import type { components } from "../services/schema";

type CostAnalysis = components["schemas"]["CostAnalysisOut"];

const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });

export default function CostAutopsyView() {
  const { isAuthenticated } = useAuth();
  const query = useQuery({
    queryKey: ["cost-analyses-list"],
    queryFn: ({ signal }) => api("/api/v1/cost-analyses", { signal }),
    enabled: isAuthenticated,
  });

  if (!isAuthenticated) {
    return (
      <section className="panel" aria-label="Sign in required">
        <h1>Cloud Cost Autopsy</h1>
        <p className="sub">Evidence-backed workload and incident cost impact tracking.</p>
        <div className="state state-muted">
          <p>An operator session is required to inspect cost analyses.</p>
          <p>Please authenticate using the <b>Sign In</b> button in the sidebar.</p>
        </div>
      </section>
    );
  }

  const analyses = query.data ?? [];
  const latest = analyses[0];

  return (
    <>
      <h1>Cloud Cost Autopsy</h1>
      <p className="sub">Evidence-backed workload and incident cost impact tracking.</p>
      <p role="status" className="state-muted">
        Billing samples and estimated savings are synthetic calculations for local operational rehearsals.
      </p>

      {query.isPending ? (
        <p role="status">Loading cost analysis data…</p>
      ) : query.isError ? (
        <div role="alert" className="state">
          <p>Unable to load cost analysis.</p>
          <button className="secondary" onClick={() => void query.refetch()}>
            Retry
          </button>
        </div>
      ) : (
        <>
          {latest && (
            <>
              <section className="grid">
                <article>
                  <span>{latest.current_period} total cost</span>
                  <strong>{usd.format(latest.total_cost)}</strong>
                </article>
                <article>
                  <span>Previous period ({latest.previous_period})</span>
                  <strong>{usd.format(latest.previous_total)}</strong>
                </article>
                <article>
                  <span>Change</span>
                  <strong>
                    {usd.format(latest.change)} (
                    {latest.change_percent === null
                      ? "no baseline"
                      : `${latest.change_percent}%`}
                    )
                  </strong>
                </article>
              </section>

              <section className="panel">
                <h2>Projected Incident Remediation Savings</h2>
                <p>
                  Estimated savings:{" "}
                  <b>{usd.format(latest.estimated_savings.amount)}</b>
                </p>
                <p>{latest.estimated_savings.assumption}</p>
                <p>
                  <small>Formula: {latest.estimated_savings.formula}</small>
                </p>
              </section>
            </>
          )}

          <section className="panel" style={{ marginTop: "24px" }}>
            <h2>Recorded Cost Reports</h2>
            {analyses.length > 0 ? (
              <div className="table-responsive">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Period</th>
                      <th>Total Cost</th>
                      <th>Estimated Savings</th>
                      <th>Recorded At</th>
                    </tr>
                  </thead>
                  <tbody>
                    {analyses.map((item: CostAnalysis) => (
                      <tr key={item.id}>
                        <td>
                          <b>{item.current_period}</b>
                        </td>
                        <td>{usd.format(item.total_cost)}</td>
                        <td>{usd.format(item.estimated_savings.amount)}</td>
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
              <p className="state-muted">No cost analysis reports generated yet.</p>
            )}
          </section>
        </>
      )}
    </>
  );
}
