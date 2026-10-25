"""Fixed, time-aligned Prometheus queries for sample workload traffic."""

import math
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from app.config import settings

MAX_SCRAPE_AGE_SECONDS = 30


class PrometheusClient:
    def __init__(self, base_url: str = settings.PROMETHEUS_URL):
        self.base_url = base_url.rstrip("/")

    async def query(self, expr: str, evaluated_at: datetime) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                f"{self.base_url}/api/v1/query",
                params={"query": expr, "time": evaluated_at.isoformat()},
            )
            response.raise_for_status()
            return response.json()

    async def get_traffic_metrics(self, window: str = "1m") -> dict[str, Any]:
        if window not in {"1m", "5m"}:
            raise ValueError("Unsupported metrics window")
        evaluated_at = datetime.now(timezone.utc)
        selector = "job='fixproof-sample',route='/api/work'"
        try:
            total_expr = f"sum(increase(sample_http_requests_total{{{selector}}}[{window}]))"
            error_expr = f"sum(increase(sample_http_requests_total{{{selector},status_class='5xx'}}[{window}]))"
            freshness_expr = f"min(timestamp(sample_http_requests_total{{{selector}}}))"

            def extract(res: dict[str, Any]) -> float:
                if res.get("status") != "success":
                    raise ValueError("Prometheus query failed")
                data = res.get("data", {})
                results = data.get("result", [])
                if data.get("resultType") != "vector" or len(results) != 1:
                    raise ValueError("Expected one aggregate sample")
                timestamp, raw = results[0]["value"]
                timestamp, value = float(timestamp), float(raw)
                if not all(math.isfinite(v) for v in (timestamp, value)) or value < 0:
                    raise ValueError("Invalid Prometheus sample")
                if abs(evaluated_at.timestamp() - timestamp) > 5:
                    raise ValueError("Query sample is not aligned to evaluation time")
                return value

            total = extract(await self.query(total_expr, evaluated_at))
            errors = extract(await self.query(error_expr, evaluated_at))
            scrape_timestamp = extract(await self.query(freshness_expr, evaluated_at))
            if not -5 <= evaluated_at.timestamp() - scrape_timestamp <= MAX_SCRAPE_AGE_SECONDS:
                raise ValueError("Sample scrape is stale")
            if errors > total:
                raise ValueError("Error count exceeds total traffic")
            ratio = errors / total if total else 0.0
            duration = timedelta(minutes=1 if window == "1m" else 5)
            return {
                "window": window,
                "window_start": (evaluated_at - duration).isoformat(),
                "window_end": evaluated_at.isoformat(),
                "sample_observed_at": datetime.fromtimestamp(
                    scrape_timestamp, timezone.utc
                ).isoformat(),
                "collected_at": datetime.now(timezone.utc).isoformat(),
                "queries": {"total": total_expr, "errors": error_expr, "freshness": freshness_expr},
                "total_requests": total,
                "error_requests_5xx": errors,
                "error_ratio": ratio,
                "is_spike": ratio > 0.20 and total >= 20,
            }
        except (httpx.HTTPError, ValueError, KeyError, TypeError, IndexError, OverflowError) as exc:
            return {
                "window": window,
                "error": type(exc).__name__,
                "collected_at": datetime.now(timezone.utc).isoformat(),
            }
