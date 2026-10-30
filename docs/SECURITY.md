# Security and authority

FixProof's supported target is an owned local sample, not an exposed multi-user infrastructure control plane. Public ports bind to loopback; PostgreSQL, AI, MCP and workers stay on private Compose networks. CORS is not authentication. Production login, rate limits, transport, administrative database roles and retention still require hardening.

## Operator and service identity

With local demo mode false, application reads require the signed operator cookie. Writes also require the configured allowed Origin and CSRF token. Login uses `OPERATOR_SECRET`; session signing uses a separate `SESSION_SIGNING_KEY`. Local demo mode bypasses that identity boundary for synthetic compatibility and must not be exposed.

Internal AI/MCP requests use `SERVICE_AUTH_TOKEN`. Only AI receives inference credentials. Only API receives operator/session secrets. Only MCP mounts Kubernetes read credentials; the optional writer token is separately scoped. `EXECUTION_SIGNING_KEY` is separate and supplied only to API/MCP through the execution overlay. Keep `.env`, kubeconfigs, reader/writer files and local evidence receipts private and ignored.

## Evidence and advice

The durable investigation path validates envelope mode/source/time/hash/UID before redaction and storage. It keeps transport provenance separately from the redacted API representation. Source failures persist explicit errors and empty payloads. Logs and model text remain untrusted instructions.

Strict `/analyze` output uses canonical retained UUIDs, bounded hypotheses, gaps and an allowlisted advisory enum. Inconsistent/unknown citations and extra YAML/target/baseline fields fail validation. The API independently constructs exact proposals from an operator-registered baseline. Neither a model finding nor a Jev/Laya result authenticates a user or authorizes action.

Chat does not yet provide all those grounding guarantees: evidence across runs, live context injection, UUID parsing, canned claims, dynamic-read persistence and chat-audit commits remain limitations. See [ChatOps](CHATOPS.md); do not present chat text as verified diagnosis or recovery.

## Approval and infrastructure writes

Approval binds the exact version/hash/content/expiry and rechecks current target state. Rejected, stale, changed or unsupported proposals cannot execute. A durable approval record must match the proposal; status alone is insufficient.

The API commits an execution claim before invoking MCP. The capability independently binds exact UID/resource version, template hashes, target, execution and expiry. The writer Role permits only get/patch on the registered sample. Kubernetes atomic tests prevent a check/patch drift race.

Unknown outcomes remain pending and block further incident execution. Reconciliation reads the marker/template; it never retries a patch. An unchanged target is not sufficient proof of no in-flight action. Recovery requires independent post-action measurements, not a successful patch response or readiness badge. See [MCP controls](MCP_KUBERNETES.md).

## Audit, delivery and data exposure

Lifecycle audit, trigger and baseline records have database immutability guards; PostgreSQL tests include TRUNCATE protection. Database administrators can still disable guards. Durable idempotency and row locks do not promise exactly-once external network delivery. Chat audit persistence is a separate unaccepted path.

Discord uses committed-event delivery, safe retained metadata and selected numeric summaries rather than raw logs, report text or model output. Mentions are disabled. Signed command reads additionally require configured application, guild and role. The bot token is registration-only. No Discord command approves or executes. A public interactions ingress needs its own review; do not expose the whole local API casually.

Internal documents preserved in ignored local storage are not secret storage or history erasure. Material already committed remains in Git history; removal from the current tracked tree does not revoke credentials. Any actual leaked credential requires rotation. Documentation screenshots, receipts and demos must never reveal operator/model keys, webhook tokens or kubeconfigs.
