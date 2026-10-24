# Docker and local topology

`compose.yaml` currently defines PostgreSQL, FastAPI, a built React UI served by Nginx, Prometheus, and Grafana on the `fixproof` bridge. PostgreSQL uses a named `postgres_data` volume and has no published port. The API waits for the database health check and migrates on startup. Prometheus scrapes only the API's `/metrics`; Grafana provisions that Prometheus as a data source. Neither kind nor the sample workload nor an MCP server is in Compose yet.

| Service | Current Compose mapping | Note |
|---|---|---|
| API | `8000:8000` | Browser fetch points here directly; cross-origin handling is absent. |
| Web | `5173:80` | Likely mismatch: web Dockerfile's unprivileged Nginx image exposes 8080. Verify and fix in Phase 0. |
| Prometheus | `9090:9090` | Only FixProof API metrics. |
| Grafana | `3000:3000` | Local demo credentials in `.env`; no provisioned incident dashboard. |

`make clean` aliases `docker compose down` and preserves PostgreSQL data. `make reset-data` runs `docker compose down -v` and deletes the local database volume; use it only when intentionally resetting the demo. The production API image installs no pytest/ruff and the web runtime image installs no pnpm, so current `make test`/`make lint` need a dev/test service or separate source environment.

## Target additions

Keep Compose as the packaging entry point for web, API, PostgreSQL, Prometheus, and one MCP server. Run a local kind cluster beside it. Expose only a sample-app port needed for health checks and Prometheus scraping. Generate a **restricted** Kubernetes client configuration for MCP whose server URL is reachable from within the container; never mount the host's admin kubeconfig. On Docker Desktop this can use the published kind API endpoint through `host.docker.internal`; document the equivalent Linux host-gateway mapping. Verify container-to-kind API access and container-to-sample metrics access during bootstrap. Keep MCP on an internal Compose network and use the API as its only client.

The API needs outbound HTTPS to Nebius Token Factory for the live Nemotron flow. A deterministic local provider is for tests and offline UI development, not the final MVP demonstration. Bind developer ports to loopback and keep generated credentials and database data out of Git. See [security](SECURITY.md) for access rules.
