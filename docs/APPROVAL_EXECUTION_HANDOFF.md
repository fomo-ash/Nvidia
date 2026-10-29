# Approval and guarded execution acceptance

## Scope

This milestone covers backend approval policy and one scoped Kubernetes restore. Operator UI work, independent recovery verdicts, browser scenarios and release rehearsal remain separate work.

The only action target is the registered `local-kind/fixproof-demo/sample-api` Deployment. Its trusted healthy template is registered independently of model output. The API binds proposal hash, version, expiry, target UID, resource version, evidence and template hashes before operator approval. The AI provides advisory findings only.

## Pending outcome safety

An execution claim is committed before MCP is called. Duplicate keys replay the original response; a new key cannot repeat the same recommendation. A pending execution now also blocks execution of another recommendation for the same incident, under the existing incident row lock.

Read-only reconciliation confirms success only when the Deployment has both the execution marker and the trusted template hash. An unchanged or drifted Deployment does not establish that the original request cannot still complete, so it remains pending. Reconciliation never submits a patch. An unresolved result requires investigation rather than automatic retry.

## Automated checks

- API SQLite: 99 passed; eight PostgreSQL-only cases skipped.
- API isolated PostgreSQL: 107 passed, including migrations, concurrency, audit integrity, replay and the incident-wide pending-execution guard.
- MCP: 33 passed, covering capability validation, atomic patch conditions and zero-patch replay rejection.
- API/script lint and formatting, generated frontend contracts: passed. Previously merged execution scripts received formatting-only corrections.
- Fixture and acceptance safety tests: 10 passed, including refusal to resume after an unacknowledged execution request or target change. Sample endpoint contract: three passed.
- Writer permissions: patch the registered sample allowed; patch another Deployment or namespace, delete the sample and patch with the reader identity denied.

The PostgreSQL container is disposable and separate from application data. These checks do not certify browser behavior or a measured recovery verdict.

## Investigation context

The sample profile describes the actual endpoint contract, and the current investigation probe records both `/healthz` and `/readyz` on the same registered origin. Functional health remains independent of readiness; a successful readiness response cannot override a failed work handler. An unavailable functional probe is a source failure. Older event timestamps remain part of the retained evidence rather than being treated as current readiness measurements.

AI tests pass (55), MCP tests include the separate current probe readings, and all three sample endpoint contract tests pass. Model gaps still require review and cannot authorize a proposal.

## Live trial

Live acceptance passed. Rejection, expired approval, drift before approval and drift after approval have zero-mutation receipts. MCP also denied bad signature, capability expiry, wrong scope, wrong UID, stale resource version and changed template hash without mutation.

Proposal `d5f6d3df-54f6-4413-9ecd-fdf6f8f87f01`, hash `c2435e7348b913637ebf47ba118ab649fa6fcb54977d8e751d031fdb18fe7e4a`, produced execution `4cb26a7e-fe66-4a79-8128-ad7eb87663fb` through the authenticated API. The Deployment UID stayed unchanged, resource version changed from `48320` to `48363`, generation advanced from 28 to 29 and the template changed from the exact faulty hash to the registered healthy hash. The returned execution marker matched the durable execution ID. API idempotent replay returned the same execution; a new key and same-execution MCP replay were denied.

The denial cases are independent fixtures against the same registered UID. Rejection and expiry receipts were retained from an earlier stopped run; the resumed run obtained fresh evidence for drift and the successful action. No previous approval was reused to authorize the restore. Earlier trials stopped on model review gaps or a missing advisory action; these incomplete receipts remain available locally rather than being discarded. The model profile and current readiness observation were clarified without relaxing any proposal or execution gate.

After cleanup, API reports live execution disabled and the normal 900-second proposal lifetime. MCP has no writer mount or execution signing key. The owned fixture reports functional health and readiness 200. The execution has zero verification records, so this acceptance makes no measured recovery claim. Uncertain-response reconciliation is covered by API integration tests, not a live interrupted-write rehearsal. The trial script creates fresh model-backed proposals for explicit rejection, expired approval, drift before approval and drift after approval. Each denial must leave Deployment identity, resource version, generation, template hash and execution marker unchanged.

Before the positive restore, internal MCP checks reject a bad signature, expired capability, wrong scope, wrong UID, stale resource version and changed template hash. A successful exact approved action must restore the trusted template, preserve UID, increment generation once and record its execution marker. Idempotent replay returns the same execution; a new API key and same-execution MCP replay must not patch again.

The script never invokes `/verify` or reports verified recovery. It resets only the owned fixture in `finally`. The outer trial command recreates the stack without the execution overlay on exit.

## Reproduce

```sh
python3.12 scripts/configure_execution.py
python3.12 scripts/check_writer_scope.py
LIVE_EXECUTION_ENABLED=true PROPOSAL_TTL_SECONDS=60 docker compose -f compose.yaml -f compose.kind.yaml -f compose.execution.yaml up -d --build --wait
python3.12 scripts/register_baseline.py
python3.12 scripts/smoke_execution.py
# Always restore the default stack after the trial.
docker compose -f compose.yaml -f compose.kind.yaml up -d --wait api mcp worker
```

If a run stops before any execution request, `python3.12 scripts/smoke_execution.py --resume` retains passed independent denial cases and collects fresh evidence for the remaining cases. Resume refuses a changed target, any recorded execution intent, an execution ID or an already-passed receipt. An unknown response must be investigated through the API, never retried through the script.

The 60-second TTL is a temporary container setting for the expiry trial; the normal default remains 900 seconds. Local `.env` keeps execution disabled. Credentials and redacted receipts remain ignored. The receipt is `.local/kind/execution-acceptance.json`; trial output is `.local/approval-execution-acceptance.log` and `.local/approval-execution-resume.log`. Incomplete attempts have separate local receipts and transcripts.

## Remaining gates

Cross-workstream review and CI remain required. Independent verification must still obtain its own post-action rollout, three health probes and full traffic window. Two complete recovery cycles and failed/inconclusive recovery rehearsals are not covered here.
