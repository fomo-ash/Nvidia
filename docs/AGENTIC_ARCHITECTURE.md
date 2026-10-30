# Investigation and agent orchestration

## Durable product workflow

The API/PostgreSQL store owns incident identity, work requests, retained evidence, analysis results, proposals, approvals and action outcomes. The separate worker in `apps/api/app/worker.py` claims queued requests under a lease, serializes collection per incident, commits each source and rejects expired claim tokens. Read-only collection can retry up to three attempts as distinct retained runs; it cannot replay infrastructure writes.

MCP envelopes bind source, observation time, mode, identity and payload hash. API validation precedes redaction and persistence. Transport IDs/hashes are provenance; canonical API UUIDs are model citation authority. All telemetry remains untrusted as instructions. Missing sources retain explicit errors and empty data.

For the integrated reasoning step, `apps/ai/app/llm/retained.py` receives the retained context through `/analyze`. It bounds source names, UUID uniqueness, JSON size, freshness and model completion. The retained-analysis path permits two concurrent calls per process, one attempt without SDK retry, at most 45 seconds and at most 8,192 completion tokens. The API reader's deadline is longer. These limits are distinct from the legacy chat/graph client defaults.

The model returns structured hypotheses, supporting/contradicting UUIDs, uncertainty, gaps and `restore_known_good_template` or `none`. Unknown or inconsistent citations and extra operation fields fail validation. The API rechecks advice at ingestion and proposal/review boundaries; older records stay readable without gaining approval authority. Missing inputs and model failures preserve observations and require review.

The sample profile explains the actual endpoint contract and the advisory action's meaning. It does not provide runtime measurements or choose a baseline. Only the API resolves its independently registered healthy template and binds an exact proposal. Citation membership establishes a reference, not truth or causation.

## Legacy graph

The standalone AI `/investigate` path uses LangGraph and MemorySaver. It has fresh investigation IDs and read tools but in-memory checkpoints are lost on restart. It is separate from the durable API worker; it is not a second approval database. A graph resume, tool response or chat message does not authorize execution.

Dynamic retrieval and conversation state must not be described as durably integrated until their observations and citations are persisted against a selected API run. The implemented chat path is documented separately in [ChatOps](CHATOPS.md).

## Jev and Laya

`JevDecisionEngine` is an optional advisory component in the legacy graph, not a required step in the integrated worker's `/analyze` call.

| `SYSTEM1_PROVIDER` | Behavior |
|---|---|
| `policy` | Offline default; evaluates source sufficiency and risk through local policy. |
| `jev` | Attempts the configured Jev provider when a usable key exists; may use the compatible endpoint when enabled, then policy fallback. |
| `laya` | Uses the configured `/v1/systemone` endpoint, validates the response and falls back to policy on failure. |

Provider answers must contain all expected fields and valid probability/choice/risk values; missing or out-of-range answers reject the whole provider response rather than mixing invalid partial output with defaults. The legacy source gate requires live Prometheus and Deployment observations; sufficiency is not proof of a cause. Risk assessment always preserves human approval. External answers cannot replace required physical evidence or human approval. The Compose `laya` service implements a deterministic compatibility protocol; it does not run Laya model weights. Real model deployment requires a separately operated compatible endpoint. Model/provider options are described in the [AI service reference](../apps/ai/README.md).

## Remaining acceptance

Strict live investigation and one scoped restore have earlier local acceptance evidence. Chat grounding, persisted dynamic reads, current merged integration tests, complete independent recovery cycles and production deployment controls remain separate gates. See [demo acceptance](DEMO_RUNBOOK.md#acceptance-status).
