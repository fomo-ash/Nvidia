# FixProof

FixProof is a local-first, self-hosted AI DevOps investigation and remediation assistant for solo developers and small teams. The intended MVP observes a sample application in a local kind cluster, investigates an incident with NVIDIA Nemotron through Nebius Token Factory, proposes a bounded fix, requires explicit operator approval, executes through one controlled FixProof MCP server, and verifies recovery from fresh health and metric readings. The frontend, backend, integrations, and incident history run on the user's machine. AI inference needs an HTTPS connection to Nebius.

**Repository status (2026-10-24): scaffold, not an end-to-end MVP.** FastAPI, React, PostgreSQL, Compose, Prometheus, Grafana, a seeded incident, a hard-coded mock recommendation, basic approval/rejection, audit rows, and synthetic cost data exist. There is no kind cluster, sample workload, Kubernetes or Prometheus evidence collector, MCP server, Nebius provider, guarded executor, or recovery verification. Approval currently changes only a recommendation status; it does not authorize a real action safely. The current dashboard is a demo scaffold.

## Start with the existing scaffold

Copy `.env.example` to `.env`, change the local passwords, then run `docker compose up --build` and `docker compose run --rm api python -m app.seed`. The API is intended at `http://localhost:8000` and the web UI at `http://localhost:5173`. **The web port mapping and browser cross-origin API access need fixes before this is a reliable quick start.** See [development notes](docs/DEVELOPMENT.md) for current limitations; do not use this stack against live infrastructure.

## Project documents

- [Current implementation and gaps](docs/INITIAL_ASSESSMENT.md)
- [Target architecture and trust boundaries](docs/ARCHITECTURE.md)
- [Ordered, testable implementation roadmap](docs/IMPLEMENTATION_PLAN.md)
- [Initial incident scenario](docs/INITIAL_INCIDENT.md)
- [Detailed incident detection and intake contract](docs/INCIDENT_INTAKE.md)
- [API contracts](docs/API_CONTRACTS.md), [data model](docs/DATABASE_SCHEMA.md), and [security policy](docs/SECURITY.md)
- [Local development](docs/DEVELOPMENT.md), [Compose](docs/DOCKER.md), and [demo runbook](docs/DEMO_RUNBOOK.md)

The existing Cloud Cost Autopsy code is a synthetic demo feature. It is outside the first verified-remediation milestone and stays clearly labeled until separately prioritized.
