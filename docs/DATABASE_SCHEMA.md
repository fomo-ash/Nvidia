# Database schema

Alembic exclusively manages application schema; startup never calls ORM create_all.

Migration `0001_initial` creates incidents, recommendations, and audit_events with UUID keys, an incident-status index, a recommendation-to-incident foreign key, and a unique (incident_id, version) constraint.

Migration `0002_proposal_integrity` adds nullable proposal_hash, expires_at, and retained evidence JSON to recommendations, plus positive-version and permitted-state checks. New investigations populate these fields. Existing rows keep their data and remain without a digest/expiry: an old record cannot acquire a new approval without reinvestigation. An old approved status is historical data, not authorization for any future executor.

Audit writes share the transaction with incident creation, proposal creation/supersession, approval, and rejection. The API exposes audit reads only. Database-level append-only policies and retention controls remain planned.

SQLite enables foreign keys for application connections. PostgreSQL is the deployment database and supplies row-lock semantics for concurrent decisions. API tests run against migrations rather than ORM-created tables; migration tests compare schema against metadata, exercise upgrade/downgrade, and preserve legacy rows. The optional PostgreSQL suite requires a disposable database whose name ends in _test.

Phase 2 still needs normalized investigations/evidence, independent approval records, executions/idempotency, verification results, cost analyses/source billing records, and broader indexes/constraints. These should arrive with the corresponding lifecycle services and migrations.
