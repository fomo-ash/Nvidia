# Documentation

## Start and operate

- [Development and setup](DEVELOPMENT.md): prerequisites, environment, startup, checks and contract generation.
- [Demo runbook](DEMO_RUNBOOK.md): synthetic mode, real investigation, guarded action and recovery acceptance.
- [kind fixture runbook](../infra/kind/README.md): owned cluster bootstrap, traffic, fault/reset and teardown.
- [Sample incident contract](INITIAL_INCIDENT.md): the deliberate fault and measurement thresholds.
- [Incident intake](INCIDENT_INTAKE.md): authenticated reports, trigger history and queued work.

## Architecture and contracts

- [Architecture](ARCHITECTURE.md): deployed components, state ownership and actual data flow.
- [Agent orchestration](AGENTIC_ARCHITECTURE.md): durable investigations, model validation, Jev/Laya and legacy graph boundaries.
- [API contracts](API_CONTRACTS.md): routes, identity, idempotency and generated schemas.
- [Database schema](DATABASE_SCHEMA.md): migrations, durable records, transactions and rollback limits.
- [MCP and Kubernetes](MCP_KUBERNETES.md): bounded reads, reader/writer scope, capabilities and reconciliation.
- [Security](SECURITY.md): authority, credentials and current limitations.

## Optional operator surfaces

- [ChatOps](CHATOPS.md): implemented UI/routes and unresolved grounding, citation and audit limitations.
- [Discord integration](DISCORD_INTEGRATION.md): delivery queue, signed read commands, setup and acceptance limits.

Public documentation describes current source separately from earlier local observations and remaining acceptance. Internal plans and historical drafts are retained locally outside the tracked reference set. Everything needed for setup and safe operation stays in these tracked documents; collaborators do not need a private plan to run the project.
