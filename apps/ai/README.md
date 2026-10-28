# FixProof AI Service (`apps/ai`)

Advisory investigation and reasoning service powering FixProof incident diagnosis.

## Decision Engine (`app/decisions/jev_engine.py`)

The AI service utilizes a fast System-1 decision engine (`JevDecisionEngine`) to evaluate investigation telemetry sufficiency and remediation risk before calling heavier System-2 LLM inference (NVIDIA Nemotron via Nebius).

### 3-Tier Fallback Hierarchy

1. **TypeSafe Jev (Cloud System-1)**:
   - Primary decision engine using TypeSafe AI's fast calibrated models.
   - Invoked via `typesafe-sdk` or direct HTTP POST to `https://api.typesafe.ai/v1/systemone` when `JEV_API_KEY` (or `TYPESAFE_API_KEY`) is provided.
2. **Laya (Open-Source System-1 Fallback)**:
   - When the Jev key is mock, missing, or unreachable, the engine falls back to [Laya](https://laya-ai.com) running locally or in a private cluster.
   - Enabled via `LAYA_ENABLED=true` and `LAYA_BASE_URL` (default: `http://localhost:8000`).
   - Targets the exact same `/v1/systemone` API contract with identical question and answer schemas.
3. **Deterministic SRE Policy (Local / Offline)**:
   - If both Jev and Laya are unavailable or disabled, the engine falls back to a deterministic SRE policy checking for core telemetry presence (`prometheus` metrics and `kubernetes:deployment` spec).

---

## TypeSafe Architectural Patterns

### 1. Speculative Fan-Out Pattern
Instead of asking atomic decision questions sequentially, the engine fans out multiple orthogonal questions concurrently in a single `/v1/systemone` payload:

#### Sufficiency Evaluation Fan-Out:
- `is_sufficient` (`noul`): Probability ($0.0 \dots 1.0$) that current telemetry is sufficient to isolate the root cause.
- `missing_source` (`choice`): Telemetry source most urgently needed (`none`, `prometheus`, `kubernetes_deployment`, `kubernetes_logs`, `direct_probe`).
- `is_active_outage` (`noul`): Probability that customer-facing traffic is actively failing.
- `severity` (`score`): Severity classification (`routine`, `degraded`, `severe`, `critical`).

#### Risk Scoring Fan-Out:
- `risk_tier` (`choice`): Risk level of proposed remediation (`low`, `medium`, `high`, `critical`).
- `requires_human_approval` (`noul`): Whether human operator confirmation is required.
- `is_reversible` (`noul`): Probability of safe rollback / reversibility.

### 2. Confidence-Gated Routing Pattern
Fast decisions are gated before proceeding:
- Evaluations with high confidence ($\ge 0.70$) and confirmed physical presence of vital telemetry proceed to hypothesis generation.
- Low-confidence or ambiguous evaluations halt automatic progression and trigger missing source collection or operator escalation.

---

## Configuration (`.env`)

```env
# System-1 Provider Configuration
SYSTEM1_PROVIDER=laya          # Preferred provider (jev or laya)

# Laya (Open Source System-1)
LAYA_ENABLED=false             # Set to true when running local Laya server
LAYA_BASE_URL=http://localhost:8000
LAYA_API_KEY=                  # Optional if local Laya requires bearer token

# TypeSafe Jev (Cloud System-1)
JEV_API_KEY=mock-jev-key       # Set live key from typesafe.ai
JEV_BASE_URL=https://api.typesafe.ai
```

