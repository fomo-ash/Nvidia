"""Unit tests for JevDecisionEngine with Laya fallback."""

import httpx
import pytest
from app.decisions.jev_engine import JevDecisionEngine
from app.schemas.state import EvidenceReference, RemediationCandidate


@pytest.mark.asyncio
async def test_jev_with_laya_http_fallback(monkeypatch):
    """Verify JevDecisionEngine falls back to Laya /v1/systemone when Jev key is mock/absent."""
    mock_answers = {
        "is_sufficient": {"noul": 0.88},
        "missing_source": {"choice": "none"},
    }

    called_urls = []

    def mock_post(request):
        called_urls.append(str(request.url))
        return httpx.Response(200, json={"answers": mock_answers})

    original_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kw: original_client(transport=httpx.MockTransport(mock_post), **kw),
    )

    engine = JevDecisionEngine(api_key="mock-key", laya_base_url="http://mock-laya:8000")
    ev_full = [
        EvidenceReference(
            id="EVD-1",
            content_hash="h1",
            source="prometheus",
            fact="metrics",
            trusted=True,
            mode="live",
        ),
        EvidenceReference(
            id="EVD-2",
            content_hash="h2",
            source="kubernetes:deployment",
            fact="deploy",
            trusted=True,
            mode="live",
        ),
    ]
    eval_result = await engine.evaluate_sufficiency(ev_full, attempt=1)
    assert eval_result.is_sufficient is True
    assert eval_result.confidence == 0.88
    assert "Laya" in eval_result.reason
    assert any("mock-laya:8000/v1/systemone" in url for url in called_urls)


@pytest.mark.asyncio
async def test_jev_with_laya_risk_fallback(monkeypatch):
    """Verify JevDecisionEngine risk scoring falls back to Laya endpoint."""
    mock_answers = {
        "risk_tier": {"choice": "low"},
        "requires_human_approval": {"noul": 0.95},
    }

    def mock_post(request):
        return httpx.Response(200, json={"answers": mock_answers})

    original_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kw: original_client(transport=httpx.MockTransport(mock_post), **kw),
    )

    engine = JevDecisionEngine(api_key="mock-key", laya_base_url="http://mock-laya:8000")
    candidate = RemediationCandidate(
        action_type="restore_known_good_template",
        parameters={"namespace": "fixproof-demo", "deployment_name": "sample-api"},
        template_hash="tmpl123",
    )
    risk_eval = await engine.score_remediation_risk(candidate, [])
    assert risk_eval.risk_tier == "low"
    assert risk_eval.requires_human_approval is True
    assert "Laya" in risk_eval.rationale
