# Incident detection and intake

Authenticated manual intake is implemented for the registered `local-kind/fixproof-demo/sample-api` Deployment. Automatic Prometheus alert ingestion is planned; creating a fixture fault alone does not open an incident or emit an incident notification.

## Reporting flow

1. Sign in through the console and load `GET /api/v1/incident-targets`.
2. Submit `POST /api/v1/incidents` with `target_id`, exact `target_uid`, `symptom: http_5xx_spike`, bounded `summary` and optional `note`, plus an idempotency key. Actor identity comes from the session, not the body.
3. The API rejects unknown targets, mismatched UID and conflicting key reuse. Matching open target/symptom reports reuse a case while retaining a separate manual trigger and queued request. Exact replay returns the original result without another trigger/job.
4. The kind-overlay worker claims the request and retains each source. Clients inspect trigger/request history and investigation status instead of posting collector results.

A report starts `unassessed`. Collection/analysis can produce `active`, `not_confirmed` or `inconclusive`; investigation status can be `collecting`, `completed`, `needs_review` or `failed`. These differ from recommendation/action states. There is no automatic incident closure endpoint in the current routes.

## Physical assessment

For the sample, a fresh 60-second `/api/work` window with at least 20 requests and more than 20% 5xx supports an active fault. Missing/stale/invalid measurements and insufficient traffic cannot be called healthy. The worker validates source identity and provenance, retains errors and refuses synthetic substitution.

Human text and telemetry are untrusted model instructions. A report cannot choose an arbitrary namespace, URL, PromQL query, shell command or mutation target. A reported or active symptom does not itself authorize a fix.

## Optional future detection

A detector could reuse the same intake service with attributable query/window identity and deduplication, but no automatic alert-ingestion workflow is accepted here. Do not describe Discord notifications or sample fault scripts as a detector. See [sample contract](INITIAL_INCIDENT.md), [API routes](API_CONTRACTS.md) and [demo steps](DEMO_RUNBOOK.md).
