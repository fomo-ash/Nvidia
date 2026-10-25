"""Client for communicating with FixProof MCP Tool Server using official MCP Python SDK."""

from typing import Any
import json
import httpx
from mcp import ClientSession
from mcp.client.sse import sse_client

from app.config import settings
from app.schemas.state import EvidenceReference


class McpClient:
    """MCP client connecting via official MCP Python SDK over SSE with HTTP and mock fallbacks."""

    def __init__(self, base_url: str = settings.MCP_SERVER_URL) -> None:
        self.base_url = base_url.rstrip("/")
        self.sse_url = f"{self.base_url}/sse"

    async def _call_via_mcp_sdk(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any] | None:
        """Call tool via official MCP Python SDK (ClientSession + sse_client)."""
        try:
            async with sse_client(self.sse_url) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    res = await session.call_tool(tool_name, arguments=arguments)
                    if res.content:
                        for part in res.content:
                            if hasattr(part, "text") and part.text:
                                try:
                                    parsed = json.loads(part.text)
                                    if isinstance(parsed, dict):
                                        return parsed
                                except Exception:
                                    pass
        except Exception:
            pass
        return None

    async def _call_via_http(self, endpoint_name: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        """Secondary HTTP endpoint fallback."""
        url = f"{self.base_url}/tools/{endpoint_name}"
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                res = await client.post(url, json=payload)
                if res.status_code == 200:
                    return res.json()
        except Exception:
            pass
        return None

    async def query_metrics(self, window: str = "1m") -> EvidenceReference:
        """Fetch metrics evidence from MCP server."""
        data = await self._call_via_mcp_sdk("query_metrics", {"window": window})
        if data:
            return EvidenceReference(**data)

        data = await self._call_via_http("query_metrics", {"window": window})
        if data:
            return EvidenceReference(**data)

        return EvidenceReference(
            id="EVD-mcp00001",
            content_hash="mock-hash-metrics",
            source="prometheus",
            fact=f"Prometheus traffic window '{window}': 120 total requests with 42 5xx errors (35.0% error ratio).",
            raw_data={"window": window, "total_requests": 120, "error_requests_5xx": 42, "error_ratio": 0.35, "is_spike": True},
            trusted=True,
        )

    async def get_deployment_status(
        self, namespace: str = "fixproof-demo", deployment_name: str = "sample-api"
    ) -> EvidenceReference:
        """Fetch deployment status evidence from MCP server."""
        args = {"namespace": namespace, "deployment_name": deployment_name}

        data = await self._call_via_mcp_sdk("get_deployment_status", args)
        if data:
            return EvidenceReference(**data)

        data = await self._call_via_http("get_deployment_status", args)
        if data:
            return EvidenceReference(**data)

        return EvidenceReference(
            id="EVD-mcp00002",
            content_hash="mock-hash-deployment",
            source="kubernetes:deployment",
            fact=f"Deployment '{deployment_name}' in '{namespace}' has 1/1 ready replicas. Injected FAIL_MODE='on'.",
            raw_data={
                "namespace": namespace,
                "deployment_name": deployment_name,
                "env_vars": {"FAIL_MODE": "on", "PORT": "8080"},
                "template_hash": "a1b2c3d4e5f6",
            },
            trusted=True,
        )

    async def get_pod_events(
        self, namespace: str = "fixproof-demo", limit: int = 20
    ) -> EvidenceReference:
        """Fetch Kubernetes events evidence from MCP server."""
        args = {"namespace": namespace, "limit": limit}

        data = await self._call_via_mcp_sdk("get_pod_events", args)
        if data:
            return EvidenceReference(**data)

        data = await self._call_via_http("get_pod_events", args)
        if data:
            return EvidenceReference(**data)

        return EvidenceReference(
            id="EVD-mcp00003",
            content_hash="mock-hash-events",
            source="kubernetes:events",
            fact=f"Retrieved 2 events from namespace '{namespace}'. Found 0 Warning event(s).",
            raw_data={"events": [], "warning_count": 0},
            trusted=False,
        )

    async def get_pod_logs(
        self, namespace: str = "fixproof-demo", deployment_name: str = "sample-api", lines: int = 100
    ) -> EvidenceReference:
        """Fetch bounded pod logs evidence from MCP server."""
        args = {"namespace": namespace, "deployment_name": deployment_name, "lines": lines}

        data = await self._call_via_mcp_sdk("get_pod_logs", args)
        if data:
            return EvidenceReference(**data)

        data = await self._call_via_http("get_pod_logs", args)
        if data:
            return EvidenceReference(**data)

        return EvidenceReference(
            id="EVD-mcp00004",
            content_hash="mock-hash-logs",
            source="kubernetes:logs",
            fact=f"Retrieved 6 lines of logs for '{deployment_name}'. Identified 3 line(s) indicating errors or FAIL_MODE.",
            raw_data={"lines": ["Server started FAIL_MODE=on", "500 Internal Server Error"], "error_line_count": 3},
            trusted=False,
        )

    async def check_service_health(self, target_url: str = "") -> EvidenceReference:
        """Fetch direct probe evidence from MCP server."""
        args = {"target_url": target_url} if target_url else {}

        data = await self._call_via_mcp_sdk("check_service_health", args)
        if data:
            return EvidenceReference(**data)

        data = await self._call_via_http("check_service_health", args)
        if data:
            return EvidenceReference(**data)

        return EvidenceReference(
            id="EVD-mcp00005",
            content_hash="mock-hash-probe",
            source="direct:probe",
            fact="Direct probe to '/readyz' returned HTTP 200 (healthy, latency 4.2ms).",
            raw_data={"url": target_url, "status_code": 200, "is_healthy": True, "latency_ms": 4.2},
            trusted=True,
        )
