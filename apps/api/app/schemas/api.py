from datetime import datetime
from uuid import UUID
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class EvidenceOut(BaseModel):
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


class IncidentOut(IncidentCreate):
    id: UUID
    status: str
    created_at: datetime
    model_config = {"from_attributes": True}


class RecommendationOut(BaseModel):
    id: UUID
    incident_id: UUID
    version: int
    status: Literal["proposed", "approved", "rejected", "superseded"]
    action: str
    target: str
    parameters: dict
    proposal_hash: str | None
    expires_at: datetime | None
    evidence: list[EvidenceOut] | None
    created_at: datetime
    model_config = {"from_attributes": True}


class ApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    proposal_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class DecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AuditEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    entity_type: str
    entity_id: UUID
    action: str
    actor: str
    details: dict
    created_at: datetime


class TimelineOut(BaseModel):
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
    mode: Literal["deterministic-demo"]


class ErrorOut(BaseModel):
    detail: str
