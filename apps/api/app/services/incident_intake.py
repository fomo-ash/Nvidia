"""Manual reports for the registered kind sample workload."""

from uuid import uuid4

from fastapi import HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.core.config import settings
from app.models.domain import Incident, IncidentTrigger, InvestigationRequest, now
from app.schemas.api import ManualIncidentOut
from app.services.idempotency import digest, finish, reserve
from app.services.recommendations import audit

TARGET_ID = "local-kind/fixproof-demo/sample-api"


def report(db, payload, actor, key):
    if actor.id == "local-demo-user":
        raise HTTPException(401, "Operator session required for live incident reports")
    if not key:
        raise HTTPException(422, "Idempotency-Key required")
    if payload.target_id != TARGET_ID or settings.sample_cluster_id != "local-kind":
        raise HTTPException(404, "Target is not registered")
    if not settings.sample_target_uid:
        raise HTTPException(503, "Sample target UID is not configured")
    if payload.target_uid != settings.sample_target_uid:
        raise HTTPException(409, "Target UID changed; refresh the registered target")
    content = payload.model_dump(mode="json")
    record, replay = reserve(db, actor, key, "/incidents", content)
    if replay is not None:
        return replay
    stamp = now()
    fingerprint = digest(
        {
            "cluster": settings.sample_cluster_id,
            "uid": payload.target_uid,
            "symptom": payload.symptom,
        }
    )
    insertion = pg_insert if db.bind.dialect.name == "postgresql" else sqlite_insert
    new_id = uuid4()
    created = db.scalar(
        insertion(Incident)
        .values(
            id=new_id,
            title=payload.summary[:200],
            status="open",
            severity="high",
            summary=payload.summary,
            created_at=stamp,
            mode="live",
            target_id=TARGET_ID,
            target_uid=payload.target_uid,
            symptom=payload.symptom,
            fingerprint=fingerprint,
            lifecycle="open",
            assessment="unassessed",
            last_reported_at=stamp,
        )
        .on_conflict_do_nothing(index_elements=["fingerprint"])
        .returning(Incident.id)
    )
    incident = (
        db.get(Incident, created)
        if created
        else db.scalar(
            select(Incident).where(Incident.fingerprint == fingerprint).with_for_update()
        )
    )
    if incident is None or incident.lifecycle != "open":
        raise HTTPException(409, "Matching incident is not open")
    incident.last_reported_at = stamp
    trigger = IncidentTrigger(
        id=uuid4(),
        incident_id=incident.id,
        source="manual",
        reporter=actor.id,
        summary=payload.summary,
        note=payload.note,
        payload_hash=digest(content),
        reported_at=stamp,
    )
    db.add(trigger)
    request = InvestigationRequest(
        id=uuid4(),
        incident_id=incident.id,
        trigger_id=trigger.id,
        status="queued",
        created_at=stamp,
    )
    db.add(request)
    audit(
        db,
        "incident",
        incident.id,
        "reported" if created else "report_added",
        {
            "trigger_id": str(trigger.id),
            "investigation_request_id": str(request.id),
            "source": "manual",
            "target_uid": payload.target_uid,
        },
        actor.id,
    )
    result = ManualIncidentOut(
        incident_id=incident.id,
        trigger_id=trigger.id,
        investigation_request_id=request.id,
        target_id=TARGET_ID,
        target_uid=payload.target_uid,
        reported_at=stamp,
        reused=not bool(created),
    ).model_dump(mode="json")
    code = 200 if created is None else 201
    finish(record, result, code)
    db.commit()
    return JSONResponse(result, status_code=code)
