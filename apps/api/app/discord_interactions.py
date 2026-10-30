"""Signed, guild/role-scoped Discord slash commands over retained read-only state."""

from datetime import datetime, timezone
import json
import re
from uuid import UUID

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_session
from app.models.domain import (
    EvidenceItem,
    Execution,
    Incident,
    Investigation,
    Recommendation,
    VerificationResult,
)

router = APIRouter()


def verify_request(body: bytes, signature: str, timestamp: str) -> None:
    if not settings.discord_public_key or len(body) > 8192:
        raise HTTPException(401, "Discord interaction signature required")
    if not re.fullmatch(r"[0-9]{1,12}", timestamp) or not re.fullmatch(
        r"[0-9a-fA-F]{128}", signature
    ):
        raise HTTPException(401, "Invalid Discord interaction signature")
    if abs(datetime.now(timezone.utc).timestamp() - int(timestamp)) > 300:
        raise HTTPException(401, "Stale Discord interaction")
    try:
        public = Ed25519PublicKey.from_public_bytes(bytes.fromhex(settings.discord_public_key))
        public.verify(bytes.fromhex(signature), timestamp.encode() + body)
    except (InvalidSignature, ValueError):
        raise HTTPException(401, "Invalid Discord interaction signature") from None


def reply(content: str) -> dict:
    return {
        "type": 4,
        "data": {"content": content[:1900], "flags": 64, "allowed_mentions": {"parse": []}},
    }


def lookup_id(options) -> UUID | None:
    if not isinstance(options, list) or len(options) != 1:
        return None
    option = options[0]
    if not isinstance(option, dict) or option.get("name") != "id" or option.get("type") != 3:
        return None
    try:
        return UUID(option["value"])
    except (KeyError, TypeError, ValueError, AttributeError):
        return None


def run_command(db: Session, data: dict) -> str:
    if (
        data.get("name") != "fixproof"
        or not isinstance(data.get("options"), list)
        or len(data["options"]) != 1
    ):
        return "Unknown read-only FixProof command."
    command = data["options"][0]
    if not isinstance(command, dict) or command.get("type") != 1:
        return "Unknown read-only FixProof command."
    name = command.get("name")
    if name == "recent" and not command.get("options"):
        rows = db.scalars(
            select(Incident)
            .where(Incident.mode == "live")
            .order_by(Incident.created_at.desc(), Incident.id.desc())
            .limit(5)
        ).all()
        if not rows:
            return "No live incidents are retained."
        return "Recent live incidents:\n" + "\n".join(
            f"{item.id} | {item.lifecycle or item.status} | {item.assessment or 'unassessed'}"
            for item in rows
        )
    if name not in {"incident", "evidence"}:
        return "Unknown read-only FixProof command."
    incident_id = lookup_id(command.get("options"))
    if incident_id is None:
        return "Provide a valid incident UUID for this read-only command."
    incident = db.get(Incident, incident_id)
    if incident is None or incident.mode != "live":
        return "Live incident not found."
    latest = db.scalar(
        select(Investigation)
        .where(Investigation.incident_id == incident.id)
        .order_by(Investigation.created_at.desc(), Investigation.id.desc())
        .limit(1)
    )
    if name == "evidence":
        if latest is None:
            return f"Incident {incident.id}: no investigation is retained yet."
        rows = db.scalars(
            select(EvidenceItem)
            .where(EvidenceItem.investigation_id == latest.id)
            .order_by(EvidenceItem.source)
            .limit(10)
        ).all()
        if not rows:
            return f"Incident {incident.id}: no evidence is retained yet."
        return (
            f"Incident {incident.id} | investigation {latest.id} | {latest.status}\n"
            + "\n".join(
                f"{item.source}: {'gap' if item.collection_error else 'retained'} | {item.id} | {item.observed_at.isoformat()}"
                for item in rows
            )
        )
    proposal = db.scalar(
        select(Recommendation)
        .where(Recommendation.incident_id == incident.id)
        .order_by(Recommendation.created_at.desc(), Recommendation.id.desc())
        .limit(1)
    )
    lines = [
        f"Incident {incident.id}",
        f"Lifecycle: {incident.lifecycle or incident.status}; assessment: {incident.assessment or 'unassessed'}",
        f"Investigation: {latest.status if latest else 'none'}",
        f"Proposal: {proposal.status if proposal else 'none'}",
    ]
    if proposal:
        execution = db.scalar(select(Execution).where(Execution.recommendation_id == proposal.id))
        lines.append(f"Execution: {execution.status if execution else 'none'}")
        if execution:
            verdict = db.scalar(
                select(VerificationResult).where(VerificationResult.execution_id == execution.id)
            )
            lines.append(f"Recovery verification: {verdict.status if verdict else 'none'}")
    return "\n".join(lines)


@router.post("/discord/interactions", include_in_schema=False)
async def interactions(request: Request, db: Session = Depends(get_session)):
    body = await request.body()
    verify_request(
        body,
        request.headers.get("X-Signature-Ed25519", ""),
        request.headers.get("X-Signature-Timestamp", ""),
    )
    try:
        payload = json.loads(body)
    except (ValueError, TypeError):
        raise HTTPException(400, "Invalid Discord interaction") from None
    if not isinstance(payload, dict):
        raise HTTPException(400, "Invalid Discord interaction")
    if payload.get("type") == 1:
        return {"type": 1}
    if payload.get("type") != 2:
        return reply("Only read-only slash commands are supported.")
    if (
        not settings.discord_application_id
        or not settings.discord_guild_id
        or not settings.discord_allowed_role_ids
        or payload.get("application_id") != settings.discord_application_id
        or payload.get("guild_id") != settings.discord_guild_id
    ):
        return reply("This FixProof command is unavailable in this server.")
    member = payload.get("member")
    roles = member.get("roles", []) if isinstance(member, dict) else []
    if not isinstance(roles, list) or not set(roles).intersection(
        settings.discord_allowed_role_ids
    ):
        return reply("You are not authorized to read FixProof incidents.")
    data = payload.get("data")
    if not isinstance(data, dict):
        return reply("Invalid read-only command.")
    return reply(run_command(db, data))
