"""MCP Tool: Inspect Kubernetes deployment status and pod template."""

from app.adapters.kubernetes import KubernetesClient
from app.schemas.evidence import EvidenceItem


async def get_deployment_status(
    namespace: str = "fixproof-demo", deployment_name: str = "sample-api"
) -> EvidenceItem:
    """Fetch Kubernetes deployment configuration, replica counts, and pod template hash."""
    client = KubernetesClient()
    data = await client.get_deployment_status(namespace=namespace, deployment_name=deployment_name)

    env_vars = data.get("env_vars", {})
    fail_mode = env_vars.get("FAIL_MODE", "unset")
    replicas_ready = data.get("replicas_ready", 0)
    replicas_desired = data.get("replicas_desired", 0)
    tmpl_hash = data.get("template_hash", "")[:12]

    fact = (
        f"Deployment '{deployment_name}' in '{namespace}' has {replicas_ready}/{replicas_desired} ready replicas. "
        f"Pod template hash prefix: {tmpl_hash}. Injected FAIL_MODE='{fail_mode}'."
    )

    return EvidenceItem(
        source="kubernetes:deployment",
        fact=fact,
        raw_data=data,
        trusted=True,
    )
