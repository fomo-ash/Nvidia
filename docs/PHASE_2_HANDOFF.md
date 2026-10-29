# Phase 2 handoff

## Implemented scope

- Normalized investigations/evidence and separate approval decisions.
- Execution and independent verification records/endpoints with server-owned adapter dependencies.
- Persisted cost analyses and exact source billing records, including detail/source reads.
- Integration configuration/status endpoint.
- UUIDs, foreign keys, state/nonnegative constraints, indexes, bounded pagination and route-bound cursors.
- Atomic actor/key request idempotency, plus durable pending claims before adapter invocation.
- Server-owned identity/role boundary, fail-closed disabled-demo mode, and audited lifecycle transitions.
- SQLite/PostgreSQL append-only audit guards.
- Legacy evidence backfill, schema/metadata parity, upgrade/downgrade compatibility, OpenAPI and generated frontend types.
- Updated all-services HTTP smoke workflow for normalized investigations, safe unavailable execution and persisted billing.

## Acceptance and release gates

Local verification:

- PostgreSQL, Python 3.13 development container, final source: 76 passed. Includes concurrent idempotent creates, competing execution keys, duplicate requests during pending execution, normalized migration backfill, and audit UPDATE/DELETE/TRUNCATE protection.
- SQLite, Python 3.13 development container, final source: 70 passed, 6 PostgreSQL-only checks skipped.
- Frontend: 7 component/client tests passed; ESLint, strict TypeScript and the production Vite build passed with the regenerated API types.
- Python lint/format, exported OpenAPI and frontend contract drift checks passed. PostgreSQL offline migration SQL compiled; legacy backfill is explicitly an online migration.
- A Python 3.13 wheel built successfully and included all new runtime modules.
- Real HTTP smoke passed against the current API on loopback port 18000 and a separate disposable PostgreSQL database: migrated readiness, normalized evidence, durable approval, idempotent unavailable execution, failed-execution verification rejection, persisted source billing/report reads, audit history and integration status. No infrastructure mutation occurred.

Container acceptance suites used the built pinned Python 3.13 development image with the current backend mounted read-only; this avoided repeating dependency downloads while testing the exact branch source. The HTTP run used that same current source and the normal Alembic/Uvicorn startup sequence. The existing five-service/Grafana smoke was not rerun as part of this backend phase.

The Phase 2 domain API milestone is marked complete following reported CI and contract-review approval. The checks above record its local acceptance; later integration results are documented in the subsequent handoffs.

## Intentional limits

The default operations adapter records an explicit unavailable failure and never mutates infrastructure. Synthetic adapter doubles exercise successful, failed, inconclusive, stale-measurement and interrupted-operation paths in tests. No API request can inject an adapter or submit a success result.

Pending operations survive interruption and must be reconciled manually; a retry replays pending rather than risking another mutation. Exactly-once infrastructure effects, workers, reconciliation, isolated candidate testing and actual workload recovery are not delivered by this phase.

The local role boundary is an integration point, not production login/authentication. External identity, project/tenant authorization, audit retention and administrative DB hardening remain Phase 8 work. Real evidence collectors, LLM integration and billing ingestion remain their respective later phases.

## Review focus

1. Confirm the migration/backfill preserves legacy IDs/evidence/digests and never invents old approval authority.
2. Review expiry/hash/evidence/approval/target checks and the commit-before-invoke boundary.
3. Verify that replayed responses cannot bypass write roles or authorize a stale execution.
4. Review rollback data-loss notes in DATABASE_SCHEMA.md.
5. Review the POST /cost-analyses creation semantics and newest-first cursor pagination with the UI workstream.
6. Agree on trusted execution/measurement adapters with the infrastructure workstream before enabling infrastructure changes.
