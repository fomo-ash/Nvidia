# API contracts

Application routes use /api/v1, UUID identifiers, JSON, and OpenAPI at /openapi.json. The source snapshot is apps/api/openapi.json; frontend definitions are generated into apps/web/src/services/schema.d.ts.

## Identity and errors

The current local demo resolves local-demo-user/operator on the server. Request bodies cannot choose an actor. An authenticated identity resolver can later replace this dependency. Read routes allow viewers; writes require operators. LOCAL_DEMO_ENABLED=false disables application access with 401 until authentication is implemented. The current demo is not production authentication.

Missing resources return 404; state/content/idempotency conflicts return 409; viewer writes return 403; invalid requests return 422. Application errors use a string detail; FastAPI validation errors use a detail array. Readiness returns 503 for unavailable/outdated databases without leaking connection details.

## Collections

Incident, investigation, recommendation, approval, execution, evidence, cost-analysis/source-record and audit collections are bounded arrays. Timeline reads are also bounded. Use limit (1–100, default 50) and optional offset (0–100000), or pass the opaque cursor from the X-Next-Cursor response header. Cursor and nonzero offset cannot be combined. Cursors bind to a particular collection/filter. Reads order newest timestamp/UUID first; incident timelines now use this same newest-first order.

Browser CORS permits Idempotency-Key and exposes X-Next-Cursor and Idempotency-Replayed.

## Idempotent writes

All application POST routes accept Idempotency-Key; execute and verify require it. Keys contain 1–128 letters/digits/dot/underscore/colon/hyphen and start with a letter or digit. A key belongs to the server-resolved actor and binds to one route and validated payload. Reusing it for a different request returns 409.

Completed retries replay the original status/body with Idempotency-Replayed: true without another state change or audit event. A replay is the original operation response, not a fresh resource read: use GET for current state. Pending execution/verification claims replay 202 and are not invoked again. Keys currently have no automatic expiry; retention and pending-operation reconciliation are deferred.

## Incident and investigation routes

- GET /dashboard/summary: incident count and latest persisted cost report, or an explicitly synthetic calculated sample fallback before an analysis exists.
- GET|POST /incidents and GET /incidents/{id}: list, create (201), detail.
- POST /incidents/{id}/investigate: retain a normalized mock investigation and bounded evidence, create a versioned recommendation, supersede older pending/approved versions. Returns the recommendation (200) for existing client compatibility.
- GET /incidents/{id}/investigations, GET /investigations, GET /investigations/{id}.
- GET /investigations/{id}/evidence: normalized IDs, source/time, content hash, trust label.
- GET /incidents/{id}/evidence: latest retained proposal snapshot, preserving the existing response shape.
- GET /incidents/{id}/timeline: real audit-derived history.
- GET /incidents/{id}/recommendations and GET /recommendations/{id}.

Investigation during a pending execution returns 409. Provider output is schema validated before any proposal is superseded.

## Approval, execution and verification

- POST /recommendations/{id}/approve with a reviewed proposal_hash; POST /recommendations/{id}/reject with {}. Both return the recommendation and persist a separate decision.
- GET /approvals, GET /approvals/{id}, GET /recommendations/{id}/approval.
- POST /recommendations/{id}/execute with proposal_hash and Idempotency-Key. Creates an execution attempt (201), or replays a pending claim (202).
- GET /executions and GET /executions/{id}.
- POST /executions/{id}/verify with {} and Idempotency-Key. Creates a separate verification attempt (201), or replays a pending claim (202).
- GET /executions/{id}/verification and GET /verifications/{id}.

The state flow is proposed → approved|rejected; approved → executed|execution_failed; executed → verified|verification_failed. Reinvestigation supersedes earlier proposed/approved recommendations. An inconclusive verification leaves the recommendation executed and does not claim recovery.

Execution rechecks current version, content hash, expiry, normalized evidence, action/target/parameter schema, and a matching durable approval. A recommendation has at most one execution attempt; retrying a failed attempt needs a fresh investigation and approval. Verification requires successful execution, a matching server-side adapter, fresh post-execution measurements, source/timestamp attribution, and outcomes consistent with numeric thresholds. Request bodies cannot submit success or measurement results.

The default operations adapter is intentionally unconfigured: execution records failed with mutation_performed=false; it does not run a shell command or change infrastructure. Verification of that failed execution returns 409. Successful/failed/inconclusive verification paths are tested using an injected synthetic adapter; actual workload adapters and recovery policy are Member 3/Phase 6 work.

## Billing and integrations

- POST /cost-analyses now creates a persisted report and source rows (201). An omitted/null/empty-object body uses the labelled sample dataset. An explicit body accepts current_period, previous_period and up to 1000 records.
- Source records contain period, service, resource, region, a finite nonnegative amount with up to six decimal places, and bounded string tags. All records belong to the selected periods, both periods need data, and previous_period must precede current_period.
- GET /cost-analyses, GET /cost-analyses/{id}, GET /cost-analyses/{id}/records. A fresh database has no analyses until one is created.
- GET /integrations reports the local database/mock provider and configuration status. It does not fabricate AWS/Kubernetes/Terraform connectivity or monitoring probes.
- GET /audit-events exposes append-only history.

Reports label synthetic mode, USD, source periods/totals/drivers, and potential savings assumptions/formula. Sources use Decimal/Numeric arithmetic; reports serialize rounded values. Real billing ingestion, partial-period normalization, credits/multi-currency and advanced cost modeling remain Phase 7 work.

## Health and contract generation

GET /health/live, GET /health/ready and GET /metrics remain outside application identity gating.

After backend contract changes:

```powershell
python apps/api/scripts/export_openapi.py
pnpm contracts:generate
```

Checks: python apps/api/scripts/export_openapi.py --check and pnpm contracts:check. Contract export never connects to a database.
