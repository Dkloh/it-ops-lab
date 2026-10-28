"""Read-only, bounded discovery and aggregates for the dashboard."""

from typing import Annotated

from fastapi import APIRouter, Path
from pydantic import BaseModel
from sqlalchemy import func, select

from app.diagnostic_schemas import UTCDateTime
from app.inventory import get_service
from app.log_ingestion import get_batch
from app.log_routes import BatchRead
from app.models import CheckResult, CheckTarget, DiagnosticRun, Finding, LogBatch, LogEvent, Service
from app.network_routes import Page
from app.network_schemas import ResultRead
from app.routes import Database
from app.search_schemas import SQLITE_MAX_INTEGER

router = APIRouter(tags=["dashboard"])
Identifier = Annotated[int, Path(gt=0, le=SQLITE_MAX_INTEGER)]


class BatchPage(BaseModel):
    items: list[BatchRead]
    total: int
    offset: int
    limit: int


class RunItem(BaseModel):
    id: int
    batch_id: int
    ruleset_version: str
    status: str
    started_at: UTCDateTime
    finished_at: UTCDateTime | None
    finding_count: int


class RunPage(BaseModel):
    items: list[RunItem]
    total: int
    offset: int
    limit: int


class RecentFinding(BaseModel):
    id: int
    run_id: int
    service_id: int
    rule_code: str
    severity: str
    summary: str
    last_seen_at: UTCDateTime
    recorded_at: UTCDateTime


class RecentObservation(ResultRead):
    target_name: str
    service_id: int


class Overview(BaseModel):
    service_count: int
    event_count: int
    error_count: int
    warning_count: int
    latest_findings: list[RecentFinding]
    recent_observations: list[RecentObservation]


@router.get("/api/v1/services/{service_id}/log-batches", response_model=BatchPage)
def batches(service_id: Identifier, session: Database, page: Page):
    get_service(session, service_id)
    offset, limit = page
    query = select(LogBatch).where(LogBatch.service_id == service_id)
    rows = session.scalars(
        query.order_by(LogBatch.created_at.desc(), LogBatch.id.desc()).offset(offset).limit(limit)
    ).all()
    total = session.scalar(
        select(func.count()).select_from(LogBatch).where(LogBatch.service_id == service_id)
    )
    return BatchPage(
        items=[BatchRead.model_validate(row) for row in rows],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/api/v1/log-batches/{batch_id}/diagnostic-runs", response_model=RunPage)
def runs(batch_id: Identifier, session: Database, page: Page):
    get_batch(session, batch_id)
    offset, limit = page
    count = (
        select(func.count())
        .select_from(Finding)
        .where(Finding.run_id == DiagnosticRun.id)
        .correlate(DiagnosticRun)
        .scalar_subquery()
    )
    rows = (
        session.execute(
            select(
                DiagnosticRun.id,
                DiagnosticRun.batch_id,
                DiagnosticRun.ruleset_version,
                DiagnosticRun.status,
                DiagnosticRun.started_at,
                DiagnosticRun.finished_at,
                count.label("finding_count"),
            )
            .where(DiagnosticRun.batch_id == batch_id)
            .order_by(DiagnosticRun.started_at.desc(), DiagnosticRun.id.desc())
            .offset(offset)
            .limit(limit)
        )
        .mappings()
        .all()
    )
    total = session.scalar(
        select(func.count()).select_from(DiagnosticRun).where(DiagnosticRun.batch_id == batch_id)
    )
    return RunPage(items=rows, total=total, offset=offset, limit=limit)


@router.get("/api/v1/dashboard", response_model=Overview)
def overview(session: Database):
    levels = dict(
        session.execute(select(LogEvent.severity, func.count()).group_by(LogEvent.severity)).all()
    )
    findings = (
        session.execute(
            select(
                Finding.id,
                Finding.run_id,
                LogBatch.service_id,
                Finding.rule_code,
                Finding.severity,
                Finding.summary,
                Finding.last_seen_at,
                DiagnosticRun.finished_at.label("recorded_at"),
            )
            .join(DiagnosticRun, Finding.run_id == DiagnosticRun.id)
            .join(LogBatch, DiagnosticRun.batch_id == LogBatch.id)
            .order_by(DiagnosticRun.finished_at.desc(), Finding.id.desc())
            .limit(5)
        )
        .mappings()
        .all()
    )
    rows = session.execute(
        select(CheckResult, CheckTarget.name, CheckTarget.service_id)
        .join(CheckTarget)
        .order_by(CheckResult.checked_at.desc(), CheckResult.id.desc())
        .limit(5)
    ).all()
    observations = [
        RecentObservation(
            **ResultRead.model_validate(row).model_dump(), target_name=name, service_id=service_id
        )
        for row, name, service_id in rows
    ]
    return Overview(
        service_count=session.scalar(select(func.count()).select_from(Service)),
        event_count=sum(levels.values()),
        error_count=levels.get("ERROR", 0) + levels.get("CRITICAL", 0),
        warning_count=levels.get("WARNING", 0),
        latest_findings=findings,
        recent_observations=observations,
    )
