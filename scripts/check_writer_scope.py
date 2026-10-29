"""Fail if the owned fixture writer or reader has broader authority than intended."""

import subprocess
import json
import tempfile
from pathlib import Path

import kind_fixture as fixture


def allowed(token, verb, resource, namespace):
    admin = json.loads(fixture.run([
        str(fixture.KUBECTL), "--kubeconfig", str(fixture.KUBECONFIG),
        "config", "view", "--raw", "-o", "json",
    ], capture=True))
    cluster = next(item["cluster"] for item in admin["clusters"]
                   if item["name"] == fixture.CONTEXT)
    config = {
        "apiVersion": "v1", "kind": "Config",
        "clusters": [{"name": "owned", "cluster": cluster}],
        "users": [{"name": "scoped", "user": {"token": token}}],
        "contexts": [{"name": "scoped", "context": {
            "cluster": "owned", "user": "scoped", "namespace": namespace,
        }}],
        "current-context": "scoped",
    }
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", dir=fixture.STATE, delete=False,
    ) as stream:
        json.dump(config, stream)
        config_path = Path(stream.name)
    try:
        config_path.chmod(0o600)
        command = [
            str(fixture.KUBECTL), "--kubeconfig", str(config_path),
            "auth", "can-i", verb, resource, "--namespace", namespace,
        ]
        result = subprocess.run(command, text=True, capture_output=True, timeout=15)
        answer = result.stdout.strip()
        if answer not in {"yes", "no"}:
            raise RuntimeError("Kubernetes permission check did not return yes/no")
        return answer == "yes"
    finally:
        config_path.unlink(missing_ok=True)


def main():
    fixture.require_owned_cluster()
    writer = (fixture.STATE / "writer" / "token").read_text().strip()
    reader = (fixture.STATE / "reader" / "token").read_text().strip()
    checks = [
        ("writer can patch sample", allowed(writer, "patch", "deployment/sample-api", fixture.NAMESPACE)),
        ("writer cannot patch other deployment", not allowed(writer, "patch", "deployment/sample-traffic", fixture.NAMESPACE)),
        ("writer cannot patch other namespace", not allowed(writer, "patch", "deployment/sample-api", "kube-system")),
        ("writer cannot delete sample", not allowed(writer, "delete", "deployment/sample-api", fixture.NAMESPACE)),
        ("reader cannot patch sample", not allowed(reader, "patch", "deployment/sample-api", fixture.NAMESPACE)),
    ]
    for label, passed in checks:
        print(f"{label}: {'pass' if passed else 'FAIL'}")
    if not all(passed for _, passed in checks):
        raise RuntimeError("Kubernetes writer scope check failed")


if __name__ == "__main__":
    main()
