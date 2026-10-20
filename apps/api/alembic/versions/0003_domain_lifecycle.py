"""Normalized lifecycle records, durable idempotency, and append-only audit events.

Revision ID: 0003_domain_lifecycle
Revises: 0002_proposal_integrity

"""

from typing import Sequence, Union
import hashlib
import json
import uuid
from datetime import datetime

from alembic import op, context
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0003_domain_lifecycle"
down_revision: Union[str, Sequence[str], None] = "0002_proposal_integrity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "cost_analyses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("current_period", sa.String(length=7), nullable=False),
        sa.Column("previous_period", sa.String(length=7), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("report", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("cost_analyses", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_cost_analyses_created_at"), ["created_at"], unique=False
        )

    op.create_table(
        "idempotency_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor", sa.String(length=120), nullable=False),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("response", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("actor", "key", name="uq_idempotency_actor_key"),
    )
    op.create_table(
        "cost_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("analysis_id", sa.Uuid(), nullable=False),
        sa.Column("period", sa.String(length=7), nullable=False),
        sa.Column("service", sa.String(length=200), nullable=False),
        sa.Column("resource", sa.String(length=200), nullable=False),
        sa.Column("region", sa.String(length=80), nullable=False),
        sa.Column("cost", sa.Numeric(precision=20, scale=6), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("cost >= 0", name="ck_cost_nonnegative"),
        sa.ForeignKeyConstraint(
            ["analysis_id"],
            ["cost_analyses.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("cost_records", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_cost_records_analysis_id"), ["analysis_id"], unique=False
        )

    op.create_table(
        "investigations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('completed', 'failed')", name="ck_investigation_status"),
        sa.ForeignKeyConstraint(
            ["incident_id"],
            ["incidents.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("investigations", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_investigations_incident_id"), ["incident_id"], unique=False
        )

    op.create_table(
        "evidence_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("investigation_id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(length=200), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fact", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("trust_label", sa.String(length=20), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.CheckConstraint("trust_label = 'untrusted'", name="ck_evidence_trust"),
        sa.ForeignKeyConstraint(
            ["investigation_id"],
            ["investigations.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("evidence_items", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_evidence_items_investigation_id"), ["investigation_id"], unique=False
        )

    op.create_table(
        "approvals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("recommendation_id", sa.Uuid(), nullable=False),
        sa.Column("recommendation_version", sa.Integer(), nullable=False),
        sa.Column("decision", sa.String(length=20), nullable=False),
        sa.Column("actor", sa.String(length=120), nullable=False),
        sa.Column("proposal_hash", sa.String(length=64), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "decision = 'rejected' OR (proposal_hash IS NOT NULL AND expires_at IS NOT NULL)",
            name="ck_approval_binding",
        ),
        sa.CheckConstraint("decision IN ('approved', 'rejected')", name="ck_approval_decision"),
        sa.CheckConstraint("recommendation_version > 0", name="ck_approval_version"),
        sa.ForeignKeyConstraint(
            ["recommendation_id"],
            ["recommendations.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("recommendation_id"),
    )
    op.create_table(
        "executions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("recommendation_id", sa.Uuid(), nullable=False),
        sa.Column("approval_id", sa.Uuid(), nullable=False),
        sa.Column("actor", sa.String(length=120), nullable=False),
        sa.Column("proposal_hash", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("target", sa.String(length=200), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("adapter", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'succeeded', 'failed')", name="ck_execution_status"
        ),
        sa.ForeignKeyConstraint(
            ["approval_id"],
            ["approvals.id"],
        ),
        sa.ForeignKeyConstraint(
            ["recommendation_id"],
            ["recommendations.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("approval_id"),
        sa.UniqueConstraint("recommendation_id"),
    )
    op.create_table(
        "verification_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("execution_id", sa.Uuid(), nullable=False),
        sa.Column("actor", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("observations", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'passed', 'failed', 'inconclusive')",
            name="ck_verification_status",
        ),
        sa.ForeignKeyConstraint(
            ["execution_id"],
            ["executions.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("execution_id"),
    )
    with op.batch_alter_table("audit_events", schema=None) as batch_op:
        batch_op.create_index(
            "ix_audit_entity_time", ["entity_type", "entity_id", "created_at", "id"], unique=False
        )

    with op.batch_alter_table("recommendations", schema=None) as batch_op:
        batch_op.add_column(sa.Column("investigation_id", sa.Uuid(), nullable=True))
        batch_op.create_unique_constraint("uq_recommendation_investigation", ["investigation_id"])
        batch_op.create_foreign_key(
            "fk_recommendation_investigation", "investigations", ["investigation_id"], ["id"]
        )
        batch_op.drop_constraint("ck_recommendation_status", type_="check")
        batch_op.create_check_constraint(
            "ck_recommendation_status",
            "status IN ('proposed', 'approved', 'rejected', 'superseded', 'executed', 'execution_failed', 'verified', 'verification_failed')",
        )

    if not context.is_offline_mode():
        backfill_evidence()
    install_audit_guards()


def downgrade() -> None:
    """Downgrade schema."""
    remove_audit_guards()
    op.drop_table("verification_results")
    op.drop_table("executions")
    op.drop_table("approvals")
    op.execute(
        "UPDATE recommendations SET status='superseded' WHERE status IN ('executed', 'execution_failed', 'verified', 'verification_failed')"
    )
    with op.batch_alter_table("recommendations", schema=None) as batch_op:
        batch_op.drop_constraint("fk_recommendation_investigation", type_="foreignkey")
        batch_op.drop_constraint("uq_recommendation_investigation", type_="unique")
        batch_op.drop_column("investigation_id")
        batch_op.drop_constraint("ck_recommendation_status", type_="check")
        batch_op.create_check_constraint(
            "ck_recommendation_status",
            "status IN ('proposed', 'approved', 'rejected', 'superseded')",
        )
    with op.batch_alter_table("audit_events", schema=None) as batch_op:
        batch_op.drop_index("ix_audit_entity_time")
    with op.batch_alter_table("evidence_items", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_evidence_items_investigation_id"))

    op.drop_table("evidence_items")
    with op.batch_alter_table("investigations", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_investigations_incident_id"))

    op.drop_table("investigations")
    with op.batch_alter_table("cost_records", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_cost_records_analysis_id"))

    op.drop_table("cost_records")
    op.drop_table("idempotency_records")
    with op.batch_alter_table("cost_analyses", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_cost_analyses_created_at"))

    op.drop_table("cost_analyses")


def backfill_evidence():
    # Historical approval actors/times are deliberately not inferred.
    bind = op.get_bind()
    metadata = sa.MetaData()
    recommendations = sa.Table(
        "recommendations",
        metadata,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("incident_id", sa.Uuid()),
        sa.Column("investigation_id", sa.Uuid()),
        autoload_with=bind,
        extend_existing=True,
    )
    investigations = sa.Table(
        "investigations",
        metadata,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("incident_id", sa.Uuid()),
        autoload_with=bind,
        extend_existing=True,
    )
    evidence = sa.Table(
        "evidence_items",
        metadata,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("investigation_id", sa.Uuid()),
        autoload_with=bind,
        extend_existing=True,
    )
    for row in bind.execute(sa.select(recommendations)).mappings():
        if not row["evidence"]:
            continue
        investigation_id = uuid.uuid4()
        bind.execute(
            investigations.insert().values(
                id=investigation_id,
                incident_id=row["incident_id"],
                provider="legacy-mock",
                mode="synthetic",
                status="completed",
                summary="Imported retained legacy demo evidence.",
                created_at=row["created_at"],
            )
        )
        for item in row["evidence"]:
            digest = hashlib.sha256(
                json.dumps(item, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
            ).hexdigest()
            bind.execute(
                evidence.insert().values(
                    id=uuid.uuid4(),
                    investigation_id=investigation_id,
                    source=item["source"],
                    observed_at=datetime.fromisoformat(item["observed_at"].replace("Z", "+00:00")),
                    fact=item["fact"],
                    content_hash=digest,
                    trust_label="untrusted",
                    mode="synthetic",
                )
            )
        bind.execute(
            recommendations.update()
            .where(recommendations.c.id == row["id"])
            .values(investigation_id=investigation_id)
        )


def install_audit_guards():
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "CREATE FUNCTION fixproof_audit_immutable() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'audit events are append-only' USING ERRCODE = '23514'; END; $$"
        )
        op.execute(
            "CREATE TRIGGER audit_events_immutable BEFORE UPDATE OR DELETE ON audit_events FOR EACH ROW EXECUTE FUNCTION fixproof_audit_immutable()"
        )
        op.execute(
            "CREATE TRIGGER audit_events_no_truncate BEFORE TRUNCATE ON audit_events FOR EACH STATEMENT EXECUTE FUNCTION fixproof_audit_immutable()"
        )
    else:
        for action in ("UPDATE", "DELETE"):
            op.execute(
                f"CREATE TRIGGER audit_events_no_{action.lower()} BEFORE {action} ON audit_events BEGIN SELECT RAISE(ABORT, 'audit events are append-only'); END"
            )


def remove_audit_guards():
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER audit_events_no_truncate ON audit_events")
        op.execute("DROP TRIGGER audit_events_immutable ON audit_events")
        op.execute("DROP FUNCTION fixproof_audit_immutable()")
    else:
        op.execute("DROP TRIGGER audit_events_no_update")
        op.execute("DROP TRIGGER audit_events_no_delete")
