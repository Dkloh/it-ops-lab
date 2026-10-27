"""Parameterized SQL search and aggregates; no HTTP or in-memory event filtering."""

from typing import get_args

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import LogBatch, LogEvent, Service
from app.search_schemas import EventPage, EventSummary, SearchFilters, Severity, TimeFilters


class EventNotFound(Exception):
    pass


def conditions(filters: TimeFilters):
    clauses = []
    if filters.service_id is not None:
        clauses.append(LogBatch.service_id == filters.service_id)
    if filters.batch_id is not None:
        clauses.append(LogEvent.batch_id == filters.batch_id)
    if filters.start_time is not None:
        clauses.append(LogEvent.occurred_at >= filters.start_time.replace(tzinfo=None))
    if filters.end_time is not None:
        clauses.append(LogEvent.occurred_at <= filters.end_time.replace(tzinfo=None))
    if isinstance(filters, SearchFilters):
        if filters.severity is not None:
            clauses.append(LogEvent.severity == filters.severity)
        if filters.message is not None:
            clauses.append(LogEvent.message.icontains(filters.message, autoescape=True))
    return clauses


def event_query():
    return select(
        LogEvent.id,
        LogBatch.service_id,
        LogEvent.batch_id,
        LogEvent.occurred_at,
        LogEvent.severity,
        LogEvent.message,
        LogEvent.source,
        LogEvent.metadata_json.label("metadata"),
    ).join(LogBatch, LogEvent.batch_id == LogBatch.id)


def search_events(session: Session, filters: SearchFilters) -> EventPage:
    clauses = conditions(filters)
    total = session.scalar(
        select(func.count()).select_from(LogEvent).join(LogBatch).where(*clauses)
    )
    rows = (
        session.execute(
            event_query()
            .where(*clauses)
            .order_by(LogEvent.occurred_at.desc(), LogEvent.id.desc())
            .offset(filters.offset)
            .limit(filters.limit)
        )
        .mappings()
        .all()
    )
    return EventPage(items=rows, total=total, offset=filters.offset, limit=filters.limit)


def get_event(session: Session, event_id: int):
    row = session.execute(event_query().where(LogEvent.id == event_id)).mappings().one_or_none()
    if row is None:
        raise EventNotFound
    return row


def summarize_events(session: Session, filters: TimeFilters) -> EventSummary:
    clauses = conditions(filters)
    total, earliest, latest = session.execute(
        select(func.count(), func.min(LogEvent.occurred_at), func.max(LogEvent.occurred_at))
        .select_from(LogEvent)
        .join(LogBatch)
        .where(*clauses)
    ).one()
    by_severity = dict.fromkeys(get_args(Severity), 0)
    by_severity.update(
        session.execute(
            select(LogEvent.severity, func.count())
            .join(LogBatch)
            .where(*clauses)
            .group_by(LogEvent.severity)
        ).all()
    )
    by_service = (
        session.execute(
            select(
                Service.id.label("service_id"),
                Service.name,
                Service.environment,
                func.count().label("count"),
            )
            .select_from(LogEvent)
            .join(LogBatch)
            .join(Service)
            .where(*clauses)
            .group_by(Service.id, Service.name, Service.environment)
            .order_by(Service.id)
        )
        .mappings()
        .all()
    )
    return EventSummary(
        total=total,
        by_severity=by_severity,
        by_service=by_service,
        earliest=earliest,
        latest=latest,
    )
