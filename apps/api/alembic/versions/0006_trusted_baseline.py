"""Operator-registered immutable baseline for the owned sample target.

Revision ID: 0006_trusted_baseline
Revises: 0005_live_evidence
"""

from alembic import op
import sqlalchemy as sa

revision = "0006_trusted_baseline"
down_revision = "0005_live_evidence"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "trusted_baselines",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("cluster", sa.String(80), nullable=False),
        sa.Column("namespace", sa.String(80), nullable=False),
        sa.Column("deployment", sa.String(80), nullable=False),
        sa.Column("target_uid", sa.String(80), nullable=False),
        sa.Column("template", sa.JSON(), nullable=False),
        sa.Column("template_hash", sa.String(64), nullable=False),
        sa.Column("registered_by", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("target_uid", name="uq_trusted_baseline_uid"),
    )
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "CREATE FUNCTION fixproof_baseline_immutable() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'trusted baselines are immutable' USING ERRCODE = '23514'; END; $$"
        )
        op.execute(
            "CREATE TRIGGER trusted_baselines_immutable BEFORE UPDATE OR DELETE ON trusted_baselines FOR EACH ROW EXECUTE FUNCTION fixproof_baseline_immutable()"
        )
        op.execute(
            "CREATE TRIGGER trusted_baselines_no_truncate BEFORE TRUNCATE ON trusted_baselines FOR EACH STATEMENT EXECUTE FUNCTION fixproof_baseline_immutable()"
        )
    else:
        for action in ("UPDATE", "DELETE"):
            op.execute(
                f"CREATE TRIGGER trusted_baselines_no_{action.lower()} BEFORE {action} ON trusted_baselines BEGIN SELECT RAISE(ABORT, 'trusted baselines are immutable'); END"
            )


def downgrade():
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER trusted_baselines_no_truncate ON trusted_baselines")
        op.execute("DROP TRIGGER trusted_baselines_immutable ON trusted_baselines")
        op.execute("DROP FUNCTION fixproof_baseline_immutable()")
    else:
        for action in ("UPDATE", "DELETE"):
            op.execute(f"DROP TRIGGER trusted_baselines_no_{action.lower()}")
    op.drop_table("trusted_baselines")
