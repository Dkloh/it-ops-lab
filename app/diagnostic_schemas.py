"""Diagnostic API contracts; timestamps are always serialized in UTC."""

from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict


def utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


UTCDateTime = Annotated[datetime, AfterValidator(utc)]


class EvidenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    occurred_at: UTCDateTime
    severity: str
    source: str | None
    message: str


class FindingSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    run_id: int
    rule_code: str
    severity: Literal["HIGH", "MEDIUM"]
    summary: str
    explanation: str
    suggested_action: str
    first_seen_at: UTCDateTime
    last_seen_at: UTCDateTime
    event_count: int
    event_ids: list[int]


class FindingRead(FindingSummary):
    service_id: int
    batch_id: int
    evidence: list[EvidenceRead]


class RunRead(BaseModel):
    id: int
    batch_id: int
    service_id: int
    ruleset_version: str
    status: Literal["completed"]
    started_at: UTCDateTime
    finished_at: UTCDateTime
    findings: list[FindingSummary]
    finding_count: int
