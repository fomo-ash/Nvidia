import uuid
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Index,
    Numeric,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


def now():
    return datetime.now(timezone.utc)


class Incident(Base):
    __tablename__ = "incidents"
    __table_args__ = (UniqueConstraint("fingerprint", name="uq_incident_open_fingerprint"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(32), default="open", index=True)
    severity: Mapped[str] = mapped_column(String(16))
    summary: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    mode: Mapped[str] = mapped_column(String(20), default="legacy_demo")
    target_id: Mapped[str | None] = mapped_column(String(200))
    target_uid: Mapped[str | None] = mapped_column(String(80))
    symptom: Mapped[str | None] = mapped_column(String(80))
    fingerprint: Mapped[str | None] = mapped_column(String(64))
    lifecycle: Mapped[str | None] = mapped_column(String(32))
    assessment: Mapped[str | None] = mapped_column(String(32))
    last_reported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class IncidentTrigger(Base):
    __tablename__ = "incident_triggers"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    incident_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("incidents.id"), index=True)
    source: Mapped[str] = mapped_column(String(20))
    reporter: Mapped[str] = mapped_column(String(120))
    summary: Mapped[str] = mapped_column(String(800))
    note: Mapped[str | None] = mapped_column(String(2000))
    payload_hash: Mapped[str] = mapped_column(String(64))
    reported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class InvestigationRequest(Base):
    __tablename__ = "investigation_requests"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    incident_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("incidents.id"), index=True)
    trigger_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("incident_triggers.id"), unique=True)
    status: Mapped[str] = mapped_column(String(20), default="queued")
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    claim_token: Mapped[str | None] = mapped_column(String(36))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Recommendation(Base):
    __tablename__ = "recommendations"
    __table_args__ = (
        UniqueConstraint("incident_id", "version", name="uq_recommendation_version"),
        UniqueConstraint("investigation_id", name="uq_recommendation_investigation"),
        CheckConstraint("version > 0", name="ck_recommendation_version"),
        CheckConstraint(
            "status IN ('proposed', 'approved', 'rejected', 'superseded', 'executed', 'execution_failed', 'verified', 'verification_failed')",
            name="ck_recommendation_status",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    incident_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("incidents.id"))
    investigation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("investigations.id", name="fk_recommendation_investigation")
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(32), default="proposed")
    action: Mapped[str] = mapped_column(String(80))
    target: Mapped[str] = mapped_column(String(200))
    parameters: Mapped[dict] = mapped_column(JSON, default=dict)
    proposal_hash: Mapped[str | None] = mapped_column(String(64))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    evidence: Mapped[list | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class TrustedBaseline(Base):
    __tablename__ = "trusted_baselines"
    __table_args__ = (UniqueConstraint("target_uid", name="uq_trusted_baseline_uid"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    cluster: Mapped[str] = mapped_column(String(80))
    namespace: Mapped[str] = mapped_column(String(80))
    deployment: Mapped[str] = mapped_column(String(80))
    target_uid: Mapped[str] = mapped_column(String(80))
    template: Mapped[dict] = mapped_column(JSON)
    template_hash: Mapped[str] = mapped_column(String(64))
    registered_by: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_entity_time", "entity_type", "entity_id", "created_at", "id"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    entity_type: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[uuid.UUID] = mapped_column()
    action: Mapped[str] = mapped_column(String(80))
    actor: Mapped[str] = mapped_column(String(120), default="local-demo-user")
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Investigation(Base):
    __tablename__ = "investigations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('collecting', 'completed', 'needs_review', 'failed')",
            name="ck_investigation_status",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    incident_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("incidents.id"), index=True)
    request_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("investigation_requests.id", name="fk_investigation_request")
    )
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    provider: Mapped[str] = mapped_column(String(80))
    mode: Mapped[str] = mapped_column(String(20), default="synthetic")
    status: Mapped[str] = mapped_column(String(20), default="completed")
    summary: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class EvidenceItem(Base):
    __tablename__ = "evidence_items"
    __table_args__ = (CheckConstraint("trust_label = 'untrusted'", name="ck_evidence_trust"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    investigation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("investigations.id"), index=True)
    source: Mapped[str] = mapped_column(String(200))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fact: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    transport_id: Mapped[str | None] = mapped_column(String(80))
    transport_hash: Mapped[str | None] = mapped_column(String(64))
    target_uid: Mapped[str | None] = mapped_column(String(80))
    raw_data: Mapped[dict] = mapped_column(JSON, default=dict)
    collection_error: Mapped[str | None] = mapped_column(String(200))
    redacted: Mapped[bool] = mapped_column(default=False)
    trust_label: Mapped[str] = mapped_column(String(20), default="untrusted")
    mode: Mapped[str] = mapped_column(String(20), default="synthetic")


class Approval(Base):
    __tablename__ = "approvals"
    __table_args__ = (
        CheckConstraint("decision IN ('approved', 'rejected')", name="ck_approval_decision"),
        CheckConstraint("recommendation_version > 0", name="ck_approval_version"),
        CheckConstraint(
            "decision = 'rejected' OR (proposal_hash IS NOT NULL AND expires_at IS NOT NULL)",
            name="ck_approval_binding",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    recommendation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("recommendations.id"), unique=True
    )
    recommendation_version: Mapped[int] = mapped_column(Integer)
    decision: Mapped[str] = mapped_column(String(20))
    actor: Mapped[str] = mapped_column(String(120))
    proposal_hash: Mapped[str | None] = mapped_column(String(64))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Execution(Base):
    __tablename__ = "executions"
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'succeeded', 'failed')", name="ck_execution_status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    recommendation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("recommendations.id"), unique=True
    )
    approval_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("approvals.id"), unique=True)
    actor: Mapped[str] = mapped_column(String(120))
    proposal_hash: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(80))
    target: Mapped[str] = mapped_column(String(200))
    parameters: Mapped[dict] = mapped_column(JSON)
    adapter: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class VerificationResult(Base):
    __tablename__ = "verification_results"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'passed', 'failed', 'inconclusive')",
            name="ck_verification_status",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    execution_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("executions.id"), unique=True)
    actor: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    observations: Mapped[dict] = mapped_column(JSON, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CostAnalysis(Base):
    __tablename__ = "cost_analyses"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    current_period: Mapped[str] = mapped_column(String(7))
    previous_period: Mapped[str] = mapped_column(String(7))
    mode: Mapped[str] = mapped_column(String(20), default="synthetic")
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    report: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)


class CostRecord(Base):
    __tablename__ = "cost_records"
    __table_args__ = (CheckConstraint("cost >= 0", name="ck_cost_nonnegative"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    analysis_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cost_analyses.id"), index=True)
    period: Mapped[str] = mapped_column(String(7))
    service: Mapped[str] = mapped_column(String(200))
    resource: Mapped[str] = mapped_column(String(200))
    region: Mapped[str] = mapped_column(String(80))
    cost: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    tags: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (UniqueConstraint("actor", "key", name="uq_idempotency_actor_key"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    actor: Mapped[str] = mapped_column(String(120))
    key: Mapped[str] = mapped_column(String(128))
    fingerprint: Mapped[str] = mapped_column(String(64))
    status_code: Mapped[int] = mapped_column(Integer, default=202)
    response: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
