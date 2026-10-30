# Discord channel updates and read-only commands

The integration is optional. No Discord credentials are committed. The API remains the sole authority for incident state, proposals, approvals, execution and verification; Discord commands cannot perform any of those writes.

## Configure

Create an incoming webhook in the intended Discord channel and a Discord application for slash commands. Put these values in ignored `.env`:

```dotenv
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/<webhook-id>/<webhook-token>
DISCORD_PUBLIC_KEY=<application-public-key-hex>
DISCORD_APPLICATION_ID=<application-id>
DISCORD_GUILD_ID=<one-authorized-server-id>
DISCORD_ALLOWED_ROLE_IDS=["<operator-role-id>"]
DISCORD_BOT_TOKEN=<token-used-only-by-registration-script>
```

The webhook URL is accepted only on `https://discord.com/api/webhooks/...`. It is passed only to API and the dedicated `discord` delivery service, and never returned to the browser or written to the database. `DISCORD_BOT_TOKEN` is read by the registration script and is **not** passed into the running containers. The commands need a public HTTPS route to the API's `POST /discord/interactions` endpoint; the default loopback Compose binding does not expose one. Configure that route in the Discord Developer Portal as the Interactions Endpoint URL. Keep the rest of the API behind the existing local or authenticated ingress. Discord verifies the URL with a signed PING.

Create or choose a channel for updates, create its incoming webhook, and install the Discord application in the intended server with application commands enabled. Assign an allowed role to the operators who should read incident status. A channel is needed for webhook updates; slash command replies are private to the caller.

Preview and then register the guild command:

```powershell
python scripts/register_discord_commands.py
python scripts/register_discord_commands.py --apply
docker compose up -d --build api discord
```

The script creates or updates only the guild's `fixproof` command. It does not overwrite other commands. No live registration or delivery was attempted in this workspace because no Discord application, webhook or role IDs are configured.

## Commands

All replies are ephemeral and disable mentions. The endpoint verifies the Ed25519 signature over the timestamp and raw body, rejects stale requests, and requires the configured application ID, guild ID and at least one allowed member role. DMs and other guilds get no incident data.

| Command | Stored data returned |
|---|---|
| `/fixproof recent` | Five latest live incident IDs, lifecycle states and assessments. |
| `/fixproof incident id:<UUID>` | One live incident's lifecycle, latest investigation, proposal, execution and recovery-verification statuses. |
| `/fixproof evidence id:<UUID>` | Latest investigation's evidence source names, IDs, observation times and gap/retained labels. Raw evidence, logs, prompts and model text are not sent. |

Unknown commands, including any approval or execution command, are rejected. The command endpoint does not use an AI answer or trigger fresh collection.

## Channel updates and delivery

Selected live audit transitions create a `discord_deliveries` row in the same database transaction: report, investigation completion, proposal, approval/rejection, execution outcome and recovery verdict. A separate worker sends only fixed state/ID text after the transaction commits. An application rollback sends nothing. Delivery never changes incident or approval state. The worker requests `wait=true`, records the Discord message ID, and disables all mentions. HTTP 429 and transient errors have bounded retries; permanent HTTP 4xx and five failed attempts stop. A timed-out post may have succeeded, so delivery is at least once and the audit event ID is included for duplicate recognition.

If the webhook URL is unset, no notifications are queued and the delivery service stays idle. Previously queued records remain in the database if the service is temporarily stopped. `discord_deliveries` is introduced by migration `0007_discord_deliveries`.

## Verification

`apps/api/tests/test_discord_integration.py` covers transaction rollback, one delivered message, disabled mentions, rate-limit retry, signed PING, invalid/stale signatures, guild and role denial, all three read commands and rejection of an action command. The local API suite passed with 106 tests and 8 skips; the isolated PostgreSQL suite passed with 110 tests. A real Discord smoke test still needs the team's webhook, app key, IDs and public HTTPS endpoint:

1. Save the public interactions endpoint in the Discord Developer Portal. Discord's signed PING must succeed.
2. Run the registration script with `--apply`; confirm `/fixproof recent`, `/fixproof incident` and `/fixproof evidence` appear in the intended server.
3. Trigger a live incident transition and confirm one ID/status update in the chosen channel. Use an audit event ID to recognize a retry duplicate if one occurs.
4. Run the read commands as a member with an allowed role, then confirm a member without that role receives no incident data.

Discord's [Interactions overview](https://docs.discord.com/developers/interactions/overview) specifies signed requests and PING validation; its [interaction response reference](https://docs.discord.com/developers/interactions/receiving-and-responding) defines ephemeral responses and the initial response deadline. The [webhook reference](https://docs.discord.com/developers/resources/webhook) defines `wait=true` and `allowed_mentions`.
