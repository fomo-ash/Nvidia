from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, text

from app.models.domain import AuditEvent, Recommendation


def test_liveness_readiness_and_metrics(client):
    assert client.get("/health/live").json() == {"status": "ok"}
    assert client.get("/health/ready").status_code == 200
    assert "python_info" in client.get("/metrics").text


def test_readiness_detects_outdated_schema(client, database):
    factory, _, _ = database
    with factory() as db:
        current_revision = db.scalar(text("SELECT version_num FROM alembic_version"))
        db.execute(text("UPDATE alembic_version SET version_num='0001_initial'"))
        db.commit()
    try:
        assert client.get("/health/ready").status_code == 503
    finally:
        with factory() as db:
            db.execute(
                text("UPDATE alembic_version SET version_num=:revision"),
                {"revision": current_revision},
            )
            db.commit()


def test_cors_allows_frontend_and_rejects_other_origins(client):
    headers = {
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    }
    response = client.options("/api/v1/incidents", headers=headers)
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == headers["Origin"]
    headers["Origin"] = "https://untrusted.example"
    assert client.options("/api/v1/incidents", headers=headers).status_code == 400


def test_incident_validation_pagination_and_audit(client, incident):
    assert client.get("/api/v1/incidents?limit=1").json()[0]["id"] == incident["id"]
    assert client.get("/api/v1/incidents?offset=1").json() == []
    assert client.get("/api/v1/incidents?limit=101").status_code == 422
    assert client.get("/api/v1/incidents?offset=-1").status_code == 422
    assert (
        client.post(
            "/api/v1/incidents", json={"title": "   ", "severity": "high", "summary": "bad"}
        ).status_code
        == 422
    )
    events = client.get("/api/v1/audit-events").json()
    assert events[0]["action"] == "created"
    assert events[0]["actor"] == "local-demo-user"


@pytest.mark.parametrize("suffix", ["", "/evidence", "/timeline", "/recommendations"])
def test_nonexistent_incident_has_no_fabricated_data(client, suffix):
    assert client.get(f"/api/v1/incidents/{uuid4()}{suffix}").status_code == 404


def test_evidence_is_retained_and_timeline_comes_from_audit(client, incident, proposal):
    path = f"/api/v1/incidents/{incident['id']}"
    assert client.get(path + "/evidence").json() == proposal["evidence"]
    assert proposal["evidence"][0]["mode"] == "synthetic"
    assert proposal["evidence"][0]["trusted"] is False
    assert [e["event"] for e in client.get(path + "/timeline").json()] == [
        "proposed",
        "investigated",
        "created",
    ]


def test_no_evidence_before_investigation(client, incident):
    assert client.get(f"/api/v1/incidents/{incident['id']}/evidence").json() == []


def test_approval_requires_exact_digest_and_rejects_actor_spoofing(client, proposal):
    path = f"/api/v1/recommendations/{proposal['id']}/approve"
    assert client.post(path, json={}).status_code == 422
    assert client.post(path, json={"proposal_hash": "0" * 64}).status_code == 409
    assert (
        client.post(
            path, json={"proposal_hash": proposal["proposal_hash"], "actor": "admin"}
        ).status_code
        == 422
    )
    response = client.post(path, json={"proposal_hash": proposal["proposal_hash"]})
    assert response.status_code == 200
    assert response.json()["status"] == "approved"
    assert client.post(path, json={"proposal_hash": proposal["proposal_hash"]}).status_code == 409
    assert client.post(path.replace("approve", "reject"), json={}).status_code == 409


def test_new_version_supersedes_prior_approval(client, incident, proposal):
    path = f"/api/v1/recommendations/{proposal['id']}"
    assert (
        client.post(
            path + "/approve", json={"proposal_hash": proposal["proposal_hash"]}
        ).status_code
        == 200
    )
    newer = client.post(f"/api/v1/incidents/{incident['id']}/investigate").json()
    assert newer["version"] == 2
    assert newer["proposal_hash"] != proposal["proposal_hash"]
    assert client.get(path).json()["status"] == "superseded"
    assert (
        client.post(
            path + "/approve", json={"proposal_hash": proposal["proposal_hash"]}
        ).status_code
        == 409
    )


@pytest.mark.parametrize("change", ["expired", "parameters", "evidence", "legacy"])
def test_unreviewable_proposals_cannot_be_approved(client, database, proposal, change):
    factory, _, _ = database
    with factory() as db:
        item = db.get(Recommendation, UUID(proposal["id"]))
        if change == "expired":
            item.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        elif change == "parameters":
            item.parameters = {"strategy": "different"}
        elif change == "evidence":
            item.evidence = []
        else:
            item.proposal_hash = None
        db.commit()
    response = client.post(
        f"/api/v1/recommendations/{proposal['id']}/approve",
        json={"proposal_hash": proposal["proposal_hash"]},
    )
    assert response.status_code == 409
    with factory() as db:
        assert not db.scalars(select(AuditEvent).where(AuditEvent.action == "approved")).all()


def test_rejection_is_final_and_missing_recommendation_returns_404(client, proposal):
    path = f"/api/v1/recommendations/{proposal['id']}"
    assert client.post(path + "/reject", json={}).json()["status"] == "rejected"
    assert (
        client.post(
            path + "/approve", json={"proposal_hash": proposal["proposal_hash"]}
        ).status_code
        == 409
    )
    assert client.post(f"/api/v1/recommendations/{uuid4()}/reject", json={}).status_code == 404


def test_cost_api_persists_an_explicitly_synthetic_analysis(client):
    response = client.post("/api/v1/cost-analyses")
    assert response.status_code == 201
    assert response.json()["mode"] == "synthetic"
    assert response.json()["estimated_savings"]["amount"] == 525
    assert client.get(f"/api/v1/cost-analyses/{response.json()['id']}").status_code == 200
