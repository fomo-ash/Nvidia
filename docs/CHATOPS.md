# ChatOps

## Implemented surfaces

The console provides `/chat` with an incident selector and an incident chat drawer. Both use the signed operator session and CSRF header for writes. The API forwards to the internal AI service using `SERVICE_AUTH_TOKEN`.

| Route | Current context behavior |
|---|---|
| `POST /api/v1/chat` | Uses a valid supplied incident ID or falls back to the newest incident. With no incidents, returns a general overview response. |
| `POST /api/v1/incidents/{incident_id}/chat` | Requires the incident and gathers evidence belonging to its investigations. |
| AI `POST /chat` | Accepts supplied evidence; if absent and an investigation ID is supplied, may read the legacy MemorySaver state. |

Request fields are `message`, `session_id` and optional `incident_id`. The public response includes `incident_id`, `response`, `citations` and `session_id`. See the generated [OpenAPI](../apps/api/openapi.json) rather than copying this description as a second schema.

Chat has no approval, capability issuance, patch or verification tool. Any suggested fix remains advisory and must pass the independent proposal/review/action path.

## Current limitations

- The API gathers evidence across all investigations for an incident, not a single selected run. It does not filter only successful/current source observations. Global chat can select the latest incident when an ID is absent or invalid.
- The API sends a retained evidence list, but the live ReAct call in `apps/ai/app/chat/agent.py` passes conversation history and the user message without injecting that list into its prompt. Live tools can fetch new MCP reads; these dynamic reads are not durably mapped into the selected API investigation.
- `CitationValidatorGuard` parses legacy `EVD-xxxxxxxx` identifiers, while retained API evidence uses UUIDs and chat templates use other citation forms. Complete UUID citation validation and dynamic-read membership are not established. A clickable citation or an empty returned citation list does not prove grounding.
- Conversation memory is an in-process dictionary trimmed to 20 messages, not durable conversation storage. It is lost on restart and does not implement a selected-run persistence contract.
- Without a usable model key, or on AI exceptions, the AI service uses keyword-based canned text. Some templates assert configuration faults, fatal errors or recovery effects based only on source presence. The global API also has an evidence-based canned fallback. These are not validated diagnoses or reliable outage notices.
- The API chat handlers call the audit helper, but do not explicitly commit those writes; the shared session dependency closes without committing. Durable chat-audit persistence must be demonstrated or corrected before it is claimed.
- The strict retained-analysis deadline/token/concurrency limits apply to `/analyze`; they are not a complete conversation/tool budget for `/chat`.

These are implementation findings, not fixes performed by the documentation cleanup. Treat ChatOps as an experimental read/advisory interface. Use retained observations and the strict investigation result for diagnosis and exact proposal review; never rely on chat fallback text as proof of recovery.

## Validation still needed

Use healthy, faulty, missing-source, stale-run, provider-outage and injected-log cases. Verify selected-run context, source freshness, UUID citations, persisted dynamic observations, committed audit events and bounded tool use. Check that fallback text never invents a fault or implies recovery. Existing graph isolation and chat UI tests do not establish these end-to-end guarantees.
