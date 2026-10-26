# Initial incident: unhealthy sample application

**Status: fixture implemented; product integration remains planned.** The sample application, guarded developer fault/reset scripts and kind manifests now live in `apps/sample`, `scripts/kind_fixture.py` and `infra/kind`. See the [fixture runbook](../infra/kind/README.md) for setup and verification. This is not an agent execution path or an API-persisted live evidence collector.

## Setup and trigger

Run a small HTTP sample application as one Deployment in kind namespace `fixproof-demo`. The initial pod template is the known-good revision. Its `/readyz` endpoint reports that the process can receive traffic, `/healthz` reports functional application health, and `/api/work` represents a user request. `/metrics` exposes request totals labeled by route and status class. A local traffic generator sends at least one `/api/work` request per second so both healthy and faulty windows have enough observations.

The sample application becomes unhealthy after a deliberately introduced configuration problem. For the first reproducible fixture, the fault command records the good pod template and its hash, then creates a new Deployment revision with `FAIL_MODE=on`. The new pods remain process-ready, but `/api/work` returns HTTP 5xx and functional `/healthz` fails. This creates a genuine Kubernetes revision change and a measurable service error spike. The reset command restores the known-good template and waits for healthy traffic. Both commands must be repeatable from a clean cluster without manual manifest editing.

## Detect or accept the incident

The MVP accepts a manually reported incident for the exact sample Deployment. An optional Prometheus rule may open the same incident path when it detects the error spike; automatic alert ingestion is not required for the first release. Record whether the trigger was `manual` or `prometheus` and retain the triggering observation. Intake queues evidence collection and does not by itself prove the fault. To classify the fault as active, require at least 20 `/api/work` requests in a 60-second window and a 5xx rate above 20%. Store the window, numerator, denominator, query, and observation time. If the series is absent or traffic is too low, report insufficient evidence rather than a healthy or faulty verdict. The full intake contract is in [Incident detection and intake](INCIDENT_INTAKE.md).

## Evidence FixProof must retain

| Source | Required observation |
|---|---|
| Prometheus | Pre-fault and fault-window request count and 5xx rate, plus scrape freshness. |
| Kubernetes API | Namespace/Deployment name and UID, desired/available replicas, current revision, pod states, ReplicaSet history, and relevant events. |
| Pod logs | Bounded excerpts from the faulty pods, with timestamps and source pod identity; log text is untrusted. |
| Direct probe | Timestamped `/healthz` result and HTTP status from the sample endpoint. |

Each snapshot gets a stable evidence ID, source, observed-at time, collection window, target identity, content hash, and any collection error. Missing events or logs remain explicit gaps. A model conclusion must cite retained evidence IDs and state uncertainty; a matching fault message alone is not proof of root cause.

## Proposed fix and approval

The only supported mutation is `restore_known_good_template` for this exact Deployment. The proposal contains the namespace, Deployment name and UID, expected faulty template hash and Kubernetes resource version, desired captured good template hash, evidence citations, version, hash, and expiry. The operator reviews that exact payload and explicitly approves it. Execution stops if the Deployment has changed, the approval has expired, or the proposal hash differs. The MCP server performs one guarded Kubernetes API patch using its namespace-scoped credential. It cannot run arbitrary commands or choose another revision.

## Recovery verdict

Execution success means only that the patch was accepted. Verification starts a **new** observation window after the patch. Mark `verified` only when the restored Deployment is available, three fresh `/healthz` probes succeed, and a 60-second Prometheus window contains at least 20 `/api/work` requests with less than 1% 5xx. Store all readings and thresholds. Persistent 5xx or failed probes mean `verification_failed`; missing metrics, too little traffic, or a timeout mean `inconclusive`. The incident remains open until the operator closes it.

Acceptance includes two repeated successful runs and negative cases for rejection, target drift, and failed or inconclusive verification. See the [roadmap](IMPLEMENTATION_PLAN.md) and [demo runbook](DEMO_RUNBOOK.md).
