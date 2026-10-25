"""LangGraph investigation workflow nodes."""

from datetime import datetime, timezone
from typing import Any
from app.decisions.jev_engine import JevDecisionEngine
from app.guardrails.citations import CitationValidatorGuard
from app.llm.nemotron import generate_causal_analysis
from app.schemas.state import InvestigationState, RemediationCandidate
from app.tools.mcp_client import McpClient

mcp = McpClient()
jev = JevDecisionEngine()


async def collect_telemetry_node(state: InvestigationState) -> dict[str, Any]:
    """Node 1: Collect bounded telemetry snapshots from MCP server."""
    ns = state.get("namespace", "fixproof-demo")
    dep = state.get("deployment_name", "sample-api")
    existing_evidence = state.get("evidence", [])
    collected_sources = {ev.source for ev in existing_evidence}

    new_evidence = []
    errors = []
    calls = [
        ("prometheus", lambda: mcp.query_metrics(window="1m")),
        (
            "kubernetes:deployment",
            lambda: mcp.get_deployment_status(namespace=ns, deployment_name=dep),
        ),
        ("kubernetes:logs", lambda: mcp.get_pod_logs(namespace=ns, deployment_name=dep, lines=50)),
        ("direct:probe", mcp.check_service_health),
        ("kubernetes:events", lambda: mcp.get_pod_events(namespace=ns, limit=10)),
    ]
    for source, call in calls:
        if source in collected_sources:
            continue
        try:
            new_evidence.append(await call())
        except Exception:
            errors.append(f"{source}: collection unavailable")

    current_attempts = state.get("sufficiency_attempts", 0) + 1

    return {
        "evidence": new_evidence,
        "telemetry_completed": True,
        "sufficiency_attempts": current_attempts,
        "investigation_status": "telemetry_collected",
        "errors": errors,
    }


async def evaluate_sufficiency_node(state: InvestigationState) -> dict[str, Any]:
    """Node 2: Jev System-1 bounded decision evaluating telemetry sufficiency."""
    evidence = state.get("evidence", [])
    attempts = state.get("sufficiency_attempts", 1)

    eval_result = await jev.evaluate_sufficiency(evidence=evidence, attempt=attempts)

    return {
        "is_sufficient": eval_result.is_sufficient,
        "missing_sources": eval_result.missing_sources,
        "investigation_status": "sufficiency_evaluated",
    }


async def reason_causes_node(state: InvestigationState) -> dict[str, Any]:
    """Node 3: NVIDIA Nemotron 70B causal reasoning with evidence grounding."""
    evidence = state.get("evidence", [])
    incident_id = state.get("incident_id", "inc-unknown")
    anomaly_id = state.get("anomaly_id", "anom-unknown")
    namespace = state.get("namespace", "fixproof-demo")
    deployment_name = state.get("deployment_name", "sample-api")

    now = datetime.now(timezone.utc)
    if any(not -5 <= (now - ev.observed_at).total_seconds() <= 120 for ev in evidence):
        return {
            "hypotheses": [],
            "root_cause_summary": "Evidence expired during collection; start a fresh investigation.",
            "investigation_status": "needs_review",
            "errors": ["Evidence is stale or future-dated"],
        }

    try:
        raw_hypotheses, summary = await generate_causal_analysis(
            incident_id=incident_id,
            anomaly_id=anomaly_id,
            namespace=namespace,
            deployment_name=deployment_name,
            evidence=evidence,
            mode=state.get("mode", "live"),
        )
    except Exception:
        return {
            "hypotheses": [],
            "root_cause_summary": "Model analysis unavailable; manual review required.",
            "investigation_status": "needs_review",
            "errors": ["Model analysis unavailable"],
        }

    verified_hypotheses = CitationValidatorGuard.validate_hypotheses(
        hypotheses=raw_hypotheses, available_evidence=evidence
    )

    return {
        "hypotheses": verified_hypotheses,
        "root_cause_summary": summary,
        "investigation_status": "causal_reasoning_completed",
    }


async def score_risk_node(state: InvestigationState) -> dict[str, Any]:
    """Node 4: Jev System-1 risk scoring for proposed remediation."""
    evidence = state.get("evidence", [])
    ns = state.get("namespace", "fixproof-demo")
    dep = state.get("deployment_name", "sample-api")

    template_hash = ""
    for ev in evidence:
        if ev.source == "kubernetes:deployment":
            template_hash = ev.raw_data.get("template_hash", "")

    candidate = RemediationCandidate(
        action_type="restore_known_good_template",
        parameters={
            "namespace": ns,
            "deployment_name": dep,
            "remove_env": ["FAIL_MODE"],
        },
        estimated_risk_level="guarded",
        reversible=True,
        template_hash=template_hash,
    )

    risk_eval = await jev.score_remediation_risk(candidate, evidence)

    return {
        "risk_tier": risk_eval.risk_tier,
        "risk_score": risk_eval.confidence,
        "requires_human_approval": risk_eval.requires_human_approval,
        "investigation_status": "risk_scored",
    }


async def synthesize_proposal_node(state: InvestigationState) -> dict[str, Any]:
    """Keep analysis advisory until a trusted baseline is registered by the API."""
    return {
        "remediation_proposal": None,
        "investigation_status": "needs_review",
        "errors": ["Trusted known-good template and exact approval binding are not configured"],
    }
