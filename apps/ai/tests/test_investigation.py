"""Unit tests for FixProof AI Agent service."""

import pytest
from app.guardrails.allowlist import ActionAllowlistGuard
from app.guardrails.citations import CitationValidatorGuard
from app.schemas.state import EvidenceReference, Hypothesis, RemediationCandidate
from app.decisions.jev_engine import JevDecisionEngine
from app.graph.workflow import investigation_workflow


@pytest.mark.asyncio
async def test_guardrail_citation_validator():
    """Verify that only citations present in valid evidence are retained."""
    evidence = [
        EvidenceReference(
            id="EVD-12345678",
            content_hash="abc",
            source="prometheus",
            fact="5xx error rate 40%",
            trusted=True,
        )
    ]

    hypotheses = [
        Hypothesis(
            cause="Error injection active [EVD-12345678] and [EVD-fake9999]",
            confidence=0.9,
            supporting_evidence_ids=["EVD-12345678", "EVD-fake9999"],
            is_root_cause=True,
        )
    ]

    sanitized = CitationValidatorGuard.validate_hypotheses(hypotheses, evidence)
    assert len(sanitized) == 1
    assert "EVD-12345678" in sanitized[0].supporting_evidence_ids
    assert "EVD-fake9999" not in sanitized[0].supporting_evidence_ids


def test_guardrail_action_allowlist():
    """Verify that arbitrary commands or namespaces are rejected."""
    allowed, _ = ActionAllowlistGuard.validate_action(
        "restore_known_good_template",
        {"namespace": "fixproof-demo", "deployment_name": "sample-api"},
    )
    assert allowed is True

    blocked_action, _ = ActionAllowlistGuard.validate_action("delete_deployment", {})
    assert blocked_action is False

    blocked_ns, _ = ActionAllowlistGuard.validate_action(
        "restore_known_good_template",
        {"namespace": "kube-system", "deployment_name": "sample-api"},
    )
    assert blocked_ns is False


@pytest.mark.asyncio
async def test_jev_sufficiency_engine():
    """Verify Jev sufficiency evaluates core telemetry sources."""
    engine = JevDecisionEngine()
    ev_partial = [
        EvidenceReference(id="EVD-1", content_hash="h1", source="prometheus", fact="metrics", trusted=True)
    ]
    eval_partial = await engine.evaluate_sufficiency(ev_partial, attempt=1)
    assert eval_partial.is_sufficient is False

    ev_full = [
        EvidenceReference(id="EVD-1", content_hash="h1", source="prometheus", fact="metrics", trusted=True),
        EvidenceReference(id="EVD-2", content_hash="h2", source="kubernetes:deployment", fact="deploy", trusted=True),
    ]
    eval_full = await engine.evaluate_sufficiency(ev_full, attempt=1)
    assert eval_full.is_sufficient is True


@pytest.mark.asyncio
async def test_jev_risk_scoring():
    """Verify Jev risk scoring evaluates candidate action."""
    engine = JevDecisionEngine()
    candidate = RemediationCandidate(
        action_type="restore_known_good_template",
        parameters={"namespace": "fixproof-demo", "deployment_name": "sample-api"},
        template_hash="tmpl123",
    )
    risk_eval = await engine.score_remediation_risk(candidate, [])
    assert risk_eval.risk_tier == "medium"
    assert risk_eval.requires_human_approval is True


@pytest.mark.asyncio
async def test_investigation_workflow_execution():
    """Run full LangGraph workflow and verify state transitions and proposal generation."""
    initial_state = {
        "incident_id": "test-inc-001",
        "anomaly_id": "anom-001",
        "namespace": "fixproof-demo",
        "deployment_name": "sample-api",
        "mode": "live",
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

    config = {"configurable": {"thread_id": "test-thread-001"}}
    final_state = await investigation_workflow.ainvoke(initial_state, config=config)

    assert final_state["investigation_status"] == "awaiting_approval"
    assert len(final_state["evidence"]) > 0
    assert len(final_state["hypotheses"]) > 0
    assert final_state["remediation_proposal"] is not None
    assert final_state["remediation_proposal"]["action_type"] == "restore_known_good_template"
