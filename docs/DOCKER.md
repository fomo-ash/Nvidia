# Docker

`compose.yaml` creates an isolated `fixproof` bridge network. `api` reaches PostgreSQL as `db`, never `localhost`; browser code uses the build-time `VITE_API_BASE_URL` (default `http://localhost:8000`). Services: web 5173, API 8000, PostgreSQL internal-only, Prometheus 9090, Grafana 3000. PostgreSQL is retained in `postgres_data` across `make clean`; only `make reset-data` removes it.

The API waits on the DB health check and then runs Alembic. Production deployments should run migrations as a separate job; the development entrypoint is intentionally convenient. Images pin versions and app containers run as non-root where supported.
