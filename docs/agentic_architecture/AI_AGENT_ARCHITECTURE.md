# AI service architecture

Status: advisory scaffold under `apps/ai`, internal port 8001. See the [authority contract](README.md) and [implementation status](CURRENT_IMPLEMENTATION_STATUS.md). This document supersedes the earlier example code and unmeasured latency table.

## Framework responsibilities

LangGraph expresses the bounded investigation sequence. Chat uses a LangGraph prebuilt ReAct agent today; migrating to LangChain `create_agent` is separate compatibility work. LangChain agents themselves use LangGraph, so these are different interfaces for orchestration rather than mutually exclusive runtimes. Neither interface grants infrastructure authority.

The current graph performs collection, sufficiency checks, causal analysis, advisory risk scoring, and a final `needs_review` result with no remediation proposal. It uses `MemorySaver`, not PostgreSQL checkpointing, and does not implement an approval interrupt, streaming, a durable queue, or recovery verification. PostgreSQL checkpoint dependencies alone do not provide persistence.

## Fresh investigation and chat contracts

`POST /investigate` always starts a new run. It returns `investigation_id` (a server-generated UUID) alongside the incident ID. That UUID is the graph thread ID. Evidence and errors may accumulate across collection passes **within that run**, never across new investigations of the same incident. The collector retries missing sources once.

`POST /chat` requires `incident_id`, `investigation_id`, `message`, and optional `session_id`. The service checks the run belongs to the incident and returns 404 if missing or mismatched. Conversation history is separated by incident, run, and session. These checks prevent accidental cross-run mixing; they are not authenticated user authorization. Only API-authenticated callers may be connected in the future.

The MCP client tries SSE then private REST. It requires live evidence, the expected source, an aware observation timestamp no more than 120 seconds old or five seconds in the future, and a matching envelope hash. The hash binds ID, source, fact, raw payload, observation time, mode and trust marker. It is an integrity check, not a signature or proof of causality. Source measurement times and windows must also be checked; a recent collection timestamp alone is insufficient.

Chat's dynamic tools currently fetch observations that are not persisted and are not added to the final citation-validation set. Existing run evidence is not fully injected into the model context. Treat ChatOps as unfinished; before operator integration, persist each read through the API evidence bridge, pass the selected bounded evidence into the model, and reject unsupported factual claims. Run selection fixes do not complete chat grounding.

## System-1 advisory decisions

`JevDecisionEngine` evaluates evidence-source sufficiency and advisory remediation risk. Provider
selection is explicit: `policy` is the no-network default, `jev` selects TypeSafe Jev, and `laya`
selects a compatible `/v1/systemone` endpoint. See the
[System-1 decision engine](JEV_IMPLEMENTATION.md) for the complete contract.

The bundled Compose service named `laya` is a deterministic compatibility fixture, not a packaged
Laya model. Remote responses are accepted only when the complete typed answer set validates.
Malformed, partial, out-of-range, or unavailable responses fall back to deterministic policy.

The sufficiency gate still requires trusted live Prometheus and Kubernetes Deployment evidence.
Provider output cannot substitute for a missing physical source. The policy-only result describes
source availability and deliberately leaves outage status and severity unassessed. Risk output is
advisory and can never remove the human-approval requirement.

## Reasoning and deterministic policy

Nebius reasoning receives bounded fact text and evidence references. Live credentials/model failure never falls back to synthetic reasoning; explicit synthetic mode is for development only. The current parser checks citation membership but turns free text into one hypothesis with fixed confidence. It is not the final diagnosis schema and cannot produce an approvable proposal.

Before live proposal integration, require structured hypotheses with supporting/contradicting evidence IDs, gaps, uncertainty, and an allowed advisory action. Reject unknown citations, malformed schemas, unsupported actions, and injected instructions. Remove hardcoded confidence. The API supplies the exact target and trusted desired template; the model never supplies Kubernetes YAML or a new baseline.

Jev can advise sufficiency and risk; when absent/unavailable a local source-presence rule runs. This rule checks source availability, not proof of an active fault or causal sufficiency. Active-fault thresholds, evidence freshness, target validity, operator approval, and execution preconditions remain deterministic API/MCP policy.

## Durable integration design

Use an API-owned investigation/job UUID and immutable retained source records. Map transport IDs to canonical API evidence UUIDs before asking the model to cite the retained bundle. Persist provider/model/request metadata with validated findings. Do not hold an incident row lock while waiting for remote inference.

A future PostgreSQL checkpointer tracks orchestration progress only. Domain state and approval remain in the API transaction. A transactional job/outbox and idempotent result ingestion must bridge checkpoints and domain commits: retrying a completed result must not create another recommendation, and a checkpoint claiming completion must not substitute for a committed API result. Serialize or reject simultaneous invocations of one run.

If a graph waits for approval, only the API can notify it after a committed approval. Execution still independently validates the current proposal version/hash, exact target/baseline, expiry, and durable actor decision. Resume cannot invoke a mutation directly. Pending unknown outcomes require reconciliation, never blind replay.

Add explicit model/tool time budgets, concurrency limits, redaction, service authentication and checkpoint retention before exposing the service beyond the local scaffold. Test persistence/restart behavior independently of model fixtures. Live model availability and output shape require a credential-gated smoke test; they are not established by unit tests.
