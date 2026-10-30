# MCP, Kubernetes and observability

## Bounded source tools

MCP is an internal service, not a general command runner. It exposes fixed-target metrics, Deployment state, pod logs, events and service probes. Kubernetes reads verify the configured Deployment UID and use owner identity for related pods/ReplicaSets/events. Responses and log excerpts are bounded; source timestamps and hashes are retained. API redaction happens before source persistence.

Prometheus queries the registered sample job and `/api/work` route. Request counts, 5xx counts, evaluation window and scrape freshness are checked together. Missing/nonfinite/stale data cannot be replaced by synthetic measurements. Functional `/healthz` and sibling `/readyz` readings remain distinct: readiness 200 does not override functional failure. An unavailable functional probe is a source error.

The [kind runbook](../infra/kind/README.md) owns fixture bootstrap, traffic, fault/reset, pinned tools and network connectivity. Its developer control commands are separate from the product action adapter.

## Credentials and scope

| Identity | Namespace | Allowed reads/writes |
|---|---|---|
| `fixproof-reader` | `fixproof-demo` | Get `sample-api`; get/list ReplicaSets, pods and events; get pod logs. No patch. |
| `fixproof-writer` | `fixproof-demo` | Get/patch only Deployment `sample-api`. No deletion or other target. |

`configure_investigation.py` provisions a 24-hour read token and verified CA. Only MCP mounts those files. Refresh after expiry or fixture recreation and recreate the overlay services. Admin kubeconfig remains a private developer fixture credential.

`configure_execution.py` provisions a separate writer token and signing configuration while leaving execution false in `.env`. `check_writer_scope.py` checks registered sample patch permission and denials for other workloads/namespaces, deletion and reader patch. The execution overlay mounts the writer only into MCP and supplies the signing key only to API/MCP; the bot/model/worker do not receive it.

## Capability and atomic patch

The private restore endpoint is `POST /internal/restore_known_good_template`, absent from model-visible tool registration. It requires service authentication plus an independently validated HMAC-SHA256 capability. Claims bind `execution_id`, `proposal_hash`, cluster, namespace, Deployment, UID, resource version, expected bad template hash, desired good template hash and an integer expiry within 60 seconds.

MCP checks signature/shape/expiry/scope, desired template hash, sample shape and exact faulty variant. It reads current state with the writer identity, then submits a JSON Patch with UID, resource-version and faulty-template `test` operations before replacing the template and recording `fixproof.dev/execution-id`. The initial read does not replace the atomic tests. Preflight failure must not mutate.

The API commits its pending execution before the call. Idempotent requests replay that attempt; another key cannot repeat the recommendation. While a live execution is unresolved, another recommendation for the same incident cannot execute. Same-execution MCP replay is rejected by exact state/marker checks.

## Unknown outcomes and verification

Timeouts can mean the patch happened without a returned response. Read-only reconciliation confirms success only from matching UID, execution marker and healthy template. An unchanged or drifted Deployment remains pending; it is not proof that an in-flight request cannot finish. No reconciliation path resubmits a patch.

`POST /internal/verify_recovery` is a separate measurement path. It waits for a complete post-action window, checks the exact restored template/marker and rollout, records three `/healthz` probes and checks fresh Prometheus traffic. A pass requires at least 20 requests and less than 1% 5xx. Failed readings produce failure; absent/stale/insufficient data is inconclusive. It does not close incidents.

These capabilities are implemented. Earlier local acceptance observed one exact approved restore and denied rejection/expiry/drift/capability/replay cases. Complete verified recovery cycles remain unaccepted; see [demo status](DEMO_RUNBOOK.md#acceptance-status).

## Guarded trial prerequisites

Register the captured baseline through `scripts/register_baseline.py`, review the exact proposal and enable `LIVE_EXECUTION_ENABLED` only for an intended scoped trial using `compose.execution.yaml`. Always recreate the normal base + kind stack afterward to remove the writer mount and signing configuration. [Execution/demo commands](DEMO_RUNBOOK.md) include expiry testing and resume restrictions. Do not grant patch rights to the reader or mount the developer kubeconfig to bypass a failed check.
