# Architecture

FixProof is a local control plane above an owned Kubernetes sample and existing telemetry. It does not replace Kubernetes or Prometheus and does not provide general cloud administration.

## Components and state

| Component | Responsibility |
|---|---|
| `apps/web` | Operator session, reporting, source observations, proposal review, action/verification records and experimental chat. |
| `apps/api` | Authoritative incident lifecycle, baseline registration, proposals, approvals, execution claims, verification records, audit and optional Discord interactions. |
| PostgreSQL | Durable incidents, triggers, requests, evidence, findings, decisions, idempotency, audit and delivery queue. SQLite supports local tests. |
| API-package investigation worker | Leased collection jobs, per-source persistence and stateless AI analysis of retained observations. Enabled by the kind overlay. |
| `apps/mcp` | Fixed-target Kubernetes/Prometheus reads, optional capability-gated restore and independent verification. |
| `apps/ai` | Strict `/analyze`, optional System-1 advice in the legacy graph, and experimental conversational chat. |
| kind + `apps/sample` | One registered Deployment, a traffic generator and an intentionally reproducible configuration fault. |
| Prometheus / Grafana | Sample/API scraping and an API-process dashboard. Dashboard availability is not recovery evidence. |
| Discord worker | Optional committed-event delivery. It cannot change incident or approval state. |

## Actual investigation and recovery path

1. A signed operator reports the configured target UID. Intake records a manual trigger, reuses the matching open case when appropriate and queues a request. A report starts `unassessed`.
2. The worker commits a lease, validates target identity and collects five bounded MCP sources. Source snapshots and errors are retained separately. Invalid sources never become synthetic readings.
3. Metrics support an `active`, `not_confirmed` or `inconclusive` assessment. The AI service receives bounded retained context and returns strict hypotheses, uncertainty, gaps and an advisory action. Source/model gaps produce `needs_review`.
4. The API independently registers the healthy baseline and constructs an exact proposal from an eligible investigation. Model output cannot select a template, target, approval or execution capability.
5. Operator approval binds the reviewed hash/version/expiry and rechecks live state. The optional execution adapter commits a pending claim before requesting one MCP patch with a short-lived signed capability.
6. MCP validates scope and performs atomic UID/resource-version/template tests. Unknown outcomes stay pending; read-only reconciliation can confirm the exact execution marker and healthy template. Further incident execution is blocked while unresolved.
7. Verification is a separate API/MCP action. Fresh rollout, health probes and a complete traffic window produce `passed`, `failed` or `inconclusive`. Patch success never sets a recovery verdict, and there is no implemented automatic incident closure.

See [agent orchestration](AGENTIC_ARCHITECTURE.md), [MCP](MCP_KUBERNETES.md) and [API contracts](API_CONTRACTS.md) for detailed boundaries.

## Chat and Discord paths

Chat is implemented in the UI and public API, forwarding to AI `/chat`. Its current grounding and citation behavior is weaker than strict investigation analysis; it is not a source of action authority. [ChatOps limitations](CHATOPS.md) are part of the current implementation contract.

Discord receives selected committed live audit transitions through `discord_deliveries`. Signed guild/role-scoped interactions read stored status. Commands cannot approve, execute, collect new evidence or run an AI investigation. [Discord setup](DISCORD_INTEGRATION.md) requires optional external credentials and HTTPS routing for interactions.

## Deployment modes

The base Compose stack has no investigation worker or kind connectivity. The kind overlay adds the worker, scoped reader credentials and a private Docker network to the sample. The execution overlay additionally supplies signing configuration and mounts a separate writer token only into MCP. Writes remain disabled by default. Synthetic API/cost compatibility is separately enabled through local demo mode.

AI and MCP health endpoints prove process availability, not working model credentials, target registration or live telemetry. Environment configuration is not an integration acceptance result. Historical live acceptance and outstanding release checks are summarized in the [demo runbook](DEMO_RUNBOOK.md).
