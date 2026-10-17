# Security

Default integration access is read-only. Proposal execution is planned as an allowlisted backend service: target and parameters are immutable after approval; changed, rejected, expired, or previously executed proposals fail. Every decision and outcome is audited. LLM text, logs, and configuration are untrusted data, not instructions.

The current demo has no external authentication and no real mutation adapter. Never reuse its sample passwords, run it on an exposed network, or interpret mock investigation output as live evidence.
