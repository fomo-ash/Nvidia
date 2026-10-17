# API contracts

All application routes use `/api/v1`, UUID identifiers, JSON, and FastAPI’s `{ "detail": "..." }` error shape. Collection pagination will use `limit` (1–100) and opaque `cursor` before collections become unbounded.

Implemented: `GET /dashboard/summary`, incident list/create/detail/investigate/evidence/timeline/recommendations, recommendation detail/approve/reject, cost analyses, and audit events. Health routes are `/health/live` and `/health/ready`.

Planned contract endpoints: recommendation execution, execution read/verify, and individual cost-analysis read. Their state machine is `proposed -> approved|rejected -> executed -> verified|verification_failed`; only `approved` exact immutable versions may execute. Invalid transitions return 409, absent resources 404, schema errors 422. OpenAPI at `/openapi.json` is the source for generated client types.
