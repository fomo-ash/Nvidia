# Phase 2 manual incident intake handoff

Updated 2026-10-28. This documents the implementation on top of `main` at `59d6e13` and the checks performed in this Windows workspace.

## What is implemented

The API can accept an authenticated manual report for the registered `local-kind/fixproof-demo/sample-api` Deployment. A report is an observation supplied by an operator. It starts with lifecycle `open` and assessment `unassessed`. Each distinct report adds an immutable `incident_triggers` row and a durable `investigation_requests` row with status `queued`. The Phase 3 collector does not consume that queue yet.

The existing synthetic incident shape remains available only while `LOCAL_DEMO_ENABLED=true`; new manual reports always require a signed operator session. For the authenticated workflow set `LOCAL_DEMO_ENABLED=false`, which disables the fixed demo actor for all API routes. Existing incident rows are labeled `legacy_demo` by migration and have no target UID or trigger. They are never treated as live reports. The synthetic investigation route returns 409 for a live report, so a queued case cannot acquire a mock proposal.

## Local setup

1. Bootstrap the owned kind fixture using [its runbook](../infra/kind/README.md). Read its Deployment UID from `python scripts/kind_fixture.py status`. This developer credential is for setup only; the API receives the UID as configuration, never a cluster-admin kubeconfig.
2. Copy `.env.example` to the ignored `.env` if necessary. Set `SAMPLE_TARGET_UID` to the observed sample Deployment UID. Generate two different random values for `OPERATOR_SECRET` and `SESSION_SIGNING_KEY` (for example, `python -c "import secrets; print(secrets.token_urlsafe(32))"` twice). Set `LOCAL_DEMO_ENABLED=false`. Keep these values out of Git.
3. Run `docker compose up --build --wait --wait-timeout 180`. The API container runs Alembic migrations before serving. For an existing manual deployment, run `alembic upgrade head` from `apps/api` before starting the API. Do not reset the database volume.
4. Open the Incidents view at `http://localhost:5173/incidents`, enter the local operator secret, check the displayed Deployment UID, and submit a short symptom summary. The UI says “awaiting evidence collection” and shows the incident ID.

The session lasts one hour. It is signed with `SESSION_SIGNING_KEY`, stored in an HttpOnly SameSite cookie and accompanied by a CSRF token held in the page. Mutating API calls with a session require an allowed browser Origin and `X-CSRF-Token`. This is a local loopback HTTP workflow; TLS and production identity remain separate release work. The login returns 503 until both secrets are configured. A changed sample UID requires updating `SAMPLE_TARGET_UID` and refreshing the page before reporting again.

## API and persistence contract

`POST /api/v1/session` takes `{ "secret": "..." }` from an allowed Origin and returns a CSRF token. `GET /api/v1/incident-targets` returns the registered target and configured UID. `POST /api/v1/incidents` takes the following body with `Idempotency-Key` and `X-CSRF-Token` headers:

```json
{
  "target_id": "local-kind/fixproof-demo/sample-api",
  "target_uid": "the-configured-deployment-uid",
  "symptom": "http_5xx_spike",
  "summary": "Sample requests return 5xx",
  "note": "Observed after fault injection"
}
```

A new case returns 201. A distinct report for the same open target UID and symptom returns 200 with `reused: true`; both include `incident_id`, `trigger_id`, `investigation_request_id`, `reported_at`, lifecycle and assessment. The same actor, key and body replays the original response without a new trigger or job. A key reused with different content returns 409. Missing key or invalid body returns 422; a mismatched UID returns 409. `GET /incidents/{id}/triggers` and `/investigation-requests` expose the retained rows. The incident detail includes mode, target, lifecycle, assessment and last report time. Timeline audit events include the trigger and job IDs.

Migration `0004_incident_intake` adds nullable target fields to preserve legacy rows, a unique active fingerprint, immutable trigger guards on SQLite and PostgreSQL, and the investigation request table. The report service inserts the incident, trigger, request, idempotency response and audit event in one transaction. The fingerprint is derived from configured cluster, UID and symptom; free text cannot split a case. Closing a case and releasing its fingerprint is later lifecycle work.

## Verification performed

- API: `uv run --extra dev --locked pytest -q` from `apps/api` with `LLM_PROVIDER=mock`: 72 passed, 6 PostgreSQL-only skipped. New tests cover replay, reuse, durable records, target drift, missing key, CSRF and Origin denial, oversized notes, and schema round trip.
- OpenAPI: `uv run --extra dev --locked python scripts/export_openapi.py` from `apps/api`; frontend types regenerated with `pnpm contracts:generate`.
- Frontend: `pnpm lint`, `pnpm typecheck`, `pnpm test`, `pnpm contracts:check`, and `pnpm --filter @fixproof/web build` passed. The UI suite has 8 passing tests, including authenticated reporting with the registered UID and CSRF header.
- API lint and format checks passed after the final change. The API suite remained at 72 passed, 6 PostgreSQL-only skipped.
- The isolated PostgreSQL container check was attempted with `docker compose -f compose.checks.yaml run --build --rm api-postgres-checks`. Docker Desktop stopped producing progress while starting its disposable `db-checks` container, before tests ran; the command was interrupted. A subsequent Compose status query showed no running check-project containers. This remains an environment acceptance gap.

## Remaining gate

The sample target UID is registered from fixture state by an operator. Phase 3 must add a restricted Kubernetes read integration, check live UID drift independently, claim queued requests, persist real MCP evidence, and expose collection errors. A queued request is not a completed investigation. PostgreSQL migration/concurrency checks and the full Compose/kind scenario still need a live host run before calling this milestone accepted on both databases.

## Environment retest, 2026-10-28

After the local `.env` was updated, the API suite was rerun: 72 passed, 6 PostgreSQL-only skipped. AI: 31 passed. MCP: 21 passed. Web: 8 passed; production build and generated contract check passed. `docker compose config --quiet` passed.

The updated `.env` still has `LOCAL_DEMO_ENABLED=true` and does not define `OPERATOR_SECRET`, `SESSION_SIGNING_KEY`, or `SAMPLE_TARGET_UID`. Therefore the authenticated operator login and registered-target report are not ready for a live run. The isolated PostgreSQL check was retried, but Docker Desktop again stopped at `db-checks Starting` before tests ran. It was interrupted; a status check showed no running check-project containers. Set the three missing values and disable local demo access as described above, then repeat the full Compose/kind intake run.
