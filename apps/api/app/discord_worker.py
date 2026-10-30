"""Deliver committed Discord updates; never influences incident or approval state."""

import json
import time

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.discord_notifications import deliver_once, webhook_url


def main():
    if not settings.discord_webhook_url:
        print(json.dumps({"event": "discord_notifications_disabled"}), flush=True)
        while True:
            time.sleep(60)
    webhook_url(settings.discord_webhook_url)
    while True:
        try:
            if not deliver_once(SessionLocal, settings.discord_webhook_url):
                time.sleep(2)
        except Exception as error:
            # Never log the webhook URL, message body or exception string.
            print(
                json.dumps({"event": "discord_worker_error", "kind": type(error).__name__}),
                flush=True,
            )
            time.sleep(2)


if __name__ == "__main__":
    main()
