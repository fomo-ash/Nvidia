# Investigation quality handoff

## Scope and ownership

The investigation service provides structured model responses, evidence grounding, uncertainty, inference budgets and validated advisory results. The API constructs exact proposals from independently registered baselines. Operator approval, execution capability and Kubernetes writes remain outside model authority.

The supported investigation path is API intake → durable worker → retained MCP observations → stateless AI `/analyze` → validated result. The API database owns job state and canonical evidence UUIDs. The older standalone LangGraph and MemorySaver endpoints are internal scaffolds, not the authoritative product workflow.

## Changes

- Retained analysis makes one provider attempt with no SDK retries. Its configurable deadline defaults to 45 seconds and cannot exceed the API reader's 60-second timeout. This replaces an inherited 20-second SDK timeout with one retry inside an outer deadline. The completion budget remains capped at 8,192 tokens, including model reasoning. At most two analysis calls run concurrently per AI process; excess calls fail before inference rather than waiting in a queue.
- Nebius defaults in service configuration and Compose now agree with the example environment: Token Factory and `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`. Existing local credentials are unchanged.
- Analysis accepts only the five registered source names, unique source/UUID pairs, fresh timezone-aware timestamps and bounded finite JSON. Evidence freshness is checked again after the model returns. Truncated responses are rejected.
- API and AI share equivalent validation: supporting and contradicting UUID lists must be unique and disjoint; contradictory evidence cannot carry low uncertainty. Unknown citations, arbitrary actions and extra fields such as YAML, target or baseline are rejected.
- Missing source context cannot suggest restoration. A validated answer with unresolved gaps uses action `none`; the worker retains the answer and marks the run `needs_review`. Model-reported gaps now propagate to the durable review status. Strict advice checks run at ingestion, proposal creation and current-proposal review, so older investigation history stays readable without allowing stale advice to be newly approved. An invalid answer retains source observations, records a model gap and cannot create a live proposal.

These checks establish the response and authority boundary. Citation membership does not establish that a diagnosis is correct; the evidence and uncertainty remain part of operator review. Prompt-injection tests check that logs remain in the untrusted context and that injected action fields fail validation, rather than claiming immunity to arbitrary prompts.

## Checks

- AI suite: 55 passed. New coverage includes timeout cancellation, no retry, capacity exhaustion, partial completion, stale context after inference, source drift, payload limits, contradictory/unknown citations, missing sources and injected operation fields.
- API SQLite suite: 98 passed, eight PostgreSQL-specific tests skipped. New coverage proves that model gaps require review and invalid advice cannot become a live proposal. No database migration or state schema changed in this workstream.
- OpenAPI export check and generated frontend contracts: passed; the public JSON response shape is unchanged.
- Live investigation acceptance: passed on the owned kind fixture. The fresh 60-second window measured approximately 120 requests, all 5xx, with functional health 500 and readiness 200. Investigation `3d671465-ffcf-44b3-a02d-4e218b4b0526` completed with five retained sources, no source/model gaps, three findings citing retained UUIDs, and the allowlisted `restore_known_good_template` suggestion from Nebius/Nemotron. Evidence survived API/worker restart unchanged. The fixture was reset to healthy afterward.
- The first trial exposed stricter validators rejecting an older record during history serialization. Validation now runs at ingestion and proposal/review boundaries; regression tests demonstrate readable historical investigations and denied approval for legacy advice with unresolved gaps. No retained records were edited or deleted to obtain acceptance.
- Ruff lint and formatting pass, including a formatting-only correction in the merged operations service. The public OpenAPI and generated frontend contracts remain unchanged. PostgreSQL, browser and GitHub CI results from other milestones are not re-certified by this workstream.

The redacted local receipt is `.local/kind/investigation-quality-acceptance.json`; live output is in `.local/investigation-quality-acceptance.log`. Successful guarded execution and measured recovery remain separate team gates. The sample reset changes its resource version, so the acceptance record cannot authorize a later action: the next proposal/approval trial requires fresh matching faulty-state observations.

## ChatOps decision

Grounded ChatOps is explicitly deferred from this milestone, for the current milestone. The legacy `/chat` endpoint is service-authenticated and not connected to the operator UI. Its in-memory history and dynamic tool results are not a durable evidence handoff. Do not expose it as a supported operator feature until it loads a selected retained run, persists every dynamic tool observation, validates citations against that complete run and enforces conversation/tool budgets. ChatOps must not gain proposal approval or execution authority.

## Reproduce

```sh
cd apps/ai
.venv/bin/pytest -q
cd ../api
.venv/bin/pytest -q
.venv/bin/python scripts/export_openapi.py --check
cd ../..
pnpm contracts:check

docker compose -f compose.yaml -f compose.kind.yaml up --build --wait --wait-timeout 180
python3.12 scripts/smoke_investigation.py
```

The live check deliberately faults only the owned kind sample, reports the fault, verifies five retained sources and a validated Nebius result, checks persistence after API/worker restart, and resets the sample in `finally`. It does not create or approve a proposal or use the execution overlay. If the 24-hour reader token expires, refresh it with `python3.12 scripts/configure_investigation.py` and recreate the kind-overlay services before retrying.

## Next handoff

Backend review covers the shared validators and advisory-gap handling against the proposal contract. A new completed, gap-free, active investigation can supply evidence to exact proposal creation; the model supplies only the allowlisted action name. Backend, infrastructure and verification workstreams cover approval, controlled patch and independent recovery trials. CI and cross-workstream review remain required before merge.

The [approval/execution acceptance](APPROVAL_EXECUTION_HANDOFF.md) records subsequent sample-profile clarification, current health/readiness evidence and the successful exact approved restore. The investigation acceptance above remains its original snapshot; independent recovery verification is still separate.
