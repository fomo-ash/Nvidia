from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

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
