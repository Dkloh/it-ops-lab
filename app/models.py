"""Inventory persistence models."""

from datetime import UTC, datetime

from sqlalchemy import DateTime, String, UniqueConstraint
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
