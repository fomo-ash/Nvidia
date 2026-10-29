from datetime import datetime, timezone
import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.llm.retained import StoredEvidence, parse_analysis
from app.config import settings
from app.main import app


def evidence():
    return StoredEvidence(
        id=uuid4(),
        source="prometheus",
        observed_at=datetime.now(timezone.utc),
        fact="Measured 120 requests and 120 5xx",
        raw_data={"total_requests": 120, "error_requests_5xx": 120},
    )


def result(item):
    return {
        "summary": "Elevated errors observed",
        "hypotheses": [
            {
                "cause": "Possible deployment fault",
                "supporting_evidence_ids": [str(item.id)],
                "contradicting_evidence_ids": [],
                "uncertainty": "medium",
            }
        ],
        "gaps": [],
        "advisory_action": "restore_known_good_template",
    }


def test_structured_analysis_citations_and_actions():
    item = evidence()
    good = result(item)
    assert parse_analysis(json.dumps(good), [item]).hypotheses[0].uncertainty == "medium"
    for bad in [
        good | {"advisory_action": "run_shell"},
        good | {"hypotheses": []},
        good | {"confidence": 0.99},
    ]:
        with pytest.raises(ValueError):
            parse_analysis(json.dumps(bad), [item])
    bad = result(item)
    bad["hypotheses"][0]["supporting_evidence_ids"] = [str(uuid4())]
    with pytest.raises(ValueError):
        parse_analysis(json.dumps(bad), [item])
    with pytest.raises(ValueError):
        parse_analysis("root cause confirmed", [item])


def test_service_auth_and_duplicate_ids(monkeypatch):
    monkeypatch.setattr(settings, "SERVICE_AUTH_TOKEN", "test-service-key-" * 3)
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert client.post("/analyze", json={}).status_code == 401
        item = evidence()
        body = {
            "incident_id": str(uuid4()),
            "target_uid": "uid",
            "evidence": [item.model_dump(mode="json")] * 2,
        }
        assert (
            client.post(
                "/analyze",
                json=body,
                headers={"Authorization": "Bearer " + settings.SERVICE_AUTH_TOKEN},
            ).status_code
            == 422
        )
