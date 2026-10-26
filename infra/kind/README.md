# Observable kind fixture

This fixture is a developer-operated test scenario, not an agent remediation adapter. It creates only cluster `fixproof-demo`, namespace `fixproof-demo`, Deployments `sample-api` and `sample-traffic`, and one sample Service. The API/MCP restore tool remains disabled.

## Requirements and bootstrap

Use Docker/Compose, Python 3.12+ and kind. Bootstrap downloads a checksum-verified project-local kubectl v1.34.0 so host kubectl version skew cannot affect the fixture. It does not replace your global kubectl. The node image is pinned to Kubernetes 1.34.0 with the multi-architecture digest published in the [kind v0.30.0 release](https://github.com/kubernetes-sigs/kind/releases/tag/v0.30.0). Host tools may be newer; local acceptance records the versions tested. macOS Docker Desktop and native Linux Docker use the same private Docker-network path.

Run from the repository root:

```sh
python3 scripts/kind_fixture.py up
docker compose -f compose.yaml -f compose.kind.yaml up --build --wait --wait-timeout 180
python3 scripts/kind_fixture.py status
python3 scripts/kind_fixture.py verify --cycles 2
```

Use `python3.12` or an activated environment if `python3` is older than 3.12. Initial pulls/builds need internet access. Verification takes roughly 7–10 minutes: it waits for complete fresh windows rather than inferring healthy traffic from a patch.

The fixture stores its dedicated kubeconfig, cluster ownership receipt, healthy template and acceptance records in ignored `.local/kind/`. It never changes your default kubectl context. Do not share or commit kubeconfig. Cluster creation includes local cluster-admin setup authority for the developer; no such credential is mounted into API, AI or MCP.

An existing cluster with that name but no matching ownership receipt is refused. Re-running `up` preserves an existing owned baseline and fault state. If sample source changes, explicitly tear down and recreate the disposable fixture; `up` refuses to replace a captured baseline silently.

## Traffic and network contract

The sample has one replica. `/readyz` checks the process and stays HTTP 200 during the fault. `/healthz` and `/api/work` return HTTP 500 when `FAIL_MODE=on`. `/metrics` exports initialized success and 5xx counters with `route='/api/work'`. Probes/metrics/unknown paths do not increment work traffic. The traffic Deployment sends two work requests per second and continues across HTTP failures. Both workloads run without a ServiceAccount token, as non-root, with a read-only root filesystem and bounded resources.

kind maps NodePort 30080 to **127.0.0.1:18080** for local probes. The opt-in Compose overlay connects Prometheus and MCP to Docker's external `kind` network. They reach `fixproof-demo-control-plane:30080` directly; no container assumes the host's loopback is reachable. The base Compose configuration remains usable without a cluster. Prometheus's overlay config scrapes the sample every 15 seconds and retains the existing API scrape.

The verifier first fetches sample metrics from inside the actual Prometheus container. It then checks fresh Prometheus query values and scrape timestamps, the Deployment identity/template/revision, readiness and functional health for healthy → fault → reset twice. Every stage waits 75 seconds after rollout to cover the complete 60-second metric window. Fault requires at least 20 requests and over 20% 5xx; reset requires at least 20 and less than 1% 5xx. It saves a redacted JSON record locally and restores healthy state even after a failed verification where safe.

This proves the local fixture, not product approval/execution or verified incident closure. It does not provide API-persisted evidence, restricted MCP Kubernetes credentials, live Nemotron analysis, or automatic incident intake.

## Manual fault and reset

```sh
python3 scripts/kind_fixture.py fault
python3 scripts/kind_fixture.py status
python3 scripts/kind_fixture.py reset
```

Bootstrap captures the healthy pod template before fault injection and binds it to Deployment UID. Fault/reset only accept the captured good template or its exact `FAIL_MODE=on` variant. They reject unrelated template drift and use atomic Kubernetes JSON Patch tests for UID/resourceVersion before replacing the template. Repeating reset/fault in the desired state does not patch again. The local capture is a fixture artifact, not the production trusted-baseline registry required before agent execution.

## Teardown

Reset first when preserving the cluster. To delete the owned **disposable sample cluster**:

```sh
python3 scripts/kind_fixture.py down
```

This deletes the owned disposable cluster and anything placed in it, while preserving the Compose database and acceptance records. Prometheus can temporarily show the removed sample target as down. To return to the base stack, run `docker compose up -d prometheus mcp`; the base config has no sample scrape. Never use `docker system prune` or delete database volumes to reset this fixture.

## Fast checks

```sh
python3 -m unittest discover -s apps/sample/tests -v
python3 -m unittest discover -s tests -v
ruff check apps/sample scripts/kind_fixture.py tests
ruff format --check apps/sample scripts/kind_fixture.py tests
```

These tests exercise the HTTP failure contract and fixture safety policy without a cluster. CI runs them and builds the sample image; live two-cycle acceptance is a separate local gate.
