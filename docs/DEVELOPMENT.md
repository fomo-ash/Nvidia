# Development

## Current scaffold

From the repository root, copy `.env.example` to `.env` and replace the local placeholder passwords. Docker Compose is the current packaging path:

```powershell
docker compose --env-file .env config
docker compose up --build -d
docker compose run --rm api python -m app.seed
```

The API container runs `alembic upgrade head` on startup. `make migrate` is available for an explicit migration run; `make seed` inserts a demo incident if the table is empty. `make down` keeps the database volume, while `make reset-data` removes it. These commands describe the scaffold, not the final kind workflow. The advertised web URL may fail until Phase 0 fixes the Nginx port mapping; cross-origin browser API calls also need a proxy or CORS fix. Do not report a clean quick start until those checks pass.

Current API docs: `http://localhost:8000/docs`; liveness: `/health/live`; readiness: `/health/ready`; metrics: `/metrics`. The seeded incident, mock recommendation, fixed evidence, and cost summary are demo data. The `LLM_*` entries in `.env.example` do not activate an inference provider.

`make test` and `make lint` currently target production containers that lack test tooling. CI installs Python dev tools and pnpm separately, but the local Make targets need repair. For a local source check with dependencies already installed, run `python -m pytest` from `apps/api` and `pnpm lint`, `pnpm typecheck`, `pnpm test --run`, and `pnpm build` from `apps/web`. Treat these as component checks only; they do not test a real incident.

## Target MVP developer loop

Phase 1 adds a pinned kind cluster bootstrap, sample app, Prometheus scrape, fault injection, and reset command. Phase 2 adds authenticated manual incident intake. Phase 3 adds a scoped Kubernetes credential for one MCP service and a connectivity check from inside Compose. Phase 4 adds `NEBIUS_API_KEY` and a configured Nemotron model ID; do not commit the key. The final runbook will lead through fault → evidence → model proposal → approval → one bounded action → measured verification. See [implementation plan](IMPLEMENTATION_PLAN.md) and [demo runbook](DEMO_RUNBOOK.md).
