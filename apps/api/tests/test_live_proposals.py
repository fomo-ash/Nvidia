"""Exact read-only proposals for retained live investigations."""

import hashlib
import json
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
import pytest

from app import worker
from app.core.config import settings
from app.models.domain import Recommendation, TrustedBaseline
from app.services.live_evidence import validate_envelope
from app.services.live_proposals import faulty_template, template_hash
from test_incident_intake import REPORT, configure
from test_live_evidence import envelope


GOOD = {
    "spec": {"containers": [{"name": "sample-api", "env": [{"name": "FAIL_MODE", "value": "off"}]}]}
}
BAD_HASH = template_hash(faulty_template(GOOD))


class Reader:
    def collect(self, source, uid):
        data = envelope(source, uid)
        if source == "kubernetes:deployment":
            data["raw_data"] = {
                "uid": uid,
                "namespace": "fixproof-demo",
                "deployment_name": "sample-api",
                "template_hash": BAD_HASH,
                "resource_version": "101",
            }
        data["content_hash"] = hashlib.sha256(
            json.dumps(
                {key: value for key, value in data.items() if key != "content_hash"},
                sort_keys=True,
            ).encode()
        ).hexdigest()
        return validate_envelope(data, source, uid)

    def analyze(self, incident_id, target_uid, evidence, gaps):
        return {
            "provider": "nebius",
            "model": "test-nemotron",
            "analysis": {
                "summary": "Configuration fault with observed 5xx traffic",
                "hypotheses": [
                    {
                        "cause": "Bad FAIL_MODE may cause the fault",
                        "supporting_evidence_ids": [evidence[0]["id"]],
                        "contradicting_evidence_ids": [],
                        "uncertainty": "medium",
                    }
                ],
                "gaps": [],
                "advisory_action": "restore_known_good_template",
            },
        }


def setup_live(client, database, monkeypatch):
    headers = configure(monkeypatch, client)
    report = client.post(
        "/api/v1/incidents",
        json=REPORT,
        headers={
            **headers,
            "Idempotency-Key": "live-proposal-report",
        },
    )
    assert report.status_code == 201
    monkeypatch.setattr(settings, "analysis_enabled", True)
    assert worker.run_once(database[0], Reader())
    incident_id = report.json()["incident_id"]
    run_id = client.get(f"/api/v1/incidents/{incident_id}/investigations").json()[0]["id"]
    return headers, incident_id, run_id


def register(client, headers, template=GOOD, key="register-good"):
    return client.post(
        "/api/v1/trusted-baselines",
        json={
            "target_uid": "fixture-uid-1",
            "template": template,
            "template_hash": template_hash(template),
        },
        headers={**headers, "Idempotency-Key": key},
    )


def test_live_proposal_approval_requires_exact_retained_state(client, database, monkeypatch):
    headers, incident_id, run_id = setup_live(client, database, monkeypatch)
    assert register(client, headers).status_code == 201
    duplicate = register(client, headers, key="register-again")
    assert duplicate.status_code == 201
    assert client.get("/api/v1/trusted-baselines/current").json()["template_hash"] == template_hash(
        GOOD
    )
    changed = {
        "spec": {
            "containers": [
                {
                    "name": "sample-api",
                    "env": [{"name": "FAIL_MODE", "value": "off"}, {"name": "EXTRA", "value": "x"}],
                }
            ]
        }
    }
    assert register(client, headers, changed, "register-changed").status_code == 409
    monkeypatch.setattr(
        "app.services.live_evidence.LiveReader.collect",
        lambda self, source, uid: Reader().collect(source, uid),
    )
    path = f"/api/v1/incidents/{incident_id}/proposals"
    body = {"investigation_id": run_id}
    response = client.post(
        path,
        json=body,
        headers={
            **headers,
            "Idempotency-Key": "propose-one",
        },
    )
    assert response.status_code == 201, response.text
    proposal = response.json()
    assert proposal["action"] == "restore_known_good_template"
    assert proposal["parameters"]["expected_bad_template_hash"] == BAD_HASH
    assert proposal["parameters"]["desired_good_template_hash"] == template_hash(GOOD)
    assert len(proposal["evidence"]) == 5
    replay = client.post(
        path,
        json=body,
        headers={
            **headers,
            "Idempotency-Key": "propose-one",
        },
    )
    assert replay.json() == proposal and replay.headers["Idempotency-Replayed"] == "true"
    approve = client.post(
        f"/api/v1/recommendations/{proposal['id']}/approve",
        json={"proposal_hash": proposal["proposal_hash"]},
        headers=headers,
    )
    assert approve.status_code == 200, approve.text
    assert approve.json()["status"] == "approved"
    assert (
        client.post(
            f"/api/v1/recommendations/{proposal['id']}/execute",
            json={"proposal_hash": proposal["proposal_hash"]},
            headers={**headers, "Idempotency-Key": "no-live-execution"},
        ).status_code
        == 409
    )
    with database[0]() as db:
        assert db.get(TrustedBaseline, UUID(proposal["parameters"]["trusted_baseline_id"]))
        assert db.scalar(select(Recommendation).where(Recommendation.id == UUID(proposal["id"])))
        with pytest.raises(IntegrityError):
            db.execute(text("UPDATE trusted_baselines SET template_hash='changed'"))
        db.rollback()


def test_live_proposal_denies_missing_baseline_and_current_drift(client, database, monkeypatch):
    headers, incident_id, run_id = setup_live(client, database, monkeypatch)
    path = f"/api/v1/incidents/{incident_id}/proposals"
    body = {"investigation_id": run_id}
    assert (
        client.post(
            path,
            json=body,
            headers={
                **headers,
                "Idempotency-Key": "before-baseline",
            },
        ).status_code
        == 409
    )
    assert register(client, headers).status_code == 201
    response = client.post(
        path,
        json=body,
        headers={
            **headers,
            "Idempotency-Key": "after-baseline",
        },
    )
    assert response.status_code == 201, response.text
    proposal = response.json()

    def drift(self, source, uid):
        value = Reader().collect(source, uid)
        value["raw_data"]["resource_version"] = "102"
        return value

    monkeypatch.setattr("app.services.live_evidence.LiveReader.collect", drift)
    result = client.post(
        f"/api/v1/recommendations/{proposal['id']}/approve",
        json={"proposal_hash": proposal["proposal_hash"]},
        headers=headers,
    )
    assert result.status_code == 409
    assert client.get(f"/api/v1/recommendations/{proposal['id']}").json()["status"] == "proposed"


def approved_live(client, database, monkeypatch):
    headers, incident_id, run_id = setup_live(client, database, monkeypatch)
    assert register(client, headers).status_code == 201
    monkeypatch.setattr(
        "app.services.live_evidence.LiveReader.collect",
        lambda self, source, uid: Reader().collect(source, uid),
    )
    proposal = client.post(
        f"/api/v1/incidents/{incident_id}/proposals",
        json={"investigation_id": run_id},
        headers={
            **headers,
            "Idempotency-Key": "propose-execution",
        },
    ).json()
    result = client.post(
        f"/api/v1/recommendations/{proposal['id']}/approve",
        json={"proposal_hash": proposal["proposal_hash"]},
        headers=headers,
    )
    assert result.status_code == 200
    monkeypatch.setattr(settings, "live_execution_enabled", True)
    monkeypatch.setattr(settings, "execution_signing_key", "test-execution-key-" * 3)
    return headers, proposal


def test_live_execution_claim_is_single_use(client, database, monkeypatch):
    headers, proposal = approved_live(client, database, monkeypatch)
    sent = []

    def post(url, payload, **kwargs):
        sent.append(payload)
        assert payload["desired_template"] == GOOD
        return {"status": "succeeded", "details": {"mutation_performed": True}}

    monkeypatch.setattr("app.services.live_evidence.post", post)
    path = f"/api/v1/recommendations/{proposal['id']}/execute"
    h = {**headers, "Idempotency-Key": "execute-once"}
    result = client.post(path, json={"proposal_hash": proposal["proposal_hash"]}, headers=h)
    assert result.status_code == 201, result.text
    assert result.json()["status"] == "succeeded"
    assert len(sent) == 1 and sent[0]["execution_id"] == result.json()["id"]
    replay = client.post(path, json={"proposal_hash": proposal["proposal_hash"]}, headers=h)
    assert replay.json() == result.json() and len(sent) == 1
    assert (
        client.post(
            path,
            json={"proposal_hash": proposal["proposal_hash"]},
            headers={
                **headers,
                "Idempotency-Key": "execute-again",
            },
        ).status_code
        == 409
    )


def test_unknown_live_outcome_stays_pending_until_observed(client, database, monkeypatch):
    headers, proposal = approved_live(client, database, monkeypatch)
    calls = []

    def timeout(url, payload, **kwargs):
        calls.append(payload["execution_id"])
        raise TimeoutError("unknown network result")

    monkeypatch.setattr("app.services.live_evidence.post", timeout)
    path = f"/api/v1/recommendations/{proposal['id']}/execute"
    h = {**headers, "Idempotency-Key": "unknown-once"}
    result = client.post(path, json={"proposal_hash": proposal["proposal_hash"]}, headers=h)
    assert result.status_code == 202 and result.json()["status"] == "pending"
    assert result.json()["result"]["outcome_unknown"] is True
    assert (
        client.post(path, json={"proposal_hash": proposal["proposal_hash"]}, headers=h).status_code
        == 202
    )
    assert len(calls) == 1
    execution_id = result.json()["id"]

    def observed(self, source, uid):
        value = Reader().collect(source, uid)
        value["raw_data"].update(
            {
                "execution_id": execution_id,
                "template_hash": template_hash(GOOD),
                "resource_version": "102",
            }
        )
        return value

    monkeypatch.setattr("app.services.live_evidence.LiveReader.collect", observed)
    reconciled = client.post(
        f"/api/v1/executions/{execution_id}/reconcile",
        json={},
        headers={
            **headers,
            "Idempotency-Key": "reconcile-once",
        },
    )
    assert reconciled.status_code == 200, reconciled.text
    assert reconciled.json()["status"] == "succeeded"
    assert len(calls) == 1


def test_live_execution_denies_target_drift_before_adapter(client, database, monkeypatch):
    headers, proposal = approved_live(client, database, monkeypatch)
    sent = []

    def post(*args, **kwargs):
        sent.append((args, kwargs))
        raise AssertionError("Mutation adapter must not run")

    def drift(self, source, uid):
        value = Reader().collect(source, uid)
        value["raw_data"]["resource_version"] = "changed-after-approval"
        return value

    monkeypatch.setattr("app.services.live_evidence.LiveReader.collect", drift)
    monkeypatch.setattr("app.services.live_evidence.post", post)
    response = client.post(
        f"/api/v1/recommendations/{proposal['id']}/execute",
        json={"proposal_hash": proposal["proposal_hash"]},
        headers={**headers, "Idempotency-Key": "drift-denied"},
    )
    assert response.status_code == 409
    assert sent == []


def test_live_verdict_requires_fresh_attributable_measurements(client, database, monkeypatch):
    from datetime import datetime, timezone

    headers, proposal = approved_live(client, database, monkeypatch)

    def post(url, payload, **kwargs):
        if url.endswith("/restore_known_good_template"):
            return {"status": "succeeded", "details": {"mutation_performed": True}}
        stamp = datetime.now(timezone.utc).isoformat()
        return {
            "status": "passed", "mode": "live", "details": {"reason": "Fresh recovery"},
            "measurements": [
                {"name": "rollout_available", "source": "kubernetes:deployment", "observed_at": stamp,
                 "value": 1, "threshold": 1, "operator": "gte"},
                *[
                    {"name": f"health_probe_{index}", "source": "direct:probe", "observed_at": stamp,
                     "value": 200, "threshold": 200, "operator": "eq"}
                    for index in range(1, 4)
                ],
                {"name": "work_requests", "source": "prometheus", "observed_at": stamp,
                 "value": 120, "threshold": 20, "operator": "gte"},
                {"name": "http_5xx_ratio", "source": "prometheus", "observed_at": stamp,
                 "value": 0, "threshold": 0.01, "operator": "lt"},
            ],
        }

    monkeypatch.setattr("app.services.live_evidence.post", post)
    execution = client.post(
        f"/api/v1/recommendations/{proposal['id']}/execute",
        json={"proposal_hash": proposal["proposal_hash"]},
        headers={**headers, "Idempotency-Key": "live-execution-verified"},
    )
    assert execution.status_code == 201
    assert execution.json()["status"] == "succeeded"
    verify = client.post(
        f"/api/v1/executions/{execution.json()['id']}/verify", json={},
        headers={**headers, "Idempotency-Key": "fresh-live-verdict"},
    )
    assert verify.status_code == 201, verify.text
    assert verify.json()["status"] == "passed"
