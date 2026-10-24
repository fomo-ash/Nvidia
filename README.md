# FixProof

FixProof is a local-first, self-hosted AI DevOps investigation and remediation assistant for solo developers and small teams. Its intended MVP accepts an incident in a local kind cluster, collects Prometheus and Kubernetes evidence through one controlled MCP server, investigates with NVIDIA Nemotron through Nebius Token Factory, requires exact human approval for a bounded fix, and independently verifies recovery. The UI, API, integrations, and incident history run locally; live AI inference needs internet access to Nebius. Verified remediation is the product goal.

The current foundation runs locally with synthetic evidence and billing data, so it needs no AWS credentials or external model key. Phase 2 **implemented** normalized investigations/evidence, exact-hash approvals, idempotent execution/verification records, persisted billing reports/sources, and audit history. The operations adapter is intentionally unconfigured: an execution attempt records an explicit unavailable failure and never mutates infrastructure. There is no kind sample workload, MCP server, Nebius provider, or real recovery verification yet. The existing Cloud Cost Autopsy is a separate synthetic feature outside the first verified-remediation milestone.

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
- [Implementation plan](docs/IMPLEMENTATION_PLAN.md): ordered work packages and exit gates for the real incident MVP.
- [Initial incident](docs/INITIAL_INCIDENT.md) and [incident intake](docs/INCIDENT_INTAKE.md): first fault and reporting contract.
- [Phase 2 handoff](docs/PHASE_2_HANDOFF.md): backend acceptance evidence, safety boundaries and review gates.
- [Architecture](docs/ARCHITECTURE.md), [API contracts](docs/API_CONTRACTS.md), [Security](docs/SECURITY.md), and [Demo runbook](docs/DEMO_RUNBOOK.md).

The next product milestone is a reproducible kind workload fault, followed by manual intake, real evidence, live Nemotron investigation, a scoped restore action, and measured verification. Optional GitHub context and broader cloud integrations follow that workflow.
