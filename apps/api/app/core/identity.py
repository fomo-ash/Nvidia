"""Server-owned identity boundary; external authentication belongs to Phase 8."""

from dataclasses import dataclass
from typing import Annotated, Literal

from fastapi import Depends, HTTPException

from app.core.config import settings


@dataclass(frozen=True)
class Actor:
    id: str
    role: Literal["viewer", "operator"]


def get_actor() -> Actor:
    if not settings.local_demo_enabled:
        raise HTTPException(401, "Authentication is not configured; local demo access is disabled")
    return Actor(id="local-demo-user", role="operator")


def require_operator(actor: Annotated[Actor, Depends(get_actor)]) -> Actor:
    if actor.role != "operator":
        raise HTTPException(403, "Operator role required")
    return actor
