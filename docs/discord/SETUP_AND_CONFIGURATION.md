# Discord Setup & Configuration Guide

This guide walks through configuring incoming webhooks and registering slash commands for FixProof.

---

## 1. Prerequisites

- A Discord account with administrative access to a Discord server (guild).
- A public HTTPS endpoint or tunnel (e.g. Cloudflare Tunnel, ngrok) if you plan to enable interactive slash commands locally.

---

## 2. Environment Variables

Add the following configuration to your `.env` file (never commit these secrets to version control):

```dotenv
# --- Discord Incoming Webhooks (for Channel Broadcasts) ---
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/123456789012345678/abcdefghijklmnopqrstuvwxyz0123456789-_

# --- Discord Slash Commands (for Interactive /fixproof Queries) ---
DISCORD_PUBLIC_KEY=a1b2c3d4e5f6...32_byte_hex_public_key...
DISCORD_APPLICATION_ID=123456789012345678
DISCORD_GUILD_ID=987654321098765432
DISCORD_ALLOWED_ROLE_IDS=["112233445566778899"]
DISCORD_BOT_TOKEN=MTA...bot_token_used_only_for_command_registration...
```

### Variable Details

| Variable | Description |
|---|---|
| `DISCORD_WEBHOOK_URL` | The official incoming webhook URL from your designated alert channel. |
| `DISCORD_PUBLIC_KEY` | The Ed25519 public key found in the Discord Developer Portal under **General Information**. Used to verify signatures on incoming interactions. |
| `DISCORD_APPLICATION_ID` | The Application / Client ID from the Discord Developer Portal. |
| `DISCORD_GUILD_ID` | The numeric snowflake ID of the authorized Discord server. |
| `DISCORD_ALLOWED_ROLE_IDS` | JSON array of role snowflake IDs permitted to execute `/fixproof` commands. |
| `DISCORD_BOT_TOKEN` | Bot authentication token. **Only used by the local registration script** to register slash commands. Never passed into container runtime environments. |

---

## 3. Creating the Incoming Webhook

1. Open your Discord server and navigate to the channel where you want incident alerts (e.g., `#sre-incidents`).
2. Click **Edit Channel** (gear icon) → **Integrations** → **Webhooks** → **New Webhook**.
3. Name the webhook `FixProof Alerts` and assign an avatar.
4. Click **Copy Webhook URL** and set it as `DISCORD_WEBHOOK_URL` in your `.env`.

---

## 4. Configuring the Discord Application for Slash Commands

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications).
2. Click **New Application** and name it `FixProof`.
3. In **General Information**:
   - Copy the **Application ID** → `DISCORD_APPLICATION_ID`.
   - Copy the **Public Key** → `DISCORD_PUBLIC_KEY`.
4. In **Bot**:
   - Click **Reset Token** to generate a new bot token → `DISCORD_BOT_TOKEN`.
   - Enable `application.commands` permissions.
5. In **Interactions Endpoint URL**:
   - Enter your public API route: `https://<your-domain-or-tunnel>/discord/interactions`.
   - Discord will send a signed PING request. If your API is running and `DISCORD_PUBLIC_KEY` is configured properly, Discord will accept and save the URL.

---

## 5. Registering the Slash Commands

Use the registration script in `scripts/register_discord_commands.py`:

```powershell
# Step 1: Dry run to preview the command schema
python scripts/register_discord_commands.py

# Step 2: Register the guild-scoped command in Discord
python scripts/register_discord_commands.py --apply
```

Output:
```json
{
  "guild_id": "987654321098765432",
  "command": {
    "name": "fixproof",
    "type": 1,
    "description": "Read retained FixProof incident status",
    "options": [ ... ]
  }
}
Command successfully registered for guild.
```

---

## 6. Starting the Delivery Service

In your Docker Compose stack, ensure the `discord` delivery service is enabled:

```powershell
docker compose up -d --build api discord
```

Check the logs to verify healthy connection:
```powershell
docker compose logs -f discord
```
You should see:
```text
{"event": "discord_worker_started", "mode": "active"}
```

---

## 7. Testing & Verification

1. **Trigger a Test Event**:
   Run the kind fixture fault command:
   ```powershell
   python scripts/kind_fixture.py fault
   ```
2. **Inspect Discord Channel**:
   Verify that a blue **"Incident reported"** card arrives in the configured channel displaying the affected workload and initial probe failure.
3. **Run a Slash Command**:
   In any channel in the server, type:
   ```text
   /fixproof recent
   ```
   Verify that the 5 most recent incidents are displayed in an ephemeral reply.
