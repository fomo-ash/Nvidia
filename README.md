# FixProof

FixProof is an AI-assisted DevOps and Cloud Operations Assistant for small teams. The intended workflow connects incident evidence, likely causes, a bounded proposed fix, testing where practical, human approval, controlled execution, and independently measured recovery. Cloud Cost Autopsy explains spending changes from billing records and labels potential savings as estimates.

The current foundation runs locally with synthetic evidence and billing data. It requires no AWS credentials or external model key. Phase 2 adds normalized investigations/evidence, durable approvals, idempotent execution/verification records, persisted billing reports/sources, and audit history. The operations adapter is intentionally unconfigured: an execution attempt records an explicit unavailable failure and never mutates infrastructure. Actual workload actions and recovery measurement remain later-phase work.

## Run locally

Prerequisite: Docker with Compose v2+ (Docker Desktop on Windows).

From the repository root, in PowerShell:

```powershell
Copy-Item .env.example .env
docker compose up --build --wait --wait-timeout 180
docker compose run --rm api python -m app.seed
```

Use the copy command only when creating your local configuration; preserve an existing `.env`. Sample passwords are for this loopback-only demo. Migrations run automatically before the API starts.

| Service | URL |
|---|---|
| Operator UI | http://localhost:5173 |
| API documentation | http://localhost:8000/docs |
| API readiness | http://localhost:8000/health/ready |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 |

Grafana credentials come from `.env`. Its provisioned FixProof dashboard monitors the API process, not a Kubernetes workload.

```powershell
python scripts/smoke.py
docker compose down
```

The smoke test needs only a host Python 3 interpreter and creates a synthetic incident. Stopping the stack preserves PostgreSQL data.

## Verify the foundation

These checks use development images and a separate test database; no host Python or Node installation is needed:

```powershell
docker compose -f compose.checks.yaml run --build --rm api-checks
docker compose -f compose.checks.yaml run --build --rm api-postgres-checks
docker compose -f compose.checks.yaml run --build --rm web-checks
```

If Make is installed, `make test`, `make lint`, and `make contracts` run the corresponding checks. See [Development](docs/DEVELOPMENT.md) for direct lint/type/contract commands.

## Project map

- `apps/api`: FastAPI routes, typed contracts, domain services, SQLAlchemy models, Alembic migrations, and tests.
- `apps/web`: React operator console, generated API types, and component/client tests.
- `infra`: Prometheus and provisioned Grafana configuration.
- `scripts/smoke.py`: HTTP smoke check of the running stack.
- [Implementation plan](docs/IMPLEMENTATION_PLAN.md): phase status and foundation work.
- [Phase 2 handoff](docs/PHASE_2_HANDOFF.md): backend acceptance evidence, safety boundaries and review gates.
- [Architecture](docs/ARCHITECTURE.md), [API contracts](docs/API_CONTRACTS.md), [Security](docs/SECURITY.md), and [Demo runbook](docs/DEMO_RUNBOOK.md).

The next product milestone is a reproducible monitored workload, followed by grounded investigation, isolated fix testing, controlled execution, and independent verification. AWS, Terraform, Kubernetes, external AI, and messaging integrations remain planned adapters.
