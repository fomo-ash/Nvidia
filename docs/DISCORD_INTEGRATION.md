# Discord integration

Discord is an optional delivery and read-only interaction layer. It cannot approve a proposal, execute a fix, choose a baseline, trigger collection or alter incident state. The API remains authoritative.

## Setup

Create an incoming webhook for the chosen channel and a Discord application for slash commands. Store configuration only in ignored `.env`:

| Name | Purpose |
|---|---|
| `DISCORD_WEBHOOK_URL` | Official incoming webhook URL; accepted only under `https://discord.com/api/webhooks/...`. |
| `DISCORD_PUBLIC_KEY` | Application Ed25519 public key for request verification. |
| `DISCORD_APPLICATION_ID`, `DISCORD_GUILD_ID` | Intended application and one authorized server. |
| `DISCORD_ALLOWED_ROLE_IDS` | JSON array of role IDs allowed to read incident status. |
| `DISCORD_BOT_TOKEN` | Used only by command registration, never injected into runtime containers. |

Install the application in the intended server with application commands enabled and assign the allowed role. Slash commands need a public HTTPS route to **`POST /discord/interactions`** and the URL configured in the Developer Portal. The default loopback API binding does not provide that route. A signed PING verifies the endpoint; expose only the required ingress, preserving the API's operator boundary.

Preview registration before explicitly applying it:

```sh
python3.12 scripts/register_discord_commands.py
python3.12 scripts/register_discord_commands.py --apply
docker compose up -d --build api discord
```

`--apply` contacts Discord and updates only the guild's `fixproof` command, not every command. The delivery service already exists in base Compose; there is no separate Discord overlay. If using kind investigation, recreate the base + kind services after configuring the webhook so both API and investigation worker can enqueue updates. Without a webhook, delivery remains idle. No successful-start log or sample output should be assumed; inspect actual service logs.

## Read commands

| Command | Retained information |
|---|---|
| `/fixproof recent` | Five latest live incident IDs, lifecycle and assessment. |
| `/fixproof incident id:<UUID>` | Incident plus latest investigation, proposal, execution and verification statuses. |
| `/fixproof evidence id:<UUID>` | Latest investigation's source names, canonical IDs, observation times and retained/gap labels. |

Ed25519 signatures bind timestamp and raw body. Requests over 8 KiB, invalid signatures and stale timestamps are rejected. Incident-data commands require matching application/guild and an allowed role; DMs/other guilds receive no incident data. Replies are ephemeral and disable mentions. Evidence replies do not send raw logs, prompts, full source bodies or model findings. Unrecognized write commands are denied.

## Event delivery

Selected committed live audit events enqueue one `discord_deliveries` row in the same transaction: report/report-added, investigation completion, proposal, approval/rejection, execution outcome/reconciliation and verification result. A rollback sends nothing. Faulting the fixture alone creates no incident/audit event, so it does not send an incident-reported card; submit a report through FixProof.

The worker leases a row, constructs a bounded card and posts with `wait=true`, storing the returned message ID. Cards include safe state/target/IDs, source categories and selected validated numeric summaries. Raw logs, report text, evidence facts, model text, credentials and full payloads are excluded. `allowed_mentions` is disabled.

Delivery retries rate limits/transient failures with bounded backoff; permanent client errors or five failed attempts terminate that delivery. A timed-out request may have posted successfully, so delivery is at least once, not exactly once. Audit-event identity allows duplicate recognition. Notification failure does not change incident/approval/execution state. Leases do not eliminate duplicates after uncertain network outcomes.

## Acceptance and limitations

The earlier integration record reports real report/investigation cards posted and read back. Its five listed sources were collection gaps caused by a target UID mismatch, not proof of healthy live telemetry. That historical observation is not re-certified against the latest merge. Registration, signed public HTTPS routing and allowed/denied-role slash-command behavior still need live team acceptance.

`apps/api/tests/test_discord_integration.py` contains transactional rollback, payload/redaction, mention suppression, retries, signature/PING, guild/role, read-command and write-denial cases. Test presence is not a current passing-suite claim. For acceptance: match the registered UID and obtain actual retained data, report through the console, inspect committed card delivery, register commands explicitly, and exercise allowed and denied roles. Keep webhook/bot tokens out of demos.
