from pathlib import Path

from alembic.script import ScriptDirectory
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.v1.routes import router
from app.core.config import settings
from app.db.session import get_session

app = FastAPI(title="FixProof API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Idempotency-Key"],
    expose_headers=["X-Next-Cursor", "Idempotency-Replayed"],
)
app.include_router(router)


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
