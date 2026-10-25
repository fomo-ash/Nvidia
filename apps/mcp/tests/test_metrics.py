"""Freshness and scope regressions without a Prometheus dependency."""

from datetime import datetime, timedelta, timezone

import pytest

from app.adapters.prometheus import PrometheusClient
from app.schemas.evidence import EvidenceItem


def sample(value, at):
    return {
        "status": "success",
        "data": {"resultType": "vector", "result": [{"value": [at, str(value)]}]},
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "fault",
    [None, "old_query", "old_scrape", "future_scrape", "impossible_counts", "missing", "nonfinite"],
)
async def test_metrics_scope_time_and_failures(monkeypatch, fault):
    calls = []

    async def query(self, expr, evaluated_at):
        calls.append((expr, evaluated_at))
        now = evaluated_at.timestamp()
        if fault == "missing":
            return {"status": "success", "data": {"resultType": "vector", "result": []}}
        value = now - 10 if "timestamp(" in expr else (30.25 if "status_class" in expr else 100.5)
        if fault == "old_scrape" and "timestamp(" in expr:
            value = now - 90
        if fault == "future_scrape" and "timestamp(" in expr:
            value = now + 60
        if fault == "impossible_counts" and "status_class" in expr:
            value = 101
        if fault == "nonfinite":
            value = "NaN"
        return sample(value, 1 if fault == "old_query" else now)

    monkeypatch.setattr(PrometheusClient, "query", query)
    result = await PrometheusClient().get_traffic_metrics()
    if fault:
        assert "error" in result
        assert "error_ratio" not in result
        return
    assert len(calls) == 3
    assert len({at for _, at in calls}) == 1
    assert all("route='/api/work'" in expr and "job='fixproof-sample'" in expr for expr, _ in calls)
    assert result["total_requests"] == 100.5
    assert result["error_requests_5xx"] == 30.25
    assert result["error_ratio"] == 30.25 / 100.5
    assert result["is_spike"]
    assert datetime.fromisoformat(result["window_end"]) - datetime.fromisoformat(
        result["window_start"]
    ) == timedelta(seconds=60)
    assert result["sample_observed_at"] != result["collected_at"]


@pytest.mark.asyncio
async def test_query_sends_explicit_evaluation_time(monkeypatch):
    import httpx
    from app.adapters import prometheus

    at = datetime.now(timezone.utc)
    original = httpx.AsyncClient

    def respond(request):
        assert request.url.params["time"] == at.isoformat()
        assert request.url.params["query"] == "fixed-query"
        return httpx.Response(200, json=sample(0, at.timestamp()))

    monkeypatch.setattr(
        prometheus.httpx,
        "AsyncClient",
        lambda **kw: original(transport=httpx.MockTransport(respond), **kw),
    )
    await PrometheusClient().query("fixed-query", at)


def test_evidence_hash_binds_time_identity_and_mode():
    at = datetime.now(timezone.utc)
    common = {
        "id": "EVD-12345678",
        "source": "prometheus",
        "fact": "observation",
        "observed_at": at,
    }
    base = EvidenceItem(**common)
    for key, value in [
        ("id", "EVD-87654321"),
        ("observed_at", at - timedelta(seconds=1)),
        ("mode", "synthetic"),
        ("trusted", True),
    ]:
        assert EvidenceItem(**(common | {key: value})).content_hash != base.content_hash
    with pytest.raises(ValueError):
        EvidenceItem(**(common | {"observed_at": at.replace(tzinfo=None)}))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "total,errors,expected",
    [(0.0, 0.0, False), (19.9, 19.9, False), (20.0, 4.0, False), (20.0, 4.01, True)],
)
async def test_real_zero_low_traffic_and_thresholds(monkeypatch, total, errors, expected):
    async def query(self, expr, evaluated_at):
        now = evaluated_at.timestamp()
        value = now if "timestamp(" in expr else (errors if "status_class" in expr else total)
        return sample(value, now)

    monkeypatch.setattr(PrometheusClient, "query", query)
    result = await PrometheusClient().get_traffic_metrics()
    assert "error" not in result
    assert result["is_spike"] is expected
    assert result["total_requests"] == total
