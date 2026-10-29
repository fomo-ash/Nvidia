# Docker

compose.yaml runs web, API, PostgreSQL, Prometheus, Grafana, AI and MCP on the fixproof bridge network. Published Compose ports bind to loopback: web 5173, API 8000, Prometheus 9090, and Grafana `${GRAFANA_PORT:-3000}`. PostgreSQL, AI and MCP are internal. The separate kind fixture maps host port 18080 to loopback; see [its runbook](../infra/kind/README.md).

The API image installs the actual application package after copying its sources, runs as an unprivileged user, migrates before startup, and execs Uvicorn so shutdown signals reach the server. Its health check uses migrated-database readiness. Production deployments should run migrations as a separate job.

The web image installs from the root pnpm workspace lockfile, builds with the configured VITE_API_BASE_URL, and serves static files from unprivileged nginx on port 8080. Its nginx configuration supports React Router deep links and a health endpoint. Changing the browser API URL requires rebuilding the web image.

Both Dockerfiles have development targets. compose.checks.yaml runs test tools and sources from those targets instead of trying to run pytest or pnpm inside minimal runtime images. Its optional api-postgres-checks service uses a distinct disposable test database and network.

Grafana provisions a Prometheus datasource and an API-process dashboard. No workload alerts or Kubernetes metrics are claimed yet. API metrics currently expose prometheus-client's default process/runtime metrics.

Use `docker compose down` or `make clean` to stop the application while retaining postgres_data. `make reset-data` / `docker compose down -v` intentionally deletes application database volumes. The checks project is separate; clean its containers with `docker compose -f compose.checks.yaml --profile checks down`.

Both builds have appropriate ignore rules. The frontend build uses the repository root as context; do not use `docker build apps/web`. Use Compose, or `docker build -f apps/web/Dockerfile .`. The API build context remains apps/api.

During initial local verification, Docker recovered from its earlier startup issue, but the pinned Grafana image repeatedly failed a layer checksum check. The database, API, web, and Prometheus were independently built/started and checked with:

```powershell
docker compose --parallel 1 up --build --wait --wait-timeout 180 db api web prometheus
```

This command is useful for isolating monitoring-image download failures. It does not start or verify Grafana, and `scripts/smoke.py` still requires all five services. Do not treat a partial-stack check as a full smoke-test pass. Phase 0 of the [implementation plan](IMPLEMENTATION_PLAN.md) requires a new full-stack check.

## Kind fixture and MCP topology

`compose.yaml` now includes the AI/MCP scaffolds alongside the original five core services. The optional `compose.kind.yaml` connects Prometheus and MCP to Docker's private `kind` network. The sample runs in cluster/namespace `fixproof-demo`; containers reach its NodePort at `fixproof-demo-control-plane:30080`, while the host uses loopback port 18080. Base Compose remains usable without kind. See the [fixture runbook](../infra/kind/README.md).

The fixture manager uses an ignored dedicated kubeconfig and a checksum-verified kubectl matching the pinned node version. It never changes the global context. Developer fixture bootstrap/fault/reset uses local cluster setup authority; that kubeconfig is never mounted into API, AI or MCP. Restricted MCP Kubernetes credentials and a reachable TLS API endpoint remain Phase 3 work. Do not substitute the developer kubeconfig.

The old Grafana checksum failure above is historical. The fixture branch successfully pulled the same pinned Grafana image, built the API/web/AI/MCP runtime images, started all seven services and passed the full-stack HTTP smoke test on its recorded host. Container regression results and the separate live kind acceptance are recorded in the [fixture handoff](KIND_FIXTURE_HANDOFF.md). Smoke adds explicitly synthetic incident/billing history; no existing database records or volume were deleted.

Keep inference keys and infrastructure credentials scoped to their owning service before live integration; the current shared local environment-file pattern is not a production secret-distribution system. The AI service uses Groq temporarily through `GROQ_API_KEY` and later Nebius through `NEBIUS_API_KEY`; Kubernetes credentials belong to MCP, and execution capability issuance belongs to API. No service currently enables the restore tool.
