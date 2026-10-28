# FixProof delivery plan

## Release target

Deliver one reproducible local kind incident. A deliberate configuration change in a new Deployment revision makes the sample application unhealthy. FixProof accepts a report, collects real Prometheus and Kubernetes evidence through one MCP server, obtains an evidence-cited NVIDIA Nemotron investigation from Nebius Token Factory, proposes restoration of the captured known-good pod template, requires exact human approval, performs one guarded Kubernetes action, and verifies recovery with fresh rollout, health, and metric readings. The frontend, backend, tools, and history run locally; AI inference needs HTTPS access to Nebius.

The current repository already has a hardened local scaffold and Phase 2 lifecycle APIs: normalized synthetic investigations/evidence, exact-hash approvals, idempotent execution/verification records, audit guards, generated API types, and persisted synthetic cost reports. Its operations adapter is unavailable by design, so it performs no infrastructure mutation. It is not the release workflow. [Current assessment](docs/INITIAL_ASSESSMENT.md) identifies the remaining gaps.

Groq is the temporary selectable live model provider during local development. The final Nebius/Nemotron gate remains open. The [kind fixture runbook](infra/kind/README.md) and [acceptance handoff](docs/KIND_FIXTURE_HANDOFF.md) record the Phase 0/1 checks completed on the fixture branch. This Windows workspace still needs its own full rebuild after Docker registry DNS is restored.

## Execution order

| Phase | Deliverable that must work before proceeding |
|---|---|
| 0. Confirm foundation | Browser/API connectivity, Compose ports, migrations, and checks are implemented; close the documented full-stack Grafana verification gap. |
| 1. Observable kind fault | Sample app is healthy, deliberately faulty, then healthy again; Prometheus sees traffic and 5xx. |
| 2. Incident intake | Authenticated operator report creates one durable incident/trigger and queues investigation. |
| 3. MCP evidence | Restricted tools retain real Kubernetes and Prometheus snapshots with provenance. |
| 4. Nemotron investigation | Live Nebius response is validated and every finding cites stored evidence. |
| 5. Exact approval | Immutable proposal is explicitly approved by the operator; mutation remains disabled. |
| 6. Guarded execution | One approved restore action patches only the sample Deployment once. |
| 7. Recovery verification | Fresh rollout, `/healthz`, and a measured metric window determine the verdict. |
| 8. Release rehearsal | Clean-machine runbook passes positive, rejected, and failed/inconclusive cases. |

The [implementation plan](docs/IMPLEMENTATION_PLAN.md) gives the tasks, dependencies, tests, and exit gate for every phase. Work in this order for a solo developer; parallel contributors meet at the contract checkpoints documented there. No phase is complete because a UI badge or model answer claims success.

[NEXT.md](NEXT.md) tracks the remaining acceptance work, UI details, and later phases from the current feature branch.

## Start here

The foundation fixes and historical Phase 2 domain work are already implemented. Full-stack/Grafana smoke and container regression checks passed on the fixture branch before it merged into `main`. The [observable kind fixture](infra/kind/README.md) passed two live healthy/fault/reset cycles on the recorded host; see the [handoff](docs/KIND_FIXTURE_HANDOFF.md). Authenticated incident intake is the next product integration step.

The new manual intake implementation and its setup, contract, checks and remaining live gates are recorded in [Phase 2 intake handoff](docs/PHASE_2_INTAKE_HANDOFF.md). It queues work for the Phase 3 collector; no live evidence collection is implied.

## Supporting contracts

- [Initial incident](docs/INITIAL_INCIDENT.md) defines the deliberate fault, evidence, action, and recovery threshold.
- [Incident intake](docs/INCIDENT_INTAKE.md) defines manual reporting and later optional Prometheus detection.
- [Architecture](docs/ARCHITECTURE.md), [API](docs/API_CONTRACTS.md), [database](docs/DATABASE_SCHEMA.md), and [security](docs/SECURITY.md) define the boundaries.
- [Demo runbook](docs/DEMO_RUNBOOK.md) defines what the final release must prove.

Optional GitHub context, automatic alert intake, and real cost ingestion remain after this first release. The current synthetic Cloud Cost Autopsy remains clearly labeled.
