# Recovery implementation handoff

The recovery workflow combines exact proposals, human approval, guarded restore and independent verification. The owned kind sample is currently healthy; the running Compose stack has live execution disabled. One exact approved live restore now passes with denial/replay evidence; see [approval and execution acceptance](APPROVAL_EXECUTION_HANDOFF.md). No independent recovery verdict was requested.

Investigation acceptance: a new live investigation passed after bounded inference and advisory-boundary hardening. See [investigation quality handoff](INVESTIGATION_QUALITY_HANDOFF.md). The two earlier recovery trials below remain historical failures; full measured recovery has not been certified. Grounded ChatOps is explicitly deferred.

## Completion status

The implementation through Gate E is written and locally tested, but the release checklist is **not complete**. Gate B/C read-only proposal and approval passed against the owned kind fixture with a real validated Nebius response. Gate D guarded execution now has one successful live patch and zero-mutation denial receipts. Gate E recovery verdicts pass unit and API integration tests but have not been accepted through live post-action measurements. Earlier full trials stopped on model timeouts; those historical failures remain recorded below. Gate F requires two successful complete live cycles and the remaining negative/browser/CI checks.

## Implemented path

1. Register the captured healthy sample template independently of model output. The registered UID, template and SHA-256 are append-only in SQLite and PostgreSQL.
2. Build an exact proposal from the latest completed, active, gap-free live investigation. The API binds target UID and resource version, bad and good template hashes, retained evidence IDs/hashes, validated advisory analysis, version and expiry. Operator approval checks the exact hash and a fresh Deployment read.
3. Claim an execution durably before any action. The optional `compose.execution.yaml` overlay gives MCP a separate writer token restricted by Kubernetes Role to `get` and `patch` on only `fixproof-demo/sample-api`. A 60-second signed capability binds one execution, proposal, target, resource version and template hashes. MCP independently checks the capability, exact healthy/faulty template shape and live state, then sends one atomic JSON Patch with UID, resource version and template `test` operations. A replay cannot submit another patch. Unknown outcomes remain pending for read-only reconciliation.
4. Verify separately from the patch. MCP waits for a complete post-action minute, checks the exact execution marker and good template, rollout availability, three direct `/healthz` HTTP 200 probes, and Prometheus work traffic. A pass needs at least 20 requests and less than 1% 5xx. Missing, stale, or insufficient traffic is inconclusive; a failed rollout/probe or measured error ratio fails. API validates the measurement set and timestamps before storing a verdict. Patch success alone never means recovery.
5. The operator UI shows the reviewed proposal and separate execute, reconcile and measure actions. Generated OpenAPI and web types were refreshed.

## Observed checks

- Scoped writer RBAC authorization check: writer may patch the sample; writer may not patch another Deployment or namespace or delete the sample; reader may not patch the sample. This was a permission check, not a live product patch. The writer token was never mounted into API, AI, worker or web.
- Final API SQLite suite: 91 passed / 8 PostgreSQL-only skipped; the isolated PostgreSQL suite passed 99 tests, including migrations, concurrency and audit. MCP suite: 31 passed. API/MCP Ruff checks and OpenAPI/web type contract drift checks pass. Web lint/build pass in the Docker build, and all 10 component tests pass.
- Prior Phase 5 live run produced five retained evidence items, a validated Nebius advisory analysis, exact proposal and operator approval. Wrong-hash approval and premature execution were denied. See [Phase 5 handoff](PHASE_5_PROPOSAL_HANDOFF.md).
- Two full recovery trial attempts injected the owned fault and measured about 120 requests/minute with 100% 5xx. Both stopped before proposal creation because the external Nebius call timed out (`OpenAITimeoutError`, AI returned 503). The script restored the sample in `finally`. No guarded patch or recovery verdict was obtained. This correctly exercises the provider-outage denial, but the two required successful live cycles remain unverified.

## Reproduce in order

Use only the disposable fixture created by `scripts/kind_fixture.py`; it verifies an ownership receipt and exact target UID. The commands below preserve the normal Compose database volume.

```powershell
python scripts/kind_fixture.py up
python scripts/configure_investigation.py
docker compose -f compose.yaml -f compose.kind.yaml up -d --build --wait
python scripts/register_baseline.py
python scripts/configure_execution.py
python scripts/check_writer_scope.py
```

After the read-only investigation and model provider are healthy, set `LIVE_EXECUTION_ENABLED=true` in ignored `.env`, then run:

```powershell
docker compose -f compose.yaml -f compose.kind.yaml -f compose.execution.yaml up -d --build --wait
python scripts/smoke_recovery.py
```

`smoke_recovery.py` runs two cycles sequentially. Each cycle requires fresh faulty traffic, a completed validated investigation, wrong-hash denial, exact approval, one restore attempt, duplicate-attempt denial, six fresh measurements and a `passed` verdict. It always resets the owned fixture on exit. The successful redacted receipt is written to ignored `.local/kind/recovery-acceptance.json`.

After a trial, set `LIVE_EXECUTION_ENABLED=false` in ignored `.env` and recreate the stack without the execution overlay. `python scripts/kind_fixture.py reset` restores only the owned sample; `python scripts/kind_fixture.py down` deletes only the owned cluster and preserves the normal database volume.

## Remaining work by workstream

Complete these gates in order. Run write trials sequentially to keep target state and acceptance evidence consistent.

| Owner | Next work | Evidence required to hand off |
|---|---|---|
| AI and investigation | Investigation-quality changes and a fresh live investigation now pass; see the investigation quality handoff. Review bounded inference, gap handling, source/citation consistency and historical-record compatibility. ChatOps is explicitly deferred. Keep provider failures in `needs_review`; use fresh observations for the next proposal trial. | A redacted investigation ID, model/provider metadata, cited evidence IDs and a passing provider-outage denial; no AI-supplied baseline, YAML or target. This unlocks the next live proposal. |
| Backend and approval | Live rejection, approval expiry and pre/post-approval drift pass with zero mutation. PostgreSQL migrations/concurrency/audit/replay tests pass (107). Complete contract and cross-workstream review; use fresh evidence for the next integrated trial. | Exact proposal hash, approval/rejection records, 409 denials, unchanged Deployment hash, and reviewed PostgreSQL/contract results. Then provide the execution workstream with one approved, current proposal. |
| Kubernetes and execution | Scoped writer permissions, invalid capability/preflight denials, one exact approved restore and replay denials now pass locally. Execution is disabled after the trial. Reconciliation safety is integration-tested; any live interrupted-write rehearsal must remain read-only until its outcome is established. See the approval/execution handoff. | Kubernetes UID, before/after resource versions and template hashes, execution marker/ID, RBAC denials and zero-mutation negative receipts. Provide verification with only a successfully recorded execution. |
| Frontend, verification and QA | For each successful execution, run the separate verification and inspect rollout, three `/healthz` probes and the full fresh Prometheus minute. Finish the trigger-to-verdict timeline and browser tests, including pending/error/empty states. Run two complete positive cycles sequentially plus failed and inconclusive cases, CI and a clean-machine demo rehearsal. | Two redacted live receipts with six post-action measurements each, positive and negative browser runs, contract/CI results, and a demo that labels only measured `passed` recovery as verified. |

The shared final review is to confirm that the release checklist is satisfied, secrets are absent from tracked files and demo records, and any optional cloud/Civo work remains outside this local acceptance path.

## Remaining release gates

- Run two complete verified recovery cycles with fresh validated investigations and inspect the redacted measurements. Live rejection, expired approval, pre/post-approval drift and one guarded restore already pass in the approval/execution handoff. Unit checks already cover drift, replay, capability expiry/scope, stale windows, insufficient traffic and provider outage, but they do not replace the live rehearsal.
- Run the PostgreSQL suite and browser E2E on the final branch, contract drift check, and CI. Review the pending/inconclusive UI and audit timeline against the release contract before merging. Do not claim release acceptance from the current provider-blocked trials.
