# Architecture and evidence correction handoff

No infrastructure mutation or new live proposal path is enabled.

## Delivered

- Aligned API/AI/MCP authority, optional Jev advice, API-owned approval, future job/checkpoint reconciliation, and implementation versus target status.
- New advisory run UUIDs prevent incident-level checkpoint reuse. Chat selects an explicit run, checks its incident, and separates session history by run.
- Timestamp-preserving evidence envelopes bind ID, observation time, mode and trust marker into the content hash. The client rejects missing/naive/stale/future timestamps and tampering; reasoning checks age again after collection.
- Fixed `/api/work` Prometheus scope, common evaluation time, real scrape freshness, source/window provenance, unrounded fractional counts/ratios, and impossible/missing sample rejection.
- Frozen per-service dependency locks, matching Docker/CI installs, pinned Ruff, formatted scaffold, and separate AI/MCP CI jobs.

## Acceptance

- AI: **20 passed** in its isolated Python 3.12 environment, using uv **0.9.17** and the frozen lockfile. One upstream deprecation warning remains for the existing LangGraph prebuilt chat agent; migration to LangChain `create_agent` is documented follow-up work.
- MCP: **21 passed** with the same Python/uv/frozen-install setup.
- Actual MCP `EvidenceItem` producer serialized to JSON and consumed by the actual AI client through an in-memory HTTP mock: passed, preserving timestamp/hash. No network/model call occurred.
- Ruff lint and format checks across API/AI/MCP/root scripts: passed, **81 Python files** checked for formatting. Public OpenAPI export check passed; no public API schema changed.
- CI/Compose YAML parsed successfully. Final whitespace validation passed.
- Existing API source and frontend are unchanged. During the preceding review of this same merged foundation, SQLite tests passed **70**, with **6** PostgreSQL-only cases skipped; frontend tests passed **7**, with lint/type/contracts/build passing.
- Docker was not running. Docker image builds, full-stack smoke, live kind/Nebius, PostgreSQL tests and GitHub CI were not executed for this change. No application database was modified.

## Compatibility and limits

Deploy AI and MCP together: old timestamp-unbound envelopes fail validation. Internal chat clients must supply the new `investigation_id`, which is returned by investigation/chat responses. Unknown runs, including those lost on restart, return 404. These internal contracts are not part of the public API's generated frontend types.

Prometheus must scrape the registered sample job at most every 15 seconds; its future sample counters must label `/api/work` and initialize success/5xx series, including zeros. A missing series stays a collection gap. These measurements do not yet establish full-window coverage or recovery.

Structured provider parsing, dynamic ChatOps evidence persistence/grounding, API evidence mapping, authentication, durable jobs/checkpoints, guarded restore and independent recovery remain the explicit gates in [current status](CURRENT_IMPLEMENTATION_STATUS.md). No delivery phase is marked complete by these unit tests. Continue with foundation smoke and the observable kind fixture before live evidence integration.
