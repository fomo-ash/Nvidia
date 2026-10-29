"""Unit tests for FixProof MCP Server tools and official protocol handlers."""

import pytest
from app.schemas.evidence import EvidenceItem
from app.schemas.actions import RestoreActionRequest
from app.tools import check_service_health, query_metrics, restore_known_good_template
from app.server import list_tools, call_tool
from app.adapters.kubernetes import KubernetesClient


@pytest.mark.asyncio
async def test_evidence_item_content_hash():
    """Verify evidence items automatically compute SHA-256 hash."""
    item = EvidenceItem(
        source="prometheus",
        fact="HTTP 5xx spike detected",
        raw_data={"ratio": 0.35},
        trusted=True,
    )
    assert item.content_hash != ""
    assert len(item.content_hash) == 64


@pytest.mark.asyncio
async def test_mcp_query_metrics_rejects_unbounded_window():
    with pytest.raises(ValueError):
        await query_metrics(window="1h] or vector(1)")


@pytest.mark.asyncio
async def test_probe_rejects_arbitrary_url():
    with pytest.raises(ValueError):
        await check_service_health("http://localhost:8000/health")


@pytest.mark.asyncio
async def test_mcp_guarded_mutation_auth():
    """Verify restore tool rejects invalid capability tokens."""
    bad_req = RestoreActionRequest(
        execution_id="00000000-0000-0000-0000-000000000001",
        proposal_hash="a" * 64,
        uid="fixture-uid",
        resource_version="10",
        expected_bad_template_hash="b" * 64,
        desired_good_template_hash="c" * 64,
        desired_template={},
        capability_token="invalid-token",
    )
    res = await restore_known_good_template(bad_req)
    assert res.status == "failed"


@pytest.mark.asyncio
async def test_official_server_list_tools():
    """Only read tools are advertised."""
    tools = await list_tools()
    tool_names = [t.name for t in tools]
    assert len(tools) == 5
    assert "query_metrics" in tool_names
    assert "restore_known_good_template" not in tool_names


@pytest.mark.asyncio
async def test_official_server_denies_mutation_tool():
    with pytest.raises(ValueError):
        await call_tool("restore_known_good_template", {})


def test_kubernetes_scope_and_missing_credentials_fail_closed(tmp_path):
    client = KubernetesClient()
    with pytest.raises(ValueError):
        client._require_target("kube-system", "sample-api")
    with pytest.raises(ValueError):
        client._require_target("fixproof-demo", "other-service")
    client.ca_cert_path = str(tmp_path / "missing-ca")
    with pytest.raises(RuntimeError):
        client._connection()


@pytest.mark.asyncio
async def test_mutation_disabled_even_with_present_token():
    request = RestoreActionRequest(
        execution_id="00000000-0000-0000-0000-000000000001",
        proposal_hash="a" * 64,
        uid="fixture-uid",
        resource_version="10",
        expected_bad_template_hash="b" * 64,
        desired_good_template_hash="c" * 64,
        desired_template={},
        capability_token="anything",
    )
    result = await restore_known_good_template(request)
    assert result.status == "failed"
