"""Live read-only proposal/approval acceptance; always reset the owned fixture."""

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

    def request(path, payload=None, key=None, expected=(200,)):
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
            response = opener.open(req, timeout=15)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            body = json.load(response)
            if response.status not in expected:
                raise RuntimeError(f"Unexpected HTTP {response.status} for {path}: {body.get('detail', '')}")
            return body

    fixture.change(True)
    try:
        physical = fixture.observe(True, 90)
        csrf = request("/api/v1/session", {"secret": config["OPERATOR_SECRET"]})["csrf_token"]
        target = request("/api/v1/incident-targets")[0]
        assert target["uid"] == physical["deployment_uid"]
        baseline = request("/api/v1/trusted-baselines/current")
        assert baseline["target_uid"] == target["uid"]
        report = request("/api/v1/incidents", {
            "target_id": target["target_id"], "target_uid": target["uid"],
            "symptom": "http_5xx_spike", "summary": "Exact proposal acceptance: live 5xx",
        }, "proposal-smoke-" + secrets.token_hex(12), expected=(200, 201))
        incident_id, job_id = report["incident_id"], report["investigation_request_id"]
        deadline = time.monotonic() + 150
        run = None
        while time.monotonic() < deadline:
            runs = request(f"/api/v1/incidents/{incident_id}/investigations")
            run = next((item for item in runs if item.get("request_id") == job_id), None)
            if run and run["status"] != "collecting":
                break
            time.sleep(2)
        assert run and run["status"] == "completed", "Live analysis unavailable"
        assert run["result"]["assessment"] == "active"
        assert run["result"]["analysis"]["analysis"]["advisory_action"] == "restore_known_good_template"
        evidence = request(f"/api/v1/investigations/{run['id']}/evidence")
        assert len(evidence) == 5 and all(not row["collection_error"] for row in evidence)
        proposal = request(f"/api/v1/incidents/{incident_id}/proposals", {
            "investigation_id": run["id"],
        }, "proposal-create-" + secrets.token_hex(12), expected=(201,))
        assert proposal["parameters"]["desired_good_template_hash"] == baseline["template_hash"]
        assert len(proposal["evidence"]) == len(evidence)
        review = f"/api/v1/recommendations/{proposal['id']}/approve"
        request(review, {"proposal_hash": "0" * 64}, "wrong-hash-" + secrets.token_hex(12), expected=(409,))
        approved = request(review, {"proposal_hash": proposal["proposal_hash"]},
                           "exact-approval-" + secrets.token_hex(12))
        assert approved["status"] == "approved"
        request(f"/api/v1/recommendations/{proposal['id']}/execute",
                {"proposal_hash": proposal["proposal_hash"]},
                "blocked-execution-" + secrets.token_hex(12), expected=(409,))
        unchanged = fixture.deployment()
        assert fixture.template_hash(unchanged["spec"]["template"]) == proposal["parameters"]["expected_bad_template_hash"]
        record = {
            "incident_id": incident_id, "investigation_id": run["id"],
            "evidence_ids": [row["id"] for row in evidence],
            "proposal_id": proposal["id"], "proposal_hash": proposal["proposal_hash"],
            "approval_status": approved["status"], "live_execution_denied": True,
            "baseline_hash": baseline["template_hash"],
            "observed_bad_hash": proposal["parameters"]["expected_bad_template_hash"],
            "physical": physical,
        }
        fixture.write_private(fixture.STATE / "proposal-acceptance.json", record)
        print(json.dumps(record), flush=True)
    finally:
        fixture.change(False)


if __name__ == "__main__":
    main()
