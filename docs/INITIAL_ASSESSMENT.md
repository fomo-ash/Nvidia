# Repository assessment

Updated 2026-10-24 from the checked-in source. The original 2026-10-17 assessment described the repository before the scaffold was added; this page now records the current baseline for the revised MVP.

## Implemented

| Area | Source | Current behavior |
|---|---|---|
| API and storage | `apps/api/app/main.py`, `api/v1/routes.py`, `models/domain.py`, Alembic `0001_initial` | FastAPI routes, PostgreSQL tables for incidents, recommendations, and audit events; liveness, database readiness, and API metrics endpoint. |
| Investigation demo | `routes.py` | `investigate` inserts a fixed `restart_demo_workload` recommendation. Evidence and timeline responses are fixed arrays with a fixed timestamp; they are not collected from an incident. Repeated investigation can collide with the unique `(incident_id, version)` constraint because every proposal defaults to version 1. |
| Approval demo | `routes.py`, `schemas/api.py` | Approve/reject toggles status and writes an audit row. The caller supplies an arbitrary actor string. No immutable hash, expiry, target precondition, authorization, execution, or verification exists. |
| Operator UI | `apps/web/src/App.tsx` | Overview and incident list fetch API data. Investigations, approvals, cost, and audit routes are placeholders. The API client is a plain fetch wrapper, with no generated types. |
| Local stack | `compose.yaml`, `Makefile`, `infra/` | Compose defines API, web, PostgreSQL, Prometheus, Grafana. Prometheus scrapes only the FixProof API. No kind, sample app, or MCP service is defined. |
| Cost demo | `apps/api/app/services/costs.py` | Hard-coded 2026-09/10 records and an estimated savings value. This is unrelated to live incident investigation. |
| Tests and CI | `apps/api/tests`, `apps/web/src/App.test.tsx`, `.github/workflows/ci.yml` | Liveness and fixed cost assertions, a trivial web test, lint/build jobs. No lifecycle, database integration, Kubernetes, provider, safety, or verification tests. |

## Known scaffold blockers

- Compose maps `5173:80`, while `nginxinc/nginx-unprivileged` normally listens on port 8080 and the web Dockerfile exposes 8080. Confirm the image config and map the actual listener before treating the UI as reachable.
- Browser code calls `http://localhost:8000` from the web origin; the API has no CORS setup or same-origin reverse proxy. A browser workflow needs one of those paths.
- `make test` and `make lint` run against production API and web images. The API image installs no dev dependency group; the web image is only Nginx. CI invokes tools in separate jobs, but these Make targets are not a working local test harness.
- The seeded incident is deterministic, not a real alert. Incident evidence routes do not check that the incident exists. The advertised `make migrate` is redundant with the API container startup migration and is not a verified clean-machine flow.
- `.env.example` contains placeholder passwords and `LLM_*` keys that are not used by an inference provider. No provider credential should be inferred from those names.

## Gap to the first product milestone

Implement one kind sample app and fault, Prometheus sample metrics, Kubernetes evidence, one local MCP server, a Nebius Nemotron provider, structured evidence-linked investigation, an exact approval gate, a single allowed restore action, and fresh independent verification. The immediate next step is the scaffold repair in [the implementation plan](IMPLEMENTATION_PLAN.md). GitHub and cost work are deferred.

This is a source inspection, not a claim that the Compose stack or end-to-end flow ran successfully. `docker compose --env-file .env.example config --quiet` completed with a local Docker config warning. The working tree also contains an unrelated untracked `images/` directory; it was left untouched.
