# Live investigation handoff

This milestone integrates authenticated incident intake, durable evidence collection and structured model analysis. Infrastructure mutation and recovery verification remain planned work.

## Implementation

- Intake endpoints expose typed target, trigger and request responses with bounded history and generated frontend contracts. Login and ordinary reads now consistently use the signed operator session.
- Migration `0005_live_evidence` preserves existing data and adds leased request attempts, normalized live evidence provenance/payload/error/redaction fields and investigation results. PostgreSQL trigger TRUNCATE is now guarded as well as UPDATE/DELETE.
- A separate API-package worker claims queued requests, serializes work per incident, commits the claim before external reads, persists each source separately and rejects expired/stale worker tokens. Expired read-only attempts may retry up to three times in distinct retained runs. Completed jobs do not run again. No infrastructure operation is retried or enabled.
- The API database is the durable source of run state and canonical evidence UUIDs. The integrated path calls the stateless AI `/analyze` endpoint over retained observations. The older LangGraph `/investigate` and ChatOps scaffolds still use MemorySaver and are not the durable product orchestration path or approval authority.
- MCP uses a 24-hour namespace-scoped read token and verified Kubernetes CA. Only MCP mounts these files, individually read-only. The developer admin kubeconfig is never mounted into application services. Deployment, ReplicaSet, pod, event and log reads check target/owner identity and cap responses. Prometheus and functional probe tools remain fixed to the sample target.
- Internal MCP/AI calls require a separate service token. Model keys reach only AI, operator/session secrets only API; MCP gets no operator/model/database secrets. The legacy local capability variable is unused and is not injected into any service.
- Envelope mode/source/time/hash/UID checks run before redaction. The source transport ID/hash is retained as provenance; a separate API hash covers the retained redacted representation. No unredacted source body is persisted. Missing sources have explicit errors and empty data, not synthetic readings.
- Structured Nebius output requires hypotheses, retained-UUID support/contradiction citations, gaps, uncertainty and one advisory action enum. Unknown citations, unsupported actions, malformed output and provider failures cannot create recommendations. There is no fixed confidence or root-cause flag in this integrated response schema. Legacy free-text parsing no longer assigns fabricated 92% confidence.
- The incident UI separates source observations from model interpretation, polls durable progress, exposes gaps and source readings, and supports direct incident links/reload. It does not offer mutation controls.

## Environment and bootstrap

Local operation requires separate operator, session-signing and internal service secrets, disabled demo access, and a registered Deployment UID matching the fixture. The validated inference model is `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`, also used in the example configuration. The previous 70B model ID was unavailable in the authenticated Nebius catalog. Store credentials in ignored `.env` and reader files.

```sh
python3.12 scripts/kind_fixture.py up
python3.12 scripts/configure_investigation.py
docker compose -f compose.yaml -f compose.kind.yaml up --build --wait --wait-timeout 180
python3.12 scripts/smoke_investigation.py
PLAYWRIGHT_CHANNEL=chrome pnpm test:e2e
```

`configure_investigation.py` refreshes the scoped read token for 24 hours, preserves existing secrets and records the current UID. Re-run it when credentials expire or the fixture is recreated, then recreate the kind-overlay services. Use localhost consistently for the browser/API cookie flow. `AI_LLM_PROVIDER` selects live inference independently of the API's compatibility mock provider. `ANALYSIS_ENABLED=false` retains physical evidence without calling the model; true enables the bounded advisory call.

Host reader files are readable by the non-root container via individual read-only mounts, inside a private mode-0700 host directory. The admin kubeconfig is separate. Do not copy these generated files or `.env` into Git.

## Acceptance evidence

| Check | Observed result |
|---|---|
| API SQLite suite, Python 3.12 | 85 passed; 8 PostgreSQL-only skipped |
| API PostgreSQL suite, disposable PostgreSQL 16.9 | 93 passed, including migrations, intake concurrency, exclusive claims, stale leases and trigger immutability |
| AI suite | 33 passed, preserving Jev/Laya selection/fallback coverage and adding strict retained-analysis cases |
| MCP suite | 25 passed, including UID/owner scope, response caps and redirect-not-healthy behavior |
| Web component/client suite | 9 passed; lint, strict types, generated contracts and production build passed |
| Real browser, installed Chrome | 2 passed: sign-in, target drift/refresh, reporting, session recovery, direct incident links and reload persistence |
| Runtime stack | API/web/MCP/AI/worker/Laya built and started with database, Prometheus and Grafana |
| Actual Kubernetes read identity | Other-namespace read and dry-run Deployment patch both denied with HTTP 403 |
| Real source failure | Prometheus was stopped briefly; the worker persisted an explicit gap, empty measurements, no model result and `needs_review`; service restarted afterward |
| Secret isolation | Running containers checked by secret category without printing values; API has no model keys, MCP no operator/model/database secrets, AI no operator/database secrets |

Browser acceptance used installed Chrome via `PLAYWRIGHT_CHANNEL=chrome`. Browser traces and screenshots are disabled to avoid retaining session material. GitHub CI and peer review remain pending. The suites report upstream Starlette/AnyIO and LangGraph deprecation warnings without test failures.

The live fault run observed approximately **120.01 requests in 60 seconds, all 5xx**, with readiness 200 and functional health 500. Authenticated intake replayed the original result for the same idempotency key. Request `226bd01e-4c14-4922-a508-c09934dbeaf4` produced investigation `5c69baa8-1c81-4dfe-abb1-f2bdeddced07`, retained five real source envelopes and a validated Nebius/Nemotron answer citing canonical evidence UUIDs. API and worker were restarted; all retained evidence IDs and bodies were unchanged. The sample was reset to healthy afterward.

Redacted local records: `.local/kind/investigation-acceptance.json` and `.local/kind/source-gap-acceptance.json`. Repeat checks exposed a `LengthFinishReasonError` at the inherited 2,048-token completion cap. The retained-analysis path now permits 8,192 completion tokens within its existing 50-second deadline and asks for at most three concise hypotheses. The repeat live acceptance passed after this adjustment, including restart persistence and fixture reset. Failures log only the exception class; malformed or incomplete output still produces manual review, never a recommendation.

The positive smoke script is repeatable; it deliberately faults only the owned fixture, adds live test reports, and resets the fixture in a finally block. It never approves or executes a product recommendation. Application history/volumes were preserved; regression tests used an entirely separate test database.

## Remaining work

CI and owner/contract review remain required. Phase 5 must register a trusted baseline in the API and construct an exact immutable proposal with target UID/resource version, bad/good template hashes, expiry and evidence. Phase 6 needs one-use execution capability, atomic Kubernetes preflight, durable replay protection and unknown-outcome reconciliation before any write permission is granted. Phase 7 needs independent post-action rollout/three-probe/full-traffic-window verdicts; a successful patch must never imply recovery. Phase 8 still requires complete positive/rejected/failed/inconclusive recovery rehearsals.

Grounded ChatOps over retained records, explicit operator incident closure, production identity/rate limiting, worker heartbeat/retention/administrative DB hardening and broader host coverage remain separate work. Legacy synthetic approvals/operations remain compatibility features and cannot authorize a live report. See NEXT.md and the implementation plan for the ordered continuation.
