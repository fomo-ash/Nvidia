from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text

from app.db.base import Base


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
