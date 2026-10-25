"""Reserved mutation boundary; execution is not enabled in this release."""

from app.schemas.actions import ActionResult, RestoreActionRequest


async def restore_known_good_template(request: RestoreActionRequest) -> ActionResult:
    return ActionResult(
        status="failed",
        details={"reason": "Restore is disabled pending exact approval and Kubernetes preflight"},
    )
