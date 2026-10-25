"""LangGraph investigation workflow nodes."""

from typing import Any
from app.decisions.jev_engine import JevDecisionEngine
from app.guardrails.allowlist import ActionAllowlistGuard
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

    if "prometheus" not in collected_sources:
        new_evidence.append(await mcp.query_metrics(window="1m"))

    if "kubernetes:deployment" not in collected_sources:
        new_evidence.append(await mcp.get_deployment_status(namespace=ns, deployment_name=dep))

    if "kubernetes:logs" not in collected_sources:
        new_evidence.append(await mcp.get_pod_logs(namespace=ns, deployment_name=dep, lines=50))

    if "direct:probe" not in collected_sources:
        new_evidence.append(await mcp.check_service_health())

    if "kubernetes:events" not in collected_sources:
        new_evidence.append(await mcp.get_pod_events(namespace=ns, limit=10))

    current_attempts = state.get("sufficiency_attempts", 0) + 1

    return {
        "evidence": new_evidence,
        "telemetry_completed": True,
        "sufficiency_attempts": current_attempts,
        "investigation_status": "telemetry_collected",
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

    raw_hypotheses, summary = await generate_causal_analysis(
        incident_id=incident_id,
        anomaly_id=anomaly_id,
        namespace=namespace,
        deployment_name=deployment_name,
        evidence=evidence,
    )

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
    """Node 5: Package validated proposal and enforce action allowlist."""
    ns = state.get("namespace", "fixproof-demo")
    dep = state.get("deployment_name", "sample-api")
    evidence = state.get("evidence", [])
    hypotheses = state.get("hypotheses", [])

    evidence_ids = []
    for h in hypotheses:
        if h.is_root_cause:
            evidence_ids.extend(h.supporting_evidence_ids)

    if not evidence_ids and evidence:
        evidence_ids = [ev.id for ev in evidence[:3]]

    template_hash = ""
    for ev in evidence:
        if ev.source == "kubernetes:deployment":
            template_hash = ev.raw_data.get("template_hash", "")

    action_type = "restore_known_good_template"
    params = {
        "namespace": ns,
        "deployment_name": dep,
        "expected_bad_template_hash": template_hash,
        "desired_good_template_hash": "sample-api-known-good-hash",
    }

    is_allowed, reason = ActionAllowlistGuard.validate_action(action_type, params)
    errors = []
    proposal = None

    if is_allowed:
        proposal = {
            "action_type": action_type,
            "parameters": params,
            "estimated_risk_level": "guarded",
            "reversible": True,
            "template_hash": template_hash,
            "evidence_ids": list(set(evidence_ids)),
        }
    else:
        errors.append(f"Proposal blocked by allowlist: {reason}")

    return {
        "remediation_proposal": proposal,
        "investigation_status": "awaiting_approval" if proposal else "failed",
        "errors": errors,
    }
