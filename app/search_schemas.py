"""Validated search parameters and public event/summary contracts."""

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Severity = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
SQLITE_MAX_INTEGER = 2**63 - 1


class TimeFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    service_id: int | None = Field(default=None, gt=0, le=SQLITE_MAX_INTEGER)
    batch_id: int | None = Field(default=None, gt=0, le=SQLITE_MAX_INTEGER)
    start_time: datetime | None = None
    end_time: datetime | None = None

    @field_validator("start_time", "end_time", mode="before")
    @classmethod
    def aware_utc(cls, value):
        if value is None:
            return None
        if isinstance(value, str):
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Use an ISO 8601 timestamp with a timezone")
        try:
            return value.astimezone(UTC)
        except OverflowError as exc:
            raise ValueError("Timestamp is outside the supported range") from exc

    @model_validator(mode="after")
    def ordered_range(self):
        if self.start_time is not None and self.end_time is not None:
            if self.start_time > self.end_time:
                raise ValueError("start_time must be at or before end_time")
        return self


class SearchFilters(TimeFilters):
    severity: Severity | None = None
    message: str | None = Field(default=None, min_length=1, max_length=8000)
    offset: int = Field(default=0, ge=0, le=SQLITE_MAX_INTEGER)
    limit: int = Field(default=50, ge=1, le=100)


class EventRead(BaseModel):
    id: int
    service_id: int
    batch_id: int
    occurred_at: datetime
    severity: Severity
    message: str
    source: str | None
    metadata: dict | None

    @field_validator("occurred_at")
    @classmethod
    def utc_timestamp(cls, value):
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class EventPage(BaseModel):
    items: list[EventRead]
    total: int
    offset: int
    limit: int


class ServiceCount(BaseModel):
    service_id: int
    name: str
    environment: str
    count: int


class EventSummary(BaseModel):
    total: int
    by_severity: dict[Severity, int]
    by_service: list[ServiceCount]
    earliest: datetime | None
    latest: datetime | None

    @field_validator("earliest", "latest")
    @classmethod
    def utc_timestamp(cls, value):
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
