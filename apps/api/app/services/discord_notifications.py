"""Optional committed-audit-event channel updates with a bounded delivery worker."""

from datetime import timedelta, timezone
import json
import math
import re
import urllib.error
import urllib.parse
import urllib.request
from uuid import UUID

from sqlalchemy import or_, select

from app.core.config import settings
from app.models.domain import (
    AuditEvent,
    DiscordDelivery,
    EvidenceItem,
    Execution,
    Incident,
    Investigation,
    Recommendation,
    VerificationResult,
    now,
)
from app.services.live_evidence import TOOLS

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

COLORS = {
    "reported": 0x3498DB,
    "report_added": 0x3498DB,
    "investigation_finished": 0x16A085,
    "proposed": 0xF1C40F,
    "approved": 0x2ECC71,
    "rejected": 0xE74C3C,
    "execution_succeeded": 0x2ECC71,
    "execution_failed": 0xE74C3C,
    "execution_outcome_unknown": 0xE67E22,
    "execution_reconciled": 0x16A085,
    "verification_passed": 0x2ECC71,
    "verification_failed": 0xE74C3C,
    "verification_inconclusive": 0xE67E22,
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


def safe(value: object, *, limit: int = 80) -> str:
    text = str(value or "")
    return text[:limit] if re.fullmatch(r"[A-Za-z0-9_:/.-]{1,80}", text) else "unknown"


def field(name: str, value: str, *, inline: bool = False) -> dict:
    return {"name": name, "value": value[:1024], "inline": inline}


def count(data: dict, key: str) -> int | None:
    value = data.get(key)
    return value if type(value) is int and 0 <= value <= 1_000_000_000 else None


def evidence_summary(item: EvidenceItem) -> str:
    if item.collection_error or not isinstance(item.raw_data, dict):
        return "Source unavailable" if item.collection_error else "Observation retained"
    data = item.raw_data
    if item.source == "prometheus":
        total, errors = count(data, "total_requests"), count(data, "error_requests_5xx")
        if total is not None and errors is not None and errors <= total:
            return (
                f"{errors}/{total} HTTP 5xx ({errors / total:.1%})"
                if total
                else "No requests observed"
            )
    elif item.source == "kubernetes:deployment":
        ready, desired = count(data, "replicas_ready"), count(data, "replicas_desired")
        if ready is not None and desired is not None:
            return f"{ready}/{desired} replicas ready"
    elif item.source == "kubernetes:events":
        warnings = count(data, "warning_count")
        if warnings is not None:
            return f"{warnings} warning events"
    elif item.source == "kubernetes:logs":
        lines, errors = count(data, "line_count"), count(data, "error_line_count")
        if lines is not None and errors is not None and errors <= lines:
            return f"{errors}/{lines} lines flagged"
    elif item.source == "direct:probe":
        status = count(data, "status_code")
        if status is not None and status <= 599:
            return f"HTTP {status} functional probe"
    return "Observation retained"


def notification(db, event: AuditEvent) -> dict:
    incident_id = (
        event.entity_id if event.entity_type == "incident" else event.details.get("incident_id")
    )
    incident = db.get(Incident, UUID(str(incident_id)))
    if incident is None:
        raise DeliveryError("MissingIncident", retryable=False)
    investigation = db.scalar(
        select(Investigation)
        .where(Investigation.incident_id == incident.id)
        .order_by(Investigation.created_at.desc(), Investigation.id.desc())
        .limit(1)
    )
    evidence = (
        db.scalars(
            select(EvidenceItem)
            .where(EvidenceItem.investigation_id == investigation.id)
            .order_by(EvidenceItem.source, EvidenceItem.id)
            .limit(10)
        ).all()
        if investigation
        else []
    )
    proposal = db.scalar(
        select(Recommendation)
        .where(Recommendation.incident_id == incident.id)
        .order_by(Recommendation.created_at.desc(), Recommendation.id.desc())
        .limit(1)
    )
    execution = (
        db.scalar(select(Execution).where(Execution.recommendation_id == proposal.id))
        if proposal
        else None
    )
    verification = (
        db.scalar(select(VerificationResult).where(VerificationResult.execution_id == execution.id))
        if execution
        else None
    )
    rows = [
        field("Incident", f"`{incident.id}`"),
        field(
            "Current state",
            f"Lifecycle **{safe(incident.lifecycle or incident.status)}** · "
            f"assessment **{safe(incident.assessment or 'unassessed')}** · "
            f"severity **{safe(incident.severity)}**",
        ),
        field(
            "Target",
            f"{safe(incident.target_id or 'unknown')} · symptom {safe(incident.symptom or 'unknown')}",
        ),
    ]
    if investigation:
        rows.append(
            field(
                "Investigation",
                f"**{safe(investigation.status)}** · `{investigation.id}`",
            )
        )
        evidence_lines = [
            f"• **{item.source if item.source in TOOLS else 'other'}** · "
            f"{'gap' if item.collection_error else 'retained'} · "
            f"{evidence_summary(item)} · "
            f"{item.observed_at:%Y-%m-%d %H:%M} UTC · `{item.id}`"
            for item in evidence
        ]
        rows.append(
            field(
                f"Evidence sources ({len(evidence)})",
                "\n".join(evidence_lines)
                if evidence_lines
                else "No evidence retained for this investigation.",
            )
        )
    else:
        rows.append(field("Evidence", "Collection queued; evidence will appear in a later update."))
    if proposal:
        rows.append(
            field(
                "Restore proposal",
                f"Version {proposal.version} · **{safe(proposal.status)}** · "
                f"action {safe(proposal.action)} · `{proposal.id}`",
            )
        )
    if execution:
        rows.append(field("Execution", f"**{safe(execution.status)}** · `{execution.id}`"))
    if verification:
        rows.append(
            field("Recovery verification", f"**{safe(verification.status)}** · `{verification.id}`")
        )
    stamp = event.created_at
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return {
        "content": f"FixProof · {EVENTS[event.action]}",
        "embeds": [
            {
                "title": EVENTS[event.action],
                "description": "Live incident update · current retained state",
                "color": COLORS[event.action],
                "fields": rows,
                "footer": {"text": f"Audit event {event.id} · evidence metadata only"},
                "timestamp": stamp.isoformat(),
            }
        ],
        "allowed_mentions": {"parse": []},
    }


class DeliveryError(Exception):
    def __init__(self, kind: str, *, retryable: bool, retry_after: float = 0):
        self.kind = kind
        self.retryable = retryable
        self.retry_after = retry_after
        super().__init__(kind)


def send(payload: dict, url: str) -> str:
    url = webhook_url(url)
    body = json.dumps(payload, separators=(",", ":")).encode()
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
        try:
            payload = notification(db, event)
        except DeliveryError as error:
            row.status, row.error_kind = "failed", error.kind
            db.commit()
            return None
        result = (row.audit_event_id, row.attempts, payload)
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
    event_id, attempt, payload = item
    try:
        message_id = send(payload, url)
    except DeliveryError as error:
        finish(factory, event_id, attempt, error=error)
    else:
        finish(factory, event_id, attempt, message_id=message_id)
    return True
