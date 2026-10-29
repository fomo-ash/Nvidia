import httpx
import pytest

from app.adapters import kubernetes
from app.config import settings


@pytest.mark.asyncio
async def test_kubernetes_response_is_bounded_during_download():
    async def response(request):
        return httpx.Response(200, content=b"x" * 262145)

    async with kubernetes.BoundedClient(transport=httpx.MockTransport(response)) as client:
        with pytest.raises(ValueError):
            await client.get("https://kubernetes.test/oversized")


@pytest.mark.asyncio
async def test_deployment_uid_drift_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "KUBERNETES_TARGET_UID", "original")
    original = kubernetes.BoundedClient
    monkeypatch.setattr(
        kubernetes,
        "BoundedClient",
        lambda **kw: original(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json={"metadata": {"uid": "recreated"}})
            ),
            **kw,
        ),
    )
    client = kubernetes.KubernetesClient()
    monkeypatch.setattr(client, "_connection", lambda: ({}, True))
    with pytest.raises(ValueError, match="UID"):
        await client.get_deployment_status()


@pytest.mark.asyncio
async def test_events_use_owner_uids_not_name_prefix(monkeypatch):
    original = kubernetes.BoundedClient
    events = {
        "items": [
            {"involvedObject": {"uid": "foreign", "name": "sample-api-forged"}},
            {"involvedObject": {"uid": "owned", "name": "actual"}, "reason": "Scaling"},
        ]
    }
    monkeypatch.setattr(
        kubernetes,
        "BoundedClient",
        lambda **kw: original(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, json=events)), **kw
        ),
    )
    client = kubernetes.KubernetesClient()
    monkeypatch.setattr(client, "_connection", lambda: ({}, True))

    async def target(*args):
        return {"uid": "owned", "replicasets": [], "pods": []}

    monkeypatch.setattr(client, "get_deployment_status", target)
    result = await client.get_pod_events()
    assert len(result) == 1 and result[0]["involved_object"]["name"] == "actual"


@pytest.mark.asyncio
async def test_redirect_is_not_functional_health(monkeypatch):
    from app.adapters import probe

    original = httpx.AsyncClient

    def response(request):
        return httpx.Response(302, headers={"Location": "http://other-target.test"})

    monkeypatch.setattr(
        probe.httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(response), **kwargs),
    )
    result = await probe.ProbeClient().check_endpoint("http://sample.test/healthz")
    assert result["status_code"] == 302 and result["is_healthy"] is False
