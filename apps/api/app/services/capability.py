"""Short-lived exact execution authorization; API never holds a Kubernetes write token."""

import base64
import hashlib
import hmac
import json
import time

from app.core.config import settings


def issue(execution):
    if len(settings.execution_signing_key) < 32:
        raise RuntimeError("Execution signing is not configured")
    params = execution.parameters
    claims = {
        "execution_id": str(execution.id),
        "proposal_hash": execution.proposal_hash,
        "cluster": params["cluster"],
        "namespace": params["namespace"],
        "deployment": params["deployment"],
        "uid": params["uid"],
        "resource_version": params["resource_version"],
        "expected_bad_template_hash": params["expected_bad_template_hash"],
        "desired_good_template_hash": params["desired_good_template_hash"],
        "expires_at": int(time.time()) + 60,
    }
    body = (
        base64.urlsafe_b64encode(json.dumps(claims, sort_keys=True, separators=(",", ":")).encode())
        .rstrip(b"=")
        .decode()
    )
    signature = hmac.new(
        settings.execution_signing_key.encode(), body.encode(), hashlib.sha256
    ).hexdigest()
    return body + "." + signature
