"""Unit tests for FixProof AI Agent service."""

import pytest

from app.chat.agent import get_chat_agent
from app.decisions.jev_engine import JevDecisionEngine
from app.graph.workflow import investigation_workflow
from app.guardrails.allowlist import ActionAllowlistGuard
from app.guardrails.citations import CitationValidatorGuard
from app.llm.nemotron import (
    _parse_or_ground_hypotheses,
    generate_causal_analysis,
    live_model_available,
    live_model_config,
)
from app.schemas.state import EvidenceReference, Hypothesis, RemediationCandidate


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
async def test_investigation_workflow_execution(monkeypatch):
    """Missing MCP evidence must leave the investigation for review."""
    from app.graph import nodes

    async def unavailable(*args, **kwargs):
        raise RuntimeError("MCP offline")

    for method in (
        "query_metrics", "get_deployment_status", "get_pod_logs",
        "get_pod_events", "check_service_health",
    ):
        monkeypatch.setattr(nodes.mcp, method, unavailable)
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

    assert final_state["investigation_status"] == "needs_review"
    assert final_state["remediation_proposal"] is None


def test_model_response_requires_real_citations():
    evidence = [EvidenceReference(
        id="EVD-12345678", content_hash="a" * 64,
        source="prometheus", fact="observed error rate", trusted=True,
    )]
    with pytest.raises(ValueError):
        _parse_or_ground_hypotheses("Likely rollout issue.", evidence)
    with pytest.raises(ValueError):
        _parse_or_ground_hypotheses("See EVD-deadbeef.", evidence)


@pytest.mark.asyncio
async def test_live_model_never_uses_synthetic_fallback(monkeypatch):
    from app.llm import nemotron

    monkeypatch.setattr(nemotron.settings, "LLM_PROVIDER", "nebius")
    monkeypatch.setattr(nemotron.settings, "NEBIUS_API_KEY", "mock-nebius-key")
    with pytest.raises(RuntimeError):
        await generate_causal_analysis(
            "inc", "anom", "fixproof-demo", "sample-api", [], mode="live"
        )


def test_groq_provider_uses_only_groq_credentials(monkeypatch):
    from app.llm import nemotron

    monkeypatch.setattr(nemotron.settings, "LLM_PROVIDER", "groq")
    monkeypatch.setattr(nemotron.settings, "GROQ_API_KEY", "groq-test-key")
    monkeypatch.setattr(nemotron.settings, "NEBIUS_API_KEY", "nebius-test-key")
    assert live_model_config() == (
        nemotron.settings.GROQ_MODEL,
        "groq-test-key",
        "https://api.groq.com/openai/v1",
    )
    assert live_model_available()
    monkeypatch.setattr(nemotron.settings, "GROQ_API_KEY", "")
    assert not live_model_available()
    monkeypatch.setattr(nemotron.settings, "LLM_PROVIDER", "other")
    assert not live_model_available()
    with pytest.raises(RuntimeError):
        live_model_config()


def test_chat_agent_builds_with_installed_langgraph(monkeypatch):
    from app.llm import nemotron

    monkeypatch.setattr(nemotron.settings, "LLM_PROVIDER", "groq")
    monkeypatch.setattr(nemotron.settings, "GROQ_API_KEY", "groq-test-key")
    assert get_chat_agent() is not None
