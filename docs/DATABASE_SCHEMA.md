# Database schema

Alembic owns schema creation. Startup never uses ORM create_all. PostgreSQL is the deployment database; SQLite supports isolated tests and local development.

## Migration history

- 0001_initial: incidents, recommendations, and audit events.
- 0002_proposal_integrity: recommendation digests, expiry, retained JSON evidence, and version/state constraints.
- 0003_domain_lifecycle: normalized lifecycle/billing records, durable idempotency, indexes, and database audit guards.

The Phase 2 migration preserves incident/recommendation IDs, proposal hashes, original evidence JSON, and historical audit events. It imports existing evidence into investigations/evidence_items. It does not invent approval actors or timestamps: historical approved status without a new approval record cannot authorize execution. Backfill runs during an online migration; offline SQL is a schema preview, not a complete data-migration deployment artifact.

## Tables

| Table | Purpose and constraints |
|---|---|
| incidents | UUID identity, severity/summary, indexed status, creation time |
| investigations | Incident FK, provider/mode, bounded investigation result, status constraint |
| evidence_items | Investigation FK/index, source, observation time, fact, content hash, untrusted label |
| recommendations | Incident FK, optional unique investigation FK, unique incident/version, positive version, lifecycle state, exact proposal snapshot/digest/expiry |
| approvals | One decision per recommendation, version/digest, server actor, decision time and expiry; approved decisions require digest/expiry |
| executions | One attempt per recommendation/approval, copied action/target/parameters/digest, actor, adapter, pending/succeeded/failed outcome and timestamps |
| verification_results | One verification attempt per execution, separate outcome and attributable observations, timestamps |
| cost_analyses | Selected periods, USD/synthetic mode, immutable application-level report snapshot, indexed creation time |
| cost_records | Analysis FK/index, source period/resource/service/region/tags, nonnegative Numeric(20,6) amount and creation time |
| idempotency_records | Unique actor/key, canonical request fingerprint, original response/status, creation time |
| audit_events | Entity reference, server actor, action/details/time; composite entity/time index and append-only database triggers |

Application routes do not expose edits to reviewed content, decisions, evidence, billing sources, or audit history. SQL UPDATE/DELETE of audit rows is blocked in SQLite and PostgreSQL; PostgreSQL TRUNCATE is also blocked. These guards are not protection against a database administrator who can disable triggers or drop tables.

## Transactions and concurrency

Creation, normalized evidence, proposal supersession, review decisions, and cost reports/source rows commit with their audit and idempotency records. PostgreSQL serializes incident-level lifecycle decisions with a row lock. Unique constraints and conditional updates provide additional protection.

Execution and verification first commit a pending claim and its replay response, then invoke their server-side adapter and persist completion in a second transaction. Interrupted operations remain pending and are never automatically invoked again. This prevents duplicate invocation through request retries; it does not promise exactly-once delivery to external infrastructure. Workers, reconciliation, cancellation and recovery policy remain Phase 6 work.

SQLite application connections enable foreign keys. PostgreSQL tests use a separate disposable database ending in _test. Migration tests compare schema with ORM metadata, upgrade/downgrade, preserve legacy rows, and import historical evidence.

## Rollback

Back up/export Phase 2 data before downgrading. Downgrading 0003 removes its normalized lifecycle, billing, and idempotency tables and audit guards. Original recommendation evidence JSON and audit history remain. New execution/verification recommendation states become superseded so the older state constraint remains valid. Downgrade is a compatibility escape hatch, not a lossless rollback of Phase 2 records.
