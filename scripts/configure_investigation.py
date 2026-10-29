"""Provision only namespace-scoped read credentials for the owned kind fixture."""

import json
import re
import secrets

import kind_fixture as fixture


def update_environment(path, values):
    text = path.read_text() if path.exists() else ""
    for key, value in values.items():
        line = key + "=" + value
        pattern = r"^" + re.escape(key) + r"=.*$"
        text = (
            re.sub(pattern, lambda _: line, text, flags=re.M)
            if re.search(pattern, text, re.M)
            else text.rstrip() + "\n" + line + "\n"
        )
    path.write_text(text)
    path.chmod(0o600)


def main():
    fixture.require_owned_cluster()
    current = fixture.deployment()
    fixture.kubectl("apply", "-f", str(fixture.ROOT / "infra/kind/mcp-reader.yaml"))
    token = fixture.kubectl("create", "token", "fixproof-reader", "--duration=24h", capture=True)
    ca = json.loads(
        fixture.kubectl("get", "configmap", "kube-root-ca.crt", "-o", "json", capture=True)
    )["data"]["ca.crt"]
    directory = fixture.STATE / "reader"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    directory.chmod(0o700)
    # Individually mounted read-only files are readable by the non-root container.
    # The private host directory prevents access by other local users.
    for name, value in [("token", token), ("ca.crt", ca)]:
        path = directory / name
        path.write_text(value)
        path.chmod(0o644)
    env = fixture.ROOT / ".env"
    existing = dict(re.findall(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", env.read_text(), re.M))
    values = {"SAMPLE_TARGET_UID": current["metadata"]["uid"], "LOCAL_DEMO_ENABLED": "false"}
    for key in ["OPERATOR_SECRET", "SESSION_SIGNING_KEY", "SERVICE_AUTH_TOKEN"]:
        if not existing.get(key) or existing[key].startswith("change-me"):
            values[key] = secrets.token_urlsafe(48)
    update_environment(env, values)
    print(
        "Read-only service account refreshed for 24 hours; local environment updated. No secrets printed."
    )


if __name__ == "__main__":
    main()
