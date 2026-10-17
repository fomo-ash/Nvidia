"""initial FixProof domain tables"""
from alembic import op
import sqlalchemy as sa
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None
def upgrade():
    op.create_table("incidents", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("title", sa.String(200), nullable=False), sa.Column("status", sa.String(32), nullable=False), sa.Column("severity", sa.String(16), nullable=False), sa.Column("summary", sa.Text(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_incidents_status", "incidents", ["status"])
    op.create_table("recommendations", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("incident_id", sa.Uuid(), sa.ForeignKey("incidents.id"), nullable=False), sa.Column("version", sa.Integer(), nullable=False), sa.Column("status", sa.String(32), nullable=False), sa.Column("action", sa.String(80), nullable=False), sa.Column("target", sa.String(200), nullable=False), sa.Column("parameters", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("incident_id", "version", name="uq_recommendation_version"))
    op.create_table("audit_events", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("entity_type", sa.String(40), nullable=False), sa.Column("entity_id", sa.Uuid(), nullable=False), sa.Column("action", sa.String(80), nullable=False), sa.Column("actor", sa.String(120), nullable=False), sa.Column("details", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
def downgrade():
    op.drop_table("audit_events"); op.drop_table("recommendations"); op.drop_index("ix_incidents_status", table_name="incidents"); op.drop_table("incidents")
