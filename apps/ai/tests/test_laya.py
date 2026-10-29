"""Provider-selection and fail-closed tests for System-1 decisions."""

from datetime import datetime, timezone

import httpx
import pytest

from app.decisions.jev_engine import JevDecisionEngine
from app.schemas.state import EvidenceReference, RemediationCandidate


def evidence(*sources: str, trusted: bool = True) -> list[EvidenceReference]:
    observed_at = datetime.now(timezone.utc)
    return [
        EvidenceReference(
            id=f"EVD-{index}",
            content_hash=f"hash-{index}",
            source=source,
            fact=f"observed {source}",
            trusted=trusted,
            mode="live",
            observed_at=observed_at,
        )
        for index, source in enumerate(sources, start=1)
    ]


def sufficiency_answers(**overrides):
    answers = {
        "is_sufficient": {"noul": 0.88},
        "missing_source": {"choice": "none"},
        "is_active_outage": {"noul": 0.91},
        "severity": {"score": "critical"},
    }
    answers.update(overrides)
    return answers


def risk_answers(**overrides):
    answers = {
        "risk_tier": {"choice": "low"},
        "requires_human_approval": {"noul": 0.05},
        "is_reversible": {"noul": 0.9},
    }
    answers.update(overrides)
    return answers


def install_transport(monkeypatch, responder):
    original_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original_client(transport=httpx.MockTransport(responder), **kwargs),
    )


@pytest.mark.asyncio
async def test_policy_provider_never_attempts_network(monkeypatch):
    def forbidden(**kwargs):
        pytest.fail(f"policy provider created an HTTP client: {kwargs}")

    monkeypatch.setattr(httpx, "AsyncClient", forbidden)
    engine = JevDecisionEngine(api_key="live-key", provider="policy")

    result = await engine.evaluate_sufficiency(evidence("prometheus", "kubernetes:deployment"))

    assert result.is_sufficient is True
    assert result.is_active_outage is False
    assert result.severity_level == "unknown"
    assert "Deterministic policy" in result.reason


@pytest.mark.asyncio
async def test_laya_provider_uses_compatible_endpoint_and_score_answer(monkeypatch):
    called_urls = []

    def respond(request):
        called_urls.append(str(request.url))
        return httpx.Response(200, json={"answers": sufficiency_answers()})

    install_transport(monkeypatch, respond)
    engine = JevDecisionEngine(
        api_key="mock-key",
        laya_base_url="http://system1-policy:8000",
        provider="laya",
    )

    result = await engine.evaluate_sufficiency(evidence("prometheus", "kubernetes:deployment"))

    assert result.is_sufficient is True
    assert result.confidence == 0.88
    assert result.severity_level == "critical"
    assert "validated advisory answers" in result.reason
    assert called_urls == ["http://system1-policy:8000/v1/systemone"]


@pytest.mark.asyncio
async def test_jev_provider_uses_jev_only_when_selected(monkeypatch):
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json={"answers": sufficiency_answers()})

    install_transport(monkeypatch, respond)
    engine = JevDecisionEngine(
        api_key="live-key",
        base_url="http://mock-jev:9000",
        laya_base_url="http://unused-laya:8000",
        provider="jev",
    )

    result = await engine.evaluate_sufficiency(evidence("prometheus", "kubernetes:deployment"))

    assert result.is_sufficient is True
    assert [str(request.url) for request in requests] == ["http://mock-jev:9000/v1/systemone"]
    assert requests[0].headers["authorization"] == "Bearer live-key"


@pytest.mark.asyncio
async def test_external_answer_cannot_bypass_physical_evidence_gate(monkeypatch):
    def respond(request):
        return httpx.Response(200, json={"answers": sufficiency_answers()})

    install_transport(monkeypatch, respond)
    engine = JevDecisionEngine(laya_base_url="http://system1-policy:8000", provider="laya")

    result = await engine.evaluate_sufficiency(evidence("prometheus"))

    assert result.is_sufficient is False
    assert result.missing_sources == ["kubernetes:deployment"]
    assert "physical evidence gate passed=False" in result.reason


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalid_answers",
    [
        sufficiency_answers(is_sufficient={"noul": 1.5}),
        sufficiency_answers(severity={"score": "catastrophic"}),
        {"is_sufficient": {"noul": 0.99}},
    ],
)
async def test_malformed_sufficiency_answers_fall_back_to_policy(monkeypatch, invalid_answers):
    def respond(request):
        return httpx.Response(200, json={"answers": invalid_answers})

    install_transport(monkeypatch, respond)
    engine = JevDecisionEngine(laya_base_url="http://system1-policy:8000", provider="laya")

    result = await engine.evaluate_sufficiency(evidence("prometheus"))

    assert result.is_sufficient is False
    assert result.missing_sources == ["kubernetes:deployment"]
    assert "Deterministic policy" in result.reason


@pytest.mark.asyncio
async def test_untrusted_source_does_not_satisfy_policy_gate():
    engine = JevDecisionEngine(provider="policy")

    result = await engine.evaluate_sufficiency(
        evidence("prometheus", "kubernetes:deployment", trusted=False)
    )

    assert result.is_sufficient is False
    assert result.missing_sources == ["prometheus", "kubernetes:deployment"]


@pytest.mark.asyncio
async def test_advisory_low_risk_never_removes_human_approval(monkeypatch):
    def respond(request):
        return httpx.Response(200, json={"answers": risk_answers()})

    install_transport(monkeypatch, respond)
    engine = JevDecisionEngine(laya_base_url="http://system1-policy:8000", provider="laya")
    candidate = RemediationCandidate(
        action_type="restore_known_good_template",
        parameters={"namespace": "fixproof-demo", "deployment_name": "sample-api"},
        template_hash="tmpl123",
    )

    result = await engine.score_remediation_risk(candidate, [])

    assert result.risk_tier == "low"
    assert result.requires_human_approval is True
    assert result.is_reversible is True
    assert "still requires explicit human approval" in result.rationale


@pytest.mark.asyncio
async def test_invalid_risk_answer_falls_back_to_guarded_policy(monkeypatch):
    def respond(request):
        invalid = risk_answers(risk_tier={"choice": "none"})
        return httpx.Response(200, json={"answers": invalid})

    install_transport(monkeypatch, respond)
    engine = JevDecisionEngine(laya_base_url="http://system1-policy:8000", provider="laya")
    candidate = RemediationCandidate(
        action_type="restore_known_good_template",
        parameters={"namespace": "fixproof-demo", "deployment_name": "sample-api"},
        template_hash="tmpl123",
    )

    result = await engine.score_remediation_risk(candidate, [])

    assert result.risk_tier == "medium"
    assert result.requires_human_approval is True
    assert "no validated external risk assessment" in result.rationale
