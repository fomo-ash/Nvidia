"""Strict advisory analysis contract: citations are retained API evidence UUIDs."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Finding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cause: str = Field(min_length=1, max_length=1000)
    supporting_evidence_ids: list[UUID] = Field(min_length=1, max_length=10)
    contradicting_evidence_ids: list[UUID] = Field(default_factory=list, max_length=10)
    uncertainty: Literal["low", "medium", "high"]


class Analysis(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str = Field(min_length=1, max_length=2000)
    hypotheses: list[Finding] = Field(min_length=1, max_length=5)
    gaps: list[str] = Field(default_factory=list, max_length=10)
    advisory_action: Literal["restore_known_good_template", "none"]


class AnalysisResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: Literal["nebius", "groq"]
    model: str = Field(min_length=1, max_length=200)
    analysis: Analysis
