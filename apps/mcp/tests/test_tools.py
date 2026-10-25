"""Unit tests for FixProof MCP Server tools and official protocol handlers."""

import pytest
from app.schemas.evidence import EvidenceItem
from app.schemas.actions import RestoreActionRequest
from app.tools import (
    check_service_health,
    get_deployment_status,
    get_pod_events,
    get_pod_logs,
    query_metrics,
    restore_known_good_template,
)
from app.server import list_tools, call_tool


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
async def test_mcp_query_metrics():
    """Verify metrics query tool."""
    ev = await query_metrics(window="1m")
    assert ev.source == "prometheus"
    assert "window" in ev.raw_data


@pytest.mark.asyncio
async def test_mcp_deployment_status():
    """Verify deployment status tool."""
    ev = await get_deployment_status()
    assert ev.source == "kubernetes:deployment"
    assert "template_hash" in ev.raw_data


@pytest.mark.asyncio
async def test_mcp_guarded_mutation_auth():
    """Verify restore tool rejects invalid capability tokens."""
    bad_req = RestoreActionRequest(
        namespace="fixproof-demo",
        deployment_name="sample-api",
        expected_bad_template_hash="bad-hash",
        desired_good_template_hash="good-hash",
        capability_token="invalid-token",
    )
    res = await restore_known_good_template(bad_req)
    assert res.status == "failed"


@pytest.mark.asyncio
async def test_official_server_list_tools():
    """Verify official MCP Server lists all 6 bounded tools."""
    tools = await list_tools()
    tool_names = [t.name for t in tools]
    assert len(tools) == 6
    assert "query_metrics" in tool_names
    assert "restore_known_good_template" in tool_names


@pytest.mark.asyncio
async def test_official_server_call_tool():
    """Verify official MCP Server call_tool routing."""
    res = await call_tool("query_metrics", {"window": "1m"})
    assert len(res) == 1
    assert "prometheus" in res[0].text
