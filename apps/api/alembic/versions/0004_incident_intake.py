"""Durable manual incident intake and investigation queue.

Revision ID: 0004_incident_intake
Revises: 0003_domain_lifecycle
"""

from alembic import op
import sqlalchemy as sa

revision = "0004_incident_intake"
down_revision = "0003_domain_lifecycle"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("incidents") as batch:
        batch.add_column(
            sa.Column("mode", sa.String(20), nullable=False, server_default="legacy_demo")
        )
        batch.add_column(sa.Column("target_id", sa.String(200)))
        batch.add_column(sa.Column("target_uid", sa.String(80)))
        batch.add_column(sa.Column("symptom", sa.String(80)))
        batch.add_column(sa.Column("fingerprint", sa.String(64)))
        batch.add_column(sa.Column("lifecycle", sa.String(32)))
        batch.add_column(sa.Column("assessment", sa.String(32)))
        batch.add_column(sa.Column("last_reported_at", sa.DateTime(timezone=True)))
        batch.create_unique_constraint("uq_incident_open_fingerprint", ["fingerprint"])
    op.create_table(
        "incident_triggers",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("incident_id", sa.Uuid(), sa.ForeignKey("incidents.id"), nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("reporter", sa.String(120), nullable=False),
        sa.Column("summary", sa.String(800), nullable=False),
        sa.Column("note", sa.String(2000)),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("reported_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_incident_triggers_incident_id", "incident_triggers", ["incident_id"])
    op.create_table(
        "investigation_requests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("incident_id", sa.Uuid(), sa.ForeignKey("incidents.id"), nullable=False),
        sa.Column(
            "trigger_id",
            sa.Uuid(),
            sa.ForeignKey("incident_triggers.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_investigation_requests_incident_id", "investigation_requests", ["incident_id"]
    )
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "CREATE FUNCTION fixproof_trigger_immutable() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'incident triggers are append-only' USING ERRCODE = '23514'; END; $$"
        )
        op.execute(
            "CREATE TRIGGER incident_triggers_immutable BEFORE UPDATE OR DELETE ON incident_triggers FOR EACH ROW EXECUTE FUNCTION fixproof_trigger_immutable()"
        )
    else:
        for action in ("UPDATE", "DELETE"):
            op.execute(
                f"CREATE TRIGGER incident_triggers_no_{action.lower()} BEFORE {action} ON incident_triggers BEGIN SELECT RAISE(ABORT, 'incident triggers are append-only'); END"
            )


def downgrade():
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER incident_triggers_immutable ON incident_triggers")
        op.execute("DROP FUNCTION fixproof_trigger_immutable()")
    else:
        for action in ("UPDATE", "DELETE"):
            op.execute(f"DROP TRIGGER incident_triggers_no_{action.lower()}")
    op.drop_index("ix_investigation_requests_incident_id", table_name="investigation_requests")
    op.drop_table("investigation_requests")
    op.drop_index("ix_incident_triggers_incident_id", table_name="incident_triggers")
    op.drop_table("incident_triggers")
    with op.batch_alter_table("incidents") as batch:
        batch.drop_constraint("uq_incident_open_fingerprint", type_="unique")
        for column in (
            "last_reported_at",
            "assessment",
            "lifecycle",
            "fingerprint",
            "symptom",
            "target_uid",
            "target_id",
            "mode",
        ):
            batch.drop_column(column)
