# Discord channel updates and read-only commands

> [!NOTE]
> Detailed technical guides and sub-specifications are organized in the [`docs/discord/`](discord/README.md) directory:
> - [Architecture & Security Overview](discord/README.md)
> - [Webhooks & Alert Pipeline](discord/WEBHOOKS_AND_ALERTS.md)
> - [Slash Commands Reference](discord/SLASH_COMMANDS.md)
> - [Step-by-Step Setup Guide](discord/SETUP_AND_CONFIGURATION.md)

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

The webhook URL is accepted only on `https://discord.com/api/webhooks/...`. It is passed to API, the kind investigation worker (so it can queue investigation completion updates), and the dedicated `discord` delivery service. It is never returned to the browser or written to the database. `DISCORD_BOT_TOKEN` is read by the registration script and is **not** passed into the running containers. The commands need a public HTTPS route to the API's `POST /discord/interactions` endpoint; the default loopback Compose binding does not expose one. Configure that route in the Discord Developer Portal as the Interactions Endpoint URL. Keep the rest of the API behind the existing local or authenticated ingress. Discord verifies the URL with a signed PING.

Create or choose a channel for updates, create its incoming webhook, and install the Discord application in the intended server with application commands enabled. Assign an allowed role to the operators who should read incident status. A channel is needed for webhook updates; slash command replies are private to the caller.

Preview and then register the guild command:

```powershell
python scripts/register_discord_commands.py
python scripts/register_discord_commands.py --apply
docker compose up -d --build api discord
```

The script creates or updates only the guild's `fixproof` command. It does not overwrite other commands. The incoming webhook was verified locally on 2026-10-30. Slash command registration remains untested because application and role settings are not configured.

## Commands

All replies are ephemeral and disable mentions. The endpoint verifies the Ed25519 signature over the timestamp and raw body, rejects stale requests, and requires the configured application ID, guild ID and at least one allowed member role. DMs and other guilds get no incident data.

| Command | Stored data returned |
|---|---|
| `/fixproof recent` | Five latest live incident IDs, lifecycle states and assessments. |
| `/fixproof incident id:<UUID>` | One live incident's lifecycle, latest investigation, proposal, execution and recovery-verification statuses. |
| `/fixproof evidence id:<UUID>` | Latest investigation's evidence source names, IDs, observation times and gap/retained labels. Raw evidence, logs, prompts and model text are not sent. |

Unknown commands, including any approval or execution command, are rejected. The command endpoint does not use an AI answer or trigger fresh collection.

## Channel updates and delivery

Selected live audit transitions create a `discord_deliveries` row in the same database transaction: report, investigation completion, proposal, approval/rejection, execution outcome and recovery verdict. A separate worker sends a colored card after the transaction commits. It shows the transition, incident and current state, target, latest investigation, evidence source names and IDs, observation times, safe numeric summaries, proposal, execution and verification when available. For example, the card can show 5xx request counts, ready replica counts, warning event counts, flagged log-line counts and probe status. Raw logs, evidence facts, free-text reports, model summaries and unfiltered source data are never posted. The initial report card says collection is queued; a later investigation card includes retained evidence. An application rollback sends nothing. Delivery never changes incident or approval state. The worker requests `wait=true`, records the Discord message ID, and disables all mentions. HTTP 429 and transient errors have bounded retries; permanent HTTP 4xx and five failed attempts stop. A timed-out post may have succeeded, so delivery is at least once and the audit event ID is included for duplicate recognition.

If the webhook URL is unset, no notifications are queued and the delivery service stays idle. Previously queued records remain in the database if the service is temporarily stopped. `discord_deliveries` is introduced by migration `0007_discord_deliveries`.

## Verification

`apps/api/tests/test_discord_integration.py` covers transaction rollback, one delivered message, the rich card and evidence summary, disabled mentions, rate-limit retry, signed PING, invalid/stale signatures, guild and role denial, all three read commands and rejection of an action command. The full local API suite passed with 107 tests and 8 skips. Live report and investigation cards were posted and read back from Discord; the investigation card listed five evidence sources. All five were collection gaps in this local fixture because its registered Deployment UID differs from the current kind Deployment UID. Numeric summaries were verified with retained evidence in the automated test and will appear in Discord once the local target registration is corrected and collection succeeds. Slash commands still need the team's application key, IDs and public HTTPS endpoint:

1. Save the public interactions endpoint in the Discord Developer Portal. Discord's signed PING must succeed.
2. Run the registration script with `--apply`; confirm `/fixproof recent`, `/fixproof incident` and `/fixproof evidence` appear in the intended server.
3. Trigger a live incident transition and confirm the colored status card in the chosen channel. When collection finishes, confirm the evidence section appears in the investigation update. Use an audit event ID to recognize a retry duplicate if one occurs.
4. Run the read commands as a member with an allowed role, then confirm a member without that role receives no incident data.

Discord's [Interactions overview](https://docs.discord.com/developers/interactions/overview) specifies signed requests and PING validation; its [interaction response reference](https://docs.discord.com/developers/interactions/receiving-and-responding) defines ephemeral responses and the initial response deadline. The [webhook reference](https://docs.discord.com/developers/resources/webhook) defines `wait=true` and `allowed_mentions`.
