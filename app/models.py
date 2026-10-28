"""Inventory persistence models."""

from datetime import UTC, datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Service(Base):
    __tablename__ = "services"
    __table_args__ = (UniqueConstraint("name", "environment", name="uq_service_name_environment"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    environment: Mapped[str] = mapped_column(String(50))
    description: Mapped[str | None] = mapped_column(String(2000))
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(UTC))


class LogBatch(Base):
    __tablename__ = "log_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20))
    accepted_count: Mapped[int] = mapped_column()
    rejected_count: Mapped[int] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(UTC))


class LogEvent(Base):
    __tablename__ = "log_events"
    __table_args__ = (
        Index("ix_log_events_batch_occurred", "batch_id", "occurred_at"),
        Index("ix_log_events_severity_occurred", "severity", "occurred_at"),
        Index("ix_log_events_occurred", "occurred_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("log_batches.id"))
    occurred_at: Mapped[datetime] = mapped_column(DateTime())
    severity: Mapped[str] = mapped_column(String(10))
    message: Mapped[str] = mapped_column(String())
    source: Mapped[str | None] = mapped_column(String(255))
    metadata_json: Mapped[dict | None] = mapped_column(JSON())


class IngestionError(Base):
    __tablename__ = "ingestion_errors"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("log_batches.id"), index=True)
    line_number: Mapped[int] = mapped_column()
    reason: Mapped[str] = mapped_column(String(100))


class DiagnosticRun(Base):
    __tablename__ = "diagnostic_runs"
    __table_args__ = (CheckConstraint("status IN ('running', 'completed')", name="ck_run_status"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("log_batches.id"))
    ruleset_version: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20))
    started_at: Mapped[datetime] = mapped_column(DateTime())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime())


class Finding(Base):
    __tablename__ = "findings"
    __table_args__ = (
        UniqueConstraint("run_id", "rule_code", name="uq_finding_run_rule"),
        CheckConstraint("severity IN ('HIGH', 'MEDIUM')", name="ck_finding_severity"),
        CheckConstraint("event_count > 0", name="ck_finding_event_count"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("diagnostic_runs.id"))
    rule_code: Mapped[str] = mapped_column(String(100))
    severity: Mapped[str] = mapped_column(String(20))
    summary: Mapped[str] = mapped_column(String())
    explanation: Mapped[str] = mapped_column(String())
    suggested_action: Mapped[str] = mapped_column(String())
    first_seen_at: Mapped[datetime] = mapped_column(DateTime())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime())
    event_count: Mapped[int] = mapped_column()


class FindingEvent(Base):
    __tablename__ = "finding_events"

    finding_id: Mapped[int] = mapped_column(ForeignKey("findings.id"), primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("log_events.id"), primary_key=True)
