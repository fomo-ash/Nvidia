"""LangChain tool definitions wrapping MCP client for ChatOps agent."""

from typing import Any
from langchain_core.tools import tool
from app.tools.mcp_client import McpClient

mcp_client = McpClient()


@tool
async def inspect_metrics(window: str = "1m") -> dict[str, Any]:
    """Inspect Prometheus metrics for HTTP traffic and 5xx error ratios over a rolling window.

    Args:
        window: Duration string such as '1m' or '5m'.
    """
    ev = await mcp_client.query_metrics(window=window)
    return ev.model_dump()


@tool
async def inspect_deployment(
    namespace: str = "fixproof-demo", deployment_name: str = "sample-api"
) -> dict[str, Any]:
    """Inspect Kubernetes deployment replica status, image, template hash, and environment variables.

    Args:
        namespace: Kubernetes namespace (default 'fixproof-demo').
        deployment_name: Target deployment (default 'sample-api').
    """
    ev = await mcp_client.get_deployment_status(namespace=namespace, deployment_name=deployment_name)
    return ev.model_dump()


@tool
async def inspect_pod_logs(
    namespace: str = "fixproof-demo", deployment_name: str = "sample-api", lines: int = 50
) -> dict[str, Any]:
    """Fetch bounded logs from target deployment pods with ANSI escape sequences stripped.

    Args:
        namespace: Kubernetes namespace.
        deployment_name: Deployment name.
        lines: Number of log lines (max 100).
    """
    ev = await mcp_client.get_pod_logs(namespace=namespace, deployment_name=deployment_name, lines=lines)
    return ev.model_dump()


@tool
async def probe_endpoint() -> dict[str, Any]:
    """Probe the registered sample service health endpoint."""
    ev = await mcp_client.check_service_health()
    return ev.model_dump()


ALL_CHATOPS_TOOLS = [inspect_metrics, inspect_deployment, inspect_pod_logs, probe_endpoint]
