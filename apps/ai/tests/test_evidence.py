"""MCP client timestamp, transport, and evidence binding regressions."""

import hashlib
import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from app.tools import mcp_client


def payload(age=0):
    value = {
        "id": "EVD-12345678",
        "source": "prometheus",
        "fact": "observed",
        "raw_data": {},
        "observed_at": (datetime.now(timezone.utc) - timedelta(seconds=age)).isoformat(),
        "mode": "live",
        "trusted": True,
    }
    value["content_hash"] = hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str).encode()
    ).hexdigest()
    return value


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "fault",
    [
        None,
        "stale",
        "future",
        "missing_time",
        "naive_time",
        "altered_time",
        "altered_id",
        "altered_data",
        "synthetic",
        "wrong_source",
    ],
)
async def test_client_evidence_validation(monkeypatch, fault):
    data = payload(121 if fault == "stale" else (-60 if fault == "future" else 0))
    if fault == "missing_time":
        data.pop("observed_at")
    if fault == "naive_time":
        data["observed_at"] = datetime.now().isoformat()
    if fault == "altered_time":
        data["observed_at"] = (
            datetime.fromisoformat(data["observed_at"]) + timedelta(seconds=1)
        ).isoformat()
    if fault == "altered_id":
        data["id"] = "EVD-87654321"
    if fault == "altered_data":
        data["raw_data"] = {"injected": True}
    if fault == "synthetic":
        data["mode"] = "synthetic"
    if fault == "wrong_source":
        data["source"] = "kubernetes:deployment"

    def offline(*args, **kwargs):
        raise RuntimeError("SSE offline")

    original = httpx.AsyncClient

    def respond(request):
        return httpx.Response(200, json=data)

    monkeypatch.setattr(mcp_client, "sse_client", offline)
    monkeypatch.setattr(
        mcp_client.httpx,
        "AsyncClient",
        lambda **kw: original(transport=httpx.MockTransport(respond), **kw),
    )
    if fault:
        with pytest.raises(RuntimeError):
            await mcp_client.McpClient("http://mcp").query_metrics()
    else:
        evidence = await mcp_client.McpClient("http://mcp").query_metrics()
        assert evidence.observed_at == datetime.fromisoformat(data["observed_at"])


@pytest.mark.asyncio
async def test_evidence_expiring_during_collection_never_reaches_model(monkeypatch):
    from app.graph import nodes
    from app.schemas.state import EvidenceReference

    async def forbidden(**kwargs):
        pytest.fail("Stale evidence reached model")

    monkeypatch.setattr(nodes, "generate_causal_analysis", forbidden)
    evidence = EvidenceReference.model_validate(payload(age=121))
    result = await nodes.reason_causes_node({"evidence": [evidence]})
    assert result["investigation_status"] == "needs_review"
    assert result["hypotheses"] == []
