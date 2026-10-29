"""Independent post-action observations are fresh, attributable and threshold-bound."""

from datetime import datetime, timedelta, timezone

import pytest

from app.config import settings
from app.tools import verification


@pytest.fixture
def observed(monkeypatch):
    now = datetime.now(timezone.utc)
    after = now - timedelta(seconds=80)
    request = verification.VerifyRequest(
        uid="fixture-uid",
        execution_id="00000000-0000-0000-0000-000000000001",
        desired_good_template_hash="a" * 64,
        after=after,
    )
    monkeypatch.setattr(settings, "KUBERNETES_TARGET_UID", request.uid)
    state = {
        "deployment": {
            "uid": request.uid,
            "execution_id": request.execution_id,
            "template_hash": request.desired_good_template_hash,
            "replicas_desired": 1,
            "replicas_available": 1,
            "resource_version": "12",
            "revision": "2",
        },
        "probe": 200,
        "metrics": {
            "window_start": (now - timedelta(seconds=60)).isoformat(),
            "window_end": now.isoformat(),
            "sample_observed_at": now.isoformat(),
            "total_requests": 120,
            "error_requests_5xx": 0,
        },
    }

    async def deployment(_self):
        return state["deployment"]

    async def probe(_self, _url):
        return {"status_code": state["probe"]}

    async def metrics(_self, _window):
        return state["metrics"]

    async def no_wait(_seconds):
        pass

    monkeypatch.setattr(verification.KubernetesClient, "get_deployment_status", deployment)
    monkeypatch.setattr(verification.ProbeClient, "check_endpoint", probe)
    monkeypatch.setattr(verification.PrometheusClient, "get_traffic_metrics", metrics)
    monkeypatch.setattr(verification.asyncio, "sleep", no_wait)
    return request, state


@pytest.mark.asyncio
async def test_fresh_recovery_passes(observed):
    request, _ = observed
    result = await verification.verify_recovery(request)
    assert result["status"] == "passed"
    assert result["mode"] == "live"
    assert len(result["measurements"]) == 6
    assert all(
        datetime.fromisoformat(row["observed_at"]) >= request.after
        for row in result["measurements"]
    )


@pytest.mark.asyncio
async def test_failed_probe_or_error_ratio_fails(observed):
    request, state = observed
    state["probe"] = 503
    assert (await verification.verify_recovery(request))["status"] == "failed"
    state["probe"] = 200
    state["metrics"]["error_requests_5xx"] = 10
    assert (await verification.verify_recovery(request))["status"] == "failed"


@pytest.mark.asyncio
async def test_insufficient_or_stale_traffic_is_inconclusive(observed):
    request, state = observed
    state["metrics"]["total_requests"] = 5
    assert (await verification.verify_recovery(request))["status"] == "inconclusive"
    state["metrics"]["total_requests"] = 120
    state["metrics"]["window_start"] = (request.after - timedelta(seconds=1)).isoformat()
    assert (await verification.verify_recovery(request))["status"] == "inconclusive"


@pytest.mark.asyncio
async def test_target_drift_and_provider_outage_are_inconclusive(observed):
    request, state = observed
    state["deployment"]["execution_id"] = "different"
    assert (await verification.verify_recovery(request))["status"] == "inconclusive"
    state["deployment"]["execution_id"] = request.execution_id
    state["metrics"] = {"error": "ConnectError"}
    assert (await verification.verify_recovery(request))["status"] == "inconclusive"
