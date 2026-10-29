"""Two sequential owned-kind restores with independent recovery measurements."""

import http.cookiejar
import json
import secrets
import time
import urllib.error
import urllib.request

import kind_fixture as fixture
from smoke_investigation import configuration


def main():
    config = configuration()
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
    )
    csrf = ""

    def request(path, payload=None, key=None, expected=(200,), timeout=15):
        headers = {"Content-Type": "application/json", "Origin": "http://localhost:5173"}
        if csrf:
            headers["X-CSRF-Token"] = csrf
        if key:
            headers["Idempotency-Key"] = key
        req = urllib.request.Request(
            "http://localhost:8000" + path,
            data=json.dumps(payload).encode() if payload is not None else None,
            headers=headers,
        )
        try:
            response = opener.open(req, timeout=timeout)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            body = json.load(response)
            if response.status not in expected:
                raise RuntimeError(
                    f"Unexpected HTTP {response.status} for {path}: {body.get('detail', '')}"
                )
            return body

    csrf = request("/api/v1/session", {"secret": config["OPERATOR_SECRET"]})["csrf_token"]
    target = request("/api/v1/incident-targets")[0]
    baseline = request("/api/v1/trusted-baselines/current")
    assert target["uid"] == baseline["target_uid"]
    receipts = []
    try:
        for cycle in (1, 2):
            fixture.change(True)
            physical_fault = fixture.observe(True, 90)
            assert physical_fault["error_ratio"] > 0.2
            report = request(
                "/api/v1/incidents",
                {
                    "target_id": target["target_id"],
                    "target_uid": target["uid"],
                    "symptom": "http_5xx_spike",
                    "summary": f"Sequential recovery acceptance {cycle}: live 5xx",
                },
                "recovery-report-" + secrets.token_hex(12),
                expected=(200, 201),
            )
            incident_id, job_id = report["incident_id"], report["investigation_request_id"]
            deadline = time.monotonic() + 150
            run = None
            while time.monotonic() < deadline:
                runs = request(f"/api/v1/incidents/{incident_id}/investigations")
                run = next((item for item in runs if item.get("request_id") == job_id), None)
                if run and run["status"] != "collecting":
                    break
                time.sleep(2)
            assert run and run["status"] == "completed", "Live investigation unavailable"
            assert run["result"]["assessment"] == "active"
            assert (
                run["result"]["analysis"]["analysis"]["advisory_action"]
                == "restore_known_good_template"
            )
            evidence = request(f"/api/v1/investigations/{run['id']}/evidence")
            assert len(evidence) == 5 and all(not row["collection_error"] for row in evidence)
            proposal = request(
                f"/api/v1/incidents/{incident_id}/proposals",
                {"investigation_id": run["id"]},
                "recovery-proposal-" + secrets.token_hex(12),
                expected=(201,),
            )
            assert proposal["parameters"]["desired_good_template_hash"] == baseline["template_hash"]
            path = f"/api/v1/recommendations/{proposal['id']}"
            request(
                path + "/approve",
                {"proposal_hash": "0" * 64},
                "wrong-hash-" + secrets.token_hex(12),
                expected=(409,),
            )
            approval = request(
                path + "/approve",
                {"proposal_hash": proposal["proposal_hash"]},
                "exact-approval-" + secrets.token_hex(12),
            )
            assert approval["status"] == "approved"
            execution_key = "execute-" + secrets.token_hex(12)
            execution = request(
                path + "/execute",
                {"proposal_hash": proposal["proposal_hash"]},
                execution_key,
                expected=(201, 202),
            )
            if execution["status"] == "pending":
                execution = request(
                    f"/api/v1/executions/{execution['id']}/reconcile",
                    {},
                    "reconcile-" + secrets.token_hex(12),
                )
            assert execution["status"] == "succeeded", execution
            replay = request(
                path + "/execute",
                {"proposal_hash": proposal["proposal_hash"]},
                execution_key,
                expected=(201, 202),
            )
            assert replay["id"] == execution["id"]
            request(
                path + "/execute",
                {"proposal_hash": proposal["proposal_hash"]},
                "duplicate-" + secrets.token_hex(12),
                expected=(409,),
            )
            verification = request(
                f"/api/v1/executions/{execution['id']}/verify",
                {},
                "verify-" + secrets.token_hex(12),
                expected=(201,),
                timeout=150,
            )
            assert verification["status"] == "passed", verification
            measurements = verification["observations"]["measurements"]
            assert len(measurements) == 6
            assert verification["observations"]["mode"] == "live"
            healthy = fixture.deployment()
            assert fixture.template_hash(healthy["spec"]["template"]) == baseline["template_hash"]
            assert (
                healthy["metadata"]["annotations"]["fixproof.dev/execution-id"] == execution["id"]
            )
            receipt = {
                "cycle": cycle,
                "incident_id": incident_id,
                "investigation_id": run["id"],
                "proposal_id": proposal["id"],
                "approval_status": approval["status"],
                "execution_id": execution["id"],
                "execution_status": execution["status"],
                "verification_id": verification["id"],
                "verification_status": verification["status"],
                "measurements": measurements,
                "wrong_hash_denied": True,
                "duplicate_execution_denied": True,
            }
            receipts.append(receipt)
            print(
                json.dumps(
                    {"cycle": cycle, "verification": "passed", "execution_id": execution["id"]}
                ),
                flush=True,
            )
        fixture.write_private(fixture.STATE / "recovery-acceptance.json", receipts)
    finally:
        fixture.change(False)


if __name__ == "__main__":
    main()
