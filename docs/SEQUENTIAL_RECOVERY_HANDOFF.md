# Completion status and sequential member handoff

Updated 2026-10-29. This implements the PDF's proposal, approval, guarded restore, and independent verification gates in sequence on branch `feat/sequential-recovery`. The owned kind sample is currently healthy; the running Compose stack has live execution disabled. No successful live restore has been observed yet.

## Completion status

The implementation through Gate E is written and locally tested, but the PDF's product-complete checklist is **not complete**. Gate B/C read-only proposal and approval passed against the owned kind fixture with a real validated Nebius response. Gate D/E guarded patch and recovery verdict pass unit and API integration tests but have not reached a live approved patch: two attempted full trials stopped on external model timeout before proposal creation. Gate F requires two successful complete live cycles and the remaining negative/browser/CI checks. No commit, PR, merge or release claim has been made from this branch.

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
- Two full recovery trial attempts on 2026-10-29 injected the owned fault and measured about 120 requests/minute with 100% 5xx. Both stopped before proposal creation because the external Nebius call timed out (`OpenAITimeoutError`, AI returned 503). The script restored the sample in `finally`. No guarded patch or recovery verdict was obtained. This correctly exercises the provider-outage denial, but the PDF's two successful live cycles remain unverified.

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

## Remaining work by PDF member

The member numbers are role placeholders from the source PDF, not assigned people. Work and accept these gates **in order**; do not run competing write trials in parallel.

| Owner | Next work | Evidence required to hand off |
|---|---|---|
| Member 3 — AI and investigation | Resolve the Nebius timeout or document a provider-side outage, then obtain one new completed live investigation with five retained sources, valid evidence UUID citations and the allowlisted advisory action. Preserve `needs_review` when the provider fails. Review malformed output, log prompt injection, source gaps and budget tests. Explicitly defer or complete grounded ChatOps. | A redacted investigation ID, model/provider metadata, cited evidence IDs and a passing provider-outage denial; no AI-supplied baseline, YAML or target. This unlocks the next live proposal. |
| Member 1 — backend and approval | Review the exact baseline/proposal/approval code, migration `0006`, generated contract and audit boundaries. On the owned fixture, demonstrate rejection, expired approval and post-approval target drift with zero mutation. Complete PostgreSQL, concurrency and replay gates on the final branch. | Exact proposal hash, approval/rejection records, 409 denials, unchanged Deployment hash, and reviewed PostgreSQL/contract results. Then hand one approved current proposal to Member 2. |
| Member 2 — Kubernetes and execution | Refresh the short-lived writer token if needed; rerun `scripts/check_writer_scope.py`. With Member 1's approved current proposal, run one guarded action through the API. Observe exactly one patch and its stored execution ID. Exercise stale resource version, UID/template drift, capability expiry/scope and duplicate submission; reconcile any unknown outcome by reading only. | Kubernetes UID, before/after resource versions and template hashes, execution marker/ID, RBAC denials and zero-mutation negative receipts. Hand only a successful recorded execution to Member 4. |
| Member 4 — frontend, verification and QA | For each successful execution, run the separate verification and inspect rollout, three `/healthz` probes and the full fresh Prometheus minute. Finish the trigger-to-verdict timeline and browser tests, including pending/error/empty states. Run two complete positive cycles sequentially plus failed and inconclusive cases, CI and a clean-machine demo rehearsal. | Two redacted live receipts with six post-action measurements each, positive and negative browser runs, contract/CI results, and a demo that labels only measured `passed` recovery as verified. |

The shared final review is to confirm that the PDF's product-complete checklist is satisfied, secrets are absent from tracked files and demo records, and any optional cloud/Civo work remains outside this local acceptance path.

## Remaining release gates

- Obtain two successful live cycles once the external model responds, and inspect the saved redacted readings. Exercise a real post-approval target drift and an explicit rejected proposal on the owned fixture. Unit checks already cover drift, replay, capability expiry/scope, stale windows, insufficient traffic and provider outage, but they do not replace the live rehearsal.
- Run the PostgreSQL suite and browser E2E on the final branch, contract drift check, and CI. Review the pending/inconclusive UI and audit timeline against the PDF before merging. Do not claim release acceptance from the current provider-blocked trials.
