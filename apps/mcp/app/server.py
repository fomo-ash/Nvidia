"""Anthropic Model Context Protocol (MCP) server implementation for FixProof."""

import asyncio
from typing import Any
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from app.tools.deployments import get_deployment_status as _get_deployment_status
from app.tools.events import get_pod_events as _get_pod_events
from app.tools.health import check_service_health as _check_service_health
from app.tools.logs import get_pod_logs as _get_pod_logs
from app.tools.metrics import query_metrics as _query_metrics

# Initialize Anthropic's official core Server
server = Server("fixproof-mcp")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List tools available on this MCP server."""
    return [
        Tool(
            name="query_metrics",
            description="Query Prometheus for HTTP request count and 5xx error ratio over a rolling time window.",
            inputSchema={
                "type": "object",
                "properties": {
                    "window": {
                        "type": "string",
                        "description": "PromQL increase duration window (e.g., '1m', '5m')",
                        "default": "1m",
                    }
                },
            },
        ),
        Tool(
            name="get_deployment_status",
            description="Fetch Kubernetes deployment status, container images, environment variables, and pod template hash.",
            inputSchema={
                "type": "object",
                "properties": {
                    "namespace": {"type": "string", "default": "fixproof-demo"},
                    "deployment_name": {"type": "string", "default": "sample-api"},
                },
            },
        ),
        Tool(
            name="get_pod_events",
            description="Retrieve recent warning and scaling events from Kubernetes for the specified namespace.",
            inputSchema={
                "type": "object",
                "properties": {
                    "namespace": {"type": "string", "default": "fixproof-demo"},
                    "limit": {"type": "integer", "default": 20, "minimum": 1, "maximum": 20},
                },
            },
        ),
        Tool(
            name="get_pod_logs",
            description="Fetch bounded logs (up to 100 lines) from target pod with ANSI escape sequences stripped.",
            inputSchema={
                "type": "object",
                "properties": {
                    "namespace": {"type": "string", "default": "fixproof-demo"},
                    "deployment_name": {"type": "string", "default": "sample-api"},
                    "lines": {"type": "integer", "default": 100, "minimum": 1, "maximum": 100},
                },
            },
        ),
        Tool(
            name="check_service_health",
            description="Directly probe HTTP health or readiness endpoint to measure status code and latency.",
            inputSchema={
                "type": "object",
                "properties": {
                    "target_url": {"type": "string", "description": "Target HTTP URL to probe"},
                },
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any] | None) -> list[TextContent]:
    """Execute tool calls routed through the official MCP protocol."""
    args = arguments or {}

    if name == "query_metrics":
        window = str(args.get("window", "1m"))
        evidence = await _query_metrics(window=window)
        return [TextContent(type="text", text=evidence.model_dump_json())]

    elif name == "get_deployment_status":
        ns = str(args.get("namespace", "fixproof-demo"))
        dep = str(args.get("deployment_name", "sample-api"))
        evidence = await _get_deployment_status(namespace=ns, deployment_name=dep)
        return [TextContent(type="text", text=evidence.model_dump_json())]

    elif name == "get_pod_events":
        ns = str(args.get("namespace", "fixproof-demo"))
        limit = int(args.get("limit", 20))
        evidence = await _get_pod_events(namespace=ns, limit=limit)
        return [TextContent(type="text", text=evidence.model_dump_json())]

    elif name == "get_pod_logs":
        ns = str(args.get("namespace", "fixproof-demo"))
        dep = str(args.get("deployment_name", "sample-api"))
        lines = int(args.get("lines", 100))
        evidence = await _get_pod_logs(namespace=ns, deployment_name=dep, lines=lines)
        return [TextContent(type="text", text=evidence.model_dump_json())]

    elif name == "check_service_health":
        url = str(args.get("target_url", ""))
        evidence = await _check_service_health(target_url=url) if url else await _check_service_health()
        return [TextContent(type="text", text=evidence.model_dump_json())]

    else:
        raise ValueError(f"Unknown tool: '{name}'")


async def main() -> None:
    """Run standard stdio MCP transport."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
