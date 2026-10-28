from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from sqlalchemy import func, select

from app.core.identity import Actor, get_actor, require_operator
from app.core.config import settings
from app.db.session import get_session
from app.models.domain import (
    Approval,
    AuditEvent,
    CostAnalysis,
    CostRecord,
    EvidenceItem,
    Execution,
    Incident,
    IncidentTrigger,
    InvestigationRequest,
    Investigation,
    Recommendation,
    VerificationResult,
)
from app.schemas.api import (
    ApprovalRequest,
    AuditEventOut,
    DashboardOut,
    DecisionRequest,
    EvidenceOut,
    ErrorOut,
    IncidentCreate,
    IncidentOut,
    ManualIncidentCreate,
    ManualIncidentOut,
    RecommendationOut,
    TimelineOut,
)
from app.schemas.lifecycle import (
    ApprovalOut,
    CostAnalysisCreate,
    CostAnalysisOut,
    CostSourceOut,
    EvidenceItemOut,
    ExecutionOut,
    IntegrationOut,
    InvestigationOut,
    VerificationOut,
)
from app.services import cost_analyses as billing
from app.services import operations
from app.services import incident_intake
from app.services import recommendations as workflow
from app.services.costs import summary as cost_summary
from app.services.idempotency import perform
from app.services.pagination import page
from sqlalchemy.orm import Session

router = APIRouter(
    prefix="/api/v1",
    dependencies=[Depends(get_actor)],
    responses={
        401: {"model": ErrorOut},
        403: {"model": ErrorOut},
        404: {"model": ErrorOut},
        409: {"model": ErrorOut},
    },
)
Database = Annotated[Session, Depends(get_session)]
Operator = Annotated[Actor, Depends(require_operator)]
Adapter = Annotated[operations.OperationsAdapter, Depends(operations.get_operations_adapter)]
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0, le=100000)]
Cursor = Annotated[str | None, Query(max_length=2048)]
Key = Annotated[
    str | None, Header(alias="Idempotency-Key", pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
]
RequiredKey = Annotated[
    str, Header(alias="Idempotency-Key", pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
]


def require(db, model, identifier):
    item = db.get(model, identifier)
    if item is None:
        raise HTTPException(404, f"{model.__name__} not found")
    return item


@router.get("/dashboard/summary", response_model=DashboardOut)
def dashboard(db: Database):
    latest = db.scalar(
        select(CostAnalysis)
        .order_by(CostAnalysis.created_at.desc(), CostAnalysis.id.desc())
        .limit(1)
    )
    return {
        "open_incidents": db.scalar(
            select(func.count()).select_from(Incident).where(Incident.status == "open")
        ),
        "cost_autopsy": latest.report if latest else cost_summary(),
        "mode": "deterministic-demo",
    }


@router.get("/incidents", response_model=list[IncidentOut])
def incidents(
    db: Database, response: Response, limit: Limit = 50, offset: Offset = 0, cursor: Cursor = None
):
    return page(db, select(Incident), Incident, response, "incidents", limit, offset, cursor)


@router.post("/incidents", response_model=IncidentOut | ManualIncidentOut, status_code=201)
def create_incident(
    payload: ManualIncidentCreate | IncidentCreate, db: Database, actor: Operator, key: Key = None
):
    if isinstance(payload, ManualIncidentCreate):
        return incident_intake.report(db, payload, actor, key)
    if not settings.local_demo_enabled:
        raise HTTPException(403, "Synthetic incident creation is disabled")

    def create():
        item = Incident(**payload.model_dump())
        db.add(item)
        db.flush()
        workflow.audit(db, "incident", item.id, "created", actor=actor.id)
        return item

    return perform(
        db, actor, key, "/incidents", payload.model_dump(mode="json"), create, IncidentOut, 201
    )


@router.get("/incident-targets")
def incident_targets():
    return [
        {
            "target_id": incident_intake.TARGET_ID,
            "cluster": "local-kind",
            "namespace": "fixproof-demo",
            "kind": "Deployment",
            "name": "sample-api",
            "uid": settings.sample_target_uid or None,
        }
    ]


@router.get("/incidents/{incident_id}/triggers")
def incident_triggers(incident_id: UUID, db: Database):
    workflow.require_incident(db, incident_id)
    triggers = db.scalars(
        select(IncidentTrigger)
        .where(IncidentTrigger.incident_id == incident_id)
        .order_by(IncidentTrigger.reported_at, IncidentTrigger.id)
    ).all()
    return [
        {
            "id": item.id,
            "source": item.source,
            "reporter": item.reporter,
            "summary": item.summary,
            "note": item.note,
            "reported_at": item.reported_at,
        }
        for item in triggers
    ]


@router.get("/incidents/{incident_id}/investigation-requests")
def incident_requests(incident_id: UUID, db: Database):
    workflow.require_incident(db, incident_id)
    requests = db.scalars(
        select(InvestigationRequest)
        .where(InvestigationRequest.incident_id == incident_id)
        .order_by(InvestigationRequest.created_at, InvestigationRequest.id)
    ).all()
    return [
        {
            "id": item.id,
            "trigger_id": item.trigger_id,
            "status": item.status,
            "created_at": item.created_at,
        }
        for item in requests
    ]


@router.get("/incidents/{incident_id}", response_model=IncidentOut)
def incident(incident_id: UUID, db: Database):
    return workflow.require_incident(db, incident_id)


@router.post("/incidents/{incident_id}/investigate", response_model=RecommendationOut)
def investigate(incident_id: UUID, db: Database, actor: Operator, key: Key = None):
    return perform(
        db,
        actor,
        key,
        f"/incidents/{incident_id}/investigate",
        {},
        lambda: workflow.investigate(db, incident_id, actor=actor),
        RecommendationOut,
    )


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
def timeline(
    incident_id: UUID,
    db: Database,
    response: Response,
    limit: Limit = 50,
    offset: Offset = 0,
    cursor: Cursor = None,
):
    workflow.require_incident(db, incident_id)
    recommendation_ids = select(Recommendation.id).where(Recommendation.incident_id == incident_id)
    query = select(AuditEvent).where(
        ((AuditEvent.entity_type == "incident") & (AuditEvent.entity_id == incident_id))
        | (
            (AuditEvent.entity_type == "recommendation")
            & AuditEvent.entity_id.in_(recommendation_ids)
        )
        | (AuditEvent.details["incident_id"].as_string() == str(incident_id))
    )
    events = page(db, query, AuditEvent, response, f"timeline:{incident_id}", limit, offset, cursor)
    return [
        {"at": event.created_at, "event": event.action, "details": event.details}
        for event in events
    ]


@router.get("/incidents/{incident_id}/recommendations", response_model=list[RecommendationOut])
def recommendations(
    incident_id: UUID,
    db: Database,
    response: Response,
    limit: Limit = 50,
    offset: Offset = 0,
    cursor: Cursor = None,
):
    workflow.require_incident(db, incident_id)
    return page(
        db,
        select(Recommendation).where(Recommendation.incident_id == incident_id),
        Recommendation,
        response,
        f"recommendations:{incident_id}",
        limit,
        offset,
        cursor,
    )


@router.get("/recommendations/{recommendation_id}", response_model=RecommendationOut)
def recommendation(recommendation_id: UUID, db: Database):
    return require(db, Recommendation, recommendation_id)


@router.post("/recommendations/{recommendation_id}/approve", response_model=RecommendationOut)
def approve(
    recommendation_id: UUID,
    payload: ApprovalRequest,
    db: Database,
    actor: Operator,
    key: Key = None,
):
    return perform(
        db,
        actor,
        key,
        f"/recommendations/{recommendation_id}/approve",
        payload.model_dump(mode="json"),
        lambda: workflow.decide(db, recommendation_id, "approved", payload.proposal_hash, actor),
        RecommendationOut,
    )


@router.post("/recommendations/{recommendation_id}/reject", response_model=RecommendationOut)
def reject(
    recommendation_id: UUID,
    payload: DecisionRequest,
    db: Database,
    actor: Operator,
    key: Key = None,
):
    return perform(
        db,
        actor,
        key,
        f"/recommendations/{recommendation_id}/reject",
        {},
        lambda: workflow.decide(db, recommendation_id, "rejected", actor=actor),
        RecommendationOut,
    )


@router.get("/investigations", response_model=list[InvestigationOut])
def investigations(
    db: Database, response: Response, limit: Limit = 50, offset: Offset = 0, cursor: Cursor = None
):
    return page(
        db, select(Investigation), Investigation, response, "investigations", limit, offset, cursor
    )


@router.get("/incidents/{incident_id}/investigations", response_model=list[InvestigationOut])
def incident_investigations(
    incident_id: UUID,
    db: Database,
    response: Response,
    limit: Limit = 50,
    offset: Offset = 0,
    cursor: Cursor = None,
):
    workflow.require_incident(db, incident_id)
    return page(
        db,
        select(Investigation).where(Investigation.incident_id == incident_id),
        Investigation,
        response,
        f"investigations:{incident_id}",
        limit,
        offset,
        cursor,
    )


@router.get("/investigations/{investigation_id}", response_model=InvestigationOut)
def investigation(investigation_id: UUID, db: Database):
    return require(db, Investigation, investigation_id)


@router.get("/investigations/{investigation_id}/evidence", response_model=list[EvidenceItemOut])
def investigation_evidence(
    investigation_id: UUID,
    db: Database,
    response: Response,
    limit: Limit = 50,
    offset: Offset = 0,
    cursor: Cursor = None,
):
    require(db, Investigation, investigation_id)
    return page(
        db,
        select(EvidenceItem).where(EvidenceItem.investigation_id == investigation_id),
        EvidenceItem,
        response,
        f"evidence:{investigation_id}",
        limit,
        offset,
        cursor,
        "observed_at",
    )


@router.get("/approvals", response_model=list[ApprovalOut])
def approvals(
    db: Database, response: Response, limit: Limit = 50, offset: Offset = 0, cursor: Cursor = None
):
    return page(db, select(Approval), Approval, response, "approvals", limit, offset, cursor)


@router.get("/approvals/{approval_id}", response_model=ApprovalOut)
def approval(approval_id: UUID, db: Database):
    return require(db, Approval, approval_id)


@router.get("/recommendations/{recommendation_id}/approval", response_model=ApprovalOut)
def recommendation_approval(recommendation_id: UUID, db: Database):
    require(db, Recommendation, recommendation_id)
    item = db.scalar(select(Approval).where(Approval.recommendation_id == recommendation_id))
    if item is None:
        raise HTTPException(404, "Approval not found")
    return item


@router.post(
    "/recommendations/{recommendation_id}/execute",
    response_model=ExecutionOut,
    status_code=201,
    responses={202: {"model": ExecutionOut, "description": "Existing operation is still pending"}},
)
def execute(
    recommendation_id: UUID,
    payload: ApprovalRequest,
    db: Database,
    actor: Operator,
    adapter: Adapter,
    key: RequiredKey,
):
    return operations.execute(db, actor, key, recommendation_id, payload.proposal_hash, adapter)


@router.get("/executions", response_model=list[ExecutionOut])
def executions(
    db: Database, response: Response, limit: Limit = 50, offset: Offset = 0, cursor: Cursor = None
):
    return page(
        db,
        select(Execution),
        Execution,
        response,
        "executions",
        limit,
        offset,
        cursor,
        "started_at",
    )


@router.get("/executions/{execution_id}", response_model=ExecutionOut)
def execution(execution_id: UUID, db: Database):
    return require(db, Execution, execution_id)


@router.post(
    "/executions/{execution_id}/verify",
    response_model=VerificationOut,
    status_code=201,
    responses={
        202: {"model": VerificationOut, "description": "Existing verification is still pending"}
    },
)
def verify(
    execution_id: UUID,
    payload: DecisionRequest,
    db: Database,
    actor: Operator,
    adapter: Adapter,
    key: RequiredKey,
):
    return operations.verify(db, actor, key, execution_id, adapter)


@router.get("/executions/{execution_id}/verification", response_model=VerificationOut)
def execution_verification(execution_id: UUID, db: Database):
    require(db, Execution, execution_id)
    item = db.scalar(
        select(VerificationResult).where(VerificationResult.execution_id == execution_id)
    )
    if item is None:
        raise HTTPException(404, "Verification not found")
    return item


@router.get("/verifications/{verification_id}", response_model=VerificationOut)
def verification(verification_id: UUID, db: Database):
    return require(db, VerificationResult, verification_id)


@router.get("/cost-analyses", response_model=list[CostAnalysisOut])
def cost_analyses(
    db: Database, response: Response, limit: Limit = 50, offset: Offset = 0, cursor: Cursor = None
):
    items = page(
        db, select(CostAnalysis), CostAnalysis, response, "cost-analyses", limit, offset, cursor
    )
    return [billing.analysis_out(db, item) for item in items]


@router.post("/cost-analyses", response_model=CostAnalysisOut, status_code=201)
def cost_analysis(
    db: Database, actor: Operator, payload: CostAnalysisCreate | None = None, key: Key = None
):
    payload = payload or CostAnalysisCreate()
    return perform(
        db,
        actor,
        key,
        "/cost-analyses",
        payload.model_dump(mode="json"),
        lambda: billing.create_analysis(db, payload, actor),
        CostAnalysisOut,
        201,
    )


@router.get("/cost-analyses/{analysis_id}", response_model=CostAnalysisOut)
def cost_analysis_detail(analysis_id: UUID, db: Database):
    return billing.analysis_out(db, require(db, CostAnalysis, analysis_id))


@router.get("/cost-analyses/{analysis_id}/records", response_model=list[CostSourceOut])
def cost_records(
    analysis_id: UUID,
    db: Database,
    response: Response,
    limit: Limit = 50,
    offset: Offset = 0,
    cursor: Cursor = None,
):
    item = require(db, CostAnalysis, analysis_id)
    query = select(CostRecord).where(CostRecord.analysis_id == item.id)
    return page(
        db, query, CostRecord, response, f"cost-records:{analysis_id}", limit, offset, cursor
    )


@router.get("/integrations", response_model=list[IntegrationOut])
def integrations(db: Database):
    # DB availability has already been exercised by this query; never claim remote connectivity.
    db.execute(select(1))
    return [
        {
            "id": "database",
            "status": "available",
            "mode": "local",
            "capabilities": ["persistence"],
            "detail": "Database query succeeded",
        },
        {
            "id": "investigation",
            "status": "available",
            "mode": "synthetic",
            "capabilities": ["investigate"],
            "detail": "Bounded mock provider",
        },
        {
            "id": "operations",
            "status": "not_configured",
            "mode": "local",
            "capabilities": [],
            "detail": "Execution and verification adapters are not configured",
        },
        *[
            {
                "id": name,
                "status": "not_configured",
                "mode": "external",
                "capabilities": [],
                "detail": "No adapter configured",
            }
            for name in ["aws", "kubernetes", "terraform"]
        ],
        *[
            {
                "id": name,
                "status": "not_checked",
                "mode": "local",
                "capabilities": [],
                "detail": "Remote health is not probed by this endpoint",
            }
            for name in ["prometheus", "grafana"]
        ],
    ]


@router.get("/audit-events", response_model=list[AuditEventOut])
def audit_events(
    db: Database, response: Response, limit: Limit = 50, offset: Offset = 0, cursor: Cursor = None
):
    return page(db, select(AuditEvent), AuditEvent, response, "audit-events", limit, offset, cursor)
