# FixProof

FixProof is a local-first DevOps assistant for investigating failures, reviewing an exact fix and checking its outcome. It connects Kubernetes and Prometheus evidence with NVIDIA Nemotron through Nebius Token Factory, while the API retains incident history and controls approval and execution.

The demo problem is concrete: a configuration change makes a Kubernetes sample return HTTP 500 even though its readiness endpoint stays ready. FixProof collects observations, explains likely causes and can prepare restoration of the independently registered healthy template.

## Implementation status

| Capability | Current status |
|---|---|
| Incident investigation | Authenticated intake, durable collection jobs, five bounded evidence sources, retained findings and strict analysis citations are implemented; earlier local investigation/restart acceptance is recorded. |
| Exact proposal and restore | Version/hash/expiry review, human approval, scoped capabilities, atomic Kubernetes preconditions and replay protection are implemented. One controlled live restore passed earlier local acceptance. Writes are disabled by default. |
| Independent verification | Rollout checks, three health probes and a fresh traffic window are implemented. Two complete verified recovery cycles and final release acceptance remain open. Patch success alone is not recovery. |
| ChatOps | Chat page, incident drawer and API/AI routes exist. Run selection, live prompt grounding, UUID citation validation and durable chat/tool history have important limitations. See [ChatOps](docs/CHATOPS.md). |
| Discord | Optional audit-event delivery and signed read-only commands are implemented. Prior webhook delivery was reported; live slash-command acceptance remains pending. |
| Cloud costs | Persisted, explicitly synthetic cost reports exist. Real billing ingestion and cloud optimization execution are planned. |

Historical acceptance does not certify every later merge. AWS/Terraform/GitHub/Slack integration, arbitrary infrastructure actions and isolated fix-testing environments are outside the demonstrated workflow.

## Local workload and telemetry

The owned kind fixture runs `sample-api` and a steady traffic generator in `fixproof-demo`. `FAIL_MODE=on` makes `/api/work` and `/healthz` fail while `/readyz` stays HTTP 200. Prometheus measures real work-request counters. MCP retains metrics, Deployment/pod state, events, bounded logs and direct probes; missing sources remain explicit gaps.

```mermaid
flowchart LR
    Web[React operator console] --> API[FastAPI control plane]
    API <--> DB[(PostgreSQL: incidents, evidence, approvals, audit)]
    Worker[Durable investigation worker] <--> DB
    Worker -->|bounded reads| MCP[MCP service]
    MCP --> Kind[Owned kind sample]
    MCP --> Prom[Prometheus]
    Prom -->|scrape| Kind
    Worker -->|retained evidence /analyze| AI[AI service]
    AI --> Nebius[Nebius Token Factory / Nemotron]
    API -->|opt-in signed action and separate verification| MCP
    API -->|experimental chat| AI
    AI -->|chat read tools| MCP
    Discord[Discord signed read commands] --> API
    DB --> Delivery[Discord outbox worker]
    Delivery -->|optional webhook| Discord
```

The API and PostgreSQL own durable state. The separate legacy LangGraph/MemorySaver path is not an approval authority. [Architecture](docs/ARCHITECTURE.md) and [agent orchestration](docs/AGENTIC_ARCHITECTURE.md) explain these boundaries.

## Stack

React, TypeScript and Vite; Python/FastAPI; SQLAlchemy/Alembic with PostgreSQL; LangChain/LangGraph and OpenAI-compatible inference; MCP, Kubernetes/kind, Prometheus and Grafana; Docker Compose, pytest, Vitest and Playwright. The bundled Laya service is a deterministic protocol fixture, not a deployed Laya model.

## Quick start

Prerequisites: Docker with Compose, Python 3.12+, kind and internet access for image/tool downloads and live Nebius inference. Node 22.12+ and pnpm 10.15.1 are needed only for host frontend development. No local GPU is required by the default remote-inference path.

From the repository root, create `.env` only if it does not already exist, then follow [environment setup](docs/DEVELOPMENT.md#environment-and-startup) before starting the stack:

```sh
cp -n .env.example .env
python3.12 scripts/kind_fixture.py up
python3.12 scripts/configure_investigation.py
# Configure live inference and local database/Grafana credentials in ignored .env.
docker compose -f compose.yaml -f compose.kind.yaml up --build --wait --wait-timeout 180
```

PowerShell uses `Copy-Item .env.example .env` only for a new configuration. Preserve existing credentials and database volumes.

Required environment names: `POSTGRES_PASSWORD`, `DATABASE_URL`, `GRAFANA_ADMIN_PASSWORD`, `NEBIUS_API_KEY`, `AI_LLM_PROVIDER`, `ANALYSIS_ENABLED`, `LOCAL_DEMO_ENABLED`. Reader setup provisions `OPERATOR_SECRET`, `SESSION_SIGNING_KEY`, `SERVICE_AUTH_TOKEN` and `SAMPLE_TARGET_UID`. Model selection uses `NEBIUS_MODEL` and `NEBIUS_BASE_URL`. Values and optional integrations are covered in setup; never publish real keys.

Open the console at http://localhost:5173, sign in and report the registered target. API docs are at http://localhost:8000/docs; Prometheus is at http://localhost:9090 and Grafana defaults to http://localhost:3000 (`GRAFANA_PORT` can change it). AI, MCP, PostgreSQL and delivery workers are internal services. Grafana's provisioned dashboard monitors the API process, not a recovery verdict.

## Testing and demo

```sh
docker compose -f compose.checks.yaml run --build --rm api-checks
docker compose -f compose.checks.yaml run --build --rm api-postgres-checks
docker compose -f compose.checks.yaml run --build --rm web-checks
```

These are test commands, not a claim that the current revision passed them. See [development checks](docs/DEVELOPMENT.md#checks-and-contracts) for AI/MCP, formatting, generated contracts and browser tests.

The [demo runbook](docs/DEMO_RUNBOOK.md) separates synthetic smoke, live investigation, approved restoration and independent recovery acceptance. It includes scripts that deliberately fault the owned sample. Keep writes disabled unless performing a reviewed, scoped trial.

[Documentation index](docs/README.md) · [Security](docs/SECURITY.md) · [Discord](docs/DISCORD_INTEGRATION.md) · [kind runbook](infra/kind/README.md)
