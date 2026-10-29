"""Bounded client for the local MCP telemetry service."""

import json
import hashlib
import asyncio
from datetime import datetime, timezone
from typing import Any

import httpx
from mcp import ClientSession
from mcp.client.sse import sse_client

from app.config import settings
from app.schemas.state import EvidenceReference


class McpClient:
    def __init__(self, base_url: str = settings.MCP_SERVER_URL) -> None:
        self.base_url = base_url.rstrip("/")

    async def _call(self, name: str, arguments: dict[str, Any]) -> EvidenceReference:
        data: dict[str, Any] | None = None
        try:
            async with asyncio.timeout(8):
                async with sse_client(
                    f"{self.base_url}/sse",
                    headers={"Authorization": "Bearer " + settings.SERVICE_AUTH_TOKEN},
                ) as streams:
                    async with ClientSession(*streams) as session:
                        await session.initialize()
                        result = await session.call_tool(name, arguments=arguments)
                        if result.isError:
                            raise RuntimeError(f"MCP tool {name} failed")
                        for part in result.content:
                            if getattr(part, "text", None):
                                data = json.loads(part.text)
                                break
        except Exception:
            # The REST adapter serves the same bounded tools on the private network.
            pass
        if data is None:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.post(
                        f"{self.base_url}/tools/{name}",
                        json=arguments,
                        headers={"Authorization": "Bearer " + settings.SERVICE_AUTH_TOKEN},
                    )
                    response.raise_for_status()
                    data = response.json()
            except (httpx.HTTPError, ValueError) as exc:
                raise RuntimeError(f"MCP telemetry unavailable: {name}") from exc
        try:
            evidence = EvidenceReference.model_validate(data)
        except ValueError as exc:
            raise RuntimeError(f"Invalid MCP evidence: {name}") from exc
        source_by_tool = {
            "query_metrics": "prometheus",
            "get_deployment_status": "kubernetes:deployment",
            "get_pod_events": "kubernetes:events",
            "get_pod_logs": "kubernetes:logs",
            "check_service_health": "direct:probe",
        }
        canonical = json.dumps(
            {
                "id": evidence.id,
                "source": evidence.source,
                "fact": evidence.fact,
                "raw_data": evidence.raw_data,
                "observed_at": evidence.observed_at.isoformat(),
                "mode": evidence.mode,
                "trusted": evidence.trusted,
            },
            sort_keys=True,
            default=str,
        )
        expected_hash = hashlib.sha256(canonical.encode()).hexdigest()
        age = (datetime.now(timezone.utc) - evidence.observed_at).total_seconds()
        if (
            not -5 <= age <= 120
            or evidence.mode != "live"
            or evidence.source != source_by_tool[name]
            or evidence.content_hash != expected_hash
        ):
            raise RuntimeError(f"MCP returned non-live or invalid evidence: {name}")
        return evidence

    async def query_metrics(self, window: str = "1m") -> EvidenceReference:
        return await self._call("query_metrics", {"window": window})

    async def get_deployment_status(
        self, namespace: str = "fixproof-demo", deployment_name: str = "sample-api"
    ) -> EvidenceReference:
        return await self._call(
            "get_deployment_status", {"namespace": namespace, "deployment_name": deployment_name}
        )

    async def get_pod_events(
        self, namespace: str = "fixproof-demo", limit: int = 20
    ) -> EvidenceReference:
        return await self._call("get_pod_events", {"namespace": namespace, "limit": limit})

    async def get_pod_logs(
        self,
        namespace: str = "fixproof-demo",
        deployment_name: str = "sample-api",
        lines: int = 100,
    ) -> EvidenceReference:
        return await self._call(
            "get_pod_logs",
            {"namespace": namespace, "deployment_name": deployment_name, "lines": lines},
        )

    async def check_service_health(self) -> EvidenceReference:
        return await self._call("check_service_health", {})
