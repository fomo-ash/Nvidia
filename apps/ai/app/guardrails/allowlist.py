"""Guardrail: Enforce strict allowlist for automated remediation actions."""

from typing import Any


class ActionAllowlistGuard:
    ALLOWED_ACTIONS = {"restore_known_good_template"}
    ALLOWED_NAMESPACES = {"fixproof-demo"}
    ALLOWED_DEPLOYMENTS = {"sample-api"}

    @classmethod
    def validate_action(cls, action_type: str, parameters: dict[str, Any]) -> tuple[bool, str]:
        """Verify action is strictly allowlisted and target matches bounded demo scope."""
        if action_type not in cls.ALLOWED_ACTIONS:
            return (
                False,
                f"Action '{action_type}' is not in the permitted allowlist {cls.ALLOWED_ACTIONS}.",
            )

        ns = parameters.get("namespace")
        if ns and ns not in cls.ALLOWED_NAMESPACES:
            return (
                False,
                f"Target namespace '{ns}' is outside permitted namespaces {cls.ALLOWED_NAMESPACES}.",
            )

        dep = parameters.get("deployment_name") or parameters.get("deployment")
        if dep and dep not in cls.ALLOWED_DEPLOYMENTS:
            return (
                False,
                f"Target deployment '{dep}' is outside permitted deployments {cls.ALLOWED_DEPLOYMENTS}.",
            )

        return True, "Action permitted by policy."
