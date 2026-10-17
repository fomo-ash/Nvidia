from fastapi.testclient import TestClient
from app.main import app
def test_liveness():
    assert TestClient(app).get("/health/live").json() == {"status":"ok"}
