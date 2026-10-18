# Implementation plan

The product scope follows the FixProof proposal: detect, investigate, explain, propose, test where practical, approve, execute, verify, and report; plus evidence-based Cloud Cost Autopsy. The suggested stack is optional. Additional integrations should support this workflow rather than expand the MVP prematurely.

## Foundation hardening (2026-10-18)

- Correct runtime/development image separation, application packaging, web port mapping, SPA routing, CORS, readiness/migration checks, shutdown signal handling, and loopback exposure.
- Add a pinned pnpm workspace and lockfile, exported OpenAPI, generated frontend types, and contract drift checks.
- Move recommendation rules into services with a bounded provider protocol. Retain synthetic evidence snapshots; derive timelines from audit history; increment proposal versions and supersede earlier pending/approved proposals.
- Bind local approvals to the exact proposal digest and expiry, enforce server-labelled identity, serialize PostgreSQL decisions, and reject invalid/stale decisions. This is an approval foundation, not a completed execution safety system.
- Compute resource-level spending changes and savings from source rows, with explicit synthetic labels and assumptions. Correct sample estimated savings to $525 ($2,100 × 25%).
- Replace placeholder tests with API/migration/provider/cost tests, PostgreSQL concurrency tests, frontend component/client tests, and an HTTP stack smoke script. CI runs supported runtimes, frozen installs, contracts, and built-container checks.
- Provision an API-process Grafana dashboard and update runbooks to distinguish implemented behavior from planned capabilities.

Remaining gates: CI has not been run on GitHub by this change; production authentication, normalized investigations/evidence, durable billing analyses, actual collectors, isolated remediation, execution/idempotency, and recovery verification remain unfinished. Phase status stays IN PROGRESS until its full acceptance criteria pass.

## Delivery phases

Verification record for foundation hardening:

- PostgreSQL suite in the Python 3.13 development image: 34 passed, including migrations and concurrent investigation/approval checks.
- SQLite suite in the Python 3.13 development image: 32 passed, 2 PostgreSQL-only checks skipped. This completes the previously interrupted container run.
- Frontend in the Node 22.19 development image: 7 component/client tests passed. Container lint, strict TypeScript, and generated-type drift checks passed; the runtime production build passed. Container API lint, formatting, and OpenAPI snapshot checks also passed.
- API and web runtime images rebuilt successfully after Docker recovered. Database, API, web, and Prometheus startup passed; the API/web/database health checks passed. Both Compose configurations validated.
- Core HTTP smoke passed against the built runtime services: migrated readiness, SPA deep links, active Prometheus scraping, incident creation/investigation, retained evidence, exact approval, duplicate approval rejection, version supersession, audit timeline, and cost totals/drivers/savings. The demo seeding command also passed.
- Full five-service startup and the unmodified all-services smoke script remain unverified because Grafana 12.1.0's layer download repeatedly fails Docker checksum validation. Expected layer digest: sha256:b13b23f8a52e01ffac7a70c9e83e3b05baa147cc837b1c5d2344a4d6e2ffd7ab; downloaded digest: sha256:cc738e4f148f14059d7add6d18c62976483ae72f2fcbcc0d731009de637bd293. Retry and a targeted failed-image removal did not resolve it. No image version change, checksum bypass, or broad cache/data cleanup was performed. Grafana was explicitly excluded from the core HTTP check.
- GitHub CI has not been executed; no files have been staged, committed, or pushed by the agent.

| Phase | Status | Owner | Objective / acceptance criteria |
|---|---|---|---|
| 0 Assessment & architecture | DONE | Member 1 | Repository assessed; architecture, ownership and contracts documented. |
| 1 Runnable scaffold & Docker | IN PROGRESS | Member 3 | Compose, health endpoints, migration, monitoring, CI; acceptance: stack builds and health checks pass. |
| 2 Database & APIs | IN PROGRESS | Member 1 | Full domain models/endpoints/state rules; acceptance: migration/API/invariant tests pass. |
| 3 Frontend workflow | IN PROGRESS | Member 4 | Operational pages and deterministic UI; acceptance: strict build/component/E2E tests pass. |
| 4 Observability & evidence | NOT STARTED | Member 3 | Sample workload, bounded logs, reproducible fault; acceptance: alert/evidence demonstration. |
| 5 AI investigation | IN PROGRESS | Member 2 | Bounded mock/provider boundary exists; external reasoning, evidence grounding and failure handling remain. |
| 6 Safe remediation | IN PROGRESS | Member 1 | Version/digest/expiry approval checks exist; isolated tests, execution, idempotency and verification remain. |
| 7 Cloud Cost Autopsy | IN PROGRESS | Member 2 | Synthetic billing/calculations/explanations; acceptance: edge-case tests and charts. |
| 8 Kind, security & demo | NOT STARTED | Member 3 | Kind adapter, hardened CI, E2E/runbook; acceptance: final controlled demo. |

Each phase requires: scoped subtasks in its owner’s tracker, dependency review at the stated integration checkpoint, automated tests, documented risk mitigation, peer review, and demonstrable acceptance criteria before status changes to DONE. Primary risks are accidental live mutation (allowlists/local-only adapters), ungrounded AI outputs (schema/evidence validation), and contract drift (OpenAPI generation/contract review).
