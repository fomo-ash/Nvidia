"""Owned-kind approval denials and one guarded restore, without recovery verification."""

import argparse
from datetime import datetime, timezone
import http.cookiejar
import json
import math
import secrets
import time
import urllib.error
import urllib.request

import kind_fixture as fixture
from smoke_investigation import configuration

DRIFT_KEY = "fixproof.dev/acceptance-drift"


class InvestigationUnavailable(RuntimeError):
    def __init__(self, run):
        analysis = run.get("result", {}).get("analysis") or {}
        self.details = {
            "investigation_id": run["id"],
            "status": run["status"],
            "gaps": run.get("result", {}).get("gaps", []),
            "advisory_action": analysis.get("analysis", {}).get("advisory_action"),
        }
        super().__init__("Investigation requires review; no proposal created")


class Operator:
    def __init__(self, secret):
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
        )
        self.csrf = ""
        self.csrf = self.request("/session", {"secret": secret})["csrf_token"]

    def request(self, path, payload=None, *, expected=(200,), key=None):
        headers = {"Content-Type": "application/json", "Origin": "http://localhost:5173"}
        if self.csrf:
            headers["X-CSRF-Token"] = self.csrf
        if payload is not None:
            headers["Idempotency-Key"] = key or secrets.token_hex(16)
        request = urllib.request.Request(
            "http://localhost:8000/api/v1" + path,
            data=json.dumps(payload).encode() if payload is not None else None,
            headers=headers,
        )
        try:
            response = self.opener.open(request, timeout=25)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            body = json.load(response)
            if response.status not in expected:
                raise RuntimeError(f"Unexpected HTTP {response.status} for {path}")
            return body


def state():
    current = fixture.deployment()
    return {
        "uid": current["metadata"]["uid"],
        "resource_version": current["metadata"]["resourceVersion"],
        "generation": current["metadata"]["generation"],
        "template_hash": fixture.template_hash(current["spec"]["template"]),
        "execution_id": current["metadata"].get("annotations", {}).get("fixproof.dev/execution-id"),
    }


def same_deployment(before):
    after = state()
    assert after == before, "A denied request changed the Deployment"
    return {"before": before, "after": after, "mutation_performed": False}


def propose(operator, target, name):
    report = operator.request(
        "/incidents",
        {
            "target_id": target["target_id"],
            "target_uid": target["uid"],
            "symptom": "http_5xx_spike",
            "summary": "Guarded execution acceptance: " + name,
        },
        expected=(200, 201),
    )
    incident = report["incident_id"]
    deadline = time.monotonic() + 150
    while time.monotonic() < deadline:
        runs = operator.request(f"/incidents/{incident}/investigations")
        run = next(
            (row for row in runs if row["request_id"] == report["investigation_request_id"]), None
        )
        if run and run["status"] != "collecting":
            break
        time.sleep(2)
    else:
        raise RuntimeError("Investigation deadline exceeded")
    analysis = run.get("result", {}).get("analysis") or {}
    if (
        run["status"] != "completed"
        or analysis.get("analysis", {}).get("advisory_action") != "restore_known_good_template"
    ):
        raise InvestigationUnavailable(run)
    assert run["result"]["assessment"] == "active"
    assert analysis["provider"] == "nebius"
    evidence = operator.request(f"/investigations/{run['id']}/evidence")
    assert len(evidence) == 5 and all(not row["collection_error"] for row in evidence)
    proposal = operator.request(
        f"/incidents/{incident}/proposals", {"investigation_id": run["id"]}, expected=(201,)
    )
    print(f"{name}: fresh investigation and exact proposal retained", flush=True)
    return proposal


def review_path(proposal):
    return f"/recommendations/{proposal['id']}"


def drift():
    fixture.kubectl(
        "annotate",
        "deployment",
        fixture.DEPLOYMENT,
        DRIFT_KEY + "=" + secrets.token_hex(8),
        "--overwrite",
    )


def internal_denials(proposal, *, replay=False):
    # Keys and capabilities stay inside API. Only denial labels/results leave it.
    code = r"""
import base64, copy, hashlib, hmac, json, sys, time
from types import SimpleNamespace
from uuid import UUID, uuid4
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.domain import Execution, TrustedBaseline
from app.services.capability import issue
from app.services.live_evidence import post
args = json.load(sys.stdin)
proposal = args["proposal"]
params = proposal["parameters"]
with SessionLocal() as db:
    good = db.get(TrustedBaseline, UUID(params["trusted_baseline_id"])).template
    if args.get("execution_id"):
        old = db.get(Execution, UUID(args["execution_id"]))
        identity = old.id
        params = old.parameters
    else:
        identity = uuid4()
results = []
for fault in (["same_execution_replay"] if args.get("execution_id") else ["signature", "expiry", "scope", "uid", "stale_resource_version", "template_hash"]):
    values = copy.deepcopy(params)
    if fault == "scope": values["namespace"] = "kube-system"
    if fault == "uid": values["uid"] = "not-the-registered-uid"
    if fault == "stale_resource_version": values["resource_version"] = "0"
    if fault == "template_hash": values["expected_bad_template_hash"] = "0" * 64
    execution = SimpleNamespace(id=identity, proposal_hash=proposal["proposal_hash"], parameters=values)
    token = issue(execution)
    if fault == "signature": token = token[:-1] + ("0" if token[-1] != "0" else "1")
    if fault == "expiry":
        body = json.loads(base64.urlsafe_b64decode(token.split(".")[0] + "=="))
        body["expires_at"] = int(time.time()) - 1
        encoded = base64.urlsafe_b64encode(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).rstrip(b"=").decode()
        token = encoded + "." + hmac.new(settings.execution_signing_key.encode(), encoded.encode(), hashlib.sha256).hexdigest()
    request = {key: values[key] for key in ("namespace", "deployment", "uid", "resource_version", "expected_bad_template_hash", "desired_good_template_hash")}
    request.update(execution_id=str(identity), proposal_hash=proposal["proposal_hash"], desired_template=good, capability_token=token)
    result = post(settings.mcp_server_url.rstrip("/") + "/internal/restore_known_good_template", request, timeout=15)
    assert result["status"] == "failed" and result["details"]["mutation_performed"] is False, fault
    results.append({"case": fault, "status": "denied", "mutation_performed": False})
print(json.dumps(results))
"""
    data = {"proposal": proposal}
    if replay:
        data["execution_id"] = replay
    output = fixture.run(
        fixture.COMPOSE + ["exec", "-T", "api", "python", "-c", code],
        stdin=json.dumps(data),
        capture=True,
    )
    return json.loads(output)


def validate_resume(previous, target_uid):
    if (
        previous.get("execution_requested")
        or previous.get("execution_id")
        or previous.get("status") == "passed"
    ):
        raise RuntimeError("An execution was already attempted; do not resume or replay")
    if previous.get("fault", {}).get("deployment_uid") != target_uid:
        raise RuntimeError("Previous acceptance belongs to another target UID")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Retain passed independent cases; refuse any previous execution attempt",
    )
    args = parser.parse_args()
    fixture.require_owned_cluster()
    runtime = json.loads(
        fixture.run(
            fixture.COMPOSE
            + [
                "exec",
                "-T",
                "api",
                "python",
                "-c",
                "import json; from app.core.config import settings; print(json.dumps({'enabled':settings.live_execution_enabled,'ttl':settings.proposal_ttl_seconds}))",
            ],
            capture=True,
        )
    )
    if runtime != {"enabled": True, "ttl": 60}:
        raise RuntimeError(
            "Use the execution overlay with LIVE_EXECUTION_ENABLED=true and PROPOSAL_TTL_SECONDS=60"
        )
    config = configuration()
    operator = Operator(config["OPERATOR_SECRET"])
    target = operator.request("/incident-targets")[0]
    assert target["uid"] == fixture.deployment()["metadata"]["uid"]
    baseline = operator.request("/trusted-baselines/current")
    assert baseline["target_uid"] == target["uid"]
    receipt = {"scope": "approval and guarded execution only", "cases": [], "status": "running"}
    output = fixture.STATE / "execution-acceptance.json"
    if args.resume:
        previous = json.loads(output.read_text())
        validate_resume(previous, target["uid"])
        receipt["cases"] = previous.get("cases", [])
        receipt["previous_stops"] = previous.get("previous_stops", []) + [
            {
                "status": previous["status"],
                "blocked_investigation": previous.get("blocked_investigation"),
            }
        ]
    completed = {row["case"] for row in receipt["cases"]}
    try:
        fixture.change(True)
        receipt["fault"] = fixture.observe(True, 90)
        for name in ("rejection", "expired_approval", "approval_drift", "execution_drift"):
            if name in completed:
                print(name + ": retained previous zero-mutation acceptance", flush=True)
                continue
            proposal = propose(operator, target, name)
            path = review_path(proposal)
            body = {"proposal_hash": proposal["proposal_hash"]}
            if name == "rejection":
                assert operator.request(path + "/reject", {})["status"] == "rejected"
                before = state()
                operator.request(path + "/approve", body, expected=(409,))
                operator.request(path + "/execute", body, expected=(409,))
            elif name == "approval_drift":
                drift()
                before = state()
                operator.request(path + "/approve", body, expected=(409,))
                operator.request(path + "/execute", body, expected=(409,))
            else:
                assert operator.request(path + "/approve", body)["status"] == "approved"
                if name == "expired_approval":
                    seconds = (
                        math.ceil(
                            (
                                datetime.fromisoformat(
                                    proposal["expires_at"].replace("Z", "+00:00")
                                )
                                - datetime.now(timezone.utc)
                            ).total_seconds()
                        )
                        + 1
                    )
                    assert 0 < seconds <= 65, "Use PROPOSAL_TTL_SECONDS=60 for this acceptance"
                    print("Waiting for the exact approval to expire", flush=True)
                    time.sleep(seconds)
                else:
                    drift()
                before = state()
                denied = operator.request(path + "/execute", body, expected=(409,))
                if name == "expired_approval":
                    assert "expired" in denied["detail"].lower()
            receipt["cases"].append(
                {
                    "case": name,
                    "proposal_id": proposal["id"],
                    "proposal_hash": proposal["proposal_hash"],
                    **same_deployment(before),
                }
            )
            fixture.write_private(output, receipt)
            print(name + ": denied with unchanged Deployment", flush=True)
        proposal = propose(operator, target, "approved_restore")
        path = review_path(proposal)
        body = {"proposal_hash": proposal["proposal_hash"]}
        before = state()
        operator.request(path + "/approve", {"proposal_hash": "0" * 64}, expected=(409,))
        assert operator.request(path + "/approve", body)["status"] == "approved"
        receipt["capability_denials"] = internal_denials(proposal)
        same_deployment(before)
        execution_key = secrets.token_hex(16)
        receipt.update(
            execution_requested=True,
            proposal_id=proposal["id"],
            proposal_hash=proposal["proposal_hash"],
        )
        fixture.write_private(output, receipt)  # Refuse resume even if the response is lost.
        execution = operator.request(
            path + "/execute", body, key=execution_key, expected=(201, 202)
        )
        receipt["execution_id"] = execution["id"]
        receipt["execution_status"] = execution["status"]
        fixture.write_private(output, receipt)
        if execution["status"] == "pending":
            execution = operator.request(f"/executions/{execution['id']}/reconcile", {})
        receipt["execution_id"] = execution["id"]
        receipt["execution_status"] = execution["status"]
        fixture.write_private(output, receipt)
        assert execution["status"] == "succeeded", "Outcome remains unresolved; do not retry"
        after = state()
        assert after["uid"] == before["uid"]
        assert after["template_hash"] == baseline["template_hash"]
        assert after["generation"] == before["generation"] + 1
        assert after["execution_id"] == execution["id"]
        replay = operator.request(path + "/execute", body, key=execution_key, expected=(201, 202))
        assert replay["id"] == execution["id"]
        operator.request(path + "/execute", body, expected=(409,))
        receipt["same_execution_replay"] = internal_denials(proposal, replay=execution["id"])
        final = state()
        assert final["generation"] == after["generation"]
        assert final["execution_id"] == after["execution_id"]
        assert final["template_hash"] == after["template_hash"]
        receipt.update(
            status="passed",
            proposal_id=proposal["id"],
            proposal_hash=proposal["proposal_hash"],
            before=before,
            after=after,
            idempotent_replay=True,
            duplicate_execution_denied=True,
            recovery_verification="not_run",
        )
        print(
            "Approved restore succeeded; replays denied; recovery verdict not requested", flush=True
        )
    except BaseException as error:
        receipt["status"] = "incomplete"
        if isinstance(error, InvestigationUnavailable):
            receipt["blocked_investigation"] = error.details
        raise
    finally:
        fixture.write_private(output, receipt)
        try:
            if DRIFT_KEY in fixture.deployment()["metadata"].get("annotations", {}):
                fixture.kubectl("annotate", "deployment", fixture.DEPLOYMENT, DRIFT_KEY + "-")
        finally:
            fixture.change(False)


if __name__ == "__main__":
    main()
