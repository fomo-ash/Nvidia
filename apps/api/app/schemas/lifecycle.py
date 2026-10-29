from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.api import CostSummaryOut, EvidenceOut, RecordOut
from app.schemas.analysis import AnalysisResult


class InvestigationResultOut(BaseModel):
    stage: str | None = None
    assessment: str | None = None
    gaps: list[str] = Field(default_factory=list)
    analysis: AnalysisResult | None = None


class InvestigationOut(RecordOut):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    incident_id: UUID
    provider: str
    mode: Literal["synthetic", "live"]
    status: Literal["collecting", "completed", "needs_review", "failed"]
    summary: str
    request_id: UUID | None = None
    result: InvestigationResultOut = Field(default_factory=InvestigationResultOut)
    created_at: datetime


class EvidenceItemOut(EvidenceOut):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    investigation_id: UUID
    content_hash: str
    trust_label: Literal["untrusted"]
    mode: Literal["synthetic", "live"]
    transport_id: str | None = None
    transport_hash: str | None = None
    target_uid: str | None = None
    raw_data: dict = Field(default_factory=dict)
    collection_error: str | None = None
    redacted: bool = False

    @field_validator("observed_at")
    @classmethod
    def normalize_time(cls, value):
        return (
            value.replace(tzinfo=timezone.utc)
            if value.tzinfo is None
            else value.astimezone(timezone.utc)
        )


class ApprovalOut(RecordOut):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    recommendation_id: UUID
    recommendation_version: int
    decision: Literal["approved", "rejected"]
    actor: str
    proposal_hash: str | None
    expires_at: datetime | None
    created_at: datetime


class ExecutionOut(RecordOut):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    recommendation_id: UUID
    approval_id: UUID
    actor: str
    proposal_hash: str
    action: str
    target: str
    parameters: dict
    adapter: str
    status: Literal["pending", "succeeded", "failed"]
    result: dict
    started_at: datetime
    completed_at: datetime | None


class VerificationOut(RecordOut):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    execution_id: UUID
    actor: str
    status: Literal["pending", "passed", "failed", "inconclusive"]
    observations: dict
    started_at: datetime
    completed_at: datetime | None


class CostSourceIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    period: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    service: str = Field(min_length=1, max_length=200)
    resource: str = Field(min_length=1, max_length=200)
    region: str = Field(min_length=1, max_length=80)
    cost: Decimal = Field(ge=0, max_digits=20, decimal_places=6, allow_inf_nan=False)
    tags: dict[
        Annotated[str, Field(min_length=1, max_length=100)], Annotated[str, Field(max_length=255)]
    ] = Field(default_factory=dict, max_length=50)


class CostAnalysisCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_period: str = Field(default="2026-10", pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    previous_period: str = Field(default="2026-09", pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    records: list[CostSourceIn] | None = Field(default=None, min_length=1, max_length=1000)

    @model_validator(mode="after")
    def periods(self):
        if self.previous_period >= self.current_period:
            raise ValueError("Previous period must precede current period")
        if self.records and any(
            r.period not in {self.previous_period, self.current_period} for r in self.records
        ):
            raise ValueError("All records must belong to the selected periods")
        return self


class CostAnalysisOut(CostSummaryOut, RecordOut):
    id: UUID
    created_at: datetime
    source_count: int


class CostSourceOut(CostSourceIn, RecordOut):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    analysis_id: UUID
    created_at: datetime


class IntegrationOut(BaseModel):
    id: str
    status: Literal["available", "not_configured", "not_checked"]
    mode: Literal["synthetic", "local", "external"]
    capabilities: list[str]
    detail: str


class IncidentTargetOut(RecordOut):
    target_id: str
    cluster: str
    namespace: str
    kind: Literal["Deployment"] = "Deployment"
    name: str
    uid: str | None


class IncidentTriggerOut(RecordOut):
    id: UUID
    source: str
    reporter: str
    summary: str
    note: str | None
    reported_at: datetime


class InvestigationRequestOut(RecordOut):
    id: UUID
    trigger_id: UUID
    status: str
    created_at: datetime
    claimed_at: datetime | None = None
    attempts: int = 0
    finished_at: datetime | None = None
