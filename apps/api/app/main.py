from pathlib import Path

from alembic.script import ScriptDirectory
import hmac
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.v1.routes import router
from app.core.config import settings
from app.core.identity import issue_session
from app.db.session import get_session

app = FastAPI(title="FixProof API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Idempotency-Key", "X-CSRF-Token"],
    allow_credentials=True,
    expose_headers=["X-Next-Cursor", "Idempotency-Replayed"],
)
app.include_router(router)


class LoginRequest(BaseModel):
    secret: str


@app.post("/api/v1/session")
def login(payload: LoginRequest, response: Response, request: Request):
    if not settings.operator_secret or not settings.session_signing_key:
        raise HTTPException(503, "Local operator login is not configured")
    if request.headers.get("origin") not in settings.cors_origins:
        raise HTTPException(403, "Allowed browser Origin required")
    if not hmac.compare_digest(payload.secret, settings.operator_secret):
        raise HTTPException(401, "Invalid operator secret")
    token, csrf = issue_session()
    response.set_cookie(
        "fixproof_session",
        token,
        max_age=3600,
        httponly=True,
        secure=False,
        samesite="strict",
        path="/",
    )
    return {"csrf_token": csrf, "expires_in": 3600}


@app.exception_handler(IntegrityError)
async def integrity_error(request, exc):
    return JSONResponse(status_code=409, content={"detail": "Conflicting state; reload and retry"})


@app.get("/health/live")
def live():
    return {"status": "ok"}


@app.get("/health/ready")
def ready(db: Session = Depends(get_session)):
    try:
        expected = ScriptDirectory(str(Path(__file__).resolve().parents[1] / "alembic")).get_heads()
        actual = list(db.scalars(text("SELECT version_num FROM alembic_version")))
        if set(actual) != set(expected):
            return JSONResponse(status_code=503, content={"detail": "Database migrations required"})
    except SQLAlchemyError:
        return JSONResponse(
            status_code=503, content={"detail": "Database unavailable or not migrated"}
        )
    return {"status": "ready"}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), headers={"Content-Type": CONTENT_TYPE_LATEST})
