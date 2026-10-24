# API contracts

FastAPI publishes the implemented contract at `/openapi.json`. This document separates **current routes** from **proposed MVP routes**. Proposed shapes are design targets and must be finalized in OpenAPI before frontend integration. All application routes use `/api/v1`; `/health/live`, `/health/ready`, and `/metrics` are separate.

## Implemented scaffold

| Method and route | Actual behavior |
|---|---|
| `GET /dashboard/summary` | Open incident count, static cost summary, `deterministic-demo` mode. |
| `GET /incidents`, `POST /incidents`, `GET /incidents/{id}` | Database list/create/detail. |
| `POST /incidents/{id}/investigate` | Inserts fixed mock recommendation; does not collect or cite evidence. |
| `GET /incidents/{id}/evidence`, `GET /incidents/{id}/timeline` | Fixed arrays, independent of the incident ID. |
| `GET /incidents/{id}/recommendations`, `GET /recommendations/{id}` | Database recommendation reads. |
| `POST /recommendations/{id}/approve`, `POST /recommendations/{id}/reject` | Status transition and audit row; `actor` is caller-supplied. No real approval control. |
| `GET /cost-analyses`, `POST /cost-analyses` | Same static cost calculation; no persistence. |
| `GET /audit-events` | Database audit rows. |

Current errors use FastAPI's `{"detail": ...}` shape. The code checks for a missing incident on detail and investigate, but not on the fixed evidence/timeline routes. Missing/non-proposed recommendations on approve/reject currently return 409. No pagination or authorization exists.

## Proposed MVP contract

Use UUID IDs, UTC timestamps, bounded collection parameters, and a consistent error body with `code`, `detail`, and `request_id`. Define `limit` (1–100) and cursor pagination for event/evidence lists. Preserve current paths where practical, but migrate callers deliberately; do not claim these endpoints exist yet.

| Method and route | Request / result |
|---|---|
| `POST /incidents` | Accept a manual incident for an allowlisted target with a reported symptom; record `trigger_source=manual`, receipt time, and reporter. A future Prometheus detector uses the same service with `trigger_source=prometheus` and a retained trigger observation. Intake does not assert that the fault is proven. |
| `POST /incidents/{id}/investigations` | Start collection for an allowlisted cluster/namespace/Deployment; return investigation ID and `collecting` state. Repeated calls create a new run or use an explicit idempotency key. |
| `GET /incidents/{id}/investigations/{run_id}` | State, collection errors, provider/model metadata, hypotheses, cited evidence IDs, and any proposed action. |
| `GET /incidents/{id}/evidence` | Stored snapshots only: ID, source, target, observed-at/window, content hash, trust label, redaction status, and bounded payload. |
| `GET /incidents/{id}/timeline` | Persisted state/audit events in time order. |
| `GET /recommendations/{id}` | Immutable proposal version/hash, action, exact target UID, expected current template hash, desired good template hash, parameters, evidence citations, expiry, and status. |
| `POST /recommendations/{id}/approve` | Operator intent for the supplied exact `proposal_hash`; server records authenticated local actor/time/expiry. Hash mismatch or stale target is 409. |
| `POST /recommendations/{id}/reject` | Record rejection and actor; no later execute. |
| `POST /recommendations/{id}/executions` | Requires `Idempotency-Key` and approved proposal; returns execution ID/state, not a success claim. |
| `GET /executions/{id}` | Preflight, attempted mutation, Kubernetes response, timestamps, and error. |
| `POST /executions/{id}/verify` | Start/retry bounded independent verification; returns verification ID/state. |
| `GET /executions/{id}/verifications/{verification_id}` | Fresh rollout, health, and metric observations, thresholds, deadline, result, and failure reason. |
| `GET /integrations/status` | Readiness of kind/Kubernetes, Prometheus, MCP, and Nebius configuration without exposing secrets. |

### State and response rules

Investigation: `collecting → analyzing → proposed | needs_review | failed`. Proposal: `proposed → approved | rejected | expired`; a changed proposal is a **new version** requiring new approval. Execution: `pending → preflight_failed | running → succeeded | failed`. Verification: `pending → verified | verification_failed | inconclusive`. Incident closure is a separate operator decision after verification. Invalid transition, stale cluster state, or hash mismatch returns 409; missing resource 404; invalid body 422; unavailable integration 503. Document any asynchronous polling and retry semantics in OpenAPI.

Approval binds the actor to one proposal hash, version, target UID, expected bad template hash, desired good template hash, and expiry. The server must recheck these against persisted data and current Kubernetes state at execution. MCP tools are private backend interfaces, not browser API routes.
