"""MCP Tool: Query Prometheus metrics for HTTP traffic and 5xx error rates."""

from app.adapters.prometheus import PrometheusClient
from app.schemas.evidence import EvidenceItem


async def query_metrics(window: str = "1m") -> EvidenceItem:
    """Query traffic and 5xx error rates from Prometheus."""
    client = PrometheusClient()
    metrics = await client.get_traffic_metrics(window=window)

    total = metrics.get("total_requests", 0)
    errors = metrics.get("error_requests_5xx", 0)
    ratio = metrics.get("error_ratio", 0.0)
    is_spike = metrics.get("is_spike", False)

    if total == 0:
        fact = f"Prometheus window '{window}': No recorded traffic for sample-api."
    elif is_spike:
        pct = round(ratio * 100, 1)
        fact = (
            f"CRITICAL ANOMALY: High HTTP 5xx error rate ({pct}%, {errors}/{total} requests) "
            f"detected in window '{window}'."
        )
    else:
        pct = round(ratio * 100, 1)
        fact = f"Traffic nominal: {total} requests with {errors} 5xx errors ({pct}%) in window '{window}'."

    return EvidenceItem(
        source="prometheus",
        fact=fact,
        raw_data=metrics,
        trusted=True,
    )
