# FixProof delivery plan

## Release target

Deliver one reproducible local kind incident. A deliberate configuration change in a new Deployment revision makes the sample application unhealthy. FixProof accepts a report, collects real Prometheus and Kubernetes evidence through one MCP server, obtains an evidence-cited NVIDIA Nemotron investigation from Nebius Token Factory, proposes restoration of the captured known-good pod template, requires exact human approval, performs one guarded Kubernetes action, and verifies recovery with fresh rollout, health, and metric readings. The frontend, backend, tools, and history run locally; AI inference needs HTTPS access to Nebius.

The current repository is a scaffold with fixed mock recommendations, basic approval status changes, and synthetic cost data. It is not the release workflow. [Current assessment](docs/INITIAL_ASSESSMENT.md) identifies the gaps.

## Execution order

| Phase | Deliverable that must work before proceeding |
|---|---|
| 0. Repair scaffold | Browser/API connectivity, Compose ports, migrations, and local test commands work. |
| 1. Observable kind fault | Sample app is healthy, deliberately faulty, then healthy again; Prometheus sees traffic and 5xx. |
| 2. Incident intake | Authenticated operator report creates one durable incident/trigger and queues investigation. |
| 3. MCP evidence | Restricted tools retain real Kubernetes and Prometheus snapshots with provenance. |
| 4. Nemotron investigation | Live Nebius response is validated and every finding cites stored evidence. |
| 5. Exact approval | Immutable proposal is explicitly approved by the operator; mutation remains disabled. |
| 6. Guarded execution | One approved restore action patches only the sample Deployment once. |
| 7. Recovery verification | Fresh rollout, `/healthz`, and a measured metric window determine the verdict. |
| 8. Release rehearsal | Clean-machine runbook passes positive, rejected, and failed/inconclusive cases. |

The [implementation plan](docs/IMPLEMENTATION_PLAN.md) gives the tasks, dependencies, tests, and exit gate for every phase. Work in this order for a solo developer; parallel contributors meet at the contract checkpoints documented there. No phase is complete because a UI badge or model answer claims success.

## Start here

Phase 0 is next: correct the Nginx port mapping and browser API path, make local test/lint commands runnable, verify migrations/seed on a fresh database, and keep mock content visibly labeled. Then build the kind fixture before designing the final evidence and action adapters around it.

## Supporting contracts

- [Initial incident](docs/INITIAL_INCIDENT.md) defines the deliberate fault, evidence, action, and recovery threshold.
- [Incident intake](docs/INCIDENT_INTAKE.md) defines manual reporting and later optional Prometheus detection.
- [Architecture](docs/ARCHITECTURE.md), [API](docs/API_CONTRACTS.md), [database](docs/DATABASE_SCHEMA.md), and [security](docs/SECURITY.md) define the boundaries.
- [Demo runbook](docs/DEMO_RUNBOOK.md) defines what the final release must prove.

Optional GitHub context, automatic alert intake, and the existing synthetic Cloud Cost Autopsy remain after this first release.
