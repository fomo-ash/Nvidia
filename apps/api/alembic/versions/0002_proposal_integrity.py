"""Retain demo evidence and bind approval to an expiring proposal digest.

Legacy proposals intentionally remain without digests and cannot be approved.
Reinvestigation creates a reviewable proposal with a new version.
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_proposal_integrity"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("recommendations") as batch:
        batch.add_column(sa.Column("proposal_hash", sa.String(64), nullable=True))
        batch.add_column(sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("evidence", sa.JSON(), nullable=True))
        batch.create_check_constraint("ck_recommendation_version", "version > 0")
        batch.create_check_constraint(
            "ck_recommendation_status",
            "status IN ('proposed', 'approved', 'rejected', 'superseded')",
        )


def downgrade():
    with op.batch_alter_table("recommendations") as batch:
        batch.drop_constraint("ck_recommendation_status", type_="check")
        batch.drop_constraint("ck_recommendation_version", type_="check")
        batch.drop_column("evidence")
        batch.drop_column("expires_at")
        batch.drop_column("proposal_hash")
