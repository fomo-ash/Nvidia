# AI service

The internal AI service exposes strict retained-evidence analysis plus separate legacy graph and conversational paths. It has no approval authority or Kubernetes writer/signing credentials.

| Endpoint | Role |
|---|---|
| `/analyze` | Stateless structured reasoning over API-retained observations. The durable API worker owns run state. |
| `/investigate` | Standalone LangGraph investigation with in-memory checkpoints. |
| `/chat` | Conversational interface used by public API chat routes; current grounding/citation/fallback limitations are documented separately. |

The `/analyze` path validates source/UUID/time/size, bounds inference, checks hypothesis citation membership and returns uncertainty/gaps with one advisory enum. A missing or invalid answer cannot authorize a proposal. Public API independently constructs and reviews exact changes.

`AI_LLM_PROVIDER` in Compose selects the service's `LLM_PROVIDER`. Nebius uses `NEBIUS_API_KEY`, `NEBIUS_BASE_URL` and `NEBIUS_MODEL`; Groq has separate key/base/model variables. Retained analysis has a maximum 45-second single attempt and 8,192 completion tokens, with two concurrent calls per process. Chat/legacy client settings differ.

## Optional System-1 advice

`SYSTEM1_PROVIDER=policy` is the offline default. `jev` uses the configured provider, optionally tries the compatible endpoint when `LAYA_ENABLED` is true, then policy fallback. `laya` selects `LAYA_BASE_URL/v1/systemone` directly with validated fallback. The bundled Compose Laya service is deterministic compatibility code, not deployed model weights.

Jev/Laya answers remain advisory, require the physical source gate and cannot remove human approval. This engine belongs to the legacy graph; it is not a mandatory stage of the durable worker's `/analyze` call.

## Development

Use this service's own environment because the Python package name `app` is shared with API/MCP:

```sh
uv sync --frozen --extra dev
uv run --frozen --extra dev pytest -q
uv run --frozen --extra dev ruff check app tests
uv run --frozen --extra dev ruff format --check app tests
```

The service's uv lock is consumed by CI and Docker. [Agent orchestration](../../docs/AGENTIC_ARCHITECTURE.md), [ChatOps limitations](../../docs/CHATOPS.md) and [setup/checks](../../docs/DEVELOPMENT.md) are the maintained references. A healthy process does not prove working provider credentials or live model quality.
