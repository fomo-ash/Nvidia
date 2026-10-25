"""Schemas for TypeSafe Jev System-1 bounded decisions."""

from typing import Literal
from pydantic import BaseModel, Field


class SufficiencyEvaluation(BaseModel):
    is_sufficient: bool = Field(..., description="Whether collected evidence is sufficient for causal root cause")
    missing_sources: list[str] = Field(
        default_factory=list, description="List of telemetry sources needed (e.g. ['kubernetes:logs'])"
    )
    confidence: float = Field(default=0.9, ge=0.0, le=1.0)
    reason: str = Field(default="")


class RiskEvaluation(BaseModel):
    risk_tier: Literal["low", "medium", "high", "critical"] = "medium"
    blast_radius: str = Field(default="single_pod", description="Assessment of affected scope")
    confidence: float = Field(default=0.85, ge=0.0, le=1.0)
    requires_human_approval: bool = True
    rationale: str = Field(default="")
