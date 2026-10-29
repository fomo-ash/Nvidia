# MCP and AI implementation status

The integrated product path now supports authenticated intake → durable source collection → structured, evidence-cited Nebius analysis. Proposal, approval, guarded execution and verification implementations are described in the [sequential recovery handoff](../SEQUENTIAL_RECOVERY_HANDOFF.md); one live guarded restore is accepted in the [approval/execution handoff](../APPROVAL_EXECUTION_HANDOFF.md), while measured live recovery remains a separate gate. The current local investigation trial uses no execution overlay. See [live acceptance](../LIVE_INVESTIGATION_HANDOFF.md), [authority contract](README.md) and [delivery plan](../IMPLEMENTATION_PLAN.md).

## Integrated path

- API sessions/CSRF protect reports, target history and evidence reads. Migration 0005 extends the durable request queue, normalized investigations and retained evidence while preserving prior records.
- A separate worker commits a lease before external reads, serializes work per incident, persists each source checkpoint, rejects stale tokens and bounds read-only retries. It verifies Deployment identity before retaining any other target-bound source. Completed jobs do not repeat. No inference call holds an incident lock.
- MCP has a namespace-scoped 24-hour read identity, verified Kubernetes CA, fixed target UID, owner-filtered pod/ReplicaSet/event/log reads, bounded responses and fixed metric/probe inputs. Its token cannot read other namespaces or patch the sample. The separate restore tool is opt-in and requires an execution capability and a restricted writer identity; the investigation path uses only reads.
- Authenticated service calls bind source/mode/time/hash/UID to each envelope. Redaction runs before API persistence; transport provenance and the retained redacted representation have separate hashes. Source errors remain explicit gaps with empty measurements.
- The API database owns canonical evidence UUIDs and all durable run state. Stateless AI `/analyze` receives bounded redacted retained context, validates structured output and citation membership, and returns provider/model metadata with uncertainty/gaps. It does not create recommendations or select exact mutation parameters.
- The incident UI polls queue progress, separates measurements from interpretation, renders source/analysis gaps and supports durable incident links/reload. Interrupted report retries retain the same idempotency key.
- Compose now scopes secrets explicitly: only AI receives inference keys; only API receives operator/session secrets; only MCP mounts scoped Kubernetes read credentials. API and AI health endpoints do not establish live source/model availability.

## Separate advisory scaffolds

The older LangGraph `/investigate` and conversational `/chat` paths remain internal scaffolds using MemorySaver, not the API's durable workflow. Their fresh run IDs prevent evidence mixing, but they are not a second source of approval or execution authority. Grounded ChatOps is explicitly deferred for this milestone. It still needs retained-record grounding, persisted dynamic reads, complete citation validation and conversation/tool budgets before exposure as an operator feature. See [investigation scope](../INVESTIGATION_QUALITY_HANDOFF.md).

Jev/Laya provider selection, answer validation, physical-evidence requirements and mandatory approval behavior are preserved. The bundled Laya container is a deterministic compatibility fixture, not a deployed Laya model. Optional System-1 advice never replaces the integrated worker's physical evidence/target policy.

## Verification and remaining gates

The [handoff](../LIVE_INVESTIGATION_HANDOFF.md) records SQLite/PostgreSQL, AI/MCP, UI/browser, real kind/Nebius, source-outage and restart results. These are local results; GitHub CI and peer review remain pending.

The investigation path enforces bounded inference, source/citation consistency and propagation of model gaps to manual review. Exact approval and guarded execution now have live local acceptance, including rejection, expiry, drift and replay denials. The next integrated gates are independent post-action measurements, complete UI acceptance and release rehearsal. Unknown-outcome reconciliation remains read-only and blocks further incident execution while unresolved. Infrastructure write permissions remain disabled. Production identity, service transport hardening, DB administrative permissions, retention and broader-host acceptance remain separate security/release work.
