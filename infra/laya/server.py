"""Deterministic local server for the System-1 HTTP compatibility contract.

This service is a bounded heuristic development fallback. It does not package or run the Laya
open-weights model. A real Laya deployment may replace it when it exposes the same endpoint.
"""

from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="FixProof System-1 Policy Compatibility Server", version="1.0.0")


class SystemOneRequest(BaseModel):
    state: str = Field(..., description="Contextual state text or telemetry facts")
    questions: dict[str, dict[str, Any]] = Field(
        ..., description="Dictionary of questions by ID with type ('noul', 'choice', 'score')"
    )


class SystemOneResponse(BaseModel):
    answers: dict[str, dict[str, Any]] = Field(
        ..., description="Calculated answers keyed by question ID"
    )


@app.get("/health")
async def health():
    return {"status": "ok", "provider": "deterministic-policy-compatibility"}


@app.post("/v1/systemone", response_model=SystemOneResponse)
async def system_one(payload: SystemOneRequest):
    """Evaluate supported questions with transparent deterministic heuristics."""
    state_lower = payload.state.lower()
    answers: dict[str, dict[str, Any]] = {}

    for q_id, q_data in payload.questions.items():
        q_type = q_data.get("type", "noul")
        instructions = q_data.get("instructions", "").lower()
        criteria = q_data.get("criteria", {})

        if q_type == "noul":
            # Probability evaluation (0.0 to 1.0)
            # Check presence of vital signals in the state
            if "sufficient" in q_id or "sufficient" in instructions:
                has_prometheus = "prometheus" in state_lower or "5xx" in state_lower
                has_k8s = (
                    "kubernetes" in state_lower
                    or "deployment" in state_lower
                    or "pod" in state_lower
                )
                noul = 0.92 if (has_prometheus and has_k8s) else 0.35
            elif "outage" in q_id or "traffic" in instructions:
                failing = any(token in state_lower for token in ("5xx", "error", "fail"))
                noul = 0.95 if failing else 0.10
            elif "human_approval" in q_id or "approval" in instructions:
                noul = 0.95
            elif "reversible" in q_id or "rollback" in instructions:
                noul = 0.90
            else:
                noul = 0.85
            answers[q_id] = {"noul": round(noul, 2)}

        elif q_type == "choice":
            # Categorical choice selection
            if isinstance(criteria, dict) and criteria:
                options = list(criteria.keys())
                # Missing source evaluation
                if "missing" in q_id or "urgently needed" in instructions:
                    has_metrics = "prometheus" in state_lower
                    has_deployment = "kubernetes" in state_lower or "deployment" in state_lower
                    has_logs = "log" in state_lower

                    if not has_metrics and "prometheus" in options:
                        chosen = "prometheus"
                    elif not has_deployment and "kubernetes_deployment" in options:
                        chosen = "kubernetes_deployment"
                    elif not has_logs and "kubernetes_logs" in options:
                        chosen = "kubernetes_logs"
                    elif "none" in options:
                        chosen = "none"
                    else:
                        chosen = options[0]
                elif "risk" in q_id:
                    chosen = (
                        "low"
                        if "restore_known_good" in state_lower or "rollback" in state_lower
                        else "medium"
                    )
                    if chosen not in options:
                        chosen = options[0]
                else:
                    chosen = options[0]
                answers[q_id] = {"choice": chosen}
            else:
                answers[q_id] = {"choice": "unknown"}

        elif q_type == "score":
            # Tier score / classification
            if isinstance(criteria, list) and criteria:
                # E.g. ["routine", "degraded", "severe", "critical"]
                if "5xx" in state_lower or "outage" in state_lower or "crash" in state_lower:
                    chosen_tier = "severe" if "severe" in criteria else criteria[-1]
                else:
                    chosen_tier = criteria[0]
                answers[q_id] = {"score": chosen_tier, "choice": chosen_tier}
            else:
                answers[q_id] = {"score": 3}

    return SystemOneResponse(answers=answers)

