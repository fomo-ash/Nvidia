"""Capability scope, exact patch and zero-mutation replay denials."""

import base64
import copy
import hashlib
import hmac
import json
import time

import httpx
import pytest

from app.adapters import kubernetes
from app.config import settings
from app.schemas.actions import RestoreActionRequest
from app.tools.capability import validate
from app.tools.patch import restore_known_good_template

GOOD = {
    "spec": {
        "containers": [
            {
                "name": "sample-api",
                "env": [
                    {"name": "FAIL_MODE", "value": "off"},
                ],
            }
        ]
    }
}
BAD = copy.deepcopy(GOOD)
BAD["spec"]["containers"][0]["env"][0]["value"] = "on"


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def request():
    return RestoreActionRequest(
        execution_id="00000000-0000-0000-0000-000000000001",
        proposal_hash="a" * 64,
        uid="fixture-uid",
        resource_version="10",
        expected_bad_template_hash=digest(BAD),
        desired_good_template_hash=digest(GOOD),
        desired_template=GOOD,
        capability_token="placeholder",
    )


def signed(item, *, expiry=60, overrides=None):
    claims = {
        "execution_id": item.execution_id,
        "proposal_hash": item.proposal_hash,
        "cluster": "local-kind",
        "namespace": item.namespace,
        "deployment": item.deployment,
        "uid": item.uid,
        "resource_version": item.resource_version,
        "expected_bad_template_hash": item.expected_bad_template_hash,
        "desired_good_template_hash": item.desired_good_template_hash,
        "expires_at": int(time.time()) + expiry,
    }
    claims.update(overrides or {})
    body = (
        base64.urlsafe_b64encode(json.dumps(claims, sort_keys=True, separators=(",", ":")).encode())
        .rstrip(b"=")
        .decode()
    )
    sig = hmac.new(
        settings.EXECUTION_SIGNING_KEY.encode(), body.encode(), hashlib.sha256
    ).hexdigest()
    return body + "." + sig


@pytest.mark.asyncio
async def test_capability_denies_wrong_scope_expiry_and_tampering(monkeypatch):
    monkeypatch.setattr(settings, "EXECUTION_SIGNING_KEY", "test-signing-key-" * 3)
    monkeypatch.setattr(settings, "KUBERNETES_WRITE_TOKEN_PATH", "/test/write-token")
    monkeypatch.setattr(settings, "KUBERNETES_TARGET_UID", "fixture-uid")
    item = request()
    item.capability_token = signed(item)
    assert validate(item.capability_token, item)["uid"] == "fixture-uid"
    calls = []

    async def patched(self, value):
        calls.append(value.execution_id)
        return {"mutation_performed": True}

    monkeypatch.setattr(kubernetes.KubernetesClient, "restore_known_good", patched)
    assert (await restore_known_good_template(item)).status == "succeeded"
    assert calls == [item.execution_id]
    signature_tail = "1" if item.capability_token[-1] == "0" else "0"
    tampered_token = item.capability_token[:-1] + signature_tail
    assert tampered_token != item.capability_token
    for token in (
        signed(item, expiry=-1),
        signed(item, overrides={"namespace": "kube-system"}),
        tampered_token,
    ):
        item.capability_token = token
        assert (await restore_known_good_template(item)).status == "failed"
    assert calls == [item.execution_id]


@pytest.mark.asyncio
async def test_exact_patch_uses_atomic_tests_and_replay_does_not_patch(monkeypatch):
    monkeypatch.setattr(settings, "KUBERNETES_TARGET_UID", "fixture-uid")
    item = request()
    current = {
        "metadata": {"uid": item.uid, "resourceVersion": "10", "annotations": {}},
        "spec": {"template": BAD},
    }
    patches = []

    def response(req):
        if req.method == "GET":
            return httpx.Response(200, json=current)
        patches.append(json.loads(req.content))
        assert req.headers["content-type"] == "application/json-patch+json"
        current["spec"]["template"] = GOOD
        current["metadata"]["resourceVersion"] = "11"
        current["metadata"]["annotations"]["fixproof.dev/execution-id"] = item.execution_id
        return httpx.Response(200, json=current)

    original = kubernetes.BoundedClient
    monkeypatch.setattr(
        kubernetes,
        "BoundedClient",
        lambda **kw: original(
            transport=httpx.MockTransport(response),
            **kw,
        ),
    )
    client = kubernetes.KubernetesClient()
    monkeypatch.setattr(client, "_write_connection", lambda: ({}, True))
    result = await client.restore_known_good(item)
    assert result["mutation_performed"] is True
    assert [step["op"] for step in patches[0]] == ["test", "test", "test", "replace", "add"]
    with pytest.raises(ValueError, match="preflight"):
        await client.restore_known_good(item)
    assert len(patches) == 1
