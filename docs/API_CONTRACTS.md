# API contracts

Application routes use `/api/v1`, UUID identifiers, JSON, and OpenAPI at `/openapi.json`. The committed snapshot is `apps/api/openapi.json`; generated frontend definitions are `apps/web/src/services/schema.d.ts`.

## Current routes

- `GET /dashboard/summary`: open incident count and synthetic cost report.
- `GET|POST /incidents`, `GET /incidents/{id}`: bounded listing, creation, and detail.
- `POST /incidents/{id}/investigate`: retain a validated demo proposal and evidence; increment version and supersede previous pending/approved versions.
- `GET /incidents/{id}/evidence`: latest retained evidence; empty before investigation.
- `GET /incidents/{id}/timeline`: paginated audit-derived history.
- `GET /incidents/{id}/recommendations`, `GET /recommendations/{id}`: reviewable proposal records.
- `POST /recommendations/{id}/approve`: body `{"proposal_hash":"<reviewed SHA-256>"}`.
- `POST /recommendations/{id}/reject`: body `{}`.
- `GET /cost-analyses`, `POST /cost-analyses`: calculate synthetic reports. POST returns 200, not a claim of a persisted resource.
- `GET /audit-events`: paginated audit history.
- `GET /health/live`, `GET /health/ready`, `GET /metrics`: process health, migrated database readiness, and Prometheus exposition.

Incident, recommendation, timeline, and audit collections accept `limit` (1–100, default 50) and `offset` (0–100000, default 0). Responses remain arrays. Cursor pagination is deferred; high-volume use will need it.

## Decisions and errors

Current recommendation states are `proposed → approved|rejected` and `proposed|approved → superseded` after reinvestigation. Only the latest proposed version can be decided. Approval checks the exact digest, retained content, expiry, and demo action/target. The server records `local-demo-user`; caller-provided actors are rejected. This identity is not authentication.

Absent resources return 404; invalid state transitions or conflicting writes return 409; request validation returns 422. Application errors use `{"detail":"message"}`; FastAPI validation errors use a detail array. Readiness returns 503 for unavailable or outdated databases and does not reveal connection details.

Cost reports identify synthetic mode, USD, source periods, totals, grouped resource/service/region changes, and an estimated savings formula. No real billing collection, partial-period normalization, or cost-analysis persistence is implied.

## Planned routes

Execution, isolated testing, execution read/verify, persisted cost-analysis detail, integrations, and authenticated approval endpoints remain planned. They require explicit records and independent verification outcomes before UI integration.

## Updating contracts

With the backend development dependencies installed:

```powershell
python apps/api/scripts/export_openapi.py
pnpm contracts:generate
```

Checks: `python apps/api/scripts/export_openapi.py --check` and `pnpm contracts:check`. Exporting OpenAPI does not start the server or connect to a database.
