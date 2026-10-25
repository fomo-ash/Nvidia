"""FastAPI application entrypoint for FixProof AI Agent Service."""

from uuid import uuid4

from fastapi import FastAPI, HTTPException
from app.chat.agent import execute_chat
from app.graph.workflow import investigation_workflow
from app.schemas.api import (
    ChatRequest,
    ChatResponse,
    InvestigationRequest,
    InvestigationResponse,
    ProposalSummary,
)

app = FastAPI(
    title="FixProof AI Agent Service",
    description="Intelligent SRE reasoning service combining LangGraph state machines, TypeSafe Jev decisions, and NVIDIA Nemotron 70B.",
    version="0.1.0",
)


@app.get("/health", tags=["System"])
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "fixproof-ai", "version": "0.1.0"}


@app.post("/investigate", response_model=InvestigationResponse, tags=["Investigation"])
async def investigate_incident(body: InvestigationRequest) -> InvestigationResponse:
    """Start a fresh advisory investigation; resumption is not exposed."""
    investigation_id = uuid4()
    initial_state = {
        "incident_id": body.incident_id,
        "investigation_id": str(investigation_id),
        "anomaly_id": body.anomaly_id,
        "namespace": body.namespace,
        "deployment_name": body.deployment_name,
        "mode": body.mode,
        "evidence": [],
        "telemetry_completed": False,
        "is_sufficient": False,
        "missing_sources": [],
        "sufficiency_attempts": 0,
        "hypotheses": [],
        "root_cause_summary": "",
        "risk_tier": "medium",
        "risk_score": 0.0,
        "requires_human_approval": True,
        "remediation_proposal": None,
        "investigation_status": "starting",
        "errors": [],
    }

    config = {"configurable": {"thread_id": str(investigation_id)}}
    result_state = await investigation_workflow.ainvoke(initial_state, config=config)

    evidence_items = result_state.get("evidence", [])
    proposal_dict = result_state.get("remediation_proposal")
    proposal = ProposalSummary(**proposal_dict) if proposal_dict else None

    return InvestigationResponse(
        investigation_id=investigation_id,
        incident_id=body.incident_id,
        status=result_state.get("investigation_status", "completed"),
        evidence_count=len(evidence_items),
        hypotheses=result_state.get("hypotheses", []),
        root_cause_summary=result_state.get("root_cause_summary", ""),
        risk_tier=result_state.get("risk_tier", "medium"),
        requires_human_approval=result_state.get("requires_human_approval", True),
        proposal=proposal,
        evidence=evidence_items,
    )


@app.post("/chat", response_model=ChatResponse, tags=["ChatOps"])
async def chat_with_incident(body: ChatRequest) -> ChatResponse:
    """Interactive conversational ChatOps endpoint with evidence grounding."""
    config = {"configurable": {"thread_id": str(body.investigation_id)}}
    state = await investigation_workflow.aget_state(config)
    values = state.values if state else {}
    if not values or values.get("incident_id") != body.incident_id:
        raise HTTPException(404, "Investigation not found for this incident")
    evidence = values.get("evidence", [])

    response_text, citations = await execute_chat(
        session_id=f"{body.investigation_id}:{body.session_id}",
        incident_id=body.incident_id,
        user_message=body.message,
        available_evidence=evidence,
    )

    return ChatResponse(
        investigation_id=body.investigation_id,
        incident_id=body.incident_id,
        response=response_text,
        citations=citations,
        session_id=body.session_id,
    )
