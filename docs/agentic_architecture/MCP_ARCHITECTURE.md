# MCP infrastructure gateway

Status: read-only scaffold under `apps/mcp`, internal port 8002. Uses the Python MCP SDK's low-level `Server` with SSE and equivalent private REST adapters. It does not use FastMCP. See the [authority contract](README.md) and [implementation status](CURRENT_IMPLEMENTATION_STATUS.md).

## Current tools

| Tool | Accepted input | Bound |
|---|---|---|
| `query_metrics` | `window` | Only `1m` or `5m`; fixed sample job and `/api/work` route; no caller-supplied PromQL |
| `get_deployment_status` | `namespace`, `deployment_name` | Registered demo namespace and `sample-api` |
| `get_pod_events` | `namespace`, `limit` | Registered namespace, sample-name filter, 1–20 results |
| `get_pod_logs` | `namespace`, `deployment_name`, `lines` | Registered Deployment, up to 100 tail lines, capped excerpts |
| `check_service_health` | `target_url` | Only the configured sample health URL; redirects disabled |

These five tools are available through MCP and `/tools/<name>` REST POST routes. Kubernetes/Prometheus source failures are collection gaps, not synthetic observations. Restore is absent from both advertised tools and REST routes; its compatibility function always fails. Baseline/target resource endpoints and kind/RBAC manifests remain planned.

## Evidence envelope and timing

Every read returns `id` (`EVD-` plus eight hex characters), `source`, `observed_at` (aware UTC collection/observation time), `fact`, bounded `raw_data`, `content_hash`, `trusted`, and `mode`. The SHA-256 hash covers all envelope fields except itself using sorted JSON; `observed_at` is normalized to UTC and encoded with `isoformat()`. The AI consumer uses the same canonicalization. A hash is not authentication; all source text remains untrusted input to reasoning even when a typed metric is marked `trusted`.

Prometheus traffic queries use one explicit evaluation time for numerator, denominator and freshness. Both traffic expressions filter `job='fixproof-sample',route='/api/work'`; this job must identify only the registered workload. Preserve fractional `increase()` values and compute the ratio before display rounding. Reject absent/nonfinite samples, misaligned result timestamps, errors greater than total, and source scrapes older than 30 seconds or more than five seconds ahead. Persist window start/end, last scrape time, collection time, and the fixed query strings in `raw_data`.

The future sample app must initialize both success and 5xx counter series, including a real zero, and expose the `route` label. Prometheus should scrape at most every 15 seconds. An absent error series is a collection gap, never assumed zero. Current windows are investigation observations; they do not by themselves prove a complete post-action verification interval or sufficient baseline coverage.

## API mapping is required

The API currently stores UUID evidence IDs, `trust_label='untrusted'`, synthetic-only output contracts, and a different evidence digest. MCP transport IDs, boolean trust fields, time metadata and raw payloads do **not** directly match those records. Add an incremental migration and explicit validated mapping; retain transport ID/hash and provenance beside the canonical API UUID. Do not overwrite an existing transport ID with changed content. AI should cite API-retained IDs for reviewable proposals. This bridge is not implemented.

Before persistence integration, replace short transport identifiers with collision-resistant IDs and update all citation parsers atomically. Preserve legacy IDs through explicit mapping rather than rewriting historical references.

## Future execution boundary

Only the API may request `restore_known_good_template`. AI/ChatOps may access approved read tools but never the mutation capability. Private networking is not authentication; authenticate service callers before granting Kubernetes write permissions.

Before enabling restore, capture a trusted baseline and bind a short-lived one-use signed capability to execution ID, proposal hash/version, authenticated operator decision, cluster/namespace/name/Deployment UID, expected resource version and bad template hash, desired trusted template hash, and expiry. API and MCP independently validate these preconditions.

The patch itself must atomically test UID/resource version before replacing the approved pod template; a separate GET then unconditional PATCH has a race. Durably consume the capability and record the attempt before patching. Lost responses and process interruption require an explicit unknown/pending reconciliation path and must not allow the same capability to patch twice.

Kubernetes credentials stay only in MCP. Start with namespace-scoped read permissions; add `patch` with `resourceNames: [sample-api]` only after the execution gate passes. Never mount cluster-admin kubeconfig or the Docker socket. A successful patch records execution only. API verification separately checks the restored rollout, three fresh functional probes, and a complete post-action 60-second traffic window with enough requests and less than 1% 5xx. Missing measurements remain inconclusive.
