# Observable kind fixture handoff

This records acceptance from the `feat/kind-observable-fault` branch, now merged into `main` through PR #7. The observations below were made on the recorded macOS host; they have not been repeated on this Windows workspace.

## Scope

- Added the dependency-free sample HTTP application, initialized route/status counters, steady traffic generator and pinned non-root Docker image.
- Added a digest-pinned kind node, restricted namespace/workloads, NodePort with loopback-only host access, and opt-in Compose-to-kind private networking.
- Added a developer-only fixture manager with a dedicated kubeconfig, checksum-verified matching kubectl, cluster ownership receipt, healthy template capture, drift/UID/resourceVersion guards, repeatable fault/reset, teardown and real metric-window verification.
- Added sample HTTP and fixture safety unit tests, a sample CI job, runbooks and local artifact exclusions. No AI/MCP mutation is enabled.

## Foundation acceptance

- All seven runtime services built/started: API, web, database, Prometheus, Grafana, AI and MCP. Grafana's previously failing pinned image pulled successfully on this laptop.
- The unmodified `python3.12 scripts/smoke.py` passed against the live stack. This creates explicitly synthetic incident/billing records; no existing history or database volume was removed.
- Development containers: SQLite **70 passed, 6 PostgreSQL-only skipped**; PostgreSQL **76 passed**; AI **20 passed**; MCP **21 passed**; frontend **7 passed**.
- Container API/AI/MCP lint/format checks and OpenAPI export passed. Frontend container lint, strict types and generated-contract checks passed; runtime frontend production build passed.
- New fixture checks: sample HTTP **3 passed**, script safety **7 passed**. Root lint/format passed across **86 Python files**. Base + kind Compose configuration validated.
- Live MCP metric and functional-health tool calls also passed through the private container network after reset: live mode, at least 20 requests, less than 1% 5xx, and HTTP 200. No model call or Kubernetes mutation was made by MCP.
- Checks-project containers/network were removed; application services/database were preserved.

## Live fixture acceptance

Two-cycle live acceptance passed. The verifier fetched sample metrics from inside the actual Prometheus container, checked fresh scrape timestamps and complete post-rollout windows, and recorded these real observations:

| Stage | Revision | Work requests / 60s | 5xx ratio | Functional health | Readiness |
|---|---|---|---|---|---|
| healthy | 1 | 119.99 | 0% | 200 | 200 |
| faulty | 2 | 119.99 | 100% | 500 | 200 |
| healthy | 3 | 118.67 | 0% | 200 | 200 |
| faulty | 4 | 119.99 | 100% | 500 | 200 |
| healthy | 5 | 120.00 | 0% | 200 | 200 |

The Deployment UID remained `c04934a2-73f9-4191-ac9d-8437781d78c2`. All healthy stages restored captured template hash `68995b21e23b491bca95770ec4b4c0436d924ff021b7874c42442d0980da97cd`. The redacted local record is `.local/kind/acceptance-20261025T194450Z.json` (UTC observation times are retained inside it). The sample was reset once more after acceptance and left healthy. No product remediation capability was enabled.

Toolchain: Docker 29.9.1, kind 0.33.0, project-local kubectl 1.34.0, Kubernetes node 1.34.0, macOS arm64. Host-global kubectl is newer and is intentionally unused by the final fixture manager. The host default Kubernetes context remains unset.

## Remaining gates

The fixture is not authenticated incident intake, API-persisted live evidence, a trusted production baseline registry, live Nemotron diagnosis, an approved product action, or independent product recovery verification. Those remain later phases. Generated kubeconfig and local acceptance records stay in ignored `.local/kind/`; only redacted acceptance evidence belongs in versioned docs.

Use [the fixture runbook](../infra/kind/README.md) for normal fault/reset/status/teardown commands. Leave the sample healthy after development. The developer can intentionally delete the owned demo cluster; this never deletes the Compose database.
