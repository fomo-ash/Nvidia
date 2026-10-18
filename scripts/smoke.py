"""Check the running local demo through its public HTTP boundaries (Python stdlib only)."""

import json
import time
import urllib.error
import urllib.request


def request(path, payload=None, *, expected=200, base="http://localhost:8000"):
    data = json.dumps(payload).encode() if payload is not None else None
    method = "POST" if payload is not None else "GET"
    req = urllib.request.Request(
        base + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
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
    assert request(path + "/investigate", {})["version"] == 2
    report = request("/api/v1/cost-analyses")[0]
    assert report["total_cost"] == 2450 and report["estimated_savings"]["amount"] == 525
    print(
        "Stack smoke passed: health, SPA routing, investigation, evidence, exact approval, versioning, costs."
    )


if __name__ == "__main__":
    main()
