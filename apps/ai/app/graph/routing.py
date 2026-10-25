"""Routing logic for conditional transitions in LangGraph."""

from typing import Literal
from app.schemas.state import InvestigationState


def route_after_sufficiency(state: InvestigationState) -> Literal["collect_telemetry", "reason_causes"]:
    """Branch based on Jev sufficiency evaluation."""
    is_sufficient = state.get("is_sufficient", False)
    attempts = state.get("sufficiency_attempts", 1)

    if is_sufficient or attempts >= 2:
        return "reason_causes"

    return "collect_telemetry"
