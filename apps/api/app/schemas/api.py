from __future__ import annotations

from datetime import datetime
from uuid import UUID
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.core.time import utc


class RecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    @field_validator("*", mode="after")
    @classmethod
    def utc_timestamps(cls, value):
        return utc(value) if isinstance(value, datetime) else value


class EvidenceOut(RecordOut):
    model_config = ConfigDict(extra="forbid")
    source: str = Field(min_length=1, max_length=200)
    observed_at: datetime
    fact: str = Field(min_length=1, max_length=8000)
    trusted: Literal[False] = False
    mode: Literal["synthetic"] = "synthetic"


class IncidentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(min_length=3, max_length=200)
    severity: str = Field(pattern="^(low|medium|high|critical)$")
    summary: str = Field(min_length=3, max_length=20000)


class IncidentOut(IncidentCreate, RecordOut):
    id: UUID
    status: str
    created_at: datetime
    mode: str = "legacy_demo"
    target_id: str | None = None
    target_uid: str | None = None
    symptom: str | None = None
    lifecycle: str | None = None
    assessment: str | None = None
    last_reported_at: datetime | None = None
    model_config = {"from_attributes": True}


class ManualIncidentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    target_id: Literal["local-kind/fixproof-demo/sample-api"]
    target_uid: str = Field(min_length=1, max_length=80)
    symptom: Literal["http_5xx_spike"]
    summary: str = Field(min_length=3, max_length=800)
    note: str | None = Field(default=None, max_length=2000)


class ManualIncidentOut(RecordOut):
    incident_id: UUID
    trigger_id: UUID
    investigation_request_id: UUID
    target_id: str
    target_uid: str
    trigger_source: Literal["manual"] = "manual"
    lifecycle: Literal["open"] = "open"
    assessment: Literal["unassessed"] = "unassessed"
    reported_at: datetime
    reused: bool


class LiveProposalEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    source: str
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class RecommendationOut(RecordOut):
    id: UUID
    incident_id: UUID
    investigation_id: UUID | None
    version: int
    status: Literal[
        "proposed",
        "approved",
        "rejected",
        "superseded",
        "executed",
        "execution_failed",
        "verified",
        "verification_failed",
    ]
    action: str
    target: str
    parameters: dict
    proposal_hash: str | None
    expires_at: datetime | None
    evidence: list[EvidenceOut | LiveProposalEvidence] | None
    created_at: datetime
    model_config = {"from_attributes": True}


class ApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    proposal_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class BaselineRegistration(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_uid: str = Field(min_length=1, max_length=80)
    template: dict
    template_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class TrustedBaselineOut(RecordOut):
    id: UUID
    cluster: str
    namespace: str
    deployment: str
    target_uid: str
    template_hash: str
    registered_by: str
    created_at: datetime


class LiveProposalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    investigation_id: UUID


class DecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AuditEventOut(RecordOut):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    entity_type: str
    entity_id: UUID
    action: str
    actor: str
    details: dict
    created_at: datetime


class TimelineOut(RecordOut):
    at: datetime
    event: str
    details: dict


class CostRecord(BaseModel):
    period: str
    service: str
    resource: str
    region: str
    cost: float
    previous_cost: float
    change: float


class SavingsOut(BaseModel):
    amount: float
    assumption: str
    formula: str


class CostSummaryOut(BaseModel):
    mode: Literal["synthetic"]
    currency: Literal["USD"]
    current_period: str
    previous_period: str
    total_cost: float
    previous_total: float
    change: float
    change_percent: float | None
    drivers: list[CostRecord]
    estimated_savings: SavingsOut


class DashboardOut(BaseModel):
    open_incidents: int
    cost_autopsy: CostSummaryOut
    mode: Literal["deterministic-demo", "local-operations"]


class ErrorOut(BaseModel):
    detail: str
