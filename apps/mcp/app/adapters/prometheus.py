"""Prometheus integration client for FixProof MCP Server."""

import httpx
import math
from datetime import datetime, timezone
from typing import Any
from app.config import settings


class PrometheusClient:
    def __init__(self, base_url: str = settings.PROMETHEUS_URL):
        self.base_url = base_url.rstrip("/")

    async def query(self, expr: str) -> dict[str, Any]:
        """Execute an instant PromQL query."""
        url = f"{self.base_url}/api/v1/query"
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url, params={"query": expr})
            response.raise_for_status()
            return response.json()

    async def get_traffic_metrics(self, window: str = "1m") -> dict[str, Any]:
        """Query traffic total and 5xx error rate for sample-api."""
        if window not in {"1m", "5m"}:
            raise ValueError("Unsupported metrics window")
        try:
            total_expr = f"sum(increase(sample_http_requests_total{{job='fixproof-sample'}}[{window}]))"
            error_expr = f"sum(increase(sample_http_requests_total{{job='fixproof-sample',status_class='5xx'}}[{window}]))"

            total_res = await self.query(total_expr)
            error_res = await self.query(error_expr)

            def extract_val(res: dict[str, Any]) -> float:
                if res.get("status") != "success":
                    raise ValueError("Prometheus query failed")
                results = res.get("data", {}).get("result", [])
                if results and len(results[0].get("value", [])) > 1:
                    value = float(results[0]["value"][1])
                    if math.isfinite(value) and value >= 0:
                        return value
                raise ValueError("Prometheus returned no finite sample")

            total_requests = int(extract_val(total_res))
            error_requests = int(extract_val(error_res))
            error_ratio = (error_requests / total_requests) if total_requests > 0 else 0.0

            return {
                "window": window,
                "total_requests": total_requests,
                "error_requests_5xx": error_requests,
                "error_ratio": round(error_ratio, 4),
                "is_spike": error_ratio > 0.20 and total_requests >= 20,
                "observed_at": datetime.now(timezone.utc).isoformat(),
            }
        except (httpx.HTTPError, ValueError) as e:
            return {
                "window": window,
                "error": type(e).__name__,
                "observed_at": datetime.now(timezone.utc).isoformat(),
            }
