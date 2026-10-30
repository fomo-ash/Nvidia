"""Discord notifications stay outside core transactions; commands only read retained state."""

from datetime import datetime, timedelta, timezone
from io import BytesIO
import json
from uuid import uuid4
import urllib.error

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import pytest
from sqlalchemy import select

from app.core.config import settings
from app.models.domain import DiscordDelivery, EvidenceItem, Incident, Investigation
from app.services.discord_notifications import deliver_once, webhook_url
from app.services.recommendations import audit

WEBHOOK = "https://discord.com/api/webhooks/1234567890/" + "a" * 40


@pytest.mark.parametrize(
    "url",
    [
        "http://discord.com/api/webhooks/1234567890/" + "a" * 40,
        "https://discord.com.evil.example/api/webhooks/1234567890/" + "a" * 40,
        "https://discord.com@evil.example/api/webhooks/1234567890/" + "a" * 40,
        "https://discord.com/api/webhooks/1234567890/" + "a" * 40 + "?wait=false",
    ],
)
def test_webhook_url_rejects_non_discord_destinations(url):
    with pytest.raises(ValueError):
        webhook_url(url)
    assert webhook_url(WEBHOOK) == WEBHOOK


def live_incident(db):
    item = Incident(
        id=uuid4(),
        title="Test",
        summary="Private raw summary",
        severity="high",
        status="open",
        mode="live",
        lifecycle="open",
        assessment="active",
    )
    db.add(item)
    db.flush()
    return item


def test_committed_live_events_deliver_once_without_mentions(database, monkeypatch):
    factory, _, _ = database
    monkeypatch.setattr(settings, "discord_webhook_url", WEBHOOK)
    with factory() as db:
        incident = live_incident(db)
        audit(db, "incident", incident.id, "reported", {"assessment": "unassessed"}, "operator")
        assert db.scalar(select(DiscordDelivery)) is not None
        db.rollback()
    with factory() as db:
        assert db.scalar(select(DiscordDelivery)) is None
        incident = live_incident(db)
        audit(db, "incident", incident.id, "reported", {"assessment": "unassessed"}, "operator")
        db.commit()

    sent = []

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def read(self, _limit):
            return b'{"id":"123456789012345678"}'

    def urlopen(request, timeout):
        sent.append((request.full_url, json.loads(request.data), timeout))
        return Response()

    monkeypatch.setattr("app.services.discord_notifications.urllib.request.urlopen", urlopen)
    assert deliver_once(factory, WEBHOOK) is True
    assert deliver_once(factory, WEBHOOK) is False
    assert len(sent) == 1 and sent[0][0].endswith("?wait=true")
    assert sent[0][1]["allowed_mentions"] == {"parse": []}
    assert "Private raw summary" not in sent[0][1]["content"]
    with factory() as db:
        row = db.scalar(select(DiscordDelivery))
        assert row.status == "delivered" and row.message_id == "123456789012345678"


def test_rate_limit_retries_without_changing_incident(database, monkeypatch):
    factory, _, _ = database
    monkeypatch.setattr(settings, "discord_webhook_url", WEBHOOK)
    with factory() as db:
        incident = live_incident(db)
        incident_id = incident.id
        audit(db, "incident", incident.id, "reported", {}, "operator")
        db.commit()

    def limited(request, timeout):
        raise urllib.error.HTTPError(
            request.full_url, 429, "Rate limited", {}, BytesIO(b'{"retry_after":2}')
        )

    monkeypatch.setattr("app.services.discord_notifications.urllib.request.urlopen", limited)
    assert deliver_once(factory, WEBHOOK) is True
    with factory() as db:
        row = db.scalar(select(DiscordDelivery))
        assert row.status == "queued" and row.attempts == 1 and row.error_kind == "RateLimited"
        assert db.get(Incident, incident_id).assessment == "active"


def test_signed_read_only_commands_and_denials(client, database, monkeypatch):
    factory, _, _ = database
    private = Ed25519PrivateKey.generate()
    monkeypatch.setattr(
        settings, "discord_public_key", private.public_key().public_bytes_raw().hex()
    )
    monkeypatch.setattr(settings, "discord_application_id", "111111111111111111")
    monkeypatch.setattr(settings, "discord_guild_id", "222222222222222222")
    monkeypatch.setattr(settings, "discord_allowed_role_ids", ["333333333333333333"])
    with factory() as db:
        incident = live_incident(db)
        incident_id = incident.id
        run = Investigation(
            id=uuid4(),
            incident_id=incident.id,
            provider="mcp",
            mode="live",
            status="completed",
            summary="Private model summary",
            result={},
        )
        db.add(run)
        db.flush()
        db.add(
            EvidenceItem(
                id=uuid4(),
                investigation_id=run.id,
                source="prometheus",
                observed_at=datetime.now(timezone.utc),
                fact="Private metric fact",
                content_hash="a" * 64,
                trust_label="untrusted",
                mode="live",
                raw_data={},
                redacted=True,
            )
        )
        db.commit()

    def call(data, *, timestamp=None, tamper=False):
        body = json.dumps(data, separators=(",", ":")).encode()
        stamp = str(timestamp or int(datetime.now(timezone.utc).timestamp()))
        signature = private.sign(stamp.encode() + body).hex()
        if tamper:
            signature = "0" * 128
        return client.post(
            "/discord/interactions",
            content=body,
            headers={
                "X-Signature-Ed25519": signature,
                "X-Signature-Timestamp": stamp,
                "Content-Type": "application/json",
            },
        )

    assert call({"type": 1}).json() == {"type": 1}
    assert call({"type": 1}, tamper=True).status_code == 401
    old = int((datetime.now(timezone.utc) - timedelta(minutes=6)).timestamp())
    assert call({"type": 1}, timestamp=old).status_code == 401
    base = {
        "type": 2,
        "application_id": settings.discord_application_id,
        "guild_id": settings.discord_guild_id,
        "member": {"roles": settings.discord_allowed_role_ids},
    }
    recent = call(
        {**base, "data": {"name": "fixproof", "options": [{"type": 1, "name": "recent"}]}}
    )
    assert recent.status_code == 200 and str(incident_id) in recent.json()["data"]["content"]
    assert recent.json()["data"]["flags"] == 64
    assert recent.json()["data"]["allowed_mentions"] == {"parse": []}

    def command(name):
        return {
            **base,
            "data": {
                "name": "fixproof",
                "options": [
                    {
                        "type": 1,
                        "name": name,
                        "options": [{"type": 3, "name": "id", "value": str(incident_id)}],
                    }
                ],
            },
        }

    status = call(command("incident")).json()["data"]["content"]
    assert "assessment: active" in status and "Private" not in status
    evidence = call(command("evidence")).json()["data"]["content"]
    assert "prometheus: retained" in evidence and "Private" not in evidence
    assert (
        "not authorized"
        in call({**command("incident"), "member": {"roles": []}}).json()["data"]["content"]
    )
    assert (
        "unavailable"
        in call({**command("incident"), "guild_id": "other"}).json()["data"]["content"]
    )
    assert "Unknown read-only" in call(command("approve")).json()["data"]["content"]
