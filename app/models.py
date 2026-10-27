"""Inventory persistence models."""

from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, UniqueConstraint
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

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("log_batches.id"), index=True)
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
