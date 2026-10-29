"""Scoped restore tool, absent from the model-visible MCP registry."""

from app.adapters.kubernetes import KubernetesClient
from app.schemas.actions import ActionResult, RestoreActionRequest
from app.tools.capability import validate


async def restore_known_good_template(request: RestoreActionRequest) -> ActionResult:
    try:
        validate(request.capability_token, request)
    except ValueError:
        return ActionResult(
            status="failed",
            details={"reason": "Invalid execution capability", "mutation_performed": False},
        )
    try:
        result = await KubernetesClient().restore_known_good(request)
    except ValueError:
        return ActionResult(
            status="failed",
            details={"reason": "Exact preflight denied", "mutation_performed": False},
        )
    return ActionResult(status="succeeded", details=result)
