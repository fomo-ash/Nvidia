import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.session import get_session
from app.main import app


@pytest.fixture
def database(tmp_path, monkeypatch):
    url = os.environ.get("TEST_DATABASE_URL", f"sqlite+pysqlite:///{tmp_path / 'test.db'}")
    # The optional PostgreSQL suite migrates down after each test; require a test DB.
    parsed = make_url(url)
    if parsed.get_backend_name() != "sqlite" and not (parsed.database or "").endswith("_test"):
        raise ValueError("TEST_DATABASE_URL must name a disposable database ending in _test")
    monkeypatch.setattr(settings, "database_url", url)
    monkeypatch.setattr(settings, "local_demo_enabled", True)
    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    command.upgrade(config, "head")
    engine = create_engine(url)
    if parsed.get_backend_name() == "sqlite":

        @event.listens_for(engine, "connect")
        def foreign_keys(connection, record):
            connection.execute("PRAGMA foreign_keys=ON")

    factory = sessionmaker(bind=engine)
    try:
        yield factory, engine, config
    finally:
        engine.dispose()
        command.downgrade(config, "base")


@pytest.fixture
def client(database):
    factory, _, _ = database

    def session():
        with factory() as db:
            try:
                yield db
            except Exception:
                db.rollback()
                raise

    app.dependency_overrides[get_session] = session
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def incident(client):
    response = client.post(
        "/api/v1/incidents",
        json={
            "title": "Demo API failure",
            "severity": "high",
            "summary": "Synthetic incident",
        },
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def proposal(client, incident):
    response = client.post(f"/api/v1/incidents/{incident['id']}/investigate")
    assert response.status_code == 200
    return response.json()
