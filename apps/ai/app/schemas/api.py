"""API request and response schemas for apps/ai endpoints."""

from typing import Any, Literal
from uuid import UUID
from pydantic import BaseModel, Field
from app.schemas.state import EvidenceReference, Hypothesis


class InvestigationRequest(BaseModel):
    incident_id: str = Field(..., description="UUID or identifier of the incident")
    anomaly_id: str = Field(..., description="ID of the detected anomaly")
    namespace: str = Field(default="fixproof-demo")
    deployment_name: str = Field(default="sample-api")
    mode: Literal["live", "synthetic"] = "live"


class ProposalSummary(BaseModel):
    action_type: str = "restore_known_good_template"
    parameters: dict[str, Any] = Field(default_factory=dict)
    estimated_risk_level: str = "guarded"
    reversible: bool = True
    template_hash: str = ""
    evidence_ids: list[str] = Field(default_factory=list)


class InvestigationResponse(BaseModel):
    investigation_id: UUID
    incident_id: str
    status: str
    evidence_count: int
    hypotheses: list[Hypothesis]
    root_cause_summary: str
    risk_tier: str
    requires_human_approval: bool
    proposal: ProposalSummary | None = None
    evidence: list[EvidenceReference] = Field(default_factory=list)


class ChatRequest(BaseModel):
    incident_id: str
    message: str
    session_id: str = "default"
    investigation_id: UUID | None = None
    evidence: list[EvidenceReference] = Field(default_factory=list)


class ChatResponse(BaseModel):
    incident_id: str
    response: str
    session_id: str
    citations: list[str] = Field(default_factory=list)
    investigation_id: UUID | None = None
    session_id: str
