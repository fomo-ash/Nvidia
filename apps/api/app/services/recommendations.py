"""Investigation persistence and server-enforced proposal review rules."""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import func, select, update
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.time import utc
from app.models.domain import (
    Approval,
    AuditEvent,
    EvidenceItem,
    Execution,
    Incident,
    Investigation,
    Recommendation,
)
from app.core.identity import Actor
from app.schemas.api import EvidenceOut
from app.services.idempotency import digest
from app.services.investigations import InvestigationProvider, MockInvestigationProvider, Proposal


def audit(
    db: Session,
    entity_type: str,
    entity_id: UUID,
    action: str,
    details=None,
    actor="local-demo-user",
):
    details = dict(details or {})
    if entity_type == "recommendation":
        item = db.get(Recommendation, entity_id)
        if item:
            details.setdefault("incident_id", str(item.incident_id))
    db.add(
        AuditEvent(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            actor=actor,
            details=details,
        )
    )


def require_incident(db: Session, incident_id: UUID, *, lock=False) -> Incident:
    query = select(Incident).where(Incident.id == incident_id)
    if lock:
        query = query.with_for_update()
    item = db.scalar(query)
    if item is None:
        raise HTTPException(404, "Incident not found")
    return item


def proposal_digest(item: Recommendation) -> str:
    # Include review evidence, target, parameters, identity, version and expiry.
    expiry = item.expires_at
    content = {
        "id": str(item.id),
        "incident_id": str(item.incident_id),
        "version": item.version,
        "action": item.action,
        "target": item.target,
        "parameters": item.parameters,
        "evidence": item.evidence,
        "expires_at": utc(expiry).isoformat() if expiry else None,
    }
    return hashlib.sha256(
        json.dumps(content, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def investigate(
    db: Session,
    incident_id: UUID,
    provider: InvestigationProvider | None = None,
    actor: Actor | None = None,
) -> Recommendation:
    actor = actor or Actor("local-demo-user", "operator")
    incident = require_incident(db, incident_id, lock=True)
    if incident.mode == "live":
        raise HTTPException(
            409,
            "Live incident evidence collection is queued; synthetic investigation is unavailable",
        )
    if db.scalar(
        select(Execution.id)
        .join(Recommendation)
        .where(Recommendation.incident_id == incident_id, Execution.status == "pending")
    ):
        raise HTTPException(409, "An execution is pending; investigation cannot supersede it")
    proposal = Proposal.model_validate((provider or MockInvestigationProvider()).investigate())
    version = (
        db.scalar(
            select(func.max(Recommendation.version)).where(
                Recommendation.incident_id == incident_id
            )
        )
        or 0
    ) + 1
    previous = db.scalars(
        select(Recommendation).where(
            Recommendation.incident_id == incident_id,
            Recommendation.status.in_(["proposed", "approved"]),
        )
    ).all()
    for item in previous:
        item.status = "superseded"
        audit(
            db, "recommendation", item.id, "superseded", {"replacement_version": version}, actor.id
        )
    investigation = Investigation(
        id=uuid4(),
        incident_id=incident_id,
        provider="mock",
        mode="synthetic",
        status="completed",
        summary=proposal.parameters.reason,
    )
    db.add(investigation)
    db.flush()
    audit(
        db,
        "investigation",
        investigation.id,
        "investigated",
        {"incident_id": str(incident_id), "provider": "mock"},
        actor.id,
    )
    for evidence in proposal.evidence:
        db.add(
            EvidenceItem(
                investigation_id=investigation.id,
                source=evidence.source,
                observed_at=evidence.observed_at,
                fact=evidence.fact,
                content_hash=digest(evidence.model_dump(mode="json")),
                trust_label="untrusted",
                mode=evidence.mode,
            )
        )
    item = Recommendation(
        id=uuid4(),
        incident_id=incident_id,
        investigation_id=investigation.id,
        version=version,
        action=proposal.action,
        target=proposal.target,
        parameters=proposal.parameters.model_dump(),
        evidence=[e.model_dump(mode="json") for e in proposal.evidence],
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=settings.proposal_ttl_seconds),
    )
    item.proposal_hash = proposal_digest(item)
    db.add(item)
    db.flush()
    audit(
        db,
        "recommendation",
        item.id,
        "proposed",
        {
            "provider": "mock",
            "incident_id": str(incident_id),
            "version": version,
            "proposal_hash": item.proposal_hash,
        },
        actor.id,
    )
    return item


def validate_current(db, item, expected_hash):
    latest = db.scalar(
        select(func.max(Recommendation.version)).where(
            Recommendation.incident_id == item.incident_id
        )
    )
    if item.version != latest:
        raise HTTPException(409, "Recommendation has been superseded")
    if not item.expires_at or utc(item.expires_at) <= datetime.now(timezone.utc):
        raise HTTPException(409, "Proposal expired; investigate again")
    if (
        not item.proposal_hash
        or expected_hash != item.proposal_hash
        or proposal_digest(item) != item.proposal_hash
    ):
        raise HTTPException(409, "Proposal content changed; investigate and review again")
    incident = db.get(Incident, item.incident_id)
    if incident is not None and incident.mode == "live":
        from app.services.live_proposals import validate_live_current

        validate_live_current(db, item)
        return
    try:
        Proposal.model_validate(
            {
                "action": item.action,
                "target": item.target,
                "parameters": item.parameters,
                "evidence": item.evidence,
            }
        )
    except ValidationError:
        raise HTTPException(
            409, "Unsupported proposal action, target, parameters or evidence"
        ) from None
    retained = db.scalars(
        select(EvidenceItem).where(EvidenceItem.investigation_id == item.investigation_id)
    ).all()
    hashes = []
    for evidence in retained:
        observed = (
            evidence.observed_at.replace(tzinfo=timezone.utc)
            if evidence.observed_at.tzinfo is None
            else evidence.observed_at.astimezone(timezone.utc)
        )
        payload = EvidenceOut(
            source=evidence.source, observed_at=observed, fact=evidence.fact, mode=evidence.mode
        ).model_dump(mode="json")
        if digest(payload) != evidence.content_hash or evidence.trust_label != "untrusted":
            raise HTTPException(409, "Retained evidence changed")
        hashes.append(evidence.content_hash)
    if not retained or sorted(hashes) != sorted(digest(e) for e in item.evidence):
        raise HTTPException(409, "Retained evidence does not match reviewed proposal")


def decide(
    db: Session,
    recommendation_id: UUID,
    status: str,
    expected_hash: str | None = None,
    actor: Actor | None = None,
):
    actor = actor or Actor("local-demo-user", "operator")
    item = db.get(Recommendation, recommendation_id)
    if item is None:
        raise HTTPException(404, "Recommendation not found")
    incident = db.get(Incident, item.incident_id)
    if incident.mode == "live" and actor.id == "local-demo-user":
        raise HTTPException(401, "Operator session required")
    require_incident(db, item.incident_id, lock=True)
    db.refresh(item)
    if item.status != "proposed":
        raise HTTPException(409, "Only proposed recommendations can be decided")
    latest = db.scalar(
        select(func.max(Recommendation.version)).where(
            Recommendation.incident_id == item.incident_id
        )
    )
    if item.version != latest:
        raise HTTPException(409, "Recommendation has been superseded")
    if status == "approved":
        validate_current(db, item, expected_hash)
    result = db.execute(
        update(Recommendation)
        .where(
            Recommendation.id == item.id,
            Recommendation.status == "proposed",
        )
        .values(status=status)
    )
    if result.rowcount != 1:
        raise HTTPException(409, "Recommendation already decided")
    approval = Approval(
        recommendation_id=item.id,
        recommendation_version=item.version,
        decision=status,
        actor=actor.id,
        proposal_hash=item.proposal_hash,
        expires_at=item.expires_at if status == "approved" else None,
    )
    db.add(approval)
    db.flush()
    audit(
        db,
        "recommendation",
        item.id,
        status,
        {
            "proposal_hash": item.proposal_hash,
            "version": item.version,
            "approval_id": str(approval.id),
        },
        actor.id,
    )
    return item
