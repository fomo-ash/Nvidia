"""Reserve keys transactionally; a committed pending operation is never invoked again."""

import hashlib
import json
from uuid import uuid4

from fastapi import HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.models.domain import IdempotencyRecord, now


def digest(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def reserve(db, actor, key, path, payload):
    if key is None:
        return None, None
    fingerprint = digest({"path": path, "payload": payload})
    insert = pg_insert if db.bind.dialect.name == "postgresql" else sqlite_insert
    identifier = uuid4()
    created = db.scalar(
        insert(IdempotencyRecord)
        .values(
            id=identifier,
            actor=actor.id,
            key=key,
            fingerprint=fingerprint,
            status_code=202,
            response=None,
            created_at=now(),
        )
        .on_conflict_do_nothing(index_elements=["actor", "key"])
        .returning(IdempotencyRecord.id)
    )
    record = db.scalar(
        select(IdempotencyRecord)
        .where(
            IdempotencyRecord.actor == actor.id,
            IdempotencyRecord.key == key,
        )
        .with_for_update()
    )
    if created is None:
        if record.fingerprint != fingerprint:
            raise HTTPException(409, "Idempotency key already binds to a different request")
        if record.response is None:
            raise HTTPException(409, "Request is still being reserved")
        response = JSONResponse(
            record.response,
            status_code=record.status_code,
            headers={"Idempotency-Replayed": "true"},
        )
        db.commit()
        return None, response
    return record, None


def finish(record, value, status_code):
    if record is not None:
        record.response = value
        record.status_code = status_code


def perform(db, actor, key, path, payload, handler, schema, status_code=200):
    record, replay = reserve(db, actor, key, path, payload)
    if replay is not None:
        return replay
    value = schema.model_validate(handler()).model_dump(mode="json")
    finish(record, value, status_code)
    db.commit()
    return JSONResponse(value, status_code=status_code)
