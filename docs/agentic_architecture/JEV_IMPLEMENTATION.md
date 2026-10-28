# System-1 decision engine

Status: advisory and read-only. The implementation is
[`JevDecisionEngine`](../../apps/ai/app/decisions/jev_engine.py).

## Purpose and authority

The engine performs two bounded assessments before or after heavier causal reasoning:

- whether the retained evidence contains enough source types to continue investigation; and
- an advisory risk classification for a proposed allowlisted remediation.

It does not authenticate an operator, approve a proposal, select a Kubernetes target, or authorize
execution. Regardless of a provider's answer, remediation continues to require explicit human
approval and independent API/MCP preconditions.

## Explicit provider behavior

`SYSTEM1_PROVIDER` accepts exactly `policy`, `jev`, or `laya`.

1. `policy` is the default. It makes no outbound System-1 request. Sufficiency requires trusted,
   live `prometheus` and `kubernetes:deployment` evidence. This proves source availability only; it
   does not assert an outage, severity, or root cause.
2. `jev` attempts the optional TypeSafe SDK and then the configured Jev HTTP endpoint when a
   non-mock key exists. If `LAYA_ENABLED=true`, a compatible endpoint may be tried next. Any failure
   falls back to deterministic policy.
3. `laya` calls `LAYA_BASE_URL/v1/systemone` directly and then falls back to policy.

The service under [`infra/laya`](../../infra/laya/) is a deterministic HTTP compatibility fixture.
It does not contain the Laya open-weights model. A separately operated Laya or compatible service
can replace it at the configured URL.

## Request and validation contract

One request fans out four sufficiency questions:

| Key | Type | Accepted result |
|---|---|---|
| `is_sufficient` | probability | `0.0` through `1.0` |
| `missing_source` | choice | `none`, `prometheus`, `kubernetes_deployment`, `kubernetes_logs`, or `direct_probe` |
| `is_active_outage` | probability | `0.0` through `1.0` |
| `severity` | score | `routine`, `degraded`, `severe`, or `critical` |

Risk assessment fans out `risk_tier`, `requires_human_approval`, and `is_reversible`. Probability
values must be bounded and the risk tier must be `low`, `medium`, `high`, or `critical`.

The response must contain every expected answer. Missing fields, unknown choices, non-numeric or
out-of-range probabilities, HTTP errors, and invalid JSON reject the entire provider response. The
engine then uses deterministic policy. It never partially combines an invalid remote response with
local defaults.

Even a valid provider response cannot bypass the physical evidence gate. The engine counts only
trusted live observations, and both Prometheus and Kubernetes Deployment evidence must be present.
SDK `score` values are normalized to the same shape used by the HTTP protocol before validation.

## Configuration

```env
# Offline and deterministic by default
SYSTEM1_PROVIDER=policy

# TypeSafe Jev
JEV_API_KEY=
TYPESAFE_BASE_URL=https://api.typesafe.ai

# Compatible HTTP endpoint
LAYA_ENABLED=false
LAYA_BASE_URL=http://laya:8000
LAYA_API_KEY=
```

`LAYA_ENABLED` applies only as an opt-in fallback after `SYSTEM1_PROVIDER=jev`. Selecting
`SYSTEM1_PROVIDER=laya` calls the configured compatible endpoint directly.

## Verification

Unit tests cover no-network policy behavior, explicit Jev and compatible-endpoint routing, physical
evidence gating, untrusted evidence, score normalization, malformed and out-of-range responses, and
the invariant that an advisory low-risk result cannot remove human approval.

```powershell
docker compose -f compose.checks.yaml run --build --rm ai-checks
docker compose build ai laya
docker compose up -d laya
Invoke-RestMethod http://localhost:8003/health
```
