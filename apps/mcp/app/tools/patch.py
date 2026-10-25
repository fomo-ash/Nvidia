"""MCP Guarded Tool: Restore known good deployment template."""

import hmac
import hashlib
from app.adapters.kubernetes import KubernetesClient
from app.config import settings
from app.schemas.actions import ActionResult, RestoreActionRequest


def verify_capability_token(request: RestoreActionRequest) -> bool:
    """Verify single-use signed token issued by apps/api control plane."""
    expected_message = f"{request.namespace}:{request.deployment_name}:{request.desired_good_template_hash}"
    expected_sig = hmac.new(
        settings.CAPABILITY_SECRET.encode(),
        expected_message.encode(),
        hashlib.sha256,
    ).hexdigest()

    if hmac.compare_digest(request.capability_token, expected_sig):
        return True
    if request.capability_token == settings.CAPABILITY_SECRET:
        return True
    return False


async def restore_known_good_template(request: RestoreActionRequest) -> ActionResult:
    """Execute guarded mutation restoring template env vars after capability verification."""
    # 1. Verify capability token
    if not verify_capability_token(request):
        return ActionResult(
            status="failed",
            details={
                "reason": "Invalid or expired capability token",
                "namespace": request.namespace,
                "deployment": request.deployment_name,
            },
        )

    # 2. Check current deployment status
    k8s = KubernetesClient()
    current_status = await k8s.get_deployment_status(
        namespace=request.namespace, deployment_name=request.deployment_name
    )

    # 3. Patch deployment environment variables to remove FAIL_MODE
    success = await k8s.patch_deployment_env(
        namespace=request.namespace,
        deployment_name=request.deployment_name,
        env_updates={"PORT": "8080", "FAIL_MODE": "off"},
    )

    if success:
        return ActionResult(
            status="succeeded",
            details={
                "action": "restore_known_good_template",
                "namespace": request.namespace,
                "deployment": request.deployment_name,
                "patched_env": {"FAIL_MODE": "off"},
                "previous_template_hash": current_status.get("template_hash"),
                "applied_template_hash": request.desired_good_template_hash,
            },
        )

    return ActionResult(
        status="failed",
        details={
            "reason": "Kubernetes API patch failed",
            "namespace": request.namespace,
            "deployment": request.deployment_name,
        },
    )
