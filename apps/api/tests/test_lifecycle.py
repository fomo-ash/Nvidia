from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.identity import Actor, get_actor
from app.main import app
from app.models.domain import (
    Approval,
    AuditEvent,
    CostAnalysis,
    EvidenceItem,
    Execution,
    IdempotencyRecord,
    Investigation,
    Recommendation,
)
from app.services.idempotency import digest
from app.services.recommendations import proposal_digest
from app.services.operations import ActionResult, Observation, get_operations_adapter


@pytest.fixture
def approved(client, proposal):
    assert (
        client.post(
            f"/api/v1/recommendations/{proposal['id']}/approve",
            json={"proposal_hash": proposal["proposal_hash"]},
        ).status_code
        == 200
    )
    return proposal


class TestAdapter:
    __test__ = False
    name = "synthetic-test-double"

    def __init__(self):
        self.calls = 0
        self.observations = 0
        self.value = 1

    def execute(self, execution):
        self.calls += 1
        return ActionResult(status="succeeded", details={"mode": "synthetic", "test_double": True})

    def verify(self, execution):
        self.observations += 1
        return Observation(
            status="passed" if self.value < 5 else "failed",
            mode="synthetic",
            details={"test_double": True},
            measurements=[
                {
                    "name": "error_percent",
                    "source": "synthetic-independent-probe",
                    "observed_at": datetime.now(timezone.utc),
                    "value": self.value,
                    "threshold": 5,
                    "operator": "lt",
                }
            ],
        )


@pytest.fixture
def adapter():
    value = TestAdapter()
    app.dependency_overrides[get_operations_adapter] = lambda: value
    try:
        yield value
    finally:
        app.dependency_overrides.pop(get_operations_adapter, None)


def execute(client, proposal, key="execution-1"):
    return client.post(
        f"/api/v1/recommendations/{proposal['id']}/execute",
        json={"proposal_hash": proposal["proposal_hash"]},
        headers={"Idempotency-Key": key},
    )


def test_normalized_investigation_and_evidence_have_provenance(client, incident, proposal):
    identifier = proposal["investigation_id"]
    assert (
        client.get(f"/api/v1/investigations/{identifier}").json()["incident_id"] == incident["id"]
    )
    assert (
        client.get(f"/api/v1/incidents/{incident['id']}/investigations").json()[0]["id"]
        == identifier
    )
    item = client.get(f"/api/v1/investigations/{identifier}/evidence").json()[0]
    assert item["content_hash"] == digest(proposal["evidence"][0])
    assert item["trust_label"] == "untrusted" and item["trusted"] is False
    assert item["investigation_id"] == identifier


def test_approval_is_a_separate_server_owned_record(client, approved):
    record = client.get(f"/api/v1/recommendations/{approved['id']}/approval").json()
    assert record["recommendation_version"] == approved["version"]
    assert record["proposal_hash"] == approved["proposal_hash"]
    assert record["decision"] == "approved" and record["actor"] == "local-demo-user"
    assert client.get(f"/api/v1/approvals/{record['id']}").status_code == 200
    assert client.get("/api/v1/approvals").json()[0]["id"] == record["id"]


def test_default_execution_records_failure_without_claiming_a_mutation(client, approved):
    response = execute(client, approved)
    assert response.status_code == 201
    value = response.json()
    assert value["status"] == "failed"
    assert value["result"]["mutation_performed"] is False
    assert value["adapter"] == "unconfigured"
    assert client.get(f"/api/v1/executions/{value['id']}").json()["status"] == "failed"
    assert (
        client.get(f"/api/v1/recommendations/{approved['id']}").json()["status"]
        == "execution_failed"
    )
    assert execute(client, approved).json() == value
    assert execute(client, approved, "other-key").status_code == 409
    assert (
        client.post(
            f"/api/v1/executions/{value['id']}/verify",
            json={},
            headers={"Idempotency-Key": "verify-1"},
        ).status_code
        == 409
    )


@pytest.mark.parametrize(
    "value,expected,state", [(1, "passed", "verified"), (9, "failed", "verification_failed")]
)
def test_verification_uses_independent_measurements(
    client, approved, adapter, value, expected, state
):
    adapter.value = value
    action = execute(client, approved).json()
    assert action["status"] == "succeeded"
    assert client.get(f"/api/v1/recommendations/{approved['id']}").json()["status"] == "executed"
    path = f"/api/v1/executions/{action['id']}/verify"
    response = client.post(path, json={}, headers={"Idempotency-Key": "verify-1"})
    assert response.status_code == 201
    verification = response.json()
    assert verification["status"] == expected
    assert verification["observations"]["measurements"][0]["value"] == value
    assert (
        client.get(f"/api/v1/executions/{action['id']}/verification").json()["id"]
        == verification["id"]
    )
    assert client.get(f"/api/v1/verifications/{verification['id']}").status_code == 200
    assert client.get(f"/api/v1/recommendations/{approved['id']}").json()["status"] == state
    assert (
        client.post(path, json={}, headers={"Idempotency-Key": "verify-1"}).json() == verification
    )
    assert client.post(path, json={}, headers={"Idempotency-Key": "verify-2"}).status_code == 409
    assert execute(client, approved).json() == action
    assert adapter.calls == 1 and adapter.observations == 1


def test_verification_cannot_be_fabricated_by_request_or_adapter(client, approved, adapter):
    with pytest.raises(ValidationError):
        Observation(status="passed", details={})
    value = execute(client, approved).json()
    path = f"/api/v1/executions/{value['id']}/verify"
    assert (
        client.post(
            path, json={"status": "passed"}, headers={"Idempotency-Key": "verify-1"}
        ).status_code
        == 422
    )
    adapter.verify = lambda execution: {"status": "passed", "details": {}}
    response = client.post(path, json={}, headers={"Idempotency-Key": "verify-1"})
    assert response.json()["status"] == "inconclusive"
    assert client.get(f"/api/v1/recommendations/{approved['id']}").json()["status"] == "executed"


@pytest.mark.parametrize(
    "change",
    [
        "expired",
        "content",
        "target",
        "evidence",
        "missing_approval",
        "approval_version",
        "approval_expiry",
        "approval_hash",
        "superseded",
    ],
)
def test_execution_revalidates_the_actual_approval_and_snapshot(client, database, approved, change):
    factory, _, _ = database
    if change == "superseded":
        client.post(f"/api/v1/incidents/{approved['incident_id']}/investigate")
    else:
        with factory() as db:
            item = db.get(Recommendation, UUID(approved["id"]))
            approval = db.scalar(select(Approval).where(Approval.recommendation_id == item.id))
            if change == "expired":
                item.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            elif change == "content":
                item.parameters = {"strategy": "rolling", "reason": "changed after review"}
            elif change == "target":
                item.target = "production/workload"
            elif change == "evidence":
                evidence = db.scalar(
                    select(EvidenceItem).where(
                        EvidenceItem.investigation_id == item.investigation_id
                    )
                )
                evidence.fact = "changed retained evidence"
            elif change == "missing_approval":
                db.delete(approval)
            elif change == "approval_version":
                approval.recommendation_version += 1
            elif change == "approval_hash":
                approval.proposal_hash = "0" * 64
            else:
                approval.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            db.commit()
    assert execute(client, approved).status_code == 409
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(Execution)) == 0


def test_stale_measurements_are_not_accepted_as_recovery(client, approved, adapter):
    value = execute(client, approved).json()
    adapter.verify = lambda execution: Observation(
        status="passed",
        mode="synthetic",
        details={},
        measurements=[
            {
                "name": "errors",
                "source": "old-probe",
                "observed_at": datetime.now(timezone.utc) - timedelta(hours=1),
                "value": 0,
                "threshold": 5,
                "operator": "lt",
            }
        ],
    )
    response = client.post(
        f"/api/v1/executions/{value['id']}/verify",
        json={},
        headers={"Idempotency-Key": "stale-measurement"},
    )
    assert response.json()["status"] == "inconclusive"


def test_unapproved_rejected_missing_and_malformed_execution_requests(client, proposal):
    assert execute(client, proposal).status_code == 409
    path = f"/api/v1/recommendations/{proposal['id']}/execute"
    assert client.post(path, json={"proposal_hash": proposal["proposal_hash"]}).status_code == 422
    assert (
        client.post(
            path,
            json={"proposal_hash": proposal["proposal_hash"], "status": "succeeded"},
            headers={"Idempotency-Key": "key"},
        ).status_code
        == 422
    )
    client.post(path.replace("execute", "reject"), json={})
    assert execute(client, proposal).status_code == 409
    missing = {**proposal, "id": str(uuid4())}
    assert execute(client, missing).status_code == 404


def test_adapter_failure_is_durable_and_does_not_leak_secrets(client, approved, adapter):
    def fail(execution):
        raise RuntimeError("do-not-leak-this-secret")

    adapter.execute = fail
    response = execute(client, approved)
    assert response.json()["status"] == "failed"
    assert response.json()["result"]["outcome_unknown"] is True
    assert "do-not-leak" not in response.text
    assert execute(client, approved).json() == response.json()


def test_committed_pending_claim_is_not_automatically_retried(client, database, approved, adapter):
    # Simulate an abrupt worker failure outside the normal adapter exception path.
    class SimulatedCrash(BaseException):
        pass

    def crash(execution):
        adapter.calls += 1
        raise SimulatedCrash()

    adapter.execute = crash
    from app.services.operations import execute as invoke

    with database[0]() as db:
        with pytest.raises(SimulatedCrash):
            invoke(
                db,
                Actor("local-demo-user", "operator"),
                "execution-1",
                UUID(approved["id"]),
                approved["proposal_hash"],
                adapter,
            )
    replay = execute(client, approved)
    assert replay.status_code == 202
    assert replay.json()["status"] == "pending"
    assert adapter.calls == 1
    assert execute(client, approved, "new-key").status_code == 409
    assert (
        client.post(f"/api/v1/incidents/{approved['incident_id']}/investigate").status_code == 409
    )


def test_idempotency_replays_without_duplicate_records_or_audits(client, database):
    payload = {"title": "Idempotent incident", "severity": "high", "summary": "Synthetic"}
    headers = {"Idempotency-Key": "create-1"}
    first = client.post("/api/v1/incidents", json=payload, headers=headers)
    replay = client.post("/api/v1/incidents", json=payload, headers=headers)
    assert first.status_code == replay.status_code == 201 and first.json() == replay.json()
    assert replay.headers["Idempotency-Replayed"] == "true"
    assert (
        client.post(
            "/api/v1/incidents", json={**payload, "title": "Different"}, headers=headers
        ).status_code
        == 409
    )
    assert client.post("/api/v1/cost-analyses", headers=headers).status_code == 409
    path = f"/api/v1/incidents/{first.json()['id']}/investigate"
    one = client.post(path, headers={"Idempotency-Key": "investigate-1"})
    two = client.post(path, headers={"Idempotency-Key": "investigate-1"})
    assert one.json() == two.json()
    with database[0]() as db:
        assert db.scalar(select(func.count()).select_from(Investigation)) == 1
        assert db.scalar(select(func.count()).select_from(IdempotencyRecord)) == 2


def test_role_boundary_and_disabled_demo_fail_closed(client, proposal, monkeypatch):
    app.dependency_overrides[get_actor] = lambda: Actor("read-only-reviewer", "viewer")
    assert client.get("/api/v1/incidents").status_code == 200
    assert (
        client.post(
            f"/api/v1/recommendations/{proposal['id']}/approve",
            json={"proposal_hash": proposal["proposal_hash"]},
        ).status_code
        == 403
    )
    assert client.post("/api/v1/cost-analyses").status_code == 403
    assert execute(client, proposal).status_code == 403
    app.dependency_overrides.pop(get_actor)
    monkeypatch.setattr(settings, "local_demo_enabled", False)
    assert client.get("/api/v1/incidents").status_code == 401
    assert client.get("/health/live").status_code == 200


def test_billing_sources_and_report_are_persisted_and_replayable(client):
    payload = {
        "previous_period": "2026-01",
        "current_period": "2026-02",
        "records": [
            {
                "period": "2026-01",
                "service": "Compute",
                "resource": "api-workers",
                "region": "test",
                "cost": "10.125",
                "tags": {"team": "small"},
            },
            {
                "period": "2026-02",
                "service": "Compute",
                "resource": "api-workers",
                "region": "test",
                "cost": "20.125",
                "tags": {"team": "small"},
            },
        ],
    }
    headers = {"Idempotency-Key": "analysis-1"}
    response = client.post("/api/v1/cost-analyses", json=payload, headers=headers)
    assert response.status_code == 201
    value = response.json()
    assert value["total_cost"] == 20.13 and value["change"] == 10 and value["source_count"] == 2
    assert client.post("/api/v1/cost-analyses", json=payload, headers=headers).json() == value
    detail = client.get(f"/api/v1/cost-analyses/{value['id']}").json()
    assert (
        detail["drivers"] == value["drivers"]
        and detail["estimated_savings"] == value["estimated_savings"]
    )
    sources = client.get(f"/api/v1/cost-analyses/{value['id']}/records").json()
    assert sources[0]["tags"] == {"team": "small"}
    assert {float(source["cost"]) for source in sources} == {10.125, 20.125}
    assert client.get("/api/v1/dashboard/summary").json()["cost_autopsy"]["total_cost"] == 20.13


@pytest.mark.parametrize(
    "payload",
    [
        {"current_period": "bad"},
        {"previous_period": "2026-10"},
        {"records": []},
        {
            "records": [
                {"period": "2026-09", "service": "a", "resource": "b", "region": "c", "cost": "NaN"}
            ]
        },
    ],
)
def test_bad_billing_requests_do_not_leave_partial_analyses(client, database, payload):
    assert client.post("/api/v1/cost-analyses", json=payload).status_code == 422
    with database[0]() as db:
        assert db.scalar(select(func.count()).select_from(CostAnalysis)) == 0


def test_keyset_pagination_is_stable_and_cursors_are_scoped(client):
    for number in range(5):
        client.post(
            "/api/v1/incidents",
            json={"title": f"Incident {number}", "severity": "high", "summary": "Synthetic"},
        )
    first = client.get("/api/v1/incidents?limit=2")
    cursor = first.headers["X-Next-Cursor"]
    second = client.get("/api/v1/incidents", params={"limit": 2, "cursor": cursor})
    third = client.get(
        "/api/v1/incidents", params={"limit": 2, "cursor": second.headers["X-Next-Cursor"]}
    )
    assert len({item["id"] for item in first.json() + second.json() + third.json()}) == 5
    assert "X-Next-Cursor" not in third.headers
    assert client.get("/api/v1/investigations", params={"cursor": cursor}).status_code == 422
    assert client.get("/api/v1/incidents", params={"cursor": "broken"}).status_code == 422
    assert (
        client.get("/api/v1/incidents", params={"cursor": cursor, "offset": 1}).status_code == 422
    )


@pytest.mark.parametrize(
    "statement", ["UPDATE audit_events SET actor='forged'", "DELETE FROM audit_events"]
)
def test_audit_records_are_append_only_in_the_database(database, incident, statement):
    factory, _, _ = database
    with factory() as db:
        with pytest.raises(IntegrityError):
            db.execute(text(statement))
        db.rollback()
        assert db.scalar(select(func.count()).select_from(AuditEvent)) == 1


@pytest.mark.parametrize(
    "path", ["investigations", "approvals", "executions", "verifications", "cost-analyses"]
)
def test_missing_lifecycle_resources_are_404(client, path):
    assert client.get(f"/api/v1/{path}/{uuid4()}").status_code == 404


def test_integration_status_does_not_claim_unconfigured_remote_connections(client):
    values = {item["id"]: item for item in client.get("/api/v1/integrations").json()}
    assert values["database"]["status"] == "available"
    assert values["operations"]["status"] == "not_configured"
    assert values["aws"]["status"] == "not_configured"
    assert values["grafana"]["status"] == "not_checked"
    assert values["discord"]["status"] == "not_configured"


def test_browser_can_send_idempotency_keys_and_read_pagination_headers(client):
    response = client.options(
        "/api/v1/incidents",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,idempotency-key",
        },
    )
    assert response.status_code == 200
    response = client.get("/api/v1/incidents", headers={"Origin": "http://localhost:5173"})
    assert "X-Next-Cursor" in response.headers["access-control-expose-headers"]


def test_proposal_digest_uses_the_expiry_instant_not_its_display_timezone():
    item = Recommendation(
        id=uuid4(),
        incident_id=uuid4(),
        version=1,
        action="restart_demo_workload",
        target="demo/api-workers",
        parameters={},
        evidence=[],
        expires_at=datetime(2026, 10, 21, tzinfo=timezone.utc),
    )
    original = proposal_digest(item)
    item.expires_at = item.expires_at.astimezone(timezone(timedelta(hours=5, minutes=30)))
    assert proposal_digest(item) == original
