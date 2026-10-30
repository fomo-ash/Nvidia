# Owned kind fixture

The fixture creates only cluster `fixproof-demo`, namespace `fixproof-demo`, Deployments `sample-api` and `sample-traffic`, and the sample Service. Developer fault/reset controls are distinct from the capability-gated product restore. Product writes are disabled by default.

## Requirements and bootstrap

Use Docker/Compose, Python 3.12+ and kind. The node image is digest-pinned in [cluster.yaml](cluster.yaml). `scripts/kind_fixture.py` downloads/checksums project-local kubectl v1.34.1 and checks its version; it does not replace your global kubectl or context. Initial downloads/builds need internet access.

From the repository root, prepare ignored `.env` as described in [setup](../../docs/DEVELOPMENT.md#environment-and-startup), then:

```sh
python3.12 scripts/kind_fixture.py up
python3.12 scripts/configure_investigation.py
docker compose -f compose.yaml -f compose.kind.yaml up --build --wait --wait-timeout 180
python3.12 scripts/kind_fixture.py status
```

The fixture keeps its dedicated kubeconfig, ownership receipt, healthy template and redacted acceptance records under ignored `.local/kind/`. An existing cluster without matching ownership is refused. Re-running `up` preserves the owned baseline and fault state. A changed sample image requires deliberate recreation of the disposable fixture; the script does not silently overwrite a captured baseline.

Reader setup provisions only the sample-namespace read Role, a 24-hour token and verified Kubernetes CA. It updates the registered UID and generates missing local operator/session/service secrets while preserving existing model credentials. Refresh on expiry or recreation and recreate the overlay services. Only MCP mounts reader files; the developer admin kubeconfig is never mounted into application services.

## Traffic and networking

`sample-api` has one replica. `/readyz` stays HTTP 200 during `FAIL_MODE=on`; `/healthz` and `/api/work` return 500. `/metrics` exports initialized work counters by route/status class. Probes, metrics and unknown paths do not increment work traffic. The traffic Deployment sends two work requests per second and continues across failures.

The sample workloads run non-root, without a ServiceAccount token, with a read-only root filesystem and bounded resources. kind maps NodePort 30080 to **127.0.0.1:18080**. The overlay connects Prometheus/MCP to the private external `kind` Docker network, reaching `fixproof-demo-control-plane:30080` instead of assuming host loopback is reachable. Prometheus scrapes the sample every 15 seconds and also retains the API scrape.

## Manual fault and reset

```sh
python3.12 scripts/kind_fixture.py fault
python3.12 scripts/kind_fixture.py status
python3.12 scripts/kind_fixture.py reset
```

Bootstrap captures the healthy template and binds it to UID. Fault/reset accept only that template or its exact `FAIL_MODE=on` variant, reject unrelated template drift and atomically test UID/resource version before replacement. Repeating the desired state does not patch again. The local capture becomes a product baseline only after API registration.

## Fixture verification

```sh
python3.12 scripts/kind_fixture.py verify --cycles 2
```

This deliberately faults/resets the owned sample twice. It checks metrics from inside Prometheus, complete fresh traffic windows, source freshness, Deployment identity/revision/template and endpoint behavior. Each stage allows 75 seconds for rollout/scrapes; two cycles take several minutes. Active fault needs at least 20 work requests and more than 20% 5xx; healthy reset needs at least 20 and less than 1% 5xx.

This verifies the fixture, not product approval, exact execution or independent incident recovery. [Demo acceptance](../../docs/DEMO_RUNBOOK.md) distinguishes those scripts and observations. [MCP controls](../../docs/MCP_KUBERNETES.md) describe the separate reader/writer roles and signed product action.

## Teardown

Reset when preserving the cluster. If removing it, stop the live collector first so it does not collect against a removed target:

```sh
docker compose -f compose.yaml -f compose.kind.yaml stop worker
python3.12 scripts/kind_fixture.py down
docker compose up -d --force-recreate prometheus mcp
```

`down` deletes only the owned disposable cluster and its contents, preserving Compose database history and acceptance records. Returning to the base configuration removes the sample scrape and MCP overlay settings. Do not use global Docker pruning or delete application volumes to reset this fixture.

## Fast checks

```sh
python3.12 -m unittest discover -s apps/sample/tests -v
python3.12 -m unittest discover -s tests -v
ruff check apps/sample scripts/kind_fixture.py tests
ruff format --check apps/sample scripts/kind_fixture.py tests
```

These tests do not start a cluster. For actual evidence/model/action scripts, use the tracked [demo runbook](../../docs/DEMO_RUNBOOK.md); private historical notes are not required in a fresh clone.
