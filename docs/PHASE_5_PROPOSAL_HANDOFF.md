# Phase 5 exact proposal and review handoff

This is the Phase 5 snapshot. Guarded execution and verification code added later is described in [the sequential recovery handoff](SEQUENTIAL_RECOVERY_HANDOFF.md); live release acceptance remains pending.

Updated 2026-10-29. Branch `feat/sequential-recovery` starts from merged main `d84dc06`.

## Delivered

- The operator can register the developer-captured healthy sample template through an authenticated, CSRF-protected API. Registration checks the configured UID, exact SHA-256, one-container sample shape and `FAIL_MODE=off`. A second different template for the same UID is rejected. SQLite and PostgreSQL triggers make registered rows append-only.
- A live proposal can be prepared only from the latest completed, active, gap-free investigation with validated model action, intact retained evidence, exact observed faulty template hash, UID and resource version, and an independently registered baseline. The API constructs the proposal; model output cannot choose YAML, target or baseline.
- The canonical proposal hash binds exact target and change, evidence IDs and hashes, analysis hash, version and expiry. Approval rechecks retained state and obtains a fresh scoped Deployment reading. Target or resource version drift denies approval. Rejection uses the existing authenticated audit path.
- The operator UI shows exact hashes, UID, resource version, expiry, evidence links and verification plan before deliberate approval or rejection. It makes no recovery claim. Live execution explicitly returns 409 while scoped capability, MCP preflight and reconciliation remain unimplemented.
- `python scripts/register_baseline.py` imports only the owned local fixture's captured baseline, signs in with the ignored local operator secret and sends the template to the API. No secret is printed.

## Checks performed

- API SQLite suite: 87 passed, 8 PostgreSQL-only skipped. New tests cover baseline registration conflict/immutability, idempotent proposal, live approval, resource version drift and execution denial.
- API Ruff check and OpenAPI export passed. Generated web types refreshed. Web TypeScript, ESLint and Vitest passed; 10 web tests in total.
- Isolated PostgreSQL container suite: 95 passed, including migrations, concurrency and append-only baseline enforcement.
- Owned kind fixture built on this host with kind v0.30.0 and Docker Desktop's bundled kubectl v1.34.1. The latter replaces the prior v1.34.0 download pin because `dl.k8s.io` did not resolve here. The API, web, AI, MCP, worker, Prometheus and Grafana containers became healthy; Grafana used local port 13000 because 3000 and 3001 were occupied. AI/MCP Dockerfiles now install pinned uv from PyPI because GHCR did not resolve.
- The live `scripts/smoke_proposal.py` run faulted the owned fixture, measured 120.02 work requests and 120.02 5xx in a fresh 60-second window, retained five real evidence records, and obtained a validated Nebius analysis. It created proposal `93454cab-2872-46df-9094-be55f40baf84` with hash `d136370618b670a35778d9d36e8ddc58eb5a8167f8f9809820ee1e46f4728b98`. Wrong-hash approval returned 409, exact approval succeeded, live execution returned 409, and the Deployment template remained faulty until the script's `finally` reset restored it. The redacted receipt is in ignored `.local/kind/proposal-acceptance.json`.

## Remaining gates

1. Confirm approval denial against a real changed Deployment; the exact-hash and live execution denials have been observed.
2. Implement and test one-use execution capability, separate restricted write identity, atomic UID/resourceVersion/template preflight, durable unknown-outcome reconciliation and zero-mutation denial cases before enabling live execution.
3. Implement independent post-action rollout, three fresh health probes and a complete 60-second Prometheus traffic window. Persist measured passed/failed/inconclusive results, complete the timeline and rehearse positive and negative cases twice.
