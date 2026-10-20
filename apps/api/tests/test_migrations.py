from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text
from sqlalchemy import MetaData, Table, select
from sqlalchemy import Column, Uuid
from datetime import datetime, timezone
from uuid import uuid4
import pytest
from sqlalchemy.exc import IntegrityError

from app.db.base import Base
from app.models.domain import Approval, EvidenceItem, Investigation, Recommendation
from app.services.idempotency import digest


def test_migrations_match_models_and_round_trip(database):
    _, engine, config = database
    with engine.connect() as connection:
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
    command.downgrade(config, "base")
    assert "incidents" not in inspect(engine).get_table_names()
    command.upgrade(config, "head")


def test_upgrade_preserves_legacy_records_without_inventing_approval(database):
    _, engine, config = database
    command.downgrade(config, "0001_initial")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO incidents (id,title,status,severity,summary,created_at) VALUES ('00000000000000000000000000000001','Legacy','open','high','Legacy incident',CURRENT_TIMESTAMP)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO recommendations (id,incident_id,version,status,action,target,parameters,created_at) VALUES ('00000000000000000000000000000002','00000000000000000000000000000001',1,'approved','restart_demo_workload','demo/api-workers','{}',CURRENT_TIMESTAMP)"
            )
        )
    command.upgrade(config, "head")
    with engine.connect() as connection:
        row = connection.execute(text("SELECT status, proposal_hash FROM recommendations")).one()
        assert row.status == "approved"
        assert row.proposal_hash is None


def test_upgrade_normalizes_legacy_evidence_without_inventing_approvals(database):
    factory, engine, config = database
    command.downgrade(config, "0002_proposal_integrity")
    metadata = MetaData()
    incidents = Table(
        "incidents", metadata, Column("id", Uuid(), primary_key=True), autoload_with=engine
    )
    recommendations = Table(
        "recommendations",
        metadata,
        Column("id", Uuid(), primary_key=True),
        Column("incident_id", Uuid()),
        autoload_with=engine,
    )
    incident_id, recommendation_id = uuid4(), uuid4()
    evidence = [
        {
            "source": "legacy-demo",
            "observed_at": "2026-10-17T10:00:00Z",
            "fact": "Historical synthetic observation",
            "trusted": False,
            "mode": "synthetic",
        }
    ]
    with engine.begin() as connection:
        connection.execute(
            incidents.insert().values(
                id=incident_id,
                title="Legacy",
                status="open",
                severity="high",
                summary="Historical demo",
                created_at=datetime.now(timezone.utc),
            )
        )
        connection.execute(
            recommendations.insert().values(
                id=recommendation_id,
                incident_id=incident_id,
                version=1,
                status="approved",
                action="restart_demo_workload",
                target="demo/api-workers",
                parameters={},
                evidence=evidence,
                proposal_hash="0" * 64,
                created_at=datetime.now(timezone.utc),
            )
        )
    command.upgrade(config, "head")
    with factory() as db:
        item = db.get(Recommendation, recommendation_id)
        assert item.evidence == evidence and item.proposal_hash == "0" * 64
        assert db.get(Investigation, item.investigation_id).provider == "legacy-mock"
        retained = db.scalar(select(EvidenceItem))
        assert retained.content_hash == digest(evidence[0])
        assert db.scalar(select(Approval)) is None


def test_audit_truncate_is_blocked_on_postgresql(database, incident):
    factory, engine, _ = database
    if engine.dialect.name != "postgresql":
        pytest.skip("SQLite has no TRUNCATE command")
    with factory() as db:
        with pytest.raises(IntegrityError):
            db.execute(text("TRUNCATE audit_events"))
        db.rollback()
