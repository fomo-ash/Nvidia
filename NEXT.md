# FixProof: remaining work

Investigation quality checks passed: bounded single-attempt Nebius analysis, strict citation/source checks, model-gap review handling and historical-record compatibility. See [investigation quality handoff](docs/INVESTIGATION_QUALITY_HANDOFF.md). Grounded ChatOps is explicitly deferred. The next integrated trial still needs fresh evidence, exact human approval and the separately guarded execution/verification steps.

Backend approval and guarded execution acceptance now pass locally; see [the approval/execution handoff](docs/APPROVAL_EXECUTION_HANDOFF.md). Rejection, expired approval, pre/post-approval drift, invalid capabilities and replay were denied without mutation, and one exact approved restore succeeded. Execution is disabled again. Independent recovery verdicts, two complete verified cycles and final UI/release acceptance remain open.

This checklist tracks the remaining work in [the MVP implementation plan](docs/IMPLEMENTATION_PLAN.md). It records unfinished work; a passing unit test or UI message is not a live recovery result.

## Current handoff

Authenticated intake acceptance and the live read-only investigation path now pass locally on macOS. See [live investigation handoff](docs/LIVE_INVESTIGATION_HANDOFF.md): API 85 SQLite / 93 PostgreSQL tests, AI 33, MCP 25, web 9, and two real-browser cases. A real faulty fixture produced five retained source envelopes and validated Nebius/Nemotron analysis; evidence survived API/worker restart. A real Prometheus outage produced an explicit gap without invented data. The fixture and monitoring were restored afterward. CI/review remain pending.

The pre-existing Jev/Laya implementation is preserved and advisory. Legacy standalone graph/ChatOps endpoints are not the integrated durable workflow. The operator/session/service secrets and registered UID are now configured locally; `.env` and scoped reader files remain ignored. No application mutation capability is enabled.

## Phase 2 acceptance (completed locally; CI/review pending)

- [x] In ignored `.env`, set two different locally generated `OPERATOR_SECRET` and `SESSION_SIGNING_KEY` values; set `SAMPLE_TARGET_UID` from `python scripts/kind_fixture.py status`; set `LOCAL_DEMO_ENABLED=false`. Keep secrets and the fixture kubeconfig out of Git.
- [x] Run `python scripts/kind_fixture.py up`, then `docker compose -f compose.yaml -f compose.kind.yaml up --build --wait --wait-timeout 180`. Confirm API readiness, browser access, Grafana, Prometheus sample scraping, and MCP health. Run `python scripts/smoke.py` where its synthetic-mode assumptions apply; record which mode was tested.
- [x] Fault the fixture, sign in through `/incidents`, report the displayed exact UID, restart the API, and confirm the incident, trigger, and queued request persist. Repeat the same idempotency key and a distinct key; check replay versus reuse, audit timeline, and `unassessed` wording. Reset the fixture afterward.
- [x] Run `docker compose -f compose.checks.yaml run --build --rm api-postgres-checks` once Docker Desktop can start `db-checks`. Verify migration up/down, concurrent same-target reports, trigger immutability, idempotency, and legacy row preservation on PostgreSQL. Update the intake handoff with actual results.
- [x] Phase 2 UI polish: the incident report now shows signed-in/session-expired guidance, refreshes a drifted target UID, and displays trigger history plus queued investigation status with loading, error, empty, and retry states. “Reported” and “unassessed” remain distinct from detected or confirmed. Component coverage is in the web suite.
- [x] Add a browser-level Phase 2 intake test once the Compose/kind acceptance environment is available; cover sign-in, target refresh, report submission, queued status, and expired-session recovery.
- [x] Give the incident-target, trigger-history, and investigation-request endpoints declared response models, regenerate the web schema, and replace the UI’s local response types with generated contract types.

## Phase 3: real MCP evidence (completed locally; CI/review pending)

- [x] Namespace-scoped read identity, verified TLS container connectivity, owner/UID checks, bounded source reads and denied writes.
- [x] Leased durable worker, per-incident serialization, bounded read retries, stale-worker rejection, canonical evidence UUIDs and retained redacted source/error metadata.
- [x] Incremental migration, typed API and generated frontend contracts, restart persistence, source-failure/redaction/concurrency tests and live missing-source acceptance.
- [x] Durable API run state replaces reliance on MemorySaver in the integrated product path. Legacy standalone graph endpoints remain advisory scaffolds; they cannot approve or execute actions.
- [ ] Merge only after CI and owner/contract review. Repeat host-specific networking on Windows/Linux before claiming those platforms accepted.

## Phase 4: evidence-cited Nemotron investigation

- [x] Verify the currently available NVIDIA Nemotron model, endpoint, and response shape with a credential-gated live Nebius call. Keep deterministic CI fixtures and bounded timeout/retry budgets. Groq remains a temporary development provider, not the release acceptance path.
- [x] Build a small redacted evidence bundle with stored IDs. Require structured hypotheses, supporting and contradicting IDs, gaps, uncertainty, and an allowlisted advisory action name. Reject malformed output, unknown citations, unsupported actions, target drift, and prompt instructions embedded in logs. Persist provider/model/request metadata and validated findings.
- [ ] Deferred: ground ChatOps in retained evidence, persist tool reads, validate dynamic citations against the complete set, and limit conversation/tool budgets before exposing it to operators. Integrated analysis has bounded inference and no fixed-confidence/root-cause fields; see the investigation quality handoff.
- [x] UI: show measurements, source gaps, and model interpretation in separate sections. On provider failure show `needs_review`; do not create an approvable proposal.

## Phase 5: exact proposal and human review (completed locally; CI/review pending)

- [x] Register the trusted known-good template independently of model output. Bind recommendation version/hash/expiry to exact cluster, namespace, Deployment UID, expected bad template and resource version, desired good template hash, and retained real evidence IDs.
- [x] Extend approval policy to the authenticated operator session. Any content or target change creates a new version and invalidates old approval. Keep Kubernetes access read-only in this phase.
- [x] UI: incident detail and review screen must show evidence, uncertainty, exact target/change, expected effect, verification plan, and separate approve/reject actions. Add denial tests for rejected, expired, changed, missing-citation, duplicate, and wrong-target proposals.

## Phase 6: one guarded restore action (locally accepted; CI/review pending)

- [x] Design pending-operation reconciliation before enabling writes; preserve the existing commit-before-adapter claim and avoid automatic repeat after interruption.
- [x] Add one-use, short-lived execution capability bound to the approved proposal and execution. API and MCP independently validate UID, resource version, bad/good template hashes, expiry, and scope. Grant Kubernetes patch only on the sample Deployment through a restricted Role (`infra/kind/mcp-writer.yaml`, verified by `scripts/check_writer_scope.py`).
- [x] Record preflight and Kubernetes result. A successful patch means `execution_succeeded`, not recovery. Test stale version, UID/template drift, replay, missing approval, and out-of-scope targets with zero mutation (`apps/mcp/tests/test_restore_guard.py` & `apps/api/tests/test_live_proposals.py` passing).
- [x] One authenticated, exact approved restore with live rejection, approval expiry, pre/post-approval drift, invalid capability and replay denials. See `scripts/smoke_execution.py` and the approval/execution handoff. Two full verified recovery cycles remain a release gate.

## Phase 7: independent recovery verdict and complete UI

- [x] Implement independent verification adapter and tool (`apps/mcp/app/adapters/prometheus.py`, `probe.py`, `apps/mcp/app/tools/verification.py` - 31/31 MCP unit tests passing).
- [ ] After the patch, use a fresh window: restored rollout availability, three functional `/healthz` probes, and 60 seconds of Prometheus `/api/work` traffic with at least 20 requests and less than 1% 5xx. Store counts, ratio, thresholds, revision, observation times, statuses, timeout, and reason.
- [ ] Return `passed`, `failed`, or `inconclusive` from measurements. Persistent errors or failed probes are failure; missing/stale metrics or insufficient traffic are inconclusive. Do not auto-close the incident.
- [x] Operator UI: show the auditable trigger → evidence → investigation → proposal → approval → execution → verification timeline, explicit pending/error/empty/retry states, and stored measurement readings. “Recovery verified” is displayed only for a persisted `passed` verdict; patch success alone is not recovery.
- [ ] Add browser E2E coverage for passed, failed, and inconclusive recovery verdicts, including a direct incident reload. Run the flow against fresh post-action measurements before claiming Phase 7 acceptance.

## Phase 8: release rehearsal

- [ ] Document clean bootstrap, fault, report, reset, and teardown commands without deleting the normal database volume. Run the entire scenario twice from a clean cluster and database, plus rejection and failed/inconclusive verification cases.
- [ ] Run API SQLite and PostgreSQL migrations/concurrency/audit tests, AI/MCP tests, sample tests, web lint/type/build/component tests, contract drift checks, full Compose smoke, and safe kind end-to-end tests in CI. Keep the live Nebius test separately credential-gated.
- [ ] Review redaction, secrets, network bindings, RBAC, replay protection, pending reconciliation, audit integrity, and Windows/Linux network instructions. Save a redacted acceptance record with times, evidence IDs, proposal hash, execution ID, and actual readings.

## After the first release

- [ ] Optional Prometheus detection through the same intake service, with traffic/freshness thresholds, deduplication, stale/low-traffic and reset/retrigger tests.
- [ ] Optional bounded GitHub deployment/commit context, kept advisory.
- [ ] Real billing ingestion and advanced Cloud Cost Autopsy as a separate track; keep synthetic reports labeled.
- [ ] Broader workloads, clusters, per-user identity, production deployment, and a new threat review.
