from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.api import CostSummaryOut, EvidenceOut, RecordOut


class InvestigationOut(RecordOut):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    incident_id: UUID
    provider: str
    mode: Literal["synthetic"]
    status: Literal["completed", "failed"]
    summary: str
    created_at: datetime


class EvidenceItemOut(EvidenceOut):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    investigation_id: UUID
    content_hash: str
    trust_label: Literal["untrusted"]

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
