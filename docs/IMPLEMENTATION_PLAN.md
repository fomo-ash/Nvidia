# Implementation plan

| Phase | Status | Owner | Objective / acceptance criteria |
|---|---|---|---|
| 0 Assessment & architecture | DONE | Member 1 | Repository assessed; architecture, ownership and contracts documented. |
| 1 Runnable scaffold & Docker | IN PROGRESS | Member 3 | Compose, health endpoints, migration, monitoring, CI; acceptance: stack builds and health checks pass. |
| 2 Database & APIs | IN PROGRESS | Member 1 | Full domain models/endpoints/state rules; acceptance: migration/API/invariant tests pass. |
| 3 Frontend workflow | IN PROGRESS | Member 4 | Operational pages and deterministic UI; acceptance: strict build/component/E2E tests pass. |
| 4 Observability & evidence | NOT STARTED | Member 3 | Sample workload, bounded logs, reproducible fault; acceptance: alert/evidence demonstration. |
| 5 AI investigation | NOT STARTED | Member 2 | Provider abstraction, structured validated mock/LLM output; acceptance: invalid-output tests. |
| 6 Safe remediation | NOT STARTED | Member 1 | Immutable approval, allowlist, execution and verification; acceptance: all invalid-transition tests. |
| 7 Cloud Cost Autopsy | IN PROGRESS | Member 2 | Synthetic billing/calculations/explanations; acceptance: edge-case tests and charts. |
| 8 Kind, security & demo | NOT STARTED | Member 3 | Kind adapter, hardened CI, E2E/runbook; acceptance: final controlled demo. |

Each phase requires: scoped subtasks in its owner’s tracker, dependency review at the stated integration checkpoint, automated tests, documented risk mitigation, peer review, and demonstrable acceptance criteria before status changes to DONE. Primary risks are accidental live mutation (allowlists/local-only adapters), ungrounded AI outputs (schema/evidence validation), and contract drift (OpenAPI generation/contract review).
