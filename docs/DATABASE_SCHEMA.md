# Database schema

Alembic owns schema creation. PostgreSQL stores deployed state; SQLite supports isolated tests and single-worker development. Startup migrates rather than calling ORM `create_all`.

## Migrations

| Revision | Scope |
|---|---|
| `0001_initial` | Incidents, recommendations and audit events. |
| `0002_proposal_integrity` | Proposal digests, version/expiry and state integrity. |
| `0003_domain_lifecycle` | Normalized evidence, approvals, execution/verification, billing, idempotency and audit guards. |
| `0004_incident_intake` | Target identity, immutable manual triggers and queued investigation requests. |
| `0005_live_evidence` | Collection leases, per-attempt runs, redacted source provenance/errors and structured results. |
| `0006_trusted_baseline` | Append-only independently registered healthy templates. |
| `0007_discord_deliveries` | Transactional notification delivery state. |

Implementation: [migration directory](../apps/api/alembic/versions) and [domain models](../apps/api/app/models/domain.py). Online backfills preserve legacy IDs/evidence/history without inventing approval actors. Offline SQL is a schema preview, not a substitute for online data migration.

## Durable records

| Tables | Meaning |
|---|---|
| `incidents`, `incident_triggers` | Target, lifecycle/assessment, manual source and server times, deduplication and immutable report history. |
| `investigation_requests` | Queued/claimed work, token, attempts and completion state. |
| `investigations`, `evidence_items` | Per-run results and canonical evidence UUIDs, source times, target UID, transport and redacted hashes, payloads and explicit errors. |
| `trusted_baselines` | Registered healthy template, SHA-256, UID, registrar and time; database update/delete protection. |
| `recommendations`, `approvals` | Exact reviewed snapshots, unique incident/version, decision actor/hash/version/expiry and one decision per recommendation. |
| `executions`, `verification_results` | One attempt per recommendation/approval and a separate verification record per execution, with pending/final state and measurements. |
| `idempotency_records` | Actor/key uniqueness, request fingerprint and original response/status. |
| `audit_events` | Lifecycle history with database append-only guards. Chat audit durability is separately limited; see ChatOps. |
| `discord_deliveries` | One delivery per selected audit event; lease, attempts, next availability, message ID and sanitized error kind. No webhook URL, bot token or message body. |
| `cost_analyses`, `cost_records` | Persisted synthetic USD reports and Numeric/Decimal source amounts. |

## Transactions and interruption

Lifecycle writes use transactions and PostgreSQL incident row locks. Conditional updates and unique constraints protect competing decisions and requests. Execution/verification commit a pending claim before external adapters; interrupted calls are not automatically repeated. Pending live executions can be reconciled only by reads and block further execution for that incident.

Collection leases apply only to read-only work. Expired attempts remain as failed runs, with at most three collection attempts; stale workers cannot overwrite successors. SQLite tests do not establish PostgreSQL multi-worker concurrency guarantees.

Discord delivery rows are enqueued with selected live audit events in the same transaction. A rolled-back event sends nothing. The independent worker updates delivery state without approving or executing actions.

Audit UPDATE/DELETE is blocked in SQLite/PostgreSQL; PostgreSQL TRUNCATE is also guarded. Baseline and trigger guards protect their histories. These are not protections against an administrator who can disable triggers or drop tables. Chat handlers currently do not establish committed audit persistence; see [ChatOps](CHATOPS.md).

## Rollback and retention

Back up application data before downgrade. Downgrades can drop newer normalized tables, provenance, claims and findings, and map unsupported states to compatible older values. They are not lossless backups. Do not downgrade or delete the database to reset the sample; use the owned [fixture reset](../infra/kind/README.md#manual-fault-and-reset).

Tests migrate only an isolated database ending in `_test`. Production administrative roles, retention and recovery procedures remain additional hardening work.
