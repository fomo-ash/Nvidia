import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.models.domain import Incident, IncidentTrigger, InvestigationRequest

ORIGIN = "http://localhost:5173"
REPORT = {
    "target_id": "local-kind/fixproof-demo/sample-api",
    "target_uid": "fixture-uid-1",
    "symptom": "http_5xx_spike",
    "summary": "Sample requests return 5xx",
    "note": "Observed after fault injection",
}


def configure(monkeypatch, client):
    monkeypatch.setattr(settings, "operator_secret", "operator-test-secret")
    monkeypatch.setattr(settings, "session_signing_key", "signing-test-secret")
    monkeypatch.setattr(settings, "sample_target_uid", "fixture-uid-1")
    monkeypatch.setattr(settings, "local_demo_enabled", False)
    login = client.post(
        "/api/v1/session", json={"secret": "operator-test-secret"}, headers={"Origin": ORIGIN}
    )
    assert login.status_code == 200
    return {"Origin": ORIGIN, "X-CSRF-Token": login.json()["csrf_token"]}


def test_manual_report_replay_reuse_and_durable_queue(client, database, monkeypatch):
    headers = configure(monkeypatch, client)
    first = client.post(
        "/api/v1/incidents", json=REPORT, headers={**headers, "Idempotency-Key": "manual-1"}
    )
    assert first.status_code == 201
    assert first.json()["assessment"] == "unassessed"
    assert first.json()["reused"] is False
    replay = client.post(
        "/api/v1/incidents", json=REPORT, headers={**headers, "Idempotency-Key": "manual-1"}
    )
    assert replay.status_code == 201 and replay.json() == first.json()
    second = client.post(
        "/api/v1/incidents", json=REPORT, headers={**headers, "Idempotency-Key": "manual-2"}
    )
    assert second.status_code == 200 and second.json()["reused"] is True
    assert second.json()["incident_id"] == first.json()["incident_id"]
    with database[0]() as db:
        assert (
            db.scalar(select(func.count()).select_from(Incident).where(Incident.mode == "live"))
            == 1
        )
        assert db.scalar(select(func.count()).select_from(IncidentTrigger)) == 2
        assert db.scalar(select(func.count()).select_from(InvestigationRequest)) == 2
        with pytest.raises(IntegrityError):
            db.execute(text("UPDATE incident_triggers SET summary='changed'"))
        db.rollback()
    detail = client.get(f"/api/v1/incidents/{first.json()['incident_id']}").json()
    assert detail["target_uid"] == "fixture-uid-1" and detail["mode"] == "live"
    assert len(client.get(f"/api/v1/incidents/{detail['id']}/triggers").json()) == 2
    assert (
        client.post(f"/api/v1/incidents/{detail['id']}/investigate", headers=headers).status_code
        == 409
    )


def test_manual_report_denials_do_not_write(client, database, monkeypatch):
    headers = configure(monkeypatch, client)
    path = "/api/v1/incidents"
    assert (
        client.post(
            path,
            json={"title": "Demo", "severity": "high", "summary": "Synthetic"},
            headers=headers,
        ).status_code
        == 403
    )
    assert client.post(path, json=REPORT, headers=headers).status_code == 422
    assert (
        client.post(
            path, json=REPORT, headers={"Origin": ORIGIN, "Idempotency-Key": "no-csrf"}
        ).status_code
        == 403
    )
    assert (
        client.post(
            path,
            json={**REPORT, "target_uid": "wrong"},
            headers={**headers, "Idempotency-Key": "wrong-uid"},
        ).status_code
        == 409
    )
    assert (
        client.post(
            path,
            json={**REPORT, "note": "x" * 2001},
            headers={**headers, "Idempotency-Key": "long"},
        ).status_code
        == 422
    )
    assert (
        client.post(
            path,
            json=REPORT,
            headers={**headers, "Origin": "http://evil.invalid", "Idempotency-Key": "origin"},
        ).status_code
        == 403
    )
    with database[0]() as db:
        assert db.scalar(select(func.count()).select_from(IncidentTrigger)) == 0
