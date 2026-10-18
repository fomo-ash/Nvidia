"""Approval rules live on the server. No execution adapter is exposed by this scaffold."""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.domain import AuditEvent, Incident, Recommendation
from app.services.investigations import InvestigationProvider, MockInvestigationProvider, Proposal


def audit(db: Session, entity_type: str, entity_id: UUID, action: str, details=None):
    db.add(
        AuditEvent(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            actor="local-demo-user",
            details=details or {},
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
        "expires_at": expiry.replace(tzinfo=timezone.utc).isoformat() if expiry else None,
    }
    return hashlib.sha256(
        json.dumps(content, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def investigate(
    db: Session, incident_id: UUID, provider: InvestigationProvider | None = None
) -> Recommendation:
    require_incident(db, incident_id, lock=True)
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
        audit(db, "recommendation", item.id, "superseded", {"replacement_version": version})
    proposal = Proposal.model_validate((provider or MockInvestigationProvider()).investigate())
    item = Recommendation(
        id=uuid4(),
        incident_id=incident_id,
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
    )
    db.commit()
    db.refresh(item)
    return item


def decide(db: Session, recommendation_id: UUID, status: str, expected_hash: str | None = None):
    item = db.get(Recommendation, recommendation_id)
    if item is None:
        raise HTTPException(404, "Recommendation not found")
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
        if not item.expires_at or item.expires_at.replace(tzinfo=timezone.utc) <= datetime.now(
            timezone.utc
        ):
            raise HTTPException(409, "Proposal expired; investigate again")
        if (
            not item.proposal_hash
            or expected_hash != item.proposal_hash
            or proposal_digest(item) != item.proposal_hash
        ):
            raise HTTPException(409, "Proposal content changed; investigate and review again")
        if item.action != "restart_demo_workload" or item.target != "demo/api-workers":
            raise HTTPException(409, "Unsupported demo action or target")
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
    audit(
        db,
        "recommendation",
        item.id,
        status,
        {"proposal_hash": item.proposal_hash, "version": item.version},
    )
    db.commit()
    db.refresh(item)
    return item
