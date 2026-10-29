"""MCP Tool: Direct probe of service readiness and health endpoints."""

from urllib.parse import urlsplit, urlunsplit

from app.adapters.probe import ProbeClient
from app.config import settings
from app.schemas.evidence import EvidenceItem


async def check_service_health(target_url: str = settings.SAMPLE_APP_HEALTH_URL) -> EvidenceItem:
    """Probe an HTTP endpoint for readiness, status code, and response latency."""
    if target_url != settings.SAMPLE_APP_HEALTH_URL:
        raise ValueError("Probe URL is outside the registered target")
    client = ProbeClient()
    result = await client.check_endpoint(target_url)
    if result.get("status_code", 0) == 0:
        raise ValueError("Functional probe unavailable")
    parts = urlsplit(target_url)
    if parts.path == "/healthz":
        # Fixed sibling on the same registered origin, never caller-selected.
        readiness_url = urlunsplit((parts.scheme, parts.netloc, "/readyz", "", ""))
        result["readiness"] = await client.check_endpoint(readiness_url)

    is_healthy = result.get("is_healthy", False)
    status_code = result.get("status_code", 0)
    latency = result.get("latency_ms", 0.0)

    if is_healthy:
        fact = f"Direct probe to '{target_url}' returned HTTP {status_code} (healthy, latency {latency}ms)."
    else:
        err = result.get("error", "HTTP error")
        fact = f"Direct probe to '{target_url}' FAILED with status {status_code} ({err}, latency {latency}ms)."

    if "readiness" in result:
        fact += f" Separate readiness probe returned HTTP {result['readiness']['status_code']}; readiness is not functional health."
    return EvidenceItem(
        source="direct:probe",
        fact=fact,
        raw_data=result,
        trusted=True,
    )
