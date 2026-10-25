"""MCP Tool: Direct probe of service readiness and health endpoints."""

from app.adapters.probe import ProbeClient
from app.config import settings
from app.schemas.evidence import EvidenceItem


async def check_service_health(target_url: str = settings.SAMPLE_APP_HEALTH_URL) -> EvidenceItem:
    """Probe an HTTP endpoint for readiness, status code, and response latency."""
    client = ProbeClient()
    result = await client.check_endpoint(target_url)

    is_healthy = result.get("is_healthy", False)
    status_code = result.get("status_code", 0)
    latency = result.get("latency_ms", 0.0)

    if is_healthy:
        fact = f"Direct probe to '{target_url}' returned HTTP {status_code} (healthy, latency {latency}ms)."
    else:
        err = result.get("error", "HTTP error")
        fact = f"Direct probe to '{target_url}' FAILED with status {status_code} ({err}, latency {latency}ms)."

    return EvidenceItem(
        source="direct:probe",
        fact=fact,
        raw_data=result,
        trusted=True,
    )
