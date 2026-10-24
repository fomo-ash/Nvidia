# Security and approval policy

This is a local self-hosted tool with an outbound Nebius inference call. Local does not mean trusted: browser input, logs, Kubernetes events, GitHub context, and model output are data. The current scaffold has **no authentication or safe execution gate**. Its `actor` body field is a display string, not identity. Do not connect it to a live cluster or expose its ports beyond a controlled development machine.

## MVP access boundary

- Bind web/API/Prometheus/Grafana published ports to loopback where possible; the MCP server needs no public port. Do not expose the database. For the single-user MVP, generate a local operator secret at bootstrap, require a short-lived authenticated operator session for approval and execution, and prevent cross-site mutation requests. For team use beyond one machine, add real per-user authentication and authorization before enabling mutation.
- The API holds the Nebius key only. The MCP server holds the restricted Kubernetes credential only. Neither key reaches browser assets, prompts, persisted evidence, logs, or audit details. `.env` and generated kubeconfigs remain ignored and local.
- Create a Kubernetes Role limited to `fixproof-demo` and the sample workload. Read verbs cover only needed pods, pod logs, events, Deployments, ReplicaSets, and rollout status. Mutation is limited to patching the one Deployment after a server-side name/UID and state check. Never mount a cluster-admin kubeconfig or Docker socket.
- Restrict MCP read tools by namespace, query template, time range, log byte/line cap, and timeout. Only one mutation tool exists: restore the captured known-good pod template. No arbitrary shell, `kubectl` command, URL fetch, or free-form PromQL from the model.

## Mandatory mutation gate

1. Persist a normalized, schema-validated proposal with version/hash, cited evidence, exact target UID, expected current bad template, desired known-good template, and expiry.
2. Require an explicit operator approval request bound to that hash from the authenticated local operator session. Record server-established actor identity and time. A model response or UI state alone cannot authorize execution.
3. At execution, re-read the approval, reject expired/rejected/changed/already-used proposals, enforce the allowlist and namespace, and compare Kubernetes UID/resource version/template hash with the proposal. Drift requires a new investigation and approval.
4. Use a unique idempotency key, transactionally claim the execution, and record preflight and mutation results. Issue a short-lived, one-use signed execution capability bound to the proposal hash and target; the MCP mutation tool validates it and repeats target and state checks. Do not trust a caller-provided approval flag.
5. Verify recovery independently. A successful Kubernetes patch is an execution outcome, not proof of service recovery.

## Data sent to inference

Send only the minimum redacted, bounded evidence necessary: metric aggregates, status/events, and short relevant log excerpts with stable evidence IDs. Strip obvious secrets, tokens, private URLs, and personal data before the HTTPS request; keep source payloads local with retention controls. Treat instructions embedded in logs or events as untrusted text. Log provider/model and request metadata without credentials or full sensitive prompts. On provider failure, keep manual inspection available and never infer approval or success.

The [roadmap](IMPLEMENTATION_PLAN.md) requires tests for missing/stale approval, target drift, duplicate execution, hostile evidence, secret redaction, and failed verification before enabling mutation.
