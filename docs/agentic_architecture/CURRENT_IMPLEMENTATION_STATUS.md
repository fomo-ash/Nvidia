# MCP and AI implementation status

AI and MCP remain read-only scaffolds for the planned local kind workflow. The [architecture contract](README.md) defines service authority, the [implementation plan](../IMPLEMENTATION_PLAN.md) defines delivery order, and this file records implementation limits. Historical fail-closed work is recorded [separately](FAIL_CLOSED_IMPLEMENTATION.md).

## Implemented

- MCP exposes five bounded read tools over SSE/private REST. Source failure never substitutes synthetic readings. Restore remains absent from the registry/routes and its internal compatibility function always fails.
- Each new AI investigation receives a fresh run UUID, independent of incident identity. Reinvestigation collects new evidence instead of appending to an older checkpoint. Chat explicitly selects a run and checks its incident; its session history is also separated by run.
- MCP evidence hashes bind ID, source, fact, raw payload, aware UTC observation time, mode and trust marker. AI retains that timestamp and rejects missing/naive/stale/future timestamps, wrong source/mode, or a mismatched hash. It also checks evidence age immediately before reasoning.
- Metrics query only the registered sample job and `/api/work` route. Total, errors and source-scrape freshness share an explicit evaluation time. Source timestamps, query strings and window boundaries are retained; absent/nonfinite/stale data fails closed. Fractional counter increases are preserved.
- `JevDecisionEngine` integrates a 3-tier fallback architecture: TypeSafe Jev (primary) -> Laya local `/v1/systemone` (open-source fallback) -> deterministic SRE policy rules. It uses Speculative Fan-Out (evaluating sufficiency, missing sources, outage status, and severity concurrently in a single request) and Confidence-Gated Routing.
- AI/MCP dependency lockfiles are consumed by Docker and a dedicated two-service CI matrix. Both services use the same pinned Ruff version as the API; imported scaffolds have been formatted.

## Local acceptance for this change

Checks run in separate Python 3.12 environments with no cloud credentials or infrastructure mutations. AI tests cover new-run isolation, chat run/incident mismatch, timestamp/hash tampering, source/mode validation, and expiry before reasoning. MCP tests cover common evaluation time, explicit query scope, scrape freshness, malformed/absent data, evidence hash binding and disabled mutation.

The final test counts and verification boundaries are recorded in the [change handoff](EVIDENCE_CONTRACT_HANDOFF.md). Local results do not establish GitHub CI, live kind connectivity, Nebius response quality, or infrastructure recovery. Docker was stopped during the initial review; container build/full-stack acceptance must be checked separately.

## Still required before operator/live integration

1. The [kind sample and traffic fixture](../../infra/kind/README.md) now exists, including initialized counters and private Prometheus networking. Add namespace-scoped MCP Kubernetes read credentials and prove its TLS API connectivity; developer fixture credentials must never be reused. See the [fixture handoff](../KIND_FIXTURE_HANDOFF.md) for later live acceptance.
2. Add authenticated API intake, durable jobs and the evidence mapping/persistence bridge. The API currently accepts only the synthetic provider. Transport evidence and API UUID records have different contracts; no direct compatibility is claimed.
3. Replace `MemorySaver` with durable checkpointing and coordinate idempotent API result ingestion through a job/outbox. No approval interrupt, restart recovery or distributed worker serialization is implemented.
4. Implement structured provider output and remove fixed-confidence/root-cause assertions. Citation membership alone does not prove a supported diagnosis. Live model endpoints and response shape need a credential-gated test.
5. Finish ChatOps grounding: inject selected evidence into model context, persist tool reads, and validate against the complete retained evidence set. Selecting the correct run does not fix dynamic-tool citation handling. Add explicit inference/tool/concurrency budgets.
6. Register a trusted baseline, persist exact target preconditions, and implement authenticated operator approval. Jev remains optional advisory input and never grants execution authority.
7. Add service authentication, one-use execution capabilities, atomic Kubernetes preconditions, durable replay protection and pending-outcome reconciliation before any write permission/tool is enabled.
8. Independently measure recovery using a complete post-action rollout/probe/traffic window. Current investigation metrics are not a verification verdict.

No new approvable proposal or infrastructure mutation is enabled by these changes. The existing Phase 2 API foundation remains complete; the new MVP delivery phases are a separate roadmap.
