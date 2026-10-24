from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from sqlalchemy import select, func
from app.models.domain import Incident, Execution
from app.main import app
from app.services.operations import get_operations_adapter, ActionResult
import time

import pytest


def require_postgres(database):
    if database[1].dialect.name != "postgresql":
        pytest.skip("PostgreSQL row locking requires the PostgreSQL suite")


def test_concurrent_investigations_get_distinct_versions(client, database, incident):
    require_postgres(database)
    barrier = Barrier(2)

    def investigate():
        barrier.wait(timeout=10)
        return client.post(f"/api/v1/incidents/{incident['id']}/investigate")

    with ThreadPoolExecutor(max_workers=2) as workers:
        responses = list(workers.map(lambda _: investigate(), range(2)))
    assert [response.status_code for response in responses] == [200, 200]
    assert sorted(response.json()["version"] for response in responses) == [1, 2]


def test_concurrent_approval_has_one_winner(client, database, proposal):
    require_postgres(database)
    barrier = Barrier(2)

    def approve():
        barrier.wait(timeout=10)
        return client.post(
            f"/api/v1/recommendations/{proposal['id']}/approve",
            json={"proposal_hash": proposal["proposal_hash"]},
        )

    with ThreadPoolExecutor(max_workers=2) as workers:
        responses = list(workers.map(lambda _: approve(), range(2)))
    assert sorted(response.status_code for response in responses) == [200, 409]


def test_concurrent_idempotent_creates_return_one_resource(client, database):
    require_postgres(database)
    barrier = Barrier(2)

    def create():
        barrier.wait(timeout=10)
        return client.post(
            "/api/v1/incidents",
            json={"title": "Concurrent", "severity": "high", "summary": "Synthetic"},
            headers={"Idempotency-Key": "same-create"},
        )

    with ThreadPoolExecutor(max_workers=2) as workers:
        responses = list(workers.map(lambda _: create(), range(2)))
    assert [response.status_code for response in responses] == [201, 201]
    assert responses[0].json() == responses[1].json()
    with database[0]() as db:
        assert db.scalar(select(func.count()).select_from(Incident)) == 1


def test_concurrent_execution_keys_cannot_invoke_an_action_twice(client, database, proposal):
    require_postgres(database)
    assert (
        client.post(
            f"/api/v1/recommendations/{proposal['id']}/approve",
            json={"proposal_hash": proposal["proposal_hash"]},
        ).status_code
        == 200
    )

    class Adapter:
        name = "test-double"
        calls = 0

        def execute(self, execution):
            self.calls += 1
            time.sleep(0.2)
            return ActionResult(status="succeeded", details={"mode": "synthetic"})

    adapter = Adapter()
    app.dependency_overrides[get_operations_adapter] = lambda: adapter
    barrier = Barrier(2)

    def invoke(key):
        barrier.wait(timeout=10)
        return client.post(
            f"/api/v1/recommendations/{proposal['id']}/execute",
            json={"proposal_hash": proposal["proposal_hash"]},
            headers={"Idempotency-Key": key},
        )

    try:
        with ThreadPoolExecutor(max_workers=2) as workers:
            responses = list(workers.map(invoke, ["one", "two"]))
        assert sorted(response.status_code for response in responses) == [201, 409]
        assert adapter.calls == 1
        with database[0]() as db:
            assert db.scalar(select(func.count()).select_from(Execution)) == 1
    finally:
        app.dependency_overrides.pop(get_operations_adapter, None)


def test_duplicate_execution_while_adapter_is_running_replays_pending(client, database, proposal):
    require_postgres(database)
    assert (
        client.post(
            f"/api/v1/recommendations/{proposal['id']}/approve",
            json={"proposal_hash": proposal["proposal_hash"]},
        ).status_code
        == 200
    )
    started, release = Event(), Event()

    class Adapter:
        name = "blocking-test-double"
        calls = 0

        def execute(self, execution):
            self.calls += 1
            started.set()
            assert release.wait(timeout=10)
            return ActionResult(status="succeeded", details={"mode": "synthetic"})

    adapter = Adapter()
    app.dependency_overrides[get_operations_adapter] = lambda: adapter

    def invoke():
        return client.post(
            f"/api/v1/recommendations/{proposal['id']}/execute",
            json={"proposal_hash": proposal["proposal_hash"]},
            headers={"Idempotency-Key": "same-execution"},
        )

    try:
        with ThreadPoolExecutor(max_workers=1) as worker:
            future = worker.submit(invoke)
            try:
                assert started.wait(timeout=10)
                duplicate = invoke()
                assert duplicate.status_code == 202
                assert duplicate.json()["status"] == "pending"
            finally:
                release.set()
            assert future.result(timeout=10).status_code == 201
        assert adapter.calls == 1
        assert invoke().json()["status"] == "succeeded"
        assert adapter.calls == 1
    finally:
        app.dependency_overrides.pop(get_operations_adapter, None)
