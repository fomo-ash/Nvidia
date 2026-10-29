"""Manage only the disposable FixProof kind fixture (Python standard library)."""

import argparse
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import platform
from pathlib import Path
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".local" / "kind"
KUBECONFIG = STATE / "kubeconfig"
KUBECTL = STATE / "bin" / ("kubectl.exe" if platform.system() == "Windows" else "kubectl")
KUBECTL_VERSION = "v1.34.1"
BASELINE = STATE / "baseline.json"
RECEIPT = STATE / "ownership.json"
CLUSTER = "fixproof-demo"
NODE = CLUSTER + "-control-plane"
NAMESPACE = "fixproof-demo"
DEPLOYMENT = "sample-api"
CONTEXT = "kind-" + CLUSTER
COMPOSE = ["docker", "compose", "-f", "compose.yaml", "-f", "compose.kind.yaml"]
SAMPLE_URL = "http://127.0.0.1:18080"
PROMETHEUS = "http://127.0.0.1:9090"


def run(args, *, stdin=None, capture=False, timeout=300):
    result = subprocess.run(
        args, cwd=ROOT, input=stdin, text=True, capture_output=capture, check=True, timeout=timeout
    )
    return result.stdout.strip() if capture else ""


def kubectl(*args, stdin=None, capture=False):
    return run(
        [
            str(KUBECTL),
            "--kubeconfig",
            str(KUBECONFIG),
            "--context",
            CONTEXT,
            "--namespace",
            NAMESPACE,
            *args,
        ],
        stdin=stdin,
        capture=capture,
    )


def now():
    return datetime.now(timezone.utc).isoformat()


def template_hash(template):
    # Matches the MCP Deployment reader's template canonicalization.
    return hashlib.sha256(json.dumps(template, sort_keys=True).encode()).hexdigest()


def image_tag():
    digest = hashlib.sha256()
    for name in ["Dockerfile", "sample.py", "traffic.py"]:
        digest.update((ROOT / "apps" / "sample" / name).read_bytes())
    return "fixproof-sample:" + digest.hexdigest()[:16]


def write_private(path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.chmod(0o600)
    temporary.replace(path)


def ensure_kubectl():
    if KUBECTL.is_file():
        version = json.loads(run([str(KUBECTL), "version", "--client", "-o", "json"], capture=True))
        if version["clientVersion"]["gitVersion"] != KUBECTL_VERSION:
            raise RuntimeError("Project-local kubectl version differs from the pinned version")
        return
    systems = {"Darwin": "darwin", "Linux": "linux", "Windows": "windows"}
    machines = {"arm64": "arm64", "aarch64": "arm64", "x86_64": "amd64", "AMD64": "amd64"}
    system, machine = systems[platform.system()], machines[platform.machine()]
    base = f"https://dl.k8s.io/release/{KUBECTL_VERSION}/bin/{system}/{machine}/" + KUBECTL.name
    print("Downloading checksum-verified project-local kubectl " + KUBECTL_VERSION, flush=True)
    with urllib.request.urlopen(base + ".sha256", timeout=30) as response:
        expected = response.read(256).decode().strip()
    with urllib.request.urlopen(base, timeout=90) as response:
        data = response.read(100_000_000)
    if hashlib.sha256(data).hexdigest() != expected:
        raise RuntimeError("kubectl download checksum mismatch")
    KUBECTL.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = KUBECTL.with_suffix(".download")
    temporary.write_bytes(data)
    temporary.chmod(0o700)
    temporary.replace(KUBECTL)


def require_owned_cluster():
    if not RECEIPT.is_file() or not KUBECONFIG.is_file():
        raise RuntimeError("No owned fixture receipt/kubeconfig; refusing to use another cluster")
    receipt = json.loads(RECEIPT.read_text())
    node_id = run(["docker", "inspect", "--format", "{{.Id}}", NODE], capture=True)
    if receipt.get("cluster") != CLUSTER or receipt.get("node_id") != node_id:
        raise RuntimeError("Cluster identity differs from the fixture receipt")


def deployment():
    require_owned_cluster()
    return json.loads(kubectl("get", "deployment", DEPLOYMENT, "-o", "json", capture=True))


def load_baseline(current):
    if not BASELINE.is_file():
        raise RuntimeError("No captured baseline; run up before fault or reset")
    baseline = json.loads(BASELINE.read_text())
    if (
        baseline.get("cluster"),
        baseline.get("namespace"),
        baseline.get("name"),
        baseline.get("uid"),
    ) != (CLUSTER, NAMESPACE, DEPLOYMENT, current["metadata"]["uid"]):
        raise RuntimeError("Baseline target identity differs from the current Deployment")
    if template_hash(baseline["template"]) != baseline.get("template_hash"):
        raise RuntimeError("Captured baseline hash mismatch")
    return baseline


def faulty_template(good):
    template = copy.deepcopy(good)
    container = next(c for c in template["spec"]["containers"] if c["name"] == "sample-api")
    setting = next(e for e in container["env"] if e["name"] == "FAIL_MODE")
    if setting.get("value") != "off":
        raise RuntimeError("Known-good template must explicitly set FAIL_MODE=off")
    setting["value"] = "on"
    return template


def http(url):
    try:
        response = urllib.request.urlopen(url, timeout=5)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        return response.status, response.read(2_000_000)


def wait_health(expected, timeout=60):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            status, _ = http(SAMPLE_URL + "/healthz")
            if status == expected and http(SAMPLE_URL + "/readyz")[0] == 200:
                return
        except OSError:
            pass
        time.sleep(1)
    raise RuntimeError(f"Sample did not reach expected functional HTTP {expected}")


def up():
    for tool in ["docker", "kind"]:
        if not shutil.which(tool):
            raise RuntimeError(f"Missing required tool: {tool}")
    run(["docker", "info"], capture=True)
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    ensure_kubectl()
    clusters = run(["kind", "get", "clusters"], capture=True).splitlines()
    if CLUSTER in clusters:
        require_owned_cluster()
    else:
        run(
            [
                "kind",
                "create",
                "cluster",
                "--name",
                CLUSTER,
                "--config",
                str(ROOT / "infra/kind/cluster.yaml"),
                "--kubeconfig",
                str(KUBECONFIG),
                "--wait",
                "120s",
            ],
            timeout=600,
        )
        KUBECONFIG.chmod(0o600)
        write_private(
            RECEIPT,
            {
                "cluster": CLUSTER,
                "node_id": run(["docker", "inspect", "--format", "{{.Id}}", NODE], capture=True),
                "created_at": now(),
            },
        )
        # A new cluster cannot use a baseline from a previously deleted cluster.
        BASELINE.unlink(missing_ok=True)
    if BASELINE.exists():
        current = deployment()
        baseline = load_baseline(current)
        if baseline["image"] != image_tag():
            raise RuntimeError(
                "Sample source changed; tear down this disposable fixture before rebuilding"
            )
        print("Existing owned fixture preserved. Use status, fault, reset or verify.", flush=True)
        return
    image = image_tag()
    run(["docker", "build", "--tag", image, str(ROOT / "apps/sample")], timeout=600)
    run(["kind", "load", "docker-image", image, "--name", CLUSTER], timeout=300)
    kubectl("apply", "-f", str(ROOT / "infra/kind/namespace.yaml"))
    manifest = json.loads((ROOT / "infra/kind/workloads.json").read_text())
    for item in manifest["items"]:
        if item["kind"] == "Deployment":
            for container in item["spec"]["template"]["spec"]["containers"]:
                container["image"] = image
    kubectl("apply", "-f", "-", stdin=json.dumps(manifest))
    for name in [DEPLOYMENT, "sample-traffic"]:
        kubectl("rollout", "status", "deployment/" + name, "--timeout=120s")
    wait_health(200)
    current = deployment()
    good = current["spec"]["template"]
    faulty_template(good)  # Refuse to capture an already-faulty template.
    write_private(
        BASELINE,
        {
            "cluster": CLUSTER,
            "namespace": NAMESPACE,
            "name": DEPLOYMENT,
            "uid": current["metadata"]["uid"],
            "captured_at": now(),
            "resource_version": current["metadata"]["resourceVersion"],
            "image": image,
            "template": good,
            "template_hash": template_hash(good),
        },
    )
    print("Captured healthy template " + template_hash(good), flush=True)


def change(fault):
    current = deployment()
    baseline = load_baseline(current)
    good = baseline["template"]
    bad = faulty_template(good)
    current_hash = template_hash(current["spec"]["template"])
    if current_hash not in {template_hash(good), template_hash(bad)}:
        raise RuntimeError("Unexpected template drift; refusing to overwrite manual changes")
    desired = bad if fault else good
    if current_hash != template_hash(desired):
        patch = [
            {"op": "test", "path": "/metadata/uid", "value": baseline["uid"]},
            {
                "op": "test",
                "path": "/metadata/resourceVersion",
                "value": current["metadata"]["resourceVersion"],
            },
            {"op": "replace", "path": "/spec/template", "value": desired},
        ]
        kubectl("patch", "deployment", DEPLOYMENT, "--type=json", "-p", json.dumps(patch))
    kubectl("rollout", "status", "deployment/" + DEPLOYMENT, "--timeout=120s")
    wait_health(500 if fault else 200)
    print(
        "Fixture is faulty" if fault else "Fixture restored to captured healthy template",
        flush=True,
    )


def status():
    current = deployment()
    baseline = load_baseline(current)
    print(
        json.dumps(
            {
                "cluster": CLUSTER,
                "deployment_uid": current["metadata"]["uid"],
                "revision": current["metadata"]
                .get("annotations", {})
                .get("deployment.kubernetes.io/revision"),
                "ready_replicas": current.get("status", {}).get("readyReplicas", 0),
                "template_hash": template_hash(current["spec"]["template"]),
                "baseline_hash": baseline["template_hash"],
                "health_status": http(SAMPLE_URL + "/healthz")[0],
                "readiness_status": http(SAMPLE_URL + "/readyz")[0],
            },
            indent=2,
        )
    )


def prom_query(expression, evaluated_at):
    query = urllib.parse.urlencode({"query": expression, "time": evaluated_at.isoformat()})
    code, body = http(PROMETHEUS + "/api/v1/query?" + query)
    payload = json.loads(body)
    values = payload.get("data", {}).get("result", [])
    if code != 200 or payload.get("status") != "success" or len(values) != 1:
        raise RuntimeError("Prometheus has no unique sample for the fixture query")
    timestamp, raw = values[0]["value"]
    value = float(raw)
    if (
        not math.isfinite(value)
        or value < 0
        or abs(float(timestamp) - evaluated_at.timestamp()) > 5
    ):
        raise RuntimeError("Prometheus returned an invalid or stale evaluation")
    return value


def observe(fault, timeout):
    print("Collecting a fresh 60-second window (75-second scrape/rollout allowance)", flush=True)
    started = time.monotonic()
    while time.monotonic() - started < 75:
        time.sleep(1)
    deadline = time.monotonic() + timeout
    last_error = "No observation"
    while time.monotonic() < deadline:
        at = datetime.now(timezone.utc)
        try:
            selector = "job='fixproof-sample',route='/api/work'"
            total = prom_query(f"sum(increase(sample_http_requests_total{{{selector}}}[1m]))", at)
            errors = prom_query(
                f"sum(increase(sample_http_requests_total{{{selector},status_class='5xx'}}[1m]))",
                at,
            )
            scrape = prom_query(f"min(timestamp(sample_http_requests_total{{{selector}}}))", at)
            if not -5 <= at.timestamp() - scrape <= 30:
                raise RuntimeError("Sample scrape is stale")
            if errors > total or total < 20:
                raise RuntimeError("Insufficient or inconsistent work traffic")
            ratio = errors / total
            if not (ratio > 0.20 if fault else ratio < 0.01):
                raise RuntimeError(f"Unexpected 5xx ratio {ratio:.4f}")
            wait_health(500 if fault else 200, timeout=5)
            current = deployment()
            baseline = load_baseline(current)
            expected = faulty_template(baseline["template"]) if fault else baseline["template"]
            if template_hash(current["spec"]["template"]) != template_hash(expected):
                raise RuntimeError("Template drift during observation")
            reading = {
                "stage": "faulty" if fault else "healthy",
                "observed_at": at.isoformat(),
                "window_seconds": 60,
                "window_start": (at - timedelta(seconds=60)).isoformat(),
                "window_end": at.isoformat(),
                "last_scrape_at": datetime.fromtimestamp(scrape, timezone.utc).isoformat(),
                "total_requests": total,
                "error_requests_5xx": errors,
                "error_ratio": ratio,
                "deployment_uid": current["metadata"]["uid"],
                "revision": current["metadata"]["annotations"]["deployment.kubernetes.io/revision"],
                "template_hash": template_hash(expected),
                "health_status": 500 if fault else 200,
                "readiness_status": 200,
            }
            print(json.dumps(reading), flush=True)
            return reading
        except (OSError, RuntimeError, ValueError, KeyError) as error:
            last_error = str(error)
            time.sleep(3)
    raise RuntimeError("Observation failed: " + last_error)


def verify(cycles, timeout):
    require_owned_cluster()
    # Prove the read path from inside the actual Compose Prometheus container.
    raw = run(
        COMPOSE
        + [
            "exec",
            "-T",
            "prometheus",
            "wget",
            "-q",
            "-O",
            "-",
            "http://" + NODE + ":30080/metrics",
        ],
        capture=True,
    )
    if "sample_http_requests_total" not in raw:
        raise RuntimeError("Container-to-kind metrics connectivity failed")
    report = {
        "started_at": now(),
        "cycles": cycles,
        "container_connectivity": "passed",
        "observations": [],
    }
    try:
        change(False)
        report["observations"].append(observe(False, timeout))
        for cycle in range(cycles):
            print(f"Cycle {cycle + 1}/{cycles}: inject configuration fault", flush=True)
            change(True)
            report["observations"].append(observe(True, timeout))
            change(False)
            report["observations"].append(observe(False, timeout))
        report["completed_at"] = now()
        output = STATE / (
            "acceptance-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + ".json"
        )
        write_private(output, report)
        print(f"{cycles}-cycle fixture acceptance passed. Record: " + str(output), flush=True)
    finally:
        change(False)


def down():
    require_owned_cluster()
    run(["kind", "delete", "cluster", "--name", CLUSTER, "--kubeconfig", str(KUBECONFIG)])
    for path in [BASELINE, RECEIPT, KUBECONFIG]:
        path.unlink(missing_ok=True)
    print("Deleted only the owned demo cluster. Compose database and acceptance records preserved.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["up", "fault", "reset", "status", "verify", "down"])
    parser.add_argument("--cycles", type=int, default=2, choices=[1, 2])
    parser.add_argument("--timeout", type=int, default=90, choices=range(15, 301))
    args = parser.parse_args()
    actions = {
        "up": up,
        "fault": lambda: change(True),
        "reset": lambda: change(False),
        "status": status,
        "verify": lambda: verify(args.cycles, args.timeout),
        "down": down,
    }
    try:
        actions[args.action]()
    except (RuntimeError, OSError, subprocess.SubprocessError) as error:
        parser.exit(1, str(error) + "\n")


if __name__ == "__main__":
    main()
