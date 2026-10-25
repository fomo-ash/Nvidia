"""MCP Tool: Fetch Kubernetes events for namespace."""

from app.adapters.kubernetes import KubernetesClient
from app.schemas.evidence import EvidenceItem


async def get_pod_events(namespace: str = "fixproof-demo", limit: int = 20) -> EvidenceItem:
    """Fetch recent Kubernetes events in the target namespace."""
    client = KubernetesClient()
    events = await client.get_pod_events(namespace=namespace, limit=limit)

    warnings = [e for e in events if e.get("type") == "Warning"]
    fact = (
        f"Retrieved {len(events)} events from namespace '{namespace}'. "
        f"Found {len(warnings)} Warning event(s)."
    )

    return EvidenceItem(
        source="kubernetes:events",
        fact=fact,
        raw_data={"events": events, "warning_count": len(warnings)},
        trusted=False,
    )
