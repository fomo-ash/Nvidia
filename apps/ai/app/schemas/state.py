"""Graph state and data structures for LangGraph investigation workflow."""

from typing import Annotated, Any, TypedDict
from pydantic import BaseModel, Field
import operator


class EvidenceReference(BaseModel):
    id: str = Field(..., description="Unique evidence ID (e.g. EVD-1a2b3c4d)")
    content_hash: str = Field(..., description="SHA-256 hash of canonical telemetry snapshot")
    source: str = Field(..., description="Telemetry source e.g. prometheus, kubernetes:logs")
    fact: str = Field(..., description="Synthesized telemetry observation fact")
    raw_data: dict[str, Any] = Field(default_factory=dict)
    trusted: bool = Field(default=False)


class Hypothesis(BaseModel):
    cause: str = Field(..., description="Causal statement explaining the anomaly")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    supporting_evidence_ids: list[str] = Field(
        default_factory=list, description="IDs of evidence verifying this hypothesis"
    )
    is_root_cause: bool = Field(default=False)


class RemediationCandidate(BaseModel):
    action_type: str = Field(default="restore_known_good_template")
    parameters: dict[str, Any] = Field(default_factory=dict)
    estimated_risk_level: str = Field(default="guarded")
    reversible: bool = Field(default=True)
    template_hash: str = Field(default="")


class InvestigationState(TypedDict):
    # Incident Identification
    incident_id: str
    anomaly_id: str
    namespace: str
    deployment_name: str
    mode: str

    # Accumulated Evidence (appended across node passes)
    evidence: Annotated[list[EvidenceReference], operator.add]

    # Telemetry Collections Status
    telemetry_completed: bool

    # Jev System-1 Decisions
    is_sufficient: bool
    missing_sources: list[str]
    sufficiency_attempts: int

    # Nemotron 70B Causal Reasoning
    hypotheses: list[Hypothesis]
    root_cause_summary: str

    # Jev Risk Scoring
    risk_tier: str
    risk_score: float
    requires_human_approval: bool

    # Generated Proposal & Action Candidate
    remediation_proposal: dict[str, Any] | None
    investigation_status: str  # e.g., 'analyzing', 'awaiting_approval', 'completed', 'failed'
    errors: Annotated[list[str], operator.add]
