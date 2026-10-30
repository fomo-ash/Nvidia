"""Register one guild-scoped read-only /fixproof command; no other commands are replaced."""

import argparse
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
COMMAND = {
    "name": "fixproof",
    "type": 1,
    "description": "Read retained FixProof incident status",
    "options": [
        {"name": "recent", "description": "Show five recent live incidents", "type": 1},
        {
            "name": "incident",
            "description": "Show one incident's lifecycle and recovery status",
            "type": 1,
            "options": [
                {"name": "id", "description": "Incident UUID", "type": 3, "required": True}
            ],
        },
        {
            "name": "evidence",
            "description": "Show retained evidence sources for one incident",
            "type": 1,
            "options": [
                {"name": "id", "description": "Incident UUID", "type": 3, "required": True}
            ],
        },
    ],
}


def values():
    result = {}
    path = ROOT / ".env"
    if path.exists():
        for name, value in re.findall(r"^([A-Z][A-Z0-9_]*)=(.*)$", path.read_text(), re.M):
            result[name] = value
    result.update(
        {name: value for name, value in os.environ.items() if name.startswith("DISCORD_")}
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="create or update the guild command")
    args = parser.parse_args()
    config = values()
    app_id, guild_id = config.get("DISCORD_APPLICATION_ID", ""), config.get("DISCORD_GUILD_ID", "")
    if not re.fullmatch(r"[0-9]{5,25}", app_id) or not re.fullmatch(r"[0-9]{5,25}", guild_id):
        raise SystemExit("Set DISCORD_APPLICATION_ID and DISCORD_GUILD_ID to Discord snowflakes")
    print(json.dumps({"guild_id": guild_id, "command": COMMAND}, indent=2))
    if not args.apply:
        print("Dry run only; pass --apply to register this command.")
        return
    token = config.get("DISCORD_BOT_TOKEN", "")
    if not token:
        raise SystemExit("Set DISCORD_BOT_TOKEN in ignored .env to register commands")
    url = f"https://discord.com/api/v10/applications/{app_id}/guilds/{guild_id}/commands"
    request = urllib.request.Request(
        url,
        data=json.dumps(COMMAND).encode(),
        method="POST",
        headers={
            "Authorization": "Bot " + token,
            "Content-Type": "application/json",
            "User-Agent": "FixProof/0.1",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            result = json.load(response)
    except urllib.error.HTTPError as error:
        raise SystemExit(f"Discord command registration failed (HTTP {error.code})") from None
    print(json.dumps({"registered_command_id": result.get("id"), "name": result.get("name")}))


if __name__ == "__main__":
    main()
