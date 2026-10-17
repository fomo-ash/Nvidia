# Team ownership

| Member | Owns | Integration dependency |
|---|---|---|
| Member 1 | FastAPI, SQLAlchemy, Alembic, APIs, approvals, audit, backend tests | Publishes OpenAPI before UI integration |
| Member 2 | Provider boundary, mock provider, evidence normalization, investigation/cost explanations | Consumes Member 1 schemas; no mutation privileges |
| Member 3 | Compose, Docker, Prometheus/Grafana, sample workload, Kind later | Supplies health/metrics contract to Members 1 and 4 |
| Member 4 | React UI, generated API types, component/E2E tests | Consumes versioned OpenAPI contract |

Module boundaries are ownership boundaries. Contract changes require an OpenAPI update, generated TypeScript types where practical, and approval from Members 1 and 4. PRs need one owner review plus one cross-stream review for contracts/infra; migrations need Member 1 review, Docker changes Member 3 review. Integration checkpoints: scaffold (Phase 1), APIs (Phase 2), demo flow (Phase 3/4), safety gate (Phase 6), final runbook (Phase 8).
