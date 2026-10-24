# Database schema

## Implemented

Alembic migration `apps/api/alembic/versions/0001_initial.py` creates only `incidents`, `recommendations`, and `audit_events`. `incidents` has UUID ID, title, status, severity, summary, and creation time. `recommendations` has UUID ID, incident FK, integer version, status, action, target string, JSON parameters, and creation time; `(incident_id, version)` is unique. `audit_events` has UUID ID, entity type/ID, action, actor, JSON details, and creation time. The application inserts audit rows, but the schema does not make the table append-only. Cost data and evidence are not persisted.

## Proposed MVP migration sequence

1. **Intake.** Extend `incidents` with target cluster/namespace/kind/name/UID, symptom fingerprint, lifecycle, symptom assessment, and first/last observed times. Add immutable `incident_triggers` (`incident_id`, source, reporter/rule ID, source and server times, normalized trigger measurements, payload hash, unique idempotency key). Keep legacy seeded incidents visibly separate; they have no verified target or trigger.
2. **Evidence and investigations.** Add `investigations` (`incident_id`, target cluster/namespace/kind/name/UID, state, started/ended times, provider/model, collection errors). Add `evidence_items` (`investigation_id`, type/source, observed_at, window_start/end, target UID, content_hash, trust label, redacted payload or bounded local reference, collected_at). Make snapshot IDs stable for citation and index by investigation/time. Add retention fields and size limits.
3. **Immutable proposals and approval.** Evolve recommendations with investigation FK, strictly increasing version, proposal hash, allowed action enum, exact target identity, expected current resource version/template hash, desired known-good template hash, evidence citation IDs, created/expiry times. Add `approvals` (`recommendation_id`, hash, actor identity, decision, decided_at, expires_at). Never update a proposal body after creation; insert a new version instead.
4. **Execution and verification.** Add `executions` (`recommendation_id`, approval ID, unique idempotency key, state, preflight snapshot, attempted_at, completed_at, result/error). Add `verification_results` (`execution_id`, state, rollout observation, health probe result, pre/post metric windows and values, threshold config, observed_at/deadline, reason). Store enough data to reproduce why a verdict was reached. Link all transitions to audit events.

Use foreign keys, uniqueness, check constraints or validated enums, and indexes for incident timelines and idempotency. One current approval may produce at most one mutating execution. Make audit append-only at the application permission boundary and test it; PostgreSQL permissions can harden it later. Do not silently delete incident history on `make down` or `make clean`.

Migrations are the only table creation path. Each migration needs upgrade and downgrade testing against an isolated database and a plan for existing scaffold rows, which lack evidence hashes and cannot become valid live approvals retroactively.
