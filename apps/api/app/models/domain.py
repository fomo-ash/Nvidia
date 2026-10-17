import uuid
from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

def now(): return datetime.now(timezone.utc)
class Incident(Base):
    __tablename__ = "incidents"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(32), default="open", index=True)
    severity: Mapped[str] = mapped_column(String(16))
    summary: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
class Recommendation(Base):
    __tablename__ = "recommendations"
    __table_args__ = (UniqueConstraint("incident_id", "version", name="uq_recommendation_version"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    incident_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("incidents.id"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(32), default="proposed")
    action: Mapped[str] = mapped_column(String(80))
    target: Mapped[str] = mapped_column(String(200))
    parameters: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    entity_type: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[uuid.UUID] = mapped_column()
    action: Mapped[str] = mapped_column(String(80))
    actor: Mapped[str] = mapped_column(String(120), default="local-demo-user")
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
