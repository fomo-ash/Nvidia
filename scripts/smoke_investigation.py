"""Real authenticated intake/evidence acceptance against the owned kind fixture."""

import http.cookiejar
import json
import secrets
import time
import urllib.error
import urllib.request

import kind_fixture as fixture


def configuration():
    result = {}
    for line in (fixture.ROOT / ".env").read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            result[key.strip()] = value.strip().strip('"').strip("'")
    return result


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
            response = opener.open(req, timeout=10)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            if response.status not in expected:
                raise RuntimeError(f"Unexpected HTTP {response.status} for {path}")
            return json.load(response)

    fixture.change(True)
    try:
        physical = fixture.observe(True, 90)
        csrf = request("/api/v1/session", {"secret": config["OPERATOR_SECRET"]})["csrf_token"]
        target = request("/api/v1/incident-targets")[0]
        assert target["uid"] == physical["deployment_uid"]
        body = {
            "target_id": target["target_id"],
            "target_uid": target["uid"],
            "symptom": "http_5xx_spike",
            "summary": "Live acceptance: sample returns 5xx",
            "note": None,
        }
        key = "live-" + secrets.token_hex(12)
        first = request("/api/v1/incidents", body, key, expected=(200, 201))
        assert request("/api/v1/incidents", body, key, expected=(200, 201)) == first
        incident = first["incident_id"]
        job = first["investigation_request_id"]
        deadline = time.monotonic() + 150
        run = None
        while time.monotonic() < deadline:
            runs = request(f"/api/v1/incidents/{incident}/investigations")
            run = next((item for item in runs if item.get("request_id") == job), None)
            if run and run["status"] != "collecting":
                break
            time.sleep(2)
        assert run and run["status"] != "collecting", "Investigation did not finish"
        evidence = request(f"/api/v1/investigations/{run['id']}/evidence")
        assert len(evidence) == 5 and all(not e["collection_error"] for e in evidence), (
            "Required live source unavailable"
        )
        assert all(e["mode"] == "live" and e["target_uid"] == target["uid"] for e in evidence)
        assert run["result"]["assessment"] == "active"
        if config.get("ANALYSIS_ENABLED", "false").lower() == "true":
            assert run["result"]["analysis"] is not None, (
                "Structured live model analysis unavailable"
            )
            assert run["result"]["analysis"]["provider"] == "nebius"
        fixture.run(fixture.COMPOSE + ["restart", "api", "worker"])
        deadline = time.monotonic() + 60
        while True:
            try:
                after = request(f"/api/v1/investigations/{run['id']}/evidence")
                assert after == evidence
                break
            except (OSError, RuntimeError):
                if time.monotonic() > deadline:
                    raise
                time.sleep(2)
        report = {
            "incident_id": incident,
            "request_id": job,
            "investigation_id": run["id"],
            "evidence_ids": [e["id"] for e in evidence],
            "sources": [e["source"] for e in evidence],
            "assessment": run["result"]["assessment"],
            "analysis_provider": run["result"]["analysis"]["provider"]
            if run["result"]["analysis"]
            else None,
            "analysis_model": run["result"]["analysis"]["model"]
            if run["result"]["analysis"]
            else None,
            "source_persistence_after_restart": True,
            "physical": physical,
        }
        fixture.write_private(fixture.STATE / "investigation-acceptance.json", report)
        print(json.dumps(report), flush=True)
    finally:
        fixture.change(False)


if __name__ == "__main__":
    main()
