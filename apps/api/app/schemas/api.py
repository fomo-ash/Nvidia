from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field

class IncidentCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    severity: str = Field(pattern="^(low|medium|high|critical)$")
    summary: str = Field(min_length=3)
class IncidentOut(IncidentCreate):
    id: UUID
    status: str
    created_at: datetime
    model_config = {"from_attributes": True}
class RecommendationOut(BaseModel):
    id: UUID
    incident_id: UUID
    version: int
    status: str
    action: str
    target: str
    parameters: dict
    model_config = {"from_attributes": True}
class ApprovalRequest(BaseModel):
    actor: str = Field(default="local-demo-user", max_length=120)
class ErrorOut(BaseModel):
    detail: str
