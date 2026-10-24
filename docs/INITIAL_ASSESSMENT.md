# Current repository assessment

Updated 2026-10-24 after pulling `origin/main` (commit `8410f31`). The original 2026-10-17 assessment described an empty repository; the implementation has advanced since then. This page records the baseline for the revised local-first MVP. [Phase 2 handoff](PHASE_2_HANDOFF.md) contains the earlier test and review evidence.

| Area | Implemented in current source | Still needed for the verified-remediation MVP |
|---|---|---|
| Local stack | Compose runs web, API, PostgreSQL, Prometheus, and Grafana. Web port/CORS, loopback bindings, development check images, migrations/readiness, CI, and an API-process Grafana dashboard are present. | kind cluster, sample workload, sample metrics scrape, MCP service, and reliable full-stack rehearsal. |
| API and storage | Alembic `0001`–`0003`; incidents, normalized investigations/evidence, versioned hashed recommendations, separate approval/execution/verification records, audit guards, idempotency, pagination, and persisted synthetic cost reports. | Target-bound incident triggers, real evidence provenance/window/error fields, trusted known-good baseline, Kubernetes preconditions, and real measurement data. |
| Investigation | Bounded synthetic provider, normalized synthetic evidence and version supersession. | Nebius Nemotron adapter, redacted real evidence bundle, evidence-linked hypotheses, provider failure handling. |
| Approval and operations | Server-owned local demo actor/role; exact proposal hash and expiry checks; durable approval and operation attempts. Default operations adapter records unavailable failure and performs no mutation. | Authenticated local operator session, one scoped MCP restore action, real preflight/reconciliation, independently measured recovery. |
| Operator UI | Browser/API connectivity, generated API types, incident and workflow components, component/client checks. | Real incident intake, evidence/proposal review for the kind target, approval and verification flow against live records. |
| Tests | Phase 2 handoff records PostgreSQL/SQLite lifecycle, migration, concurrency, audit, API, frontend, and HTTP smoke checks. | kind fault/integration, MCP scope, live Nebius smoke, real execution denial paths, and full recovery/failed-verification tests. |

The synthetic cost module is more than a static calculation now: Phase 2 persists reports and source rows with Decimal/Numeric arithmetic. It remains outside the first kind incident milestone. The current role resolver is not production authentication. A successful synthetic adapter test or persisted verification record is not evidence of an actual recovered workload.

The earlier foundation run recorded a Grafana image checksum problem, so a full five-service smoke was not verified there; core database/API/web/Prometheus startup and HTTP smoke were. Recheck the merged stack before marking the new Phase 0 gate complete. No real kind, MCP, Nebius, or infrastructure action exists yet.

The unrelated untracked `images/` directory in this working tree was left untouched. No local secrets were inspected or staged.
