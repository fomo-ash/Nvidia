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

    def validate_citations(self):
        support = set(self.supporting_evidence_ids)
        contradict = set(self.contradicting_evidence_ids)
        if len(support) != len(self.supporting_evidence_ids) or len(contradict) != len(
            self.contradicting_evidence_ids
        ):
            raise ValueError("Duplicate evidence citations")
        if support & contradict:
            raise ValueError("Evidence cannot both support and contradict the same finding")
        if contradict and self.uncertainty == "low":
            raise ValueError("Contradicting evidence requires explicit uncertainty")
        return self


class Analysis(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str = Field(min_length=1, max_length=2000)
    hypotheses: list[Finding] = Field(min_length=1, max_length=5)
    gaps: list[str] = Field(default_factory=list, max_length=10)
    advisory_action: Literal["restore_known_good_template", "none"]

    def validate_advisory(self):
        """Validate new advice at ingestion/proposal boundaries, not history reads."""
        for finding in self.hypotheses:
            finding.validate_citations()
        if any(not gap.strip() or len(gap) > 500 for gap in self.gaps):
            raise ValueError("Invalid analysis gap")
        if self.gaps and self.advisory_action != "none":
            raise ValueError("Unresolved gaps require manual review without a restore suggestion")
        return self


class AnalysisResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: Literal["nebius", "groq"]
    model: str = Field(min_length=1, max_length=200)
    analysis: Analysis
