"""Durable read-only investigation runs and retained live evidence.

Revision ID: 0005_live_evidence
Revises: 0004_incident_intake
"""

from alembic import op
import sqlalchemy as sa

revision = "0005_live_evidence"
down_revision = "0004_incident_intake"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("investigation_requests") as batch:
        batch.add_column(sa.Column("claimed_at", sa.DateTime(timezone=True)))
        batch.add_column(sa.Column("claim_token", sa.String(36)))
        batch.add_column(sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("finished_at", sa.DateTime(timezone=True)))
    with op.batch_alter_table("investigations") as batch:
        batch.drop_constraint("ck_investigation_status", type_="check")
        batch.create_check_constraint(
            "ck_investigation_status",
            "status IN ('collecting','completed','needs_review','failed')",
        )
        batch.add_column(sa.Column("request_id", sa.Uuid()))
        batch.create_foreign_key(
            "fk_investigation_request", "investigation_requests", ["request_id"], ["id"]
        )
        batch.add_column(sa.Column("result", sa.JSON(), nullable=False, server_default="{}"))
    with op.batch_alter_table("evidence_items") as batch:
        for name, kind in [
            ("transport_id", sa.String(80)),
            ("transport_hash", sa.String(64)),
            ("target_uid", sa.String(80)),
            ("collection_error", sa.String(200)),
        ]:
            batch.add_column(sa.Column(name, kind))
        batch.add_column(sa.Column("raw_data", sa.JSON(), nullable=False, server_default="{}"))
        batch.add_column(
            sa.Column("redacted", sa.Boolean(), nullable=False, server_default=sa.false())
        )
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "CREATE TRIGGER incident_triggers_no_truncate BEFORE TRUNCATE ON incident_triggers FOR EACH STATEMENT EXECUTE FUNCTION fixproof_trigger_immutable()"
        )


def downgrade():
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER incident_triggers_no_truncate ON incident_triggers")
    with op.batch_alter_table("evidence_items") as batch:
        for name in [
            "redacted",
            "raw_data",
            "collection_error",
            "target_uid",
            "transport_hash",
            "transport_id",
        ]:
            batch.drop_column(name)
    op.execute(
        "UPDATE investigations SET status='failed' WHERE status NOT IN ('completed','failed')"
    )
    with op.batch_alter_table("investigations") as batch:
        batch.drop_constraint("fk_investigation_request", type_="foreignkey")
        batch.drop_column("request_id")
        batch.drop_column("result")
        batch.drop_constraint("ck_investigation_status", type_="check")
        batch.create_check_constraint("ck_investigation_status", "status IN ('completed','failed')")
    with op.batch_alter_table("investigation_requests") as batch:
        for name in ["finished_at", "attempts", "claim_token", "claimed_at"]:
            batch.drop_column(name)
