# MCP and AI implementation status

The repository contains separate `apps/mcp` and `apps/ai` services. They are scaffolds for the planned local kind investigation, not a completed remediation workflow.

For the exact failure path, tool bounds, graph routing, Jev role, and verification commands, see [Fail-closed MCP and agent implementation](FAIL_CLOSED_IMPLEMENTATION.md).

## What works

- MCP advertises five read tools over SSE and exposes equivalent private REST endpoints. Queries are limited to the registered demo namespace, Deployment, metrics windows, and health URL. Kubernetes and Prometheus failures surface as errors instead of synthetic observations.
- AI collects the available MCP evidence, records collection gaps, and routes insufficient investigations to `needs_review`. A live investigation requires a configured Nebius key; model failure or uncited output cannot generate a proposal. Explicit synthetic mode is for local tests only.
- The restore function is disabled and is absent from the MCP tool list and HTTP routes. The API's existing operations adapter also remains unavailable.
- Development Docker images include the test sources. Run `docker compose -f compose.checks.yaml run --build --rm mcp-checks` and the corresponding `ai-checks` command.

## Verification recorded on this branch

- `docker compose -f compose.checks.yaml run --build --rm mcp-checks`: 8 passed.
- `docker compose -f compose.checks.yaml run --build --rm ai-checks`: 8 passed.
- `docker compose config --quiet` and Python compilation of both service packages passed.
- A full Ruff run still reports style findings in the imported service scaffolds. It is not a passing release gate yet.

These checks use mocks and local test data. They do not establish live kind connectivity, model quality, or recovery.

## Required before real remediation

1. Add the kind sample workload, namespace-scoped Kubernetes credentials and a reachable sample health URL. Verify access from inside the MCP container.
2. Connect the API's incident/evidence records to the new services. The AI service currently uses an in-memory LangGraph checkpointer and does not persist evidence or proposals into the API database.
3. Register and verify a trusted known-good template. Bind a proposal to the exact Deployment UID, resource version, bad and good template hashes, evidence, expiry, and authenticated operator approval.
4. Implement a one-use execution capability, independent MCP preflight, replay protection, and measured recovery verification before enabling any Kubernetes write permission or restore tool.
5. Exercise live Nebius output with a credential-gated test and confirm the model and response contract. The current analysis parser only extracts evidence IDs from free text; it is not the final structured investigation schema.

The detailed architecture documents describe the intended design. This status file describes current behavior and is the source of truth when those plans differ from the code.
