# Demo runbook

## What works today

The scaffold can seed a demo incident and insert a fixed mock recommendation through `POST /api/v1/incidents/{id}/investigate`. Approval changes a database status and adds an audit row. `/evidence` and `/timeline` return fixed data; Cloud Cost Autopsy returns static figures. **There is no real detection, Kubernetes action, Nebius call, or recovery verification.** The web listener and browser API path need Phase 0 fixes, so this is not yet a clean-machine end-to-end demo.

To inspect the current API path, start Compose after copying `.env.example` to `.env`, run `docker compose run --rm api python -m app.seed`, and use `http://localhost:8000/docs`. This exercise demonstrates only API and persistence scaffolding. Do not describe the recommendation as evidence-backed or its approval as executable.

## MVP acceptance runbook to implement

The commands below are required deliverables, not commands that exist today. Document their exact names when Phase 1 lands. The [initial incident specification](INITIAL_INCIDENT.md) defines the measurable fault and recovery thresholds.

1. From a clean checkout, configure local passwords and `NEBIUS_API_KEY` plus a currently available Nemotron model ID. Start Compose and create the pinned kind cluster with the bootstrap command. Confirm the API, MCP, Kubernetes, Prometheus, and Nebius status indicators.
2. Deploy the known-good sample revision and generate baseline requests. Confirm `/healthz` succeeds and Prometheus has nonempty request and error series for the sample app.
3. Invoke the controlled fault command. Confirm the new Deployment revision is unhealthy, sample requests include 5xx, and Prometheus reports a raised error rate. Record fault time and bad template hash.
4. Open an incident and start investigation. Inspect stored pod status, events, bounded logs, rollout history, and metric snapshots with source times and IDs. Confirm the Nemotron response cites only those IDs and presents the one allowed restore action with target and preconditions.
5. Approve the exact proposal as the local operator. Execute once. Observe an audit record and a single MCP mutation attempt; retry the same idempotency key and confirm no second patch.
6. Wait for verification. Confirm the restored revision is available, a fresh `/healthz` request succeeds, and a post-action Prometheus window meets the configured threshold with sufficient traffic. The UI displays `verified` with readings and timestamps.
7. Repeat after reset. Also reject one proposal and show that execution is denied. Induce persistent errors or remove metrics and show `verification_failed` or `inconclusive`, never a fabricated success.

The acceptance record should include the exact commands, observed revisions, evidence IDs, provider/model, proposal hash, approval actor/time, execution ID, and verification readings. Redact credentials. See [roadmap](IMPLEMENTATION_PLAN.md) for phase gates.
