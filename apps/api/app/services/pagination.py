"""Bounded array responses with optional route-bound keyset cursors."""

import base64
import json
from datetime import datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import and_, or_


def page(
    db, query, model, response, scope, limit=50, offset=0, cursor=None, time_column="created_at"
):
    timestamp = getattr(model, time_column)
    if cursor:
        if offset:
            raise HTTPException(422, "Cursor and offset cannot be combined")
        try:
            value = json.loads(
                base64.b64decode(cursor + "=" * (-len(cursor) % 4), altchars=b"-_", validate=True)
            )
            if value["scope"] != scope or value["v"] != 1:
                raise ValueError
            at, identifier = datetime.fromisoformat(value["at"]), UUID(value["id"])
        except (ValueError, KeyError, TypeError, json.JSONDecodeError):
            raise HTTPException(422, "Invalid pagination cursor") from None
        query = query.where(or_(timestamp < at, and_(timestamp == at, model.id < identifier)))
    items = db.scalars(
        query.order_by(timestamp.desc(), model.id.desc()).limit(limit + 1).offset(offset)
    ).all()
    if len(items) > limit:
        last = items[limit - 1]
        payload = {
            "v": 1,
            "scope": scope,
            "at": getattr(last, time_column).isoformat(),
            "id": str(last.id),
        }
        response.headers["X-Next-Cursor"] = (
            base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode())
            .decode()
            .rstrip("=")
        )
    return items[:limit]
