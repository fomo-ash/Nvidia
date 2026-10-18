from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.domain import AuditEvent, Incident, Recommendation
from app.schemas.api import (
    ApprovalRequest,
    AuditEventOut,
    CostSummaryOut,
    DashboardOut,
    DecisionRequest,
    EvidenceOut,
    ErrorOut,
    IncidentCreate,
    IncidentOut,
    RecommendationOut,
    TimelineOut,
)
from app.services import recommendations as workflow
from app.services.costs import summary as cost_summary

router = APIRouter(prefix="/api/v1", responses={404: {"model": ErrorOut}, 409: {"model": ErrorOut}})
Database = Annotated[Session, Depends(get_session)]
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0, le=100000)]


@router.get("/dashboard/summary", response_model=DashboardOut)
def dashboard(db: Database):
    return {
        "open_incidents": db.scalar(
            select(func.count()).select_from(Incident).where(Incident.status == "open")
        ),
        "cost_autopsy": cost_summary(),
        "mode": "deterministic-demo",
    }


@router.get("/incidents", response_model=list[IncidentOut])
def incidents(db: Database, limit: Limit = 50, offset: Offset = 0):
    return db.scalars(
        select(Incident)
        .order_by(Incident.created_at.desc(), Incident.id)
        .limit(limit)
        .offset(offset)
    ).all()


@router.post("/incidents", response_model=IncidentOut, status_code=201)
def create_incident(payload: IncidentCreate, db: Database):
    item = Incident(**payload.model_dump())
    db.add(item)
    db.flush()
    workflow.audit(db, "incident", item.id, "created")
    db.commit()
    db.refresh(item)
    return item


@router.get("/incidents/{incident_id}", response_model=IncidentOut)
def incident(incident_id: UUID, db: Database):
    return workflow.require_incident(db, incident_id)


@router.post("/incidents/{incident_id}/investigate", response_model=RecommendationOut)
def investigate(incident_id: UUID, db: Database):
    return workflow.investigate(db, incident_id)


@router.get("/incidents/{incident_id}/evidence", response_model=list[EvidenceOut])
def evidence(incident_id: UUID, db: Database):
    workflow.require_incident(db, incident_id)
    latest = db.scalar(
        select(Recommendation)
        .where(Recommendation.incident_id == incident_id)
        .order_by(Recommendation.version.desc())
        .limit(1)
    )
    return (latest.evidence or []) if latest else []


@router.get("/incidents/{incident_id}/timeline", response_model=list[TimelineOut])
def timeline(incident_id: UUID, db: Database, limit: Limit = 50, offset: Offset = 0):
    workflow.require_incident(db, incident_id)
    recommendation_ids = select(Recommendation.id).where(Recommendation.incident_id == incident_id)
    events = db.scalars(
        select(AuditEvent)
        .where(
            ((AuditEvent.entity_type == "incident") & (AuditEvent.entity_id == incident_id))
            | (
                (AuditEvent.entity_type == "recommendation")
                & AuditEvent.entity_id.in_(recommendation_ids)
            )
        )
        .order_by(AuditEvent.created_at, AuditEvent.id)
        .limit(limit)
        .offset(offset)
    ).all()
    return [
        {"at": event.created_at, "event": event.action, "details": event.details}
        for event in events
    ]


@router.get("/incidents/{incident_id}/recommendations", response_model=list[RecommendationOut])
def recommendations(incident_id: UUID, db: Database, limit: Limit = 50, offset: Offset = 0):
    workflow.require_incident(db, incident_id)
    return db.scalars(
        select(Recommendation)
        .where(Recommendation.incident_id == incident_id)
        .order_by(Recommendation.version.desc())
        .limit(limit)
        .offset(offset)
    ).all()


@router.get("/recommendations/{recommendation_id}", response_model=RecommendationOut)
def recommendation(recommendation_id: UUID, db: Database):
    item = db.get(Recommendation, recommendation_id)
    if item is None:
        raise HTTPException(404, "Recommendation not found")
    return item


@router.post("/recommendations/{recommendation_id}/approve", response_model=RecommendationOut)
def approve(recommendation_id: UUID, payload: ApprovalRequest, db: Database):
    return workflow.decide(db, recommendation_id, "approved", payload.proposal_hash)


@router.post("/recommendations/{recommendation_id}/reject", response_model=RecommendationOut)
def reject(recommendation_id: UUID, payload: DecisionRequest, db: Database):
    return workflow.decide(db, recommendation_id, "rejected")


@router.get("/cost-analyses", response_model=list[CostSummaryOut])
def cost_analyses():
    return [cost_summary()]


@router.post("/cost-analyses", response_model=CostSummaryOut)
def cost_analysis():
    # This calculates a synthetic report; it does not create a persisted analysis yet.
    return cost_summary()


@router.get("/audit-events", response_model=list[AuditEventOut])
def audit_events(db: Database, limit: Limit = 50, offset: Offset = 0):
    return db.scalars(
        select(AuditEvent)
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id)
        .limit(limit)
        .offset(offset)
    ).all()
