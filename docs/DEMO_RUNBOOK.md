# Demo runbook

Use the owned local sample and keep synthetic compatibility, source collection, patch success and independently measured recovery visibly distinct. No script below authorizes arbitrary infrastructure.

## Read-only investigation demo

Follow [setup](DEVELOPMENT.md#environment-and-startup), then:

1. Confirm the owned fixture UID/template and functional health with `python3.12 scripts/kind_fixture.py status`.
2. Use `python3.12 scripts/kind_fixture.py fault` to inject the controlled configuration fault. Allow a complete fresh minute of traffic; the fixture verifier uses a 75-second rollout/scrape allowance.
3. Sign in to the console and report the exact registered target. A report is not yet a confirmed cause.
4. Inspect queue/run state, retained source UUIDs/times, metric counts and probe readings. Show `/healthz` failing separately from `/readyz` remaining ready. Missing sources or model gaps require review.
5. Inspect the validated Nemotron hypotheses and their retained evidence. Show model and provider metadata without displaying credentials. Do not use ChatOps canned text as proof.
6. Reset with `python3.12 scripts/kind_fixture.py reset` when finished.

`python3.12 scripts/smoke_investigation.py` automates a real fault/report/model/persistence check and restarts API/worker. It resets the owned sample in `finally` and saves a private receipt. It requires live credentials and creates incident history; it is not a credential-free unit test.

## Exact proposal and guarded restore

Before granting writer access, inspect the registered baseline, source gaps, action preconditions and denial tests. Keep `LIVE_EXECUTION_ENABLED=false` outside an intended trial.

```sh
python3.12 scripts/register_baseline.py
python3.12 scripts/configure_execution.py
python3.12 scripts/check_writer_scope.py
```

The baseline comes from the captured healthy fixture, not AI output. Writer setup leaves execution disabled. In the console, review the exact target UID/resource version, bad/good template hashes, evidence, version, expiry and proposal hash before approving. Execution needs its own idempotency key.

For a deliberate owned-fixture acceptance trial on a POSIX shell:

```sh
LIVE_EXECUTION_ENABLED=true PROPOSAL_TTL_SECONDS=60 docker compose -f compose.yaml -f compose.kind.yaml -f compose.execution.yaml up -d --build --wait
python3.12 scripts/smoke_execution.py
# Always remove the writer configuration afterward, including after failure:
docker compose -f compose.yaml -f compose.kind.yaml up -d --wait api mcp worker
```

The script checks real rejection, approval expiry, drift, capability/preflight denials, one approved restore and replay. It resets the fixture in `finally`, but removing the execution overlay is a separate cleanup step. Restore the normal stack even if a command fails; keep `.env` execution false. PowerShell needs session environment overrides and must remove them before cleanup.

If a trial stopped before any execution request, `--resume` retains passed independent denial cases and gathers fresh evidence for remaining cases. It refuses a changed UID, recorded execution intent/ID or a passed receipt. Never use it to retry an uncertain write. Use the API's read-only reconciliation instead.

`smoke_proposal.py` exercises proposal/review with execution disabled. `smoke_recovery.py` attempts two full guarded actions plus independent verdicts; run it only when all required safety and verification prerequisites are reviewed. Neither is a harmless read-only smoke.

## Independent recovery acceptance

After a successful execution, `/verify` must retain a restored rollout, three new `/healthz` HTTP 200 probes and a full fresh post-action minute with at least 20 work requests and less than 1% 5xx. Show numerator, denominator, source times, thresholds and reason. Failed measurements mean `failed`; stale/missing data or insufficient traffic means `inconclusive`. Do not equate a patch response, readiness badge or reset script with recovery, and do not auto-close the incident.

Release acceptance still requires two complete positive cycles plus rejection, expiry, drift, provider-outage and failed/inconclusive recovery cases. Browser/UI state, contract drift, PostgreSQL concurrency and clean-machine instructions need acceptance on the final merged revision.

## Acceptance status

| Area | Evidence boundary |
|---|---|
| Owned fault and real investigation | Earlier local records demonstrated live source collection, validated Nemotron findings and evidence persistence after restart. |
| Exact approved action | Earlier local acceptance demonstrated one restore and zero-mutation denial/replay checks. Execution `4cb26a7e-fe66-4a79-8128-ad7eb87663fb` was recorded as succeeded, with no verification record. |
| Independent recovery | Implementation and tests exist; two complete measured recovery cycles are not established by those records. |
| ChatOps | UI/API integration exists; grounding, citation, fallback and durable audit limitations remain. |
| Discord | Earlier webhook cards were reported delivered with source gaps; live slash-command acceptance remains open. |
| Current merged revision | Re-run relevant checks; historical counts and diagrams are not fresh test or demo results. Documentation cleanup itself does not run a live scenario. |

Useful receipts live under ignored `.local/kind/` and are not shipped in fresh clones. Save redacted new receipts with run/evidence/proposal/execution identity and actual readings; never invent replacement receipts when the model requires review.

## Synthetic compatibility demo

Use [explicit synthetic mode](DEVELOPMENT.md#explicit-synthetic-mode) and `scripts/smoke.py`. Cost reports are labeled sample calculations, not AWS bills. The base unconfigured operations adapter records an unavailable failure rather than a real patch. Show those modes honestly and keep their records separate from a live target investigation.

Stop with `docker compose down` to preserve database data. Reset/teardown of kind uses the [owned fixture runbook](../infra/kind/README.md), not volume deletion or global Docker pruning.
