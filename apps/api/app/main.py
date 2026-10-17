from fastapi import FastAPI
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text
from app.api.v1.routes import router
from app.db.session import get_session

app = FastAPI(title="FixProof API", version="0.1.0")
app.include_router(router)
@app.get("/health/live")
def live(): return {"status":"ok"}
@app.get("/health/ready")
def ready():
    session = next(get_session())
    try: session.execute(text("SELECT 1")); return {"status":"ready"}
    finally: session.close()
@app.get("/metrics")
def metrics(): return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
