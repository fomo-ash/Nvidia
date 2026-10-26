"""Create, fault, reset, and measure the local kind incident fixture.

Requires Docker, kind, kubectl, and (for verify) the Compose stack. Run from any
working directory: python scripts/kind_demo.py bootstrap|fault|reset|verify ...
"""

import argparse
import copy
import hashlib
import json
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / ".local" / "kind_baseline.json"
CLUSTER = "fixproof"
NAMESPACE = "fixproof-demo"
DEPLOYMENT = "sample-api"
SAMPLE_URL = "http://localhost:18080"
PROMETHEUS_URL = "http://localhost:9090"
KIND = (
    str(ROOT / ".local" / "bin" / "kind.exe")
    if (ROOT / ".local" / "bin" / "kind.exe").exists()
    else "kind"
)


def run(*args, capture=False):
    result = subprocess.run(args, cwd=ROOT, check=True, text=True, capture_output=capture)
    return result.stdout if capture else ""


def deployment():
    return json.loads(
        run(
            "kubectl",
            "--context",
            "kind-fixproof",
            "-n",
            NAMESPACE,
            "get",
            "deployment",
            DEPLOYMENT,
            "-o",
            "json",
            capture=True,
        )
    )


def digest(template):
    raw = json.dumps(template, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def request(url):
    try:
        response = urllib.request.urlopen(url, timeout=5)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        return response.status, response.read()


def wait_http(path, expected, seconds=60):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            status, _ = request(SAMPLE_URL + path)
            if status == expected:
                return
        except OSError:
            pass
        time.sleep(2)
    raise RuntimeError(f"{path} did not return HTTP {expected} within {seconds}s")


def rollout():
    run(
        "kubectl",
        "--context",
        "kind-fixproof",
        "-n",
        NAMESPACE,
        "rollout",
        "status",
        f"deployment/{DEPLOYMENT}",
        "--timeout=120s",
    )


def save_baseline(current):
    template = current["spec"]["template"]
    containers = template["spec"]["containers"]
    if any(
        item.get("name") == "FAIL_MODE" and item.get("value", "").lower() == "on"
        for container in containers
        for item in container.get("env", [])
    ):
        raise RuntimeError("Refusing to capture a faulty Deployment as the trusted baseline")
    baseline = {
        "cluster": CLUSTER,
        "namespace": NAMESPACE,
        "deployment": DEPLOYMENT,
        "uid": current["metadata"]["uid"],
        "revision": current["metadata"]
        .get("annotations", {})
        .get("deployment.kubernetes.io/revision"),
        "captured_at": datetime.now(UTC).isoformat(),
        "template": template,
        "template_hash": digest(template),
    }
    BASELINE.parent.mkdir(parents=True, exist_ok=True)
    BASELINE.write_text(json.dumps(baseline, indent=2) + "\n", encoding="utf-8")
    return baseline


def load_baseline(current):
    if not BASELINE.exists():
        raise RuntimeError("No trusted baseline. Run bootstrap while the sample is healthy.")
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    if (baseline["cluster"], baseline["namespace"], baseline["deployment"]) != (
        CLUSTER,
        NAMESPACE,
        DEPLOYMENT,
    ):
        raise RuntimeError("Local baseline target mismatch")
    if baseline["uid"] != current["metadata"]["uid"]:
        raise RuntimeError("Deployment UID changed; rebootstrap the healthy fixture")
    if baseline["template_hash"] != digest(baseline["template"]):
        raise RuntimeError("Local baseline hash mismatch")
    return baseline


def patch_template(current, template):
    patch = json.dumps(
        [
            {"op": "test", "path": "/metadata/uid", "value": current["metadata"]["uid"]},
            {
                "op": "test",
                "path": "/metadata/resourceVersion",
                "value": current["metadata"]["resourceVersion"],
            },
            {"op": "replace", "path": "/spec/template", "value": template},
        ],
        separators=(",", ":"),
    )
    run(
        "kubectl",
        "--context",
        "kind-fixproof",
        "-n",
        NAMESPACE,
        "patch",
        "deployment",
        DEPLOYMENT,
        "--type=json",
        "-p",
        patch,
    )
    rollout()


def bootstrap():
    clusters = run(KIND, "get", "clusters", capture=True).splitlines()
    if CLUSTER not in clusters:
        run(
            KIND,
            "create",
            "cluster",
            "--name",
            CLUSTER,
            "--config",
            str(ROOT / "infra" / "kind" / "cluster.yaml"),
        )
    run("docker", "build", "-t", "fixproof/sample-api:local", str(ROOT / "apps" / "sample"))
    run(KIND, "load", "docker-image", "fixproof/sample-api:local", "--name", CLUSTER)
    run(
        "kubectl",
        "--context",
        "kind-fixproof",
        "apply",
        "-f",
        str(ROOT / "infra" / "kind" / "sample.yaml"),
    )
    rollout()
    run(
        "kubectl",
        "--context",
        "kind-fixproof",
        "-n",
        NAMESPACE,
        "rollout",
        "status",
        "deployment/sample-traffic",
        "--timeout=120s",
    )
    wait_http("/healthz", 200)
    current = deployment()
    if BASELINE.exists():
        try:
            baseline = load_baseline(current)
        except RuntimeError as error:
            if "UID changed" not in str(error):
                raise
            baseline = save_baseline(current)
    else:
        baseline = save_baseline(current)
    if digest(current["spec"]["template"]) != baseline["template_hash"]:
        raise RuntimeError("Current template differs from saved baseline; run reset")
    print(
        f"Healthy baseline: UID={baseline['uid']} revision={baseline['revision']} "
        f"sha256={baseline['template_hash']}"
    )


def fault():
    current = deployment()
    baseline = load_baseline(current)
    if digest(current["spec"]["template"]) != baseline["template_hash"]:
        raise RuntimeError("Deployment already changed; reset before injecting another fault")
    template = copy.deepcopy(baseline["template"])
    container = template["spec"]["containers"][0]
    container["env"] = [
        item for item in container.get("env", []) if item.get("name") != "FAIL_MODE"
    ] + [{"name": "FAIL_MODE", "value": "on"}]
    patch_template(current, template)
    wait_http("/readyz", 200)
    wait_http("/healthz", 500)
    updated = deployment()
    if int(
        updated["metadata"].get("annotations", {}).get("deployment.kubernetes.io/revision", 0)
    ) <= int(baseline["revision"] or 0):
        raise RuntimeError("Fault did not create a new Deployment revision")
    print(
        f"Fault active: revision={updated['metadata'].get('annotations', {}).get('deployment.kubernetes.io/revision')} "
        f"sha256={digest(updated['spec']['template'])}"
    )


def reset():
    current = deployment()
    baseline = load_baseline(current)
    patch_template(current, baseline["template"])
    wait_http("/healthz", 200)
    updated = deployment()
    if digest(updated["spec"]["template"]) != baseline["template_hash"]:
        raise RuntimeError("Reset did not restore the exact captured pod template")
    print(
        f"Reset healthy: revision={updated['metadata'].get('annotations', {}).get('deployment.kubernetes.io/revision')} "
        f"sha256={baseline['template_hash']}"
    )


def prom_value(query):
    url = PROMETHEUS_URL + "/api/v1/query?" + urllib.parse.urlencode({"query": query})
    status, raw = request(url)
    if status != 200:
        raise RuntimeError(f"Prometheus returned HTTP {status}")
    result = json.loads(raw)
    if result["status"] != "success":
        raise RuntimeError("Prometheus query failed")
    samples = result["data"]["result"]
    return float(samples[0]["value"][1]) if samples else 0.0


def verify(phase):
    # Prometheus' own successful scrape is the container-side connectivity proof.
    if prom_value('up{job="fixproof-sample"}') != 1:
        raise RuntimeError("Prometheus cannot scrape the kind sample from its container")
    expected = 500 if phase == "fault" else 200
    wait_http("/healthz", expected, seconds=10)
    wait_http("/readyz", 200, seconds=10)
    current = deployment()
    baseline = load_baseline(current)
    changed = digest(current["spec"]["template"]) != baseline["template_hash"]
    if changed != (phase == "fault"):
        raise RuntimeError("Deployment template does not match expected phase")
    if phase == "fault" and int(
        current["metadata"].get("annotations", {}).get("deployment.kubernetes.io/revision", 0)
    ) <= int(baseline["revision"] or 0):
        raise RuntimeError("Fault is not a later Deployment revision")
    total = prom_value(
        'sum(increase(sample_http_requests_total{job="fixproof-sample",route="/api/work"}[1m]))'
    )
    errors = prom_value(
        'sum(increase(sample_http_requests_total{job="fixproof-sample",route="/api/work",status_class="5xx"}[1m]))'
    )
    ratio = errors / total if total else 0.0
    observation = {
        "observed_at": datetime.now(UTC).isoformat(),
        "phase": phase,
        "revision": current["metadata"]
        .get("annotations", {})
        .get("deployment.kubernetes.io/revision"),
        "requests_60s": round(total, 1),
        "errors_60s": round(errors, 1),
        "error_ratio": round(ratio, 3),
        "prometheus_up": True,
        "health_status": expected,
        "readiness_status": 200,
    }
    print(json.dumps(observation, indent=2))
    if total < 20:
        raise RuntimeError("Fewer than 20 work requests in the 60-second metric window")
    if phase == "fault" and ratio <= 0.20:
        raise RuntimeError("Fault did not produce more than 20% 5xx")
    if phase == "healthy" and ratio >= 0.01:
        raise RuntimeError("Healthy window still has at least 1% 5xx")
    return observation


def cycle():
    """Exercise the acceptance gate twice and save measured, local results."""
    bootstrap()
    observations = []
    time.sleep(70)
    observations.append(verify("healthy"))
    for _ in range(2):
        fault()
        time.sleep(70)
        observations.append(verify("fault"))
        reset()
        time.sleep(70)
        observations.append(verify("healthy"))
    path = ROOT / ".local" / "kind_acceptance.json"
    path.write_text(json.dumps(observations, indent=2) + "\n", encoding="utf-8")
    print(f"Two healthy/fault/reset cycles passed; observations saved to {path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("bootstrap", "fault", "reset", "verify", "cycle"))
    parser.add_argument("--phase", choices=("healthy", "fault"), help="Required for verify")
    args = parser.parse_args()
    try:
        if args.command == "bootstrap":
            bootstrap()
        elif args.command == "fault":
            fault()
        elif args.command == "reset":
            reset()
        elif args.command == "cycle":
            cycle()
        elif args.phase:
            verify(args.phase)
        else:
            parser.error("verify requires --phase healthy or --phase fault")
    except (subprocess.CalledProcessError, OSError, RuntimeError, ValueError) as error:
        print(f"kind demo failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
