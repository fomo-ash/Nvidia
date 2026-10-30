"""Durable optional Discord channel notification outbox.

Revision ID: 0007_discord_deliveries
Revises: 0006_trusted_baseline
"""

from alembic import op
import sqlalchemy as sa

revision = "0007_discord_deliveries"
down_revision = "0006_trusted_baseline"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "discord_deliveries",
        sa.Column("audit_event_id", sa.Uuid(), sa.ForeignKey("audit_events.id"), primary_key=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True)),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("message_id", sa.String(80)),
        sa.Column("error_kind", sa.String(80)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('queued', 'leased', 'delivered', 'failed')",
            name="ck_discord_delivery_status",
        ),
    )
    op.create_index("ix_discord_delivery_ready", "discord_deliveries", ["status", "available_at"])


def downgrade():
    op.drop_index("ix_discord_delivery_ready", table_name="discord_deliveries")
    op.drop_table("discord_deliveries")
