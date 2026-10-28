"""Local operator sessions with a separate compatibility boundary for synthetic demos."""

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from typing import Annotated, Literal

from fastapi import Depends, HTTPException, Request

from app.core.config import settings


@dataclass(frozen=True)
class Actor:
    id: str
    role: Literal["viewer", "operator"]


def issue_session() -> tuple[str, str]:
    csrf = secrets.token_urlsafe(24)
    body = base64.urlsafe_b64encode(
        json.dumps({"sub": "local-operator", "exp": int(time.time()) + 3600, "csrf": csrf}).encode()
    ).decode()
    signature = hmac.new(
        settings.session_signing_key.encode(), body.encode(), hashlib.sha256
    ).hexdigest()
    return f"{body}.{signature}", csrf


def get_actor(request: Request) -> Actor:
    token = request.cookies.get("fixproof_session", "")
    if token and settings.session_signing_key:
        try:
            body, signature = token.rsplit(".", 1)
            expected = hmac.new(
                settings.session_signing_key.encode(), body.encode(), hashlib.sha256
            ).hexdigest()
            if not hmac.compare_digest(expected, signature):
                raise ValueError("signature")
            claims = json.loads(base64.urlsafe_b64decode(body))
            if claims["sub"] != "local-operator" or claims["exp"] <= time.time():
                raise ValueError("expiry")
            if request.method not in ("GET", "HEAD", "OPTIONS"):
                origin = request.headers.get("origin")
                if origin not in settings.cors_origins:
                    raise HTTPException(403, "Allowed browser Origin required")
                if not hmac.compare_digest(request.headers.get("x-csrf-token", ""), claims["csrf"]):
                    raise HTTPException(403, "CSRF token required")
            return Actor(id=claims["sub"], role="operator")
        except (ValueError, KeyError, TypeError, json.JSONDecodeError):
            raise HTTPException(401, "Invalid or expired operator session") from None
    if settings.local_demo_enabled:
        return Actor(id="local-demo-user", role="operator")
    raise HTTPException(401, "Operator session required")


def require_operator(actor: Annotated[Actor, Depends(get_actor)]) -> Actor:
    if actor.role != "operator":
        raise HTTPException(403, "Operator role required")
    return actor
