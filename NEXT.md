  # FixProof: remaining work

Updated 2026-10-28. This is the actionable continuation of [the MVP implementation plan](docs/IMPLEMENTATION_PLAN.md), based on the current feature branch. It records unfinished work; a passing unit test or UI message is not a live recovery result.

## Current handoff

- Phases 0 and 1 have acceptance records from the earlier host in [the kind fixture handoff](docs/KIND_FIXTURE_HANDOFF.md). Repeat the full stack and kind checks on this Windows host.
- Phase 2 manual intake is implemented locally: operator session, CSRF, registered sample target, immutable triggers, idempotent open-case reuse, durable queued investigation requests, and the report form. The [intake handoff](docs/PHASE_2_INTAKE_HANDOFF.md) has setup and test details. Its live Compose/kind and PostgreSQL gates remain open.
- The System-1 Jev/Laya decision path has been stabilized and checked locally. The bundled compatibility server is deterministic; see [its handoff](docs/agentic_architecture/SYSTEM1_STABILIZATION_HANDOFF.md). It is advisory and does not supply real incident evidence or action authority.
- The latest rerun passed API 72 tests (6 PostgreSQL-only skipped), AI 31, MCP 21, web 8, web build, generated contracts, and Compose config. Docker Desktop twice stalled at `db-checks Starting` before PostgreSQL tests began. The existing untracked `images/` directory is unrelated to this work.

## Do first: close Phase 2 acceptance

- [ ] In ignored `.env`, set two different locally generated `OPERATOR_SECRET` and `SESSION_SIGNING_KEY` values; set `SAMPLE_TARGET_UID` from `python scripts/kind_fixture.py status`; set `LOCAL_DEMO_ENABLED=false`. Keep secrets and the fixture kubeconfig out of Git.
- [ ] Run `python scripts/kind_fixture.py up`, then `docker compose -f compose.yaml -f compose.kind.yaml up --build --wait --wait-timeout 180`. Confirm API readiness, browser access, Grafana, Prometheus sample scraping, and MCP health. Run `python scripts/smoke.py` where its synthetic-mode assumptions apply; record which mode was tested.
- [ ] Fault the fixture, sign in through `/incidents`, report the displayed exact UID, restart the API, and confirm the incident, trigger, and queued request persist. Repeat the same idempotency key and a distinct key; check replay versus reuse, audit timeline, and `unassessed` wording. Reset the fixture afterward.
- [ ] Run `docker compose -f compose.checks.yaml run --build --rm api-postgres-checks` once Docker Desktop can start `db-checks`. Verify migration up/down, concurrent same-target reports, trigger immutability, idempotency, and legacy row preservation on PostgreSQL. Update the intake handoff with actual results.
- [ ] Finish Phase 2 UI polish: show a clear signed-in/session-expired state, target refresh when UID drifts, trigger history and queued job status on incident detail, and explicit loading/error/empty/retry states. Keep “reported” and “unassessed” distinct from detected or confirmed. Add component and browser tests for those states.

## Phase 3: real MCP evidence

- [ ] Give MCP a namespace-scoped read identity with a container-reachable TLS Kubernetes API address. Never mount the developer cluster-admin kubeconfig into API, AI, or MCP. Prove container-side reads and denied out-of-scope reads on Windows; document the Linux host-gateway path.
- [ ] Complete bounded Prometheus, Deployment/ReplicaSet, pod, event, capped-log, and direct-probe reads for the exact sample UID. Enforce time windows, size limits, source freshness, target allowlist, and explicit per-source errors.
- [ ] Add a durable worker/outbox that claims queued `investigation_requests`, serializes work per incident, survives restart, and ingests MCP envelopes idempotently. Map transport evidence IDs/hashes/timestamps into API `investigations` and `evidence_items` with target UID, observation window, redaction marker, bounded payload, trust label, and collection error. Preserve original source provenance.
- [ ] Replace in-memory AI checkpointing with durable run state. Test duplicate delivery, restart, timeout, missing source, hostile log text, and evidence persistence after restart. Refresh OpenAPI, generated web types, schema docs, and the runbook.
- [ ] Exit only when a faulty sample retains real metric, rollout, pod, event, log, and probe observations where available, and a disabled source appears as an error without invented evidence.

## Phase 4: evidence-cited Nemotron investigation

- [ ] Verify the currently available NVIDIA Nemotron model, endpoint, and response shape with a credential-gated live Nebius call. Keep deterministic CI fixtures and bounded timeout/retry budgets. Groq remains a temporary development provider, not the release acceptance path.
- [ ] Build a small redacted evidence bundle with stored IDs. Require structured hypotheses, supporting and contradicting IDs, gaps, uncertainty, and an allowlisted advisory action name. Reject malformed output, unknown citations, unsupported actions, target drift, and prompt instructions embedded in logs. Persist provider/model/request metadata and validated findings.
- [ ] Ground ChatOps in retained evidence, persist tool reads, validate dynamic citations against the complete set, and limit inference/tool/concurrency budgets. Remove fixed-confidence and fixed-root-cause claims.
- [ ] UI: show measurements, source gaps, and model interpretation in separate sections. On provider failure show `needs_review`; do not create an approvable proposal.

## Phase 5: exact proposal and human review

- [ ] Register the trusted known-good template independently of model output. Bind recommendation version/hash/expiry to exact cluster, namespace, Deployment UID, expected bad template and resource version, desired good template hash, and retained real evidence IDs.
- [ ] Extend approval policy to the authenticated operator session. Any content or target change creates a new version and invalidates old approval. Keep Kubernetes access read-only in this phase.
- [ ] UI: incident detail and review screen must show evidence, uncertainty, exact target/change, expected effect, verification plan, and separate approve/reject actions. Add denial tests for rejected, expired, changed, missing-citation, duplicate, and wrong-target proposals.

## Phase 6: one guarded restore action

- [ ] Design pending-operation reconciliation before enabling writes; preserve the existing commit-before-adapter claim and avoid automatic repeat after interruption.
- [ ] Add one-use, short-lived execution capability bound to the approved proposal and execution. API and MCP independently validate UID, resource version, bad/good template hashes, expiry, and scope. Grant Kubernetes patch only on the sample Deployment through a restricted Role.
- [ ] Record preflight and Kubernetes result. A successful patch means `execution_succeeded`, not recovery. Test stale version, UID/template drift, replay, missing approval, and out-of-scope targets with zero mutation.

## Phase 7: independent recovery verdict and complete UI

- [ ] After the patch, use a fresh window: restored rollout availability, three functional `/healthz` probes, and 60 seconds of Prometheus `/api/work` traffic with at least 20 requests and less than 1% 5xx. Store counts, ratio, thresholds, revision, observation times, statuses, timeout, and reason.
- [ ] Return `passed`, `failed`, or `inconclusive` from measurements. Persistent errors or failed probes are failure; missing/stale metrics or insufficient traffic are inconclusive. Do not auto-close the incident.
- [ ] UI: complete trigger → evidence → investigation → proposal → approval → execution → verification timeline, with pending/error/empty states and links to stored readings. Regenerate OpenAPI and frontend types; test that patch success never displays as verified recovery.

## Phase 8: release rehearsal

- [ ] Document clean bootstrap, fault, report, reset, and teardown commands without deleting the normal database volume. Run the entire scenario twice from a clean cluster and database, plus rejection and failed/inconclusive verification cases.
- [ ] Run API SQLite and PostgreSQL migrations/concurrency/audit tests, AI/MCP tests, sample tests, web lint/type/build/component tests, contract drift checks, full Compose smoke, and safe kind end-to-end tests in CI. Keep the live Nebius test separately credential-gated.
- [ ] Review redaction, secrets, network bindings, RBAC, replay protection, pending reconciliation, audit integrity, and Windows/Linux network instructions. Save a redacted acceptance record with times, evidence IDs, proposal hash, execution ID, and actual readings.

## After the first release

- [ ] Optional Prometheus detection through the same intake service, with traffic/freshness thresholds, deduplication, stale/low-traffic and reset/retrigger tests.
- [ ] Optional bounded GitHub deployment/commit context, kept advisory.
- [ ] Real billing ingestion and advanced Cloud Cost Autopsy as a separate track; keep synthetic reports labeled.
- [ ] Broader workloads, clusters, per-user identity, production deployment, and a new threat review.
