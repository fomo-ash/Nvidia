# API contracts

The public generated contract is [apps/api/openapi.json](../apps/api/openapi.json); the browser types are [schema.d.ts](../apps/web/src/services/schema.d.ts). This page explains behavior, not a replacement schema. Application paths below use `/api/v1`.

## Identity and retry behavior

`POST /session` accepts the configured operator secret, sets the HTTP-only `fixproof_session` cookie and returns a CSRF token. Authenticated non-GET application requests need the allowed browser `Origin` and `X-CSRF-Token`. The local session lasts one hour. Local demo mode is a separate synthetic compatibility boundary, not production identity.

Manual reports require `Idempotency-Key` in the intake service. Baseline/proposal creation, execution, verification and reconciliation routes declare required keys. Approval/rejection and some synthetic compatibility routes accept optional keys; supply one for deliberate retry handling. Chat does not use the lifecycle idempotency wrapper.

A key binds an actor to the canonical path/payload. Reusing it with different content returns 409. Exact retries replay the original status/body with `Idempotency-Replayed: true`; that response can remain pending even after later reconciliation, so use GET for current state. No request body can inject an adapter, submit a success verdict or supply collector measurements.

## Incidents and evidence

| Routes | Behavior |
|---|---|
| `GET /dashboard/summary`, `/incidents`, `/incidents/{id}` | Retained incident and dashboard data; separately labeled synthetic compatibility. |
| `GET /incident-targets` | Configured registered target and UID, not arbitrary cluster discovery. |
| `POST /incidents` | Authenticated manual report with target ID/UID, symptom and summary; creates/reuses a live case, trigger and queued request. Synthetic creation requires demo mode. |
| `GET /incidents/{id}/triggers`, `/incidents/{id}/investigation-requests` | Newest bounded trigger and collection-request history. |
| `GET /investigations`, `/investigations/{id}`, `/incidents/{id}/investigations` | Durable run state, request identity, assessment, source/model gaps and validated analysis where available. |
| `GET /investigations/{id}/evidence` | Normalized source UUIDs, observation times, redacted payloads, hashes/provenance and collection errors. |
| `GET /incidents/{id}/timeline`, `/incidents/{id}/recommendations`, `/incidents/{id}/evidence` | Audit-derived history and compatibility proposal/evidence views. For live source observations use the selected investigation's evidence route. |
| `POST /incidents/{id}/investigate` | Legacy synthetic proposal workflow; live incidents use queued intake and the worker instead. |

A report is `unassessed` until real readings support `active`, `not_confirmed` or `inconclusive`. A completed collection without requested inference does not imply a diagnosis or approvable proposal. Failed analysis keeps source evidence and cannot supply a valid live proposal.

## Exact proposals, decisions and actions

| Routes | Behavior |
|---|---|
| `POST /trusted-baselines`, `GET /trusted-baselines/current` | Register/read an independently captured healthy template and hash bound to the configured UID. Different replacement content is denied. |
| `POST /incidents/{id}/proposals` | Uses a selected eligible live investigation and registered baseline; creates an immutable exact recommendation with version/hash/expiry and evidence bindings. |
| `GET /recommendations/{id}` | Reviewed action snapshot, target, parameters, evidence and status. |
| `POST /recommendations/{id}/approve` | Requires the exact `proposal_hash`; rechecks current content, expiry, target state and advice. |
| `POST /recommendations/{id}/reject` | Persists a separate rejection; rejected recommendations cannot execute. |
| `GET /approvals`, `/approvals/{id}`, `/recommendations/{id}/approval` | Stored decision records. |
| `POST /recommendations/{id}/execute` | Commits one pending claim before adapter invocation; only the opt-in scoped live adapter can patch a live target. Returns 201 for a final outcome or 202 when unknown/pending. |
| `GET /executions`, `/executions/{id}` | Durable attempt and outcome. |
| `POST /executions/{id}/reconcile` | Read-only confirmation of a pending live action using marker/template identity. Unchanged or drifted state remains unresolved; never resubmits a patch. |
| `POST /executions/{id}/verify` | Separate successful-execution verification request; stored readings yield `passed`, `failed` or `inconclusive`. |
| `GET /executions/{id}/verification`, `/verifications/{id}` | Stored independent verdict and measurements. |

Version, hash, expiry, retained evidence and matching approval are rechecked before action. A recommendation has at most one attempt. Any unresolved live execution blocks further incident execution, including a different proposal. Missing/stale telemetry is not recovery. A successful patch alone leaves recovery unverified. The default unconfigured adapter cannot mutate infrastructure.

## Chat, Discord and billing

`POST /chat` and `POST /incidents/{id}/chat` return advisory text and citation lists. Their grounding, run selection, fallback and audit limitations are documented in [ChatOps](CHATOPS.md), separately from the strict analysis contract.

`POST /discord/interactions` is outside `/api/v1` and deliberately omitted from generated OpenAPI. It uses Discord signatures plus application/guild/role checks rather than the operator cookie. It supports retained-data reads only; see [Discord](DISCORD_INTEGRATION.md).

`GET|POST /cost-analyses`, `GET /cost-analyses/{id}` and `/records` persist synthetic cost reports and sources using bounded finite amounts and Decimal arithmetic. Empty input selects the labeled sample dataset; there is no live billing connector. `GET /integrations` reports configuration status, not proof of remote reachability. `GET /audit-events` exposes retained lifecycle audit history.

Outside application identity gating: `/health/live`, `/health/ready`, `/metrics` and session creation. Internal AI `/analyze`, `/investigate`, `/chat` and MCP endpoints use a separate service token; they are not public operator APIs.

## Contract workflow

Run `python apps/api/scripts/export_openapi.py --check` and `pnpm contracts:check` to detect drift. Generate only after intentional implementation changes, using export without `--check` followed by `pnpm contracts:generate`. Documentation-only discrepancies must not be hidden by regenerating a broken contract. [Development](DEVELOPMENT.md) lists isolated checks.
