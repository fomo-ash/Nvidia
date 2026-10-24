# Architecture

FixProof is a modular monolith. React/Vite owns the operator experience; FastAPI owns contracts and domain rules; PostgreSQL owns durable incident, recommendation, and audit records. SQLite supports isolated unit/integration tests and optional host development. Prometheus and Grafana currently observe the API process.

```mermaid
flowchart LR
  UI[React operator console] --> API[FastAPI routes and OpenAPI]
  API --> Workflow[Investigation and approval services]
  Workflow --> Provider[Validated mock provider]
  Workflow --> DB[(PostgreSQL)]
  API --> Costs[Deterministic billing arithmetic]
  Prometheus --> API
  Grafana --> Prometheus
```

## Implemented boundaries

Routes handle HTTP input and output; recommendation services enforce lifecycle decisions and transaction boundaries. A provider protocol separates advisory investigation from persistence. The mock provider returns a bounded, schema-validated local proposal with explicitly synthetic, untrusted evidence. No provider has a mutation tool or cloud credentials.

Each investigation persists normalized evidence with source/time, content hash and trust label, while retaining the original proposal JSON for compatibility. Its SHA-256 digest binds recommendation identity, incident, version, action, target, parameters, evidence and expiry. Separate approval decisions bind actor/version/hash/expiry. Approval and execution independently validate the reviewed snapshot and normalized evidence. Reinvestigation supersedes pending or approved earlier proposals and is blocked during a pending execution.

PostgreSQL serializes investigation and decision operations with an incident row lock. The unique incident/version constraint and conditional decision update provide additional safeguards. SQLite is a convenience/test backend; it does not reproduce PostgreSQL row locking. Concurrency tests therefore run against PostgreSQL.

Timeline entries come from retained audit events, protected by append-only database triggers. Collection reads are bounded with limit/offset or route-bound keyset cursors and newest-first timestamp/UUID ordering.

Phase 2 persists billing analyses and Decimal/Numeric source rows together with their audit events. Idempotency records bind a server actor/key to a route/body and replay the original result. Execution and verification commit a pending claim before adapter invocation so a crash does not silently repeat an action. These are separate records and outcomes; verification requires attributable, fresh post-execution measurements consistent with their numeric thresholds. The default adapter records an explicit unavailable execution failure and performs no infrastructure mutation.

## Contracts and runtime

The API exports a committed OpenAPI snapshot. The frontend generates TypeScript definitions from that snapshot and derives response types from paths. CI checks both generated artifacts for drift, alongside lint, build, SQLite/PostgreSQL tests, development-image tests, and an HTTP stack smoke test.

Runtime images exclude test tools. Separate development targets contain test dependencies and sources. The web runtime serves SPA routes on port 8080. Compose exposes the console, API, and monitoring only on loopback. API readiness checks database connectivity and the current migration revision.

## Remaining product layers

Production authentication/project authorization, isolated candidate testing, pending-operation reconciliation/workers, real metrics/log/deployment collectors, and infrastructure/measurement adapters remain future work. A server-owned local role resolver provides the Phase 2 authorization boundary; it is not production login. LOCAL_DEMO_ENABLED=false fails application access closed until authentication is configured. At-most-one invocation through the API does not guarantee exactly-once delivery to an external infrastructure system.

The target product sequence remains detect → investigate → explain → propose → test where practical → approve → execute → verify → report. This scaffold implements only part of that sequence and must not report an actual infrastructure change or recovered workload.

## Target local kind MVP

The first real incident is a deliberately faulty configuration in a new Deployment revision of the [sample application](INITIAL_INCIDENT.md). The MVP adds one local FixProof MCP server as the infrastructure boundary. The existing FastAPI lifecycle remains the policy and persistence owner; do not give Nemotron direct MCP access or move approval checks into the UI.

```mermaid
flowchart LR
  Operator --> Web[Local React UI]
  Web --> API[Local FastAPI policy/workflow]
  API --> DB[(Local PostgreSQL history)]
  API --> MCP[One local FixProof MCP server]
  MCP --> K8S[kind Kubernetes API]
  MCP --> PROM[Local Prometheus]
  K8S --> Sample[Sample Deployment]
  Sample --> PROM
  API -->|bounded redacted evidence over HTTPS| Nebius[Nebius Token Factory / NVIDIA Nemotron]
```

1. Bootstrap a known-good pod template and record its hash in trusted local baseline state. Fault injection creates a new revision with `FAIL_MODE=on`; `/api/work` returns 5xx and functional `/healthz` fails while `/readyz` keeps traffic flowing.
2. An authenticated local operator reports the registered target. The API records a trigger and queues investigation. Optional metric detection may later enter the same intake service.
3. MCP read tools collect capped Prometheus windows, Deployment/ReplicaSet/pod state, events, logs, and a direct probe. Extend existing evidence records with target identity, window, collection error, and redaction metadata. The model receives only stored evidence IDs and sanitized excerpts.
4. The Nebius provider returns advisory hypotheses, support/contradiction citations, uncertainty, and an allowed action name. FastAPI validates the output and fills target and desired template from trusted local state.
5. The operator approves the exact immutable proposal. FastAPI rechecks existing hash/version/expiry/approval rules plus current Kubernetes UID/resource version/template hash. A short-lived, one-use capability binds the execution; the MCP mutation tool independently checks scope and state before restoring the captured good template.
6. Execution and verification remain separate records. Fresh rollout availability, three post-action `/healthz` probes, and a 60-second Prometheus window with sufficient traffic decide verified, failed, or inconclusive. No model statement or accepted patch alone closes the incident.

Compose runs web/API/database/Prometheus and the planned MCP service; kind runs the sample workload. The bootstrap must prove Compose-to-kind API and metrics connectivity **from inside containers**. Use a namespace-scoped ServiceAccount credential, never the host's cluster-admin kubeconfig or Docker socket. Nebius inference is the sole required remote service for this MVP and needs an internet connection. See [implementation plan](IMPLEMENTATION_PLAN.md) and [security](SECURITY.md).
