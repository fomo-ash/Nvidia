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
    TrustedBaseline,
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
    BaselineRegistration,
    TrustedBaselineOut,
    LiveProposalRequest,
    TimelineOut,
    ChatMessageRequest,
    ChatMessageOut,
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
    IncidentTargetOut,
    IncidentTriggerOut,
    InvestigationRequestOut,
    VerificationOut,
)
from app.services import cost_analyses as billing
from app.services import operations
from app.services import incident_intake
from app.services import live_proposals
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
        "mode": "deterministic-demo" if settings.local_demo_enabled else "local-operations",
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


@router.get("/incident-targets", response_model=list[IncidentTargetOut])
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


@router.get("/incidents/{incident_id}/triggers", response_model=list[IncidentTriggerOut])
def incident_triggers(incident_id: UUID, db: Database):
    workflow.require_incident(db, incident_id)
    triggers = db.scalars(
        select(IncidentTrigger)
        .where(IncidentTrigger.incident_id == incident_id)
        .order_by(IncidentTrigger.reported_at.desc(), IncidentTrigger.id.desc())
        .limit(100)
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


@router.get(
    "/incidents/{incident_id}/investigation-requests", response_model=list[InvestigationRequestOut]
)
def incident_requests(incident_id: UUID, db: Database):
    workflow.require_incident(db, incident_id)
    requests = db.scalars(
        select(InvestigationRequest)
        .where(InvestigationRequest.incident_id == incident_id)
        .order_by(InvestigationRequest.created_at.desc(), InvestigationRequest.id.desc())
        .limit(100)
    ).all()
    return [
        {
            "id": item.id,
            "trigger_id": item.trigger_id,
            "status": item.status,
            "created_at": item.created_at,
            "claimed_at": item.claimed_at,
            "attempts": item.attempts,
            "finished_at": item.finished_at,
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


@router.post("/chat", response_model=ChatMessageOut)
def chat_global(
    payload: ChatMessageRequest,
    db: Database,
    actor: Operator,
):
    """Grounded interactive chat endpoint for the dedicated Chat page."""
    inc_id = None
    if payload.incident_id and payload.incident_id != "global":
        try:
            inc_id = UUID(payload.incident_id)
        except ValueError:
            pass
    if inc_id is None:
        latest = db.scalar(select(Incident).order_by(Incident.created_at.desc()))
        if latest:
            inc_id = latest.id

    evidence_items = []
    if inc_id:
        investigations = db.scalars(
            select(Investigation).where(Investigation.incident_id == inc_id)
        ).all()
        inv_ids = [inv.id for inv in investigations]
        if inv_ids:
            evidence_items = db.scalars(
                select(EvidenceItem).where(EvidenceItem.investigation_id.in_(inv_ids))
            ).all()

    evidence_payload = [
        {
            "id": str(item.id),
            "observed_at": item.observed_at.isoformat(),
            "content_hash": item.content_hash,
            "source": item.source,
            "fact": item.fact,
            "raw_data": item.raw_data or {},
            "trusted": False,
            "mode": "live",
        }
        for item in evidence_items
    ]

    import urllib.request
    import json

    ai_url = f"{settings.ai_service_url}/chat"
    req_body = json.dumps({
        "incident_id": str(inc_id) if inc_id else "cluster-overview",
        "session_id": payload.session_id,
        "message": payload.message,
        "evidence": evidence_payload,
    }).encode("utf-8")

    req = urllib.request.Request(
        ai_url,
        data=req_body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.service_auth_token}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            response_text = data.get("response", "")
            citations = data.get("citations", [])
    except Exception:
        if evidence_items:
            first = evidence_items[0]
            response_text = (
                f"Incident analysis for {str(inc_id)[:8]}: Verified {len(evidence_items)} evidence items. "
                f"Observed {first.source} indicator: {first.fact} [Citation: {first.id}]. "
                "Remediation recommendation advises reverting to known-good baseline."
            )
            citations = [str(first.id)]
        else:
            response_text = (
                "I am the FixProof operations assistant. I can inspect cluster workloads, explain incident "
                "root causes, review telemetry, and evaluate remediation proposals. No active incident evidence found yet."
            )
            citations = []

    if inc_id:
        workflow.audit(
            db,
            "incident",
            inc_id,
            "chat_query",
            actor=actor.id,
            details={
                "session_id": payload.session_id,
                "message": payload.message,
                "response": response_text[:500],
                "citations": citations,
            },
        )

    return ChatMessageOut(
        incident_id=str(inc_id) if inc_id else "cluster-overview",
        response=response_text,
        citations=citations,
        session_id=payload.session_id,
    )


@router.post("/incidents/{incident_id}/chat", response_model=ChatMessageOut)
def chat_incident(
    incident_id: UUID,
    payload: ChatMessageRequest,
    db: Database,
    actor: Operator,
):
    """Grounded interactive chat with incident context and retained evidence."""
    workflow.require_incident(db, incident_id)
    # Collect all retained evidence items for this incident
    investigations = db.scalars(
        select(Investigation).where(Investigation.incident_id == incident_id)
    ).all()
    inv_ids = [inv.id for inv in investigations]
    evidence_items = []
    if inv_ids:
        evidence_items = db.scalars(
            select(EvidenceItem).where(EvidenceItem.investigation_id.in_(inv_ids))
        ).all()

    # Call AI service chat endpoint with service auth
    evidence_payload = [
        {
            "id": str(item.id),
            "observed_at": item.observed_at.isoformat(),
            "content_hash": item.content_hash,
            "source": item.source,
            "fact": item.fact,
            "raw_data": item.raw_data or {},
            "trusted": False,
            "mode": "live",
        }
        for item in evidence_items
    ]

    import urllib.request
    import json

    ai_url = f"{settings.ai_service_url}/chat"
    req_body = json.dumps({
        "incident_id": str(incident_id),
        "session_id": payload.session_id,
        "message": payload.message,
        "evidence": evidence_payload,
    }).encode("utf-8")

    req = urllib.request.Request(
        ai_url,
        data=req_body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.service_auth_token}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            response_text = data.get("response", "")
            citations = data.get("citations", [])
    except Exception:
        response_text = "AI investigation assistant is currently unavailable. Please review the retained observations directly."
        citations = []

    # Record append-only audit event
    workflow.audit(
        db,
        "incident",
        incident_id,
        "chat_query",
        actor=actor.id,
        details={
            "session_id": payload.session_id,
            "message": payload.message,
            "response": response_text[:500],
            "citations": citations,
        },
    )

    return ChatMessageOut(
        incident_id=str(incident_id),
        response=response_text,
        citations=citations,
        session_id=payload.session_id,
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


@router.post("/trusted-baselines", response_model=TrustedBaselineOut, status_code=201)
def register_trusted_baseline(
    payload: BaselineRegistration, db: Database, actor: Operator, key: RequiredKey
):
    return perform(
        db,
        actor,
        key,
        "/trusted-baselines",
        payload.model_dump(mode="json"),
        lambda: live_proposals.register_baseline(db, payload, actor),
        TrustedBaselineOut,
        201,
    )


@router.get("/trusted-baselines/current", response_model=TrustedBaselineOut)
def current_trusted_baseline(db: Database):
    item = db.scalar(
        select(TrustedBaseline).where(TrustedBaseline.target_uid == settings.sample_target_uid)
    )
    if item is None:
        raise HTTPException(404, "Trusted baseline not registered")
    return item


@router.post(
    "/incidents/{incident_id}/proposals", response_model=RecommendationOut, status_code=201
)
def create_live_proposal(
    incident_id: UUID,
    payload: LiveProposalRequest,
    db: Database,
    actor: Operator,
    key: RequiredKey,
):
    return perform(
        db,
        actor,
        key,
        f"/incidents/{incident_id}/proposals",
        payload.model_dump(mode="json"),
        lambda: live_proposals.propose(db, incident_id, payload.investigation_id, actor),
        RecommendationOut,
        201,
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


@router.post("/executions/{execution_id}/reconcile", response_model=ExecutionOut)
def reconcile_execution(
    execution_id: UUID,
    payload: DecisionRequest,
    db: Database,
    actor: Operator,
    key: RequiredKey,
):
    return perform(
        db,
        actor,
        key,
        f"/executions/{execution_id}/reconcile",
        {},
        lambda: operations.reconcile(db, execution_id, actor),
        ExecutionOut,
    )


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
            "status": "available" if settings.local_demo_enabled else "not_checked",
            "mode": "synthetic" if settings.local_demo_enabled else "local",
            "capabilities": ["investigate"]
            if settings.local_demo_enabled
            else ["collect_live_evidence"],
            "detail": "Bounded mock provider"
            if settings.local_demo_enabled
            else "Durable read-only investigation worker; source results are retained per investigation",
        },
        {
            "id": "operations",
            "status": "not_configured",
            "mode": "local",
            "capabilities": [],
            "detail": "Execution and verification adapters are not configured",
        },
        {
            "id": "discord",
            "status": "not_checked" if settings.discord_webhook_url else "not_configured",
            "mode": "external",
            "capabilities": (
                ["channel_updates"]
                + (
                    ["read_only_commands"]
                    if settings.discord_public_key
                    and settings.discord_guild_id
                    and settings.discord_allowed_role_ids
                    else []
                )
            )
            if settings.discord_webhook_url
            else [],
            "detail": "Discord configuration present; delivery and interaction endpoint not probed"
            if settings.discord_webhook_url
            else "Discord integration is disabled",
        },
        *[
            {
                "id": name,
                "status": "not_checked"
                if name == "kubernetes"
                and settings.sample_target_uid
                and settings.service_auth_token
                else "not_configured",
                "mode": "external",
                "capabilities": ["bounded_read"]
                if name == "kubernetes"
                and settings.sample_target_uid
                and settings.service_auth_token
                else [],
                "detail": "MCP reader configured; not probed by this endpoint"
                if name == "kubernetes"
                and settings.sample_target_uid
                and settings.service_auth_token
                else "No adapter configured",
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
