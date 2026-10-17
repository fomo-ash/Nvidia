import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db.session import get_session
from app.models.domain import AuditEvent, Incident, Recommendation
from app.schemas.api import ApprovalRequest, IncidentCreate, IncidentOut, RecommendationOut
from app.services.costs import summary as cost_summary

router = APIRouter(prefix="/api/v1")
def audit(db, entity_type, entity_id, action, actor="local-demo-user", details=None):
    db.add(AuditEvent(entity_type=entity_type, entity_id=entity_id, action=action, actor=actor, details=details or {}))
@router.get("/dashboard/summary")
def dashboard(db: Session = Depends(get_session)):
    return {"open_incidents": len(db.scalars(select(Incident).where(Incident.status == "open")).all()), "cost_autopsy": cost_summary(), "mode": "deterministic-demo"}
@router.get("/incidents", response_model=list[IncidentOut])
def incidents(db: Session = Depends(get_session)): return db.scalars(select(Incident).order_by(Incident.created_at.desc())).all()
@router.post("/incidents", response_model=IncidentOut, status_code=201)
def create_incident(payload: IncidentCreate, db: Session = Depends(get_session)):
    incident = Incident(**payload.model_dump()); db.add(incident); db.flush(); audit(db, "incident", incident.id, "created"); db.commit(); db.refresh(incident); return incident
@router.get("/incidents/{incident_id}", response_model=IncidentOut)
def incident(incident_id: uuid.UUID, db: Session = Depends(get_session)):
    item = db.get(Incident, incident_id)
    if not item: raise HTTPException(404, "Incident not found")
    return item
@router.post("/incidents/{incident_id}/investigate", response_model=RecommendationOut)
def investigate(incident_id: uuid.UUID, db: Session = Depends(get_session)):
    if not db.get(Incident, incident_id): raise HTTPException(404, "Incident not found")
    recommendation = Recommendation(incident_id=incident_id, action="restart_demo_workload", target="demo/api-workers", parameters={"strategy":"rolling", "reason":"mock evidence indicates elevated error rate"})
    db.add(recommendation); db.flush(); audit(db, "recommendation", recommendation.id, "proposed", details={"provider":"mock"}); db.commit(); db.refresh(recommendation); return recommendation
@router.get("/incidents/{incident_id}/evidence")
def evidence(incident_id: uuid.UUID): return [{"source":"demo-metrics", "observed_at":"2026-10-17T10:00:00Z", "fact":"5xx error rate increased to 18%", "trusted":False}]
@router.get("/incidents/{incident_id}/timeline")
def timeline(incident_id: uuid.UUID): return [{"at":"2026-10-17T10:00:00Z", "event":"Alert detected"}, {"at":"2026-10-17T10:02:00Z", "event":"Mock evidence normalized"}]
@router.get("/incidents/{incident_id}/recommendations", response_model=list[RecommendationOut])
def recommendations(incident_id: uuid.UUID, db: Session = Depends(get_session)): return db.scalars(select(Recommendation).where(Recommendation.incident_id == incident_id)).all()
@router.get("/recommendations/{recommendation_id}", response_model=RecommendationOut)
def recommendation(recommendation_id: uuid.UUID, db: Session = Depends(get_session)):
    item = db.get(Recommendation, recommendation_id)
    if not item: raise HTTPException(404, "Recommendation not found")
    return item
@router.post("/recommendations/{recommendation_id}/approve", response_model=RecommendationOut)
def approve(recommendation_id: uuid.UUID, payload: ApprovalRequest, db: Session = Depends(get_session)):
    item = db.get(Recommendation, recommendation_id)
    if not item or item.status != "proposed": raise HTTPException(409, "Only proposed recommendations can be approved")
    item.status="approved"; audit(db, "recommendation", item.id, "approved", payload.actor); db.commit(); db.refresh(item); return item
@router.post("/recommendations/{recommendation_id}/reject", response_model=RecommendationOut)
def reject(recommendation_id: uuid.UUID, payload: ApprovalRequest, db: Session = Depends(get_session)):
    item = db.get(Recommendation, recommendation_id)
    if not item or item.status != "proposed": raise HTTPException(409, "Only proposed recommendations can be rejected")
    item.status="rejected"; audit(db, "recommendation", item.id, "rejected", payload.actor); db.commit(); db.refresh(item); return item
@router.get("/cost-analyses")
def cost_analyses(): return [cost_summary()]
@router.post("/cost-analyses", status_code=201)
def cost_analysis(): return cost_summary()
@router.get("/audit-events")
def audit_events(db: Session = Depends(get_session)): return db.scalars(select(AuditEvent).order_by(AuditEvent.created_at.desc())).all()
