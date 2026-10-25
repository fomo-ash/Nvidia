"""Routing logic for conditional transitions in LangGraph."""

from typing import Literal
from app.schemas.state import InvestigationState


def route_after_sufficiency(state: InvestigationState) -> Literal["collect_telemetry", "reason_causes", "needs_review"]:
    """Branch based on Jev sufficiency evaluation."""
    is_sufficient = state.get("is_sufficient", False)
    attempts = state.get("sufficiency_attempts", 1)

    if is_sufficient:
        return "reason_causes"
    return "needs_review" if attempts >= 2 else "collect_telemetry"
