# Sample incident contract

The first supported incident is an intentionally faulted application on the owned local kind cluster. The workload, real source collection, exact proposal and scoped restore are implemented. Complete independent recovery/release acceptance remains open.

## Workload and fault

`sample-api` is a single-replica Deployment in `fixproof-demo`; `sample-traffic` sends two `/api/work` requests per second. `/readyz` remains HTTP 200 while the process serves requests. `FAIL_MODE=on` makes `/api/work` and `/healthz` return 500. `/metrics` exports initialized work counters by route/status class; probes and unknown paths do not dilute work traffic.

Fixture bootstrap captures the healthy pod template and UID before faulting. Fault/reset accept only that template or its exact `FAIL_MODE=on` variant and use atomic UID/resource-version tests. Unrelated drift is refused. This captured local template becomes a product baseline only after authenticated API registration.

## Evidence and action

The product retains metrics/window/freshness, Deployment/pod/ReplicaSet state, events, bounded timestamped logs and current functional/readiness probes. Canonical UUIDs link model findings to stored snapshots. Collection errors and contradictory observations remain visible.

An active fault requires at least 20 work requests in a fresh minute and more than 20% 5xx. The only action is restoring the independently registered healthy template for the exact UID/version and observed bad hash. Human approval binds the exact proposal hash/expiry; MCP independently verifies scope and atomic state preconditions. No arbitrary commands or revisions are supported.

## Recovery criterion

A successful patch is not recovery. Independent verification needs the restored rollout, three fresh `/healthz` HTTP 200 probes and a full post-action minute with at least 20 requests and less than 1% 5xx. Failed measurements mean `failed`; stale/missing measurements or insufficient traffic mean `inconclusive`. No automatic incident closure is implemented.

Use [kind operations](../infra/kind/README.md) for fault/reset and the [demo runbook](DEMO_RUNBOOK.md) for acceptance. Two complete verified cycles and negative recovery cases remain release requirements, not results inferred from a healthy badge.
