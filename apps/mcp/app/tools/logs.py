"""MCP Tool: Fetch bounded pod logs with ANSI stripped."""

from app.adapters.kubernetes import KubernetesClient
from app.schemas.evidence import EvidenceItem


async def get_pod_logs(
    namespace: str = "fixproof-demo",
    deployment_name: str = "sample-api",
    lines: int = 100,
) -> EvidenceItem:
    """Fetch bounded logs (max 100 lines) from target pod."""
    client = KubernetesClient()
    bounded_lines = min(max(1, lines), 100)
    log_lines = await client.get_pod_logs(
        namespace=namespace, deployment_name=deployment_name, lines=bounded_lines
    )

    error_count = sum(
        1 for line in log_lines if "500" in line or "ERROR" in line or "FAIL_MODE" in line
    )
    fact = (
        f"Retrieved {len(log_lines)} lines of logs for '{deployment_name}'. "
        f"Identified {error_count} line(s) indicating errors or FAIL_MODE."
    )

    return EvidenceItem(
        source="kubernetes:logs",
        fact=fact,
        raw_data={
            "lines": log_lines,
            "line_count": len(log_lines),
            "error_line_count": error_count,
        },
        trusted=False,
    )
