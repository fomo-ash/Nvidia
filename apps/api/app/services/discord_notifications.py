"""Optional committed-audit-event channel updates with a bounded delivery worker."""

from datetime import timedelta
import json
import math
import re
import urllib.error
import urllib.parse
import urllib.request
from uuid import UUID

from sqlalchemy import or_, select

from app.core.config import settings
from app.models.domain import AuditEvent, DiscordDelivery, Incident, now

EVENTS = {
    "reported": "Incident reported",
    "report_added": "Incident report added",
    "investigation_finished": "Investigation finished",
    "proposed": "Restore proposed",
    "approved": "Restore approved",
    "rejected": "Restore rejected",
    "execution_succeeded": "Restore patch succeeded; recovery unverified",
    "execution_failed": "Restore patch failed",
    "execution_outcome_unknown": "Restore outcome unknown; reconciliation required",
    "execution_reconciled": "Restore outcome reconciled",
    "verification_passed": "Recovery verified by fresh measurements",
    "verification_failed": "Recovery verification failed",
    "verification_inconclusive": "Recovery verification inconclusive",
}


def webhook_url(value: str) -> str:
    parsed = urllib.parse.urlsplit(value)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "discord.com"
        or parsed.port is not None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or not re.fullmatch(r"/api/webhooks/[0-9]{5,25}/[A-Za-z0-9_-]{20,}", parsed.path)
    ):
        raise ValueError("Discord webhook URL must be an official incoming webhook")
    return value


def enqueue(db, event: AuditEvent) -> None:
    if not settings.discord_webhook_url or event.action not in EVENTS:
        return
    incident_id = (
        event.entity_id if event.entity_type == "incident" else event.details.get("incident_id")
    )
    try:
        incident = db.get(Incident, UUID(str(incident_id)))
    except (TypeError, ValueError):
        return
    if incident is not None and incident.mode == "live":
        db.add(
            DiscordDelivery(
                audit_event_id=event.id,
                status="queued",
                attempts=0,
                available_at=now(),
                created_at=now(),
            )
        )


def content(event: AuditEvent) -> str:
    fields = [
        EVENTS[event.action],
        f"incident {event.entity_id if event.entity_type == 'incident' else event.details['incident_id']}",
    ]
    if event.entity_type != "incident":
        fields.append(f"{event.entity_type} {event.entity_id}")
    for key in ("status", "assessment", "version"):
        value = event.details.get(key)
        if isinstance(value, (str, int)) and re.fullmatch(r"[A-Za-z0-9_-]{1,40}", str(value)):
            fields.append(f"{key} {value}")
    fields.append(f"event {event.id}")
    return " | ".join(fields)[:1800]


class DeliveryError(Exception):
    def __init__(self, kind: str, *, retryable: bool, retry_after: float = 0):
        self.kind = kind
        self.retryable = retryable
        self.retry_after = retry_after
        super().__init__(kind)


def send(event: AuditEvent, url: str) -> str:
    url = webhook_url(url)
    body = json.dumps(
        {"content": content(event), "allowed_mentions": {"parse": []}}, separators=(",", ":")
    ).encode()
    request = urllib.request.Request(
        url + "?wait=true",
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": "FixProof/0.1"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            if response.status != 200:
                raise DeliveryError("UnexpectedStatus", retryable=response.status >= 500)
            result = json.loads(response.read(8193))
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            try:
                retry_after = float(json.loads(exc.read(1024)).get("retry_after", 1))
            except (ValueError, TypeError, json.JSONDecodeError):
                retry_after = 1
            if not math.isfinite(retry_after):
                retry_after = 1
            raise DeliveryError(
                "RateLimited", retryable=True, retry_after=max(1, min(retry_after, 300))
            ) from None
        raise DeliveryError(f"HTTP{exc.code}", retryable=exc.code >= 500) from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise DeliveryError("TransportError", retryable=True) from None
    except (ValueError, TypeError, json.JSONDecodeError):
        raise DeliveryError("InvalidResponse", retryable=True) from None
    message_id = result.get("id") if isinstance(result, dict) else None
    if not isinstance(message_id, str) or not re.fullmatch(r"[0-9]{5,25}", message_id):
        raise DeliveryError("MissingMessageId", retryable=True)
    return message_id


def claim(factory):
    stamp = now()
    with factory() as db:
        row = db.scalar(
            select(DiscordDelivery)
            .where(
                or_(
                    (DiscordDelivery.status == "queued") & (DiscordDelivery.available_at <= stamp),
                    (DiscordDelivery.status == "leased")
                    & (DiscordDelivery.claimed_at < stamp - timedelta(seconds=60)),
                )
            )
            .order_by(DiscordDelivery.available_at, DiscordDelivery.audit_event_id)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if row is None:
            return None
        row.status, row.attempts, row.claimed_at = "leased", row.attempts + 1, stamp
        event = db.get(AuditEvent, row.audit_event_id)
        if event is None:
            row.status, row.error_kind = "failed", "MissingAuditEvent"
            db.commit()
            return None
        db.expunge(event)
        result = (row.audit_event_id, row.attempts, event)
        db.commit()
        return result


def finish(factory, event_id, attempt, message_id=None, error: DeliveryError | None = None):
    with factory() as db:
        row = db.get(DiscordDelivery, event_id, with_for_update=True)
        if row is None or row.status != "leased" or row.attempts != attempt:
            return
        if message_id:
            row.status, row.message_id, row.error_kind = "delivered", message_id, None
        elif error:
            row.error_kind = error.kind
            if not error.retryable or attempt >= 5:
                row.status = "failed"
            else:
                row.status = "queued"
                row.available_at = now() + timedelta(
                    seconds=max(error.retry_after, min(2**attempt, 300))
                )
        db.commit()


def deliver_once(factory, url):
    item = claim(factory)
    if item is None:
        return False
    event_id, attempt, event = item
    try:
        message_id = send(event, url)
    except DeliveryError as error:
        finish(factory, event_id, attempt, error=error)
    else:
        finish(factory, event_id, attempt, message_id=message_id)
    return True
