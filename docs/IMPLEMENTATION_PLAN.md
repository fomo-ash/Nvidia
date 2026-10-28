# FixProof MVP implementation plan

Updated 2026-10-24 after merging current `main`. This is an **execution plan**, not a claim that the target workflow exists. The repository has a working local scaffold and Phase 2 lifecycle foundation: normalized synthetic investigations/evidence, exact-hash approval decisions, idempotent execution/verification records, append-only audit guards, generated frontend API types, and persisted synthetic cost reports. The default operations adapter fails unavailable without mutating infrastructure. See [repository assessment](INITIAL_ASSESSMENT.md) and [Phase 2 handoff](PHASE_2_HANDOFF.md). The release target is the single [unhealthy sample application incident](INITIAL_INCIDENT.md).

## Delivery rule

Build one vertical path through real components. Each phase ends with a command or UI action that produces an observable result, an automated test for its main failure mode, and updated OpenAPI/schema/runbook documentation. Do not start the next mutation-capable phase until its preceding safety gate passes. A green UI badge or model statement is never evidence of recovery.

**Critical path:** scaffold repair → kind fault → manual intake → MCP evidence → Nebius investigation → exact approval → guarded action → independent verification → clean-machine release. Manual intake satisfies “detect or accept an incident.” Prometheus-triggered automatic detection is an optional follow-on using the same intake service.

## Phase map

| Phase | Depends on | Deliverable demonstrated at exit | Status |
|---|---|---|---|
| 0. Confirm foundation | Current `main` | Full five-service Compose and Grafana smoke path verified; existing checks remain green | Ready for review: full-stack smoke and container checks passed; see KIND_FIXTURE_HANDOFF.md |
| 1. Observable kind fault | 0 | Healthy → deliberate config fault → healthy reset, with sample metrics in Prometheus | Ready for review: two live fault/reset cycles passed; see KIND_FIXTURE_HANDOFF.md |
| 2. Incident intake | 1 | Authenticated operator reports the exact workload; one durable incident/trigger queues investigation | Implemented locally; PostgreSQL and live kind acceptance remain; see PHASE_2_INTAKE_HANDOFF.md |
| 3. MCP evidence | 1–2 | One restricted MCP service returns and persists real metric/Kubernetes evidence | Not started |
| 4. Nemotron investigation | 3 | A live Nebius call returns a validated hypothesis and cited proposal | Not started |
| 5. Proposal and approval | 2, 4 | Operator approves an immutable exact proposal; no infrastructure action yet | Not started |
| 6. Guarded execution | 1, 3, 5 | One approved restore action patches only the sample Deployment | Not started |
| 7. Recovery verification and UI | 6 | Fresh rollout, health, and metrics decide verified/failed/inconclusive | Not started |
| 8. Release rehearsal | 0–7 | Clean setup and repeated positive/negative runs pass the runbook | Not started |

The phases are ordered for a solo developer. With several contributors, sample workload, API migration design, and UI shell can proceed in parallel after Phase 0, but they must meet at the contract gates below. [Team ownership](TEAM_OWNERSHIP.md) is a coordination map, not an assertion that anyone has completed a stream.

## Phase 0 — confirm the existing foundation

Local foundation acceptance now passes on `feat/kind-observable-fault`, including Grafana, all seven runtime services, the HTTP smoke and container regressions. CI/peer review remain merge gates. See [fixture handoff](KIND_FIXTURE_HANDOFF.md).

**Implement**

- Preserve the already implemented Nginx port/CORS fixes, development check images, migration tests, OpenAPI/type generation, proposal versioning, and mock labels. Do not redo those completed changes.
- Re-run the full five-service `docker compose up --build --wait --wait-timeout 180` path and `python scripts/smoke.py` on the merged source. Earlier core-stack checks passed, but a Grafana image checksum failure prevented a complete five-service smoke; see [Docker notes](DOCKER.md). Record whether that host-specific pull issue remains.
- Run the existing API SQLite/PostgreSQL, web, lint, formatting, and contract checks through `compose.checks.yaml`. Fix only concrete regressions found after the merge.

**Exit gate:** the current core-stack and check suites remain green and the full five-service smoke passes. If the Grafana image pull is still blocked by the host environment, document that blocker and continue isolated kind work without marking Phase 0 complete. No kind or Nebius key is needed for this gate. The foundation and Phase 2 handoff retain their prior acceptance record.

## Phase 1 — create one observable fault

Implemented and locally accepted on `feat/kind-observable-fault`: two healthy → fault → reset cycles passed with real Prometheus windows, revision changes and template restoration. [Acceptance record](KIND_FIXTURE_HANDOFF.md). CI and peer review remain pending; this does not complete authenticated incident intake or product remediation.

**Implement**

- Add `infra/kind/` with a pinned kind node image, cluster creation/teardown, `fixproof-demo` namespace, sample Deployment/Service, traffic generator, and reset scripts. Keep manifests in Git and generated credentials out of Git.
- Add the sample HTTP app under an isolated folder such as `apps/sample/`: `/readyz` is process readiness; `/healthz` is functional health; `/api/work` is the request path; `/metrics` counts requests by route/status class.
- Bootstrap records the known-good Deployment pod template and hash in local baseline state before fault injection. The fault command creates a new revision with `FAIL_MODE=on`. Pods remain process-ready so traffic reaches them; `/api/work` returns 5xx and `/healthz` fails. Reset restores the trusted captured template. The model must never supply or rewrite that baseline.
- Configure Compose Prometheus to scrape the sample app through a documented kind-to-container path. Add a container-side connectivity check and a metric query check; do not assume host-only access proves the integration works.

**Exit gate:** run healthy → fault → reset twice without editing manifests. During fault, a 60-second window has at least 20 sample requests and more than 20% 5xx; the Deployment revision and functional health reflect the fault. After reset, health and metrics return to baseline. Save observed revision IDs, sample counts, and timestamps. Missing scrape data fails this phase.

## Phase 2 — accept and track an incident

**Implement**

- Replace the existing server-owned `local-demo-user` role boundary with a locally generated operator secret and short-lived session for this mutation-capable MVP. The current boundary prevents body-level actor spoofing but is not a login. Protect state-changing browser requests from cross-site submission.
- Extend the existing `incidents` table and idempotency service; add immutable `incident_triggers` through a new Alembic migration. Persist target cluster/namespace/name/UID, symptom fingerprint, lifecycle, symptom assessment, source, reporter, source/server times, and audit event. Preserve seeded rows as labeled legacy demo incidents.
- Extend the existing `POST /api/v1/incidents` route and incident UI to accept the registered sample target. Add transactional reuse of an open case with the same target/symptom and explicit `unassessed` state. Queue an investigation request; the real collector is connected in Phase 3. Follow [incident intake](INCIDENT_INTAKE.md).

**Exit gate:** a manual report creates one incident and trigger, shows “reported, awaiting evidence collection,” and survives API restart. Reusing an idempotency key creates nothing new; a distinct report appends a trigger to the open case. Unknown target, wrong UID, unauthenticated request, and oversized note are rejected. Intake does not claim detection, diagnosis, or approval.

## Phase 3 — collect real evidence through one MCP server

A read-only MCP scaffold now exists; this phase remains incomplete until real kind connectivity and API evidence persistence pass. AI run isolation and timestamp checks do not complete that integration.

**Implement**

- Add `apps/mcp/` as the sole infrastructure tool server. Give it a scoped Kubernetes ServiceAccount/Role for the sample namespace and read-only Prometheus access. API and AI are permitted bounded read clients; only the API may request future mutations with an independently validated execution capability. See [agentic authority contract](agentic_architecture/README.md). Do not mount a cluster-admin kubeconfig or Docker socket.
- Bootstrap a restricted kubeconfig whose API-server address is reachable from inside the MCP container; refresh expiring credentials. On Windows Docker Desktop, validate the published kind endpoint via `host.docker.internal`; document the Linux host-gateway equivalent.
- Implement bounded tools for approved Prometheus query templates, Deployment/ReplicaSet status, pods, events, and capped pod logs. Restrict namespace, target, time range, result size, and timeout. Mutation remains disabled.
- Extend the existing `investigations` and `evidence_items` schema and APIs. They already retain normalized synthetic source/time/hash/trust data; add the target UID, observation window, redaction marker, bounded real payload, and per-source collection error needed for this incident. Keep existing generated contracts in sync. Missing sources are visible gaps, never generated facts.

**Exit gate:** for a faulty sample app, one investigation retains real metric, rollout, pod, event, log, and direct-probe observations where available, with stable evidence IDs. Disable one source and show an explicit collection error without fake data. Tests cover size bounds, unauthorized namespace/target, hostile log text, and evidence persistence after restart.

## Phase 4 — investigate with NVIDIA Nemotron via Nebius

**Implement**

- Extend the existing bounded mock provider interface with a Nebius Token Factory adapter for the release path. Configure `NEBIUS_API_KEY`, endpoint, model ID, timeout, and retry budget locally. Select a currently available NVIDIA Nemotron model and test the exact response behavior with a live call ([Nebius Nemotron guide](https://nebius.com/services/token-factory/nemotron)). Keep deterministic fixtures for CI.
- Build a bounded, redacted evidence bundle containing evidence IDs and short relevant excerpts. Keep credentials, unrestricted logs, and arbitrary local files out of the prompt.
- Validate the model response against a strict schema: hypotheses, supporting/contradicting evidence IDs, gaps, uncertainty, and one proposed action name from the allowlist. The API fills exact target and desired template from trusted local state. Reject unknown citations, malformed output, unsupported actions, and target drift. Persist provider/model/request metadata and validated findings.
- Show measured evidence and model interpretation separately in the incident UI. If Nebius is unavailable, retain evidence and show `needs_review`; never silently substitute a mock result in a live incident.

**Exit gate:** the fault fixture yields a real Nebius-backed, evidence-cited investigation. Invalid JSON/schema, unknown evidence IDs, prompt-injection text in logs, timeout, and provider failure cannot create an approvable proposal. Automated tests use fixtures; a documented live smoke test checks the external integration.

## Phase 5 — bind an exact proposal to human approval

**Implement**

- Extend the existing immutable recommendation versions, SHA-256 proposal hash, expiry, and separate approval/rejection records with exact Kubernetes target UID, expected bad template/resource version, desired captured good template hash, and real evidence citations. Resolve the desired template from local trusted baseline state, not model output.
- Reuse the existing current-version/content/expiry/approval checks, adding the real target precondition and authenticated operator session. Any payload or target change creates a new version and invalidates the old approval.
- Build a review screen that presents evidence, uncertainty, exact target, exact change, expected effect, and verification plan before the operator explicitly clicks approve or reject. Keep this phase read-only to Kubernetes.

**Exit gate:** exact-hash approval persists and appears in the audit timeline. Rejected, expired, changed, missing-citation, duplicate, and wrong-target proposals cannot become executable. UI tests confirm that review and deliberate approval are separate actions. No MCP mutation capability is enabled yet.

## Phase 6 — execute one guarded action

**Implement**

- Extend the existing durable execution/idempotency records and commit-before-adapter claim with a Kubernetes preflight snapshot and real action outcome. Preserve its rule that an interrupted pending attempt is not automatically invoked again; design explicit reconciliation before enabling real mutation.
- Add the single MCP mutation tool for restoring the captured known-good pod template. Before patching, API and MCP independently check namespace/name/UID, current resource version and bad-template hash, desired good-template hash, approved proposal, and expiry. Use a short-lived one-use signed capability bound to this execution; MCP rejects a replay.
- Patch through the Kubernetes API using a namespace Role scoped to the sample Deployment. Record the API result. A successful patch is `execution_succeeded`, not `verified`.

**Exit gate:** one approved exact proposal causes one patch. Duplicate request returns the prior execution. Missing/rejected/expired approval, stale resource version, changed UID/template, replayed capability, and any out-of-scope target fail without mutation. Audit evidence shows the actor, proposal hash, preflight state, and result.

## Phase 7 — verify recovery independently

**Implement**

- Extend the existing separate `verification_results` record and API with real post-action measurements. Start a new observation window after the patch; poll restored rollout availability, perform three fresh functional `/healthz` probes, and query a 60-second Prometheus window with at least 20 `/api/work` requests and less than 1% 5xx.
- Store thresholds, actual counts/ratio, observation times, rollout revision, probe statuses, timeout, and the decision reason. Reuse the current verification API states `passed`, `failed`, and `inconclusive`; the UI may label `passed` as “verified recovery.” A failed probe or persistent errors is failure; missing/stale metrics or insufficient traffic is inconclusive. Do not auto-close the incident.
- Complete the existing incident detail/timeline UI for trigger → evidence → investigation → proposal → approval → execution → verification. Regenerate the committed OpenAPI snapshot and frontend types after route/schema changes; preserve contract-drift checks and pending/error/empty states.

**Exit gate:** the successful run reaches `verified` only after all independent conditions pass. A patch that leaves the app unhealthy reports failure; unavailable metrics reports inconclusive. Every verdict can be traced to stored readings, not model prose.

## Phase 8 — clean-machine release rehearsal

**Implement**

- Turn bootstrap, fault, reset, and teardown into documented commands in [demo runbook](DEMO_RUNBOOK.md). Keep the local database across normal `down`; mark destructive reset commands clearly. Add integration readiness to the UI/API without exposing credentials.
- Run the full scenario twice from a clean cluster and database, then run denial and failed-verification cases. Check Compose↔kind networking on the supported host platform and a documented Linux equivalent.
- Extend the existing CI jobs for API migrations/contracts and web lint/build with MCP unit tests, sample metrics, and safe end-to-end tests. Keep the live Nebius smoke test explicitly credential-gated; deterministic tests alone do not satisfy release acceptance.
- Review evidence redaction, secret handling, network bindings, RBAC, audit integrity, and the docs against actual observed behavior.

**Release gate:** a developer with Docker/Compose, kind, and a Nebius key can follow the runbook without code edits and see an evidence-backed proposal, explicit approval, exactly one scoped action, and measured recovery. The same runbook demonstrates rejection and a failed or inconclusive verification. Save commands, timestamps, evidence IDs, proposal hash, execution ID, and readings in a redacted acceptance record.

## Contract checkpoints and sequencing

1. **After Phase 0:** browser/API route, local test commands, and Compose ports are fixed. Freeze the sample target naming convention.
2. **Before Phase 2 migration:** agree on target identity, incident trigger fields, idempotency, and lifecycle versus symptom assessment. Publish OpenAPI before UI work consumes it.
3. **Before Phase 4:** agree on evidence IDs, timestamp/window format, trust labels, and bounded MCP tool responses. Model output can cite only stored IDs.
4. **Before Phase 6:** review proposal hash canonicalization, Kubernetes preconditions, one-use capability, Role permissions, and execution state machine. Mutation stays disabled until negative tests pass.
5. **Before Phase 8:** freeze verification thresholds and report shape based on observed sample traffic; verify that the UI and API describe the same outcome.

Database migrations should extend the existing `0001`–`0003` history incrementally at the phase that first needs each field/table; test upgrades/downgrades in an isolated PostgreSQL database. Existing mock recommendations and persisted synthetic cost rows must remain visibly demo-only or be removed through a deliberate migration, never interpreted as real investigation history.

## How to ship the phases

Keep each phase in small reviewable changes rather than one repository-wide rewrite. A useful order is: (a) contract/migration and fixture, (b) backend/tool behavior, (c) UI, (d) integration test and runbook update. Merge only when the phase's exit gate works on its own. Each PR should state the command used to verify it, the actual observed result, any schema/API change, and how to reset the local fixture. Preserve the current user's untracked files and database volume unless a reset is explicitly requested.

Use three levels of checks:

| Check | When | What it proves |
|---|---|---|
| Fast unit/component checks | Every PR | Parsing, state rules, schema validation, idempotency, UI rendering. |
| Local kind integration | Phases 1, 3, 6, 7, 8 | Container networking, real Kubernetes/Prometheus reads, guarded patch, and measured recovery. |
| Nebius live smoke test | Phases 4 and 8 with a supplied key | The configured Nemotron model and actual response shape work over HTTPS. This is separate from deterministic CI fixtures. |

| Risk | Earliest proof and response |
|---|---|
| Compose cannot reach kind | Phase 1 tests metrics from inside Prometheus; Phase 3 tests Kubernetes API from inside MCP. Do not proceed with host-only checks. |
| Fault produces no useful 5xx traffic | Phase 1 keeps pods process-ready, runs a traffic generator, and records numerator/denominator before investigation work. |
| Model invents evidence or a command | Phase 4 rejects unknown citations and action names; Phase 5 fills the actual target/template from trusted state. |
| Approval is stale or action targets another workload | Phases 5–6 bind hash, UID, resource version, template hashes, expiry, session actor, and one-use capability; negative tests are mandatory. |
| Patch succeeds while app stays unhealthy | Phase 7 stores fresh rollout, probe, and metric readings and reports failure or inconclusive, never inferred success. |
| Nebius is unavailable | Phase 4 retains local evidence and `needs_review`; no automatic mock promotion or action. |

If the restore patch fails, record `execution_failed`, leave the incident open, and use the documented local reset command for the demo. Do not silently retry a mutation or claim verification without a new execution decision.

## Explicitly after the first release

- **Automatic detection:** add the Prometheus rule/poller described in [incident intake](INCIDENT_INTAKE.md), enter through the same intake service, and test deduplication, stale data, low traffic, and reset/retrigger. The MVP can ship with manual intake.
- **Optional GitHub context:** read recent commits/deployments for the exact target with bounded scopes; store provenance and keep it advisory.
- **Cloud Cost Autopsy:** revisit the existing persisted synthetic cost reports as a separate product track with real source ingestion; measured totals and estimated savings already have distinct calculations.
- **Broader infrastructure/team use:** additional workloads, clusters, cloud providers, per-user auth/roles, and production deployment require a new threat review and separate acceptance criteria.
