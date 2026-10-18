# Security

The current scaffold is a local synthetic demo. Compose binds published ports to 127.0.0.1; PostgreSQL has no published port. Configured CORS origins allow the local console, but CORS is not authentication. Sample passwords and local-demo-user are unsuitable for exposed or multi-user deployments.

Investigation providers are read-only and schema constrained. Evidence is explicitly synthetic and untrusted. Only the mock provider is configurable today; unsupported provider names fail configuration validation. External models must later receive bounded read-only evidence and return validated structured proposals, with timeouts and evidence references.

Approval requires a caller-supplied digest of the exact reviewed proposal. The server checks retained content, expiry, latest version, status, and the local demo action/target. A changed or superseded proposal requires a fresh investigation and review. The server labels local decisions itself and rejects actor spoofing. PostgreSQL row locks and conditional updates guard concurrent decisions.

These checks protect the current review workflow. There is no infrastructure executor. A future executor must independently recheck authorization, identity, exact content, expiry, action schema, target/environment, idempotency, and isolated-test policy. Approval status alone must never authorize execution. Verification must use independent measurements and record failure honestly.

The API appends audit records for supported state changes; database-level audit immutability and authenticated actor attribution are not implemented. Secrets, credentials, and raw unbounded logs must not be added to evidence or audit payloads.

The intended trust boundaries are UI → API, evidence/provider output → validated domain service, and approved action → controlled executor. Do not expose the scaffold until authentication/authorization, secret handling, rate limits, durable job handling, and production deployment controls are implemented.
