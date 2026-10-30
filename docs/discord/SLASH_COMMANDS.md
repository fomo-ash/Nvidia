# Discord Slash Commands Reference

FixProof implements a secure, read-only Discord slash command interface through the `POST /discord/interactions` endpoint.

---

## 1. Security Architecture

### Ed25519 Cryptographic Verification
Discord requires all interaction endpoints to verify the authenticity of incoming requests using Ed25519 public-key cryptography.

FixProof inspects every request:
1. Validates the presence of `X-Signature-Ed25519` and `X-Signature-Timestamp` headers.
2. Enforces timestamp freshness (rejects requests older than 300 seconds to prevent replay attacks).
3. Verifies the signature against `DISCORD_PUBLIC_KEY` over `timestamp + raw_body`.
4. Rejects requests exceeding 8 KB in size.

```python
# Verification logic in apps/api/app/discord_interactions.py
public = Ed25519PublicKey.from_public_bytes(bytes.fromhex(settings.discord_public_key))
public.verify(bytes.fromhex(signature), timestamp.encode() + body)
```

### Role-Based Access Control (RBAC)
- **Guild Scoping**: Commands are only registered and accepted within the designated server (`DISCORD_GUILD_ID`).
- **Role Verification**: Inbound requests must carry at least one role matching `DISCORD_ALLOWED_ROLE_IDS`. Unauthorized users receive an immediate denial message.
- **Ephemeral Responses**: All command replies are marked with `flags: 64` (ephemeral), ensuring that incident details are visible only to the operator running the command.

---

## 2. Available Commands

All commands are subcommands under the `/fixproof` namespace:

### 1. `/fixproof recent`
Lists the five most recent live incidents recorded in FixProof.

- **Parameters**: None
- **Returned Data**:
  - Incident UUID
  - Current Lifecycle Status (`reported`, `investigating`, `approved`, `executing`, `recovered`, etc.)
  - Assessment Summary
- **Example Response**:
  ```text
  Recent live incidents:
  754e1a33-90a7-45c5-86d6-8ce04d10669c | recovered | Root cause: Deployment FAIL_MODE=on
  d978aa0d-893b-46db-bab4-3905710efbc8 | investigating | Investigating probe failure
  ```

---

### 2. `/fixproof incident id:<UUID>`
Inspects the detailed status, latest investigation, remediation proposal, and verification verdict for a specific incident.

- **Parameters**:
  - `id` (String, Required): Canonical Incident UUID.
- **Returned Data**:
  - Incident ID & Title
  - Target Workload UID & Namespace
  - Latest Investigation Status
  - Remediation Proposal State (Proposed, Approved, Rejected, None)
  - Execution Status & Recovery Verification Verdict (`passed`, `failed`, `inconclusive`)
- **Example Response**:
  ```text
  Incident 754e1a33-90a7-45c5-86d6-8ce04d10669c (sample-api degradation)
  Target: local-kind/fixproof-demo/sample-api
  Status: recovered
  Investigation: Completed (5 retained evidence items)
  Proposal: Restore known-good baseline (Approved by local-operator)
  Verification: PASSED (3/3 health probes 200 OK, 5xx rate 0.0%)
  ```

---

### 3. `/fixproof evidence id:<UUID>`
Lists the retained, cryptographically attested evidence items collected by the MCP worker for an incident.

- **Parameters**:
  - `id` (String, Required): Canonical Incident UUID.
- **Returned Data**:
  - Source Names (`kubernetes:deployment`, `direct:probe`, `prometheus`, `kubernetes:logs`)
  - Canonical Evidence Item UUIDs
  - Observation Timestamps
  - Collection Status (Retained vs. Gap)
- **Example Response**:
  ```text
  Retained Evidence for Incident 754e1a33-90a7-45c5-86d6-8ce04d10669c:
  • kubernetes:deployment | e3f1... | 2026-10-30T10:05:00Z | Retained
  • direct:probe | a902... | 2026-10-30T10:05:02Z | Retained (HTTP 500)
  • prometheus | c118... | 2026-10-30T10:05:04Z | Retained (5xx: 24%)
  • kubernetes:logs | 76b3... | 2026-10-30T10:05:05Z | Retained
  ```

---

## 3. Rejection of Write Commands

FixProof enforces a **strict non-mutation invariant** over Discord:

> [!CAUTION]
> If a user attempts to issue approval, execution, or remediation commands via Discord (e.g. `/fixproof approve` or `/fixproof execute`), the API will immediately reject the command:
> ```text
> "Unknown read-only FixProof command."
> ```
> All approvals and state mutations require an authenticated session in the FixProof Web Console to guarantee operator non-repudiation and audit trail integrity.
