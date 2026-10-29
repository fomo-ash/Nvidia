"""Independent MCP validation of a bounded API-issued execution capability."""

import base64
import binascii
import hashlib
import hmac
import json
import time

from app.config import settings


def validate(token, request):
    if len(settings.EXECUTION_SIGNING_KEY) < 32 or not settings.KUBERNETES_WRITE_TOKEN_PATH:
        raise ValueError("Execution capability is not configured")
    if not isinstance(token, str) or len(token) > 4096:
        raise ValueError("Invalid execution capability")
    try:
        body, signature = token.rsplit(".", 1)
        expected = hmac.new(
            settings.EXECUTION_SIGNING_KEY.encode(), body.encode(), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError("Bad signature")
        claims = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
        if not isinstance(claims, dict) or set(claims) != {
            "execution_id",
            "proposal_hash",
            "cluster",
            "namespace",
            "deployment",
            "uid",
            "resource_version",
            "expected_bad_template_hash",
            "desired_good_template_hash",
            "expires_at",
        }:
            raise ValueError("Unexpected capability shape")
        if (
            not isinstance(claims["expires_at"], int)
            or not 0 < claims["expires_at"] - time.time() <= 60
        ):
            raise ValueError("Expired capability")
        if (
            claims["cluster"] != "local-kind"
            or claims["namespace"] != "fixproof-demo"
            or claims["deployment"] != "sample-api"
            or claims["uid"] != settings.KUBERNETES_TARGET_UID
            or any(
                claims[field] != getattr(request, field)
                for field in (
                    "execution_id",
                    "proposal_hash",
                    "namespace",
                    "deployment",
                    "uid",
                    "resource_version",
                    "expected_bad_template_hash",
                    "desired_good_template_hash",
                )
            )
        ):
            raise ValueError("Capability scope mismatch")
        return claims
    except (ValueError, TypeError, KeyError, UnicodeError, binascii.Error) as exc:
        raise ValueError("Invalid execution capability") from exc
