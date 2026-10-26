# Development

## Container workflow

Copy .env.example to .env once, then use `docker compose up --build --wait --wait-timeout 180`. Migrations run before API startup. Run `docker compose run --rm api python -m app.seed` for the sample incident. All published ports bind to loopback.

Runtime and development images are separate. Check containers need no .env, cloud keys, or running application stack:

```powershell
docker compose -f compose.checks.yaml run --build --rm api-checks
docker compose -f compose.checks.yaml run --build --rm api-postgres-checks
docker compose -f compose.checks.yaml run --build --rm web-checks
docker compose -f compose.checks.yaml run --build --rm api-checks ruff check app tests scripts alembic
docker compose -f compose.checks.yaml run --build --rm api-checks ruff format --check app tests scripts alembic
docker compose -f compose.checks.yaml run --build --rm web-checks pnpm lint
docker compose -f compose.checks.yaml run --build --rm web-checks pnpm typecheck
docker compose -f compose.checks.yaml run --build --rm api-checks python scripts/export_openapi.py --check
docker compose -f compose.checks.yaml run --build --rm web-checks pnpm contracts:check
```

The checks project has its own PostgreSQL container/network and never publishes a database port. Tests migrate its disposable fixproof_test database up/down. SQLite runs skip PostgreSQL-only concurrency tests. Stop checks with `docker compose -f compose.checks.yaml --profile checks down`; add `-v` only to discard this test project's disposable volumes. The profile flag ensures the profiled test database is included in cleanup.

Make aliases: `make up`, `make migrate`, `make seed`, `make test`, `make lint`, `make contracts`, `make down`. Make is optional on Windows.

## Host development

Use Python 3.12+ (CI/runtime use 3.13), Node 22.12+ (container/CI use 22.19), and pnpm 10.15.1. Install the project in a virtual environment with `python -m pip install -e "apps/api[dev]"`. From the repository root run `pnpm install --frozen-lockfile`.

Set DATABASE_URL deliberately for host execution: Compose's hostname db resolves only inside its network. Without an environment file, the API defaults to a persistent local SQLite file. From apps/api run `alembic upgrade head`, `python -m app.seed`, and `uvicorn app.main:app --reload`. Set LLM_PROVIDER=mock. No cloud credentials are needed.

Frontend commands from the root: `pnpm --filter @fixproof/web dev`, `pnpm lint`, `pnpm typecheck`, `pnpm test`, `pnpm build`.

After API contract changes, run `python apps/api/scripts/export_openapi.py`, then `pnpm contracts:generate`. Commit both generated artifacts. CI detects drift.

## Verification boundaries

SQLite checks API behavior, source arithmetic/persistence, migration/backfill compatibility, role boundaries, audit immutability, lifecycle/idempotency rules, and provider validation. PostgreSQL adds production-dialect migrations, audit TRUNCATE protection, concurrent idempotent creates, competing execution requests, and duplicate requests during a pending action. Component tests exercise loading, rendering, failure/retry, and client errors/cancellation. The stack smoke test uses HTTP across the built runtime services, checks SPA deep links, creates a persisted sample cost report and records an explicit unavailable action attempt. It performs no infrastructure mutation.

Root scripts use ruff.toml; the standalone API build uses the aligned settings in apps/api/pyproject.toml. Check both with `ruff check apps/api scripts` and `ruff format --check apps/api scripts` from the repository root. Build from a feature branch and use a pull request into main. Phase 2 was marked DONE after the project owner confirmed CI and review; see PHASE_2_HANDOFF.md for the recorded local acceptance and its limits.

These do not prove real workload recovery, external AI quality, AWS cost ingestion, authentication, or isolated remediation. Those belong to the next implementation phases.

## Next developer loop

Use the [implementation plan](IMPLEMENTATION_PLAN.md) in order. The [kind fixture runbook](KIND_FIXTURE.md) has the Phase 0/1 commands, acceptance thresholds, baseline behavior, Groq configuration, and current verification limits. After its exit gate passes, extend the domain records for manual intake and real MCP evidence; keep synthetic rows visibly distinct. Groq is the temporary live model provider; Nebius can be selected later with its own key. Do not commit credentials. The final local loop is fault -> report -> evidence -> cited proposal -> approval -> one scoped action -> measured verification.
