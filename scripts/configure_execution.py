"""Provision a separate scoped writer only for the owned sample Deployment."""

import re
import secrets

import kind_fixture as fixture
from configure_investigation import update_environment


def main():
    fixture.require_owned_cluster()
    current = fixture.deployment()
    baseline = fixture.load_baseline(current)
    if fixture.template_hash(baseline["template"]) != baseline["template_hash"]:
        raise RuntimeError("Trusted fixture baseline changed")
    fixture.kubectl("apply", "-f", str(fixture.ROOT / "infra/kind/mcp-writer.yaml"))
    token = fixture.kubectl("create", "token", "fixproof-writer", "--duration=24h", capture=True)
    directory = fixture.STATE / "writer"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    directory.chmod(0o700)
    path = directory / "token"
    path.write_text(token)
    path.chmod(0o644)
    env = fixture.ROOT / ".env"
    existing = dict(re.findall(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", env.read_text(), re.M))
    values = {"LIVE_EXECUTION_ENABLED": "false"}
    if not existing.get("EXECUTION_SIGNING_KEY") or existing["EXECUTION_SIGNING_KEY"].startswith(
        "change-me"
    ):
        values["EXECUTION_SIGNING_KEY"] = secrets.token_urlsafe(48)
    update_environment(env, values)
    print(
        "Scoped writer token and execution signing key configured; live execution remains disabled."
    )


if __name__ == "__main__":
    main()
