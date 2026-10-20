# Security

The current scaffold is a local synthetic demo. Compose binds published ports to 127.0.0.1; PostgreSQL has no published port. Configured CORS origins allow the local console, but CORS is not authentication. Sample passwords and local-demo-user are unsuitable for exposed or multi-user deployments.

Investigation providers are read-only and schema constrained. Evidence is explicitly synthetic and untrusted. Only the mock provider is configurable today; unsupported provider names fail configuration validation. External models must later receive bounded read-only evidence and return validated structured proposals, with timeouts and evidence references.

Approval requires a caller-supplied digest of the exact reviewed proposal. The server checks retained content, expiry, latest version, status, and the local demo action/target. A changed or superseded proposal requires a fresh investigation and review. The server labels local decisions itself and rejects actor spoofing. PostgreSQL row locks and conditional updates guard concurrent decisions.

Execution and verification endpoints now persist attempts and outcomes. The default server-owned operations adapter is unconfigured and never mutates infrastructure. Execution rechecks roles, current version, exact content, normalized evidence, expiry, schema/target, durable approval and uniqueness. Approval status alone never authorizes execution. Verification requires successful execution and fresh independent measurements, and rejects contradicted or unsupported success claims. A real adapter must additionally enforce environment/credential scope and isolated-test policy before enabling workload mutation.

Execution/verification claims are committed before adapter invocation. Retries replay pending or completed records; they never automatically invoke an interrupted attempt again. Pending-operation reconciliation is deferred. Adapter exceptions are sanitized, and an unknown action outcome is not a reason to retry blindly.

SQLite/PostgreSQL audit UPDATE/DELETE operations are blocked by triggers; PostgreSQL TRUNCATE is also blocked. Administrative DB permissions and retention policy still need production hardening. A server-owned role resolver permits local operator writes and viewer reads; caller-supplied actors are rejected. LOCAL_DEMO_ENABLED=false denies application access until real authentication is implemented. Secrets, credentials, and raw unbounded logs must not be added to evidence or audit payloads.

The intended trust boundaries are UI → API, evidence/provider output → validated domain service, and approved action → controlled executor. Do not expose the scaffold until authentication/authorization, secret handling, rate limits, durable job handling, and production deployment controls are implemented.
