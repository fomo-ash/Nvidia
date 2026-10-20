"""Check the running local demo through its public HTTP boundaries (Python stdlib only)."""

import json
import time
import urllib.error
import urllib.request


def request(path, payload=None, *, expected=200, base="http://localhost:8000", headers=None):
    data = json.dumps(payload).encode() if payload is not None else None
    method = "POST" if payload is not None else "GET"
    req = urllib.request.Request(
        base + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    try:
        response = urllib.request.urlopen(req, timeout=10)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        if response.status != expected:
            raise RuntimeError(f"{method} {path}: expected {expected}, got {response.status}")
        raw = response.read()
        return (
            json.loads(raw)
            if "application/json" in response.headers.get("Content-Type", "")
            else raw
        )


def main():
    request("/health/ready")
    assert b'id="root"' in request("/incidents", base="http://localhost:5173")
    for base, path in [
        ("http://localhost:9090", "/-/ready"),
        ("http://localhost:3000", "/api/health"),
    ]:
        deadline = time.monotonic() + 60
        while True:
            try:
                request(path, base=base)
                break
            except (OSError, RuntimeError):
                if time.monotonic() >= deadline:
                    raise
                time.sleep(1)
    incident = request(
        "/api/v1/incidents",
        {
            "title": "Foundation smoke incident",
            "severity": "high",
            "summary": "Synthetic scaffold verification",
        },
        expected=201,
    )
    path = f"/api/v1/incidents/{incident['id']}"
    proposal = request(path + "/investigate", {})
    assert request(path + "/evidence") == proposal["evidence"]
    approval = f"/api/v1/recommendations/{proposal['id']}/approve"
    assert request(approval, {"proposal_hash": proposal["proposal_hash"]})["status"] == "approved"
    request(approval, {"proposal_hash": proposal["proposal_hash"]}, expected=409)
    newer = request(path + "/investigate", {})
    assert newer["version"] == 2
    request(
        f"/api/v1/recommendations/{newer['id']}/approve", {"proposal_hash": newer["proposal_hash"]}
    )
    execution_path = f"/api/v1/recommendations/{newer['id']}/execute"
    execution_headers = {"Idempotency-Key": "smoke-" + newer["id"]}
    execution = request(
        execution_path,
        {"proposal_hash": newer["proposal_hash"]},
        expected=201,
        headers=execution_headers,
    )
    assert execution["status"] == "failed" and execution["result"]["mutation_performed"] is False
    assert (
        request(
            execution_path,
            {"proposal_hash": newer["proposal_hash"]},
            expected=201,
            headers=execution_headers,
        )["id"]
        == execution["id"]
    )
    assert request(f"/api/v1/executions/{execution['id']}")["status"] == "failed"
    report = request("/api/v1/cost-analyses", {}, expected=201)
    assert request(f"/api/v1/cost-analyses/{report['id']}")["source_count"] == 3
    assert len(request(f"/api/v1/cost-analyses/{report['id']}/records")) == 3
    assert report["total_cost"] == 2450 and report["estimated_savings"]["amount"] == 525
    print(
        "Stack smoke passed: health, SPA routing, normalized investigation, exact approval, idempotent unavailable execution, and persisted sample costs. No infrastructure mutation occurred."
    )


if __name__ == "__main__":
    main()
