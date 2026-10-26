# Fail-closed MCP and agent implementation

Historical record: see [current status](CURRENT_IMPLEMENTATION_STATUS.md) and the [architecture contract](README.md) for subsequent run isolation, timestamp-bound hashes, metric freshness checks and CI changes. The verification counts and old hash format below apply only to the original branch.

This document records the changes on `fix/agent-mcp-fail-closed`. It describes the code as it runs now. The [architecture documents](README.md) describe the intended release; the [current status](CURRENT_IMPLEMENTATION_STATUS.md) lists the remaining gates. The changes here make the new services safer to develop against. They do not complete the incident-to-recovery product flow.

| Commit | Area | Main files |
|---|---|---|
| `6afd41f` | MCP read bounds, source errors, disabled mutation, Compose isolation | `apps/mcp/`, `compose.yaml`, `.env.example` |
| `e94900b` | AI evidence validation, graph routing, model and chat behavior | `apps/ai/` |
| `0d4d30e` | Corrected status and README | `README.md`, `CURRENT_IMPLEMENTATION_STATUS.md` |
| `793a059` | Ignore the temporary PR helper | `.gitignore` |

## Why this change was needed

The imported MCP scaffold returned believable hardcoded Kubernetes deployments, events, and logs when the Kubernetes API was absent. Its restore endpoint accepted a shared secret as a capability and could report success after a failed patch. The AI MCP client also invented metric, deployment, event, log, and probe evidence after both transport calls failed. In live mode, the model adapter could silently replace an unavailable Nebius response with synthetic analysis. Those paths made an unavailable dependency look like a diagnosed incident.

The new rule is: **a failed source is a collection gap, not a measurement**. An investigation without required live evidence or model analysis ends at `needs_review`. Infrastructure writes are disabled until the API owns a trusted baseline, exact operator approval, and execution preflight.

| Situation | Current behavior |
|---|---|
| Kubernetes credential, CA, API request, or target check fails | The Kubernetes adapter raises an error. No sample Deployment, event, or log payload is substituted. |
| Prometheus request fails or a query has no finite sample | The metrics tool raises an availability error. It does not turn missing data into zero requests. A real zero sample remains a zero-traffic observation. |
| AI cannot call MCP over SSE or the private REST route | The AI client raises `MCP telemetry unavailable: <tool>`. It does not invent an evidence ID or fact. |
| A required evidence source is still absent after two collection passes | The graph returns `needs_review` and no proposal. |
| Selected live provider credentials, response, or citations are invalid | Analysis returns `needs_review` and no proposal. `LLM_PROVIDER` selects Groq or Nebius; synthetic reasoning runs only when the request explicitly selects `synthetic` mode. |
| A caller requests restore | Restore is absent from MCP's advertised tools and REST routes. The remaining internal function always reports failure. |

## Request and evidence path

`apps/ai/app/main.py` accepts `POST /investigate` and starts the LangGraph workflow with the incident ID, target, and mode. The graph in `apps/ai/app/graph/workflow.py` calls the five read methods of `McpClient` through `collect_telemetry_node`. The MCP service in `apps/mcp/app/main.py` serves the official SDK's SSE transport at `/sse` and private REST equivalents under `/tools/`. Its registry in `apps/mcp/app/server.py` advertises exactly five read tools: `query_metrics`, `get_deployment_status`, `get_pod_events`, `get_pod_logs`, and `check_service_health`.

Each successful MCP tool returns an `EvidenceItem` with a generated `EVD-` ID, observation time, source, fact, bounded `raw_data`, `mode`, and a SHA-256 `content_hash`. The hash is calculated from JSON containing `source`, `fact`, and `raw_data`, with sorted keys. The AI client recomputes it and also checks that the source matches the requested tool and that the mode is `live`. This catches a malformed or altered response in transit. The hash is **not** a signature or proof that the infrastructure reading itself is true; the current services have no durable evidence attestation.

The AI client first tries MCP over SSE with an eight-second limit. If that transport fails, it tries the corresponding REST endpoint on the same private service with a five-second HTTP timeout. A non-2xx REST response, invalid evidence schema, wrong source, non-live mode, or hash mismatch becomes an exception. There is no synthetic fallback in this client. The REST fallback is a transport fallback, not a data fallback.

For example, with Kubernetes unavailable, the Deployment read raises instead of returning the old hardcoded `FAIL_MODE=on` object. The AI tries both transports, records `kubernetes:deployment: collection unavailable`, and makes one more collection pass. The local sufficiency rule cannot pass without live Deployment and Prometheus evidence, so the graph returns `needs_review` with no proposal. Jev never supplies the missing Deployment data.

## MCP read tools and bounds

### Kubernetes

`apps/mcp/app/adapters/kubernetes.py` checks the configured `fixproof-demo` namespace and exact `sample-api` Deployment before building target-specific API URLs. The client requires a nonempty bearer token and a CA certificate file and uses that CA for TLS verification; it does not set `verify=False`. Kubernetes HTTP errors and connection errors propagate to the tool caller. Each request has a five-second timeout.

The Deployment read returns replica counts, image, UID, resource version, conditions, a SHA-256 hash of the pod template JSON, and only the `FAIL_MODE` environment value. It does not return other environment values. The events read asks Kubernetes for at most 100 events, keeps only objects whose names start with `sample-api`, and returns at most the requested 1–20 events with messages capped at 500 characters. The logs read selects a pod with the registered app label, requests 1–100 tail lines, reads at most 16 KiB of response text, removes ANSI escapes, and caps each returned line at 500 characters. An empty pod list produces empty log evidence; an API failure does not.

### Prometheus

`apps/mcp/app/tools/metrics.py` and `apps/mcp/app/adapters/prometheus.py` accept only `1m` or `5m` windows. They assemble fixed `sample_http_requests_total` queries for total requests and `status_class='5xx'`, rather than accepting arbitrary PromQL from a caller. Results must have successful Prometheus status and a finite, nonnegative sample. The tool raises when the adapter reports a query error. The observed ratio and the current demo threshold (`>20%` 5xx with at least 20 requests) are included in successful evidence. These are detection values, not a recovery verdict.

### Direct probe

`apps/mcp/app/tools/health.py` accepts only the configured `SAMPLE_APP_HEALTH_URL`. The HTTP probe does not follow redirects. A connection failure is represented as a negative probe observation with status code `0`, latency, and an error string; that is a measurement of a failed probe, not a claim that the app returned HTTP 0. The configured URL must still be made reachable from the MCP container when the kind workload is added.

## Agent graph and Jev's actual role

`collect_telemetry_node` attempts metrics, Deployment, logs, direct probe, and events. It skips already collected sources on a second pass. It catches each failure separately and appends a source-specific `collection unavailable` entry to graph state. Only successful MCP responses enter the evidence list.

`evaluate_sufficiency_node` then calls `JevDecisionEngine`. **Jev is not the telemetry collector.** With a configured non-mock key, this class can call the remote TypeSafe endpoint using short fact excerpts. Without such a key, or when that call fails, it applies a local rule: both live Prometheus and live Deployment evidence must exist. The code may note missing logs, but logs are not currently required for that basic rule. Even when the remote service responds, its sufficiency answer cannot override the requirement for those two live sources. The graph retries collection once; after the second insufficient pass it routes to `needs_review`.

If evidence is sufficient, `reason_causes_node` calls the selected OpenAI-compatible model adapter. `LLM_PROVIDER=groq` uses `GROQ_API_KEY`, `GROQ_BASE_URL`, and `GROQ_MODEL`; `LLM_PROVIDER=nebius` uses the corresponding Nebius settings. The prompt contains evidence IDs, sources, hash prefixes, and fact text, not the full raw payload. The current parser extracts `EVD-` citations from model text and rejects an answer with no citations or any citation absent from the collected evidence. Model and parsing errors route to `needs_review`. The parser still turns free text into one hypothesis with a fixed confidence value; it is **not** a validated structured diagnosis or proof of causation.

The graph can then call Jev's risk scorer. The remote scorer is optional; its local fallback reports medium risk and always requires human approval. Neither path grants execution. The final `synthesize_proposal_node` deliberately returns `remediation_proposal=None` and `needs_review` because there is no registered, verified known-good pod template or API approval binding. The LangGraph checkpointer is currently `MemorySaver`, so this service does not durably store its graph state in PostgreSQL or in the API's evidence tables.

Jev remains in the code. This branch removed an unused SDK import and dependency, **not** the TypeSafe HTTP path. The proposed no-cost replacement is a separate task: implement explicit local sufficiency and risk policy, test it against real workload evidence, then remove the Jev configuration and client. Nebius is a separate model dependency and may still incur cost in live mode.

## Chat and execution boundaries

ChatOps no longer answers missing-model requests with invented 5xx or `FAIL_MODE` claims. It returns a manual-review message, and it validates citation IDs in normal responses against the evidence available for that incident. In-memory conversation history is keyed by `(incident_id, session_id)` and capped at 20 messages. Its model tools still call only bounded MCP read methods. This in-memory chat history is not an authenticated audit record.

The restore tool was removed from `list_tools`, `call_tool`, and the REST routes. `apps/mcp/app/tools/patch.py` retains a function for internal compatibility, but it always returns `failed`. `KubernetesClient.patch_deployment_env` also returns `False` and makes no PATCH request. The default capability secret was removed from MCP settings, `.env.example`, and Compose. MCP and AI no longer publish host ports; Compose services can still reach them on the private `fixproof` network. This network placement is not a substitute for future service authentication.

## How to verify this branch

From the repository root:

```powershell
docker compose -f compose.checks.yaml run --build --rm mcp-checks
docker compose -f compose.checks.yaml run --build --rm ai-checks
docker compose -f compose.checks.yaml run --rm mcp-checks ruff check --select E4,E7,E9,F app tests
docker compose -f compose.checks.yaml run --rm ai-checks ruff check --select E4,E7,E9,F app tests
docker compose config --quiet
```

On this branch, both test suites passed with 8 tests each, both focused Ruff checks passed, and Compose validated. The MCP tests cover the disabled mutation surface, target rejection, missing CA, URL and window bounds, and evidence hashing. The AI tests cover missing-source routing, rejection of uncited or unknown-cited model text, refusal to use synthetic analysis in live mode, local sufficiency/risk fallback, and ChatOps construction. Full Ruff lint still reports style findings across the imported scaffold. The tests do not start kind, exercise live Kubernetes or Prometheus data, call Nebius, persist an incident through the API, or prove recovery.

## Work required for the first real incident

1. Add the pinned kind cluster, sample app, traffic generator, fault/reset scripts, and Prometheus scrape. Capture a trusted known-good template before fault injection.
2. Provide MCP with a namespace-scoped Kubernetes credential, CA, reachable API URL, and reachable health URL. Prove these paths from inside its container and test partial source failure.
3. Connect authenticated API incident intake to MCP evidence collection. Persist evidence IDs, target UID, time window, redaction metadata, and collection errors; use a durable worker/checkpointer.
4. Replace the optional Jev path with tested local policy if avoiding its cost. Keep sufficiency, risk, and approval decisions separate from model prose.
5. Validate a live Nebius response against a strict structured schema and stored citations; surface uncertainty and gaps. Keep provider output advisory.
6. Bind a proposal to the trusted baseline, current Deployment UID/resource version/template hash, expiry, evidence, and an authenticated operator approval. Implement one-use execution capability and independent API/MCP preflight before restoring write access.
7. Verify a completed rollout, functional `/healthz`, and a fresh metric window after the action. Record passed, failed, or inconclusive independently of execution success.

Until those gates pass, `needs_review` is an honest result, and neither the AI service nor MCP claims a verified fix.
