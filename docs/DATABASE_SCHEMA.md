# Database schema

Current migration `0001_initial` creates `incidents`, `recommendations`, and `audit_events`. UUID primary keys, an indexed incident status, and a unique `(incident_id, version)` recommendation constraint enforce the first domain invariants.

Phase 2 adds normalized investigations, evidence items, approvals with expiry/version hashes, executions with idempotency keys, verification results, cost analyses, and cost records. Foreign keys and append-only audit records will preserve traceability; application tables are created only by Alembic, never startup ORM creation.
