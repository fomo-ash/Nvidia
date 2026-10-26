# Docker

compose.yaml runs the application on a fixproof bridge network: web, API, PostgreSQL, Prometheus, Grafana, AI, and MCP. Compose published ports are loopback-only: web 5173 to 8080, API 8000, Prometheus 9090, and Grafana `${GRAFANA_PORT:-3000}` to 3000. PostgreSQL, AI, and MCP are internal. The separate kind fixture maps host port 18080 on all interfaces for the sample NodePort; see [its runbook](KIND_FIXTURE.md).

The API image installs the actual application package after copying its sources, runs as an unprivileged user, migrates before startup, and execs Uvicorn so shutdown signals reach the server. Its health check uses migrated-database readiness. Production deployments should run migrations as a separate job.

The web image installs from the root pnpm workspace lockfile, builds with the configured VITE_API_BASE_URL, and serves static files from unprivileged nginx on port 8080. Its nginx configuration supports React Router deep links and a health endpoint. Changing the browser API URL requires rebuilding the web image.

Both Dockerfiles have development targets. compose.checks.yaml runs test tools and sources from those targets instead of trying to run pytest or pnpm inside minimal runtime images. Its optional api-postgres-checks service uses a distinct disposable test database and network.

Grafana provisions a Prometheus datasource and an API-process dashboard. Prometheus is configured to scrape the kind sample at `host.docker.internal:18080` when the [fixture](KIND_FIXTURE.md) is running. No workload alerts or Kubernetes evidence collection are claimed yet. API metrics currently expose prometheus-client's default process/runtime metrics.

Use `docker compose down` or `make clean` to stop the application while retaining postgres_data. `make reset-data` / `docker compose down -v` intentionally deletes application database volumes. The checks project is separate; clean its containers with `docker compose -f compose.checks.yaml --profile checks down`.

Both builds have appropriate ignore rules. The frontend build uses the repository root as context; do not use `docker build apps/web`. Use Compose, or `docker build -f apps/web/Dockerfile .`. The API build context remains apps/api.

During local verification on 2026-10-18, Docker recovered from its earlier startup issue, but the pinned Grafana image repeatedly failed a layer checksum check. The database, API, web, and Prometheus were independently built/started and checked with:

```powershell
docker compose --parallel 1 up --build --wait --wait-timeout 180 db api web prometheus
```

This command is useful for isolating monitoring-image download failures. It does not start or verify Grafana, and `scripts/smoke.py` still requires all five services. Do not treat a partial-stack check as a full smoke-test pass. Phase 0 of the [implementation plan](IMPLEMENTATION_PLAN.md) requires a new full-stack check.

## Kind and MCP topology

Compose now includes private AI and MCP services. kind runs the sample app in `fixproof-demo`, maps its Service to host port 18080, and Prometheus scrapes it through `host.docker.internal`. MCP still needs a restricted Kubernetes API credential whose server address is reachable **from inside its container**. On Docker Desktop this can use the published kind API endpoint through `host.docker.internal`; the Linux host-gateway equivalent is configured for Prometheus. The Kubernetes MCP path is a later gate.

Only MCP should receive the future namespace-scoped Kubernetes credential. The AI service receives the selected Groq or Nebius key from ignored `.env`. MCP and AI stay on the internal Compose network without public listeners; developer ports stay on loopback. Generated kubeconfigs, baseline state, and database data stay out of Git. Live inference requires outbound HTTPS, while local history and manual inspection should remain available when it is offline.
