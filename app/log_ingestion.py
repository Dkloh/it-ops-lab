"""Atomic persistence of parsed batches, accepted events, and safe rejections."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.inventory import get_service
from app.log_parser import parse_logs
from app.models import IngestionError, LogBatch, LogEvent


class BatchNotFound(Exception):
    pass


def get_batch(session: Session, batch_id: int) -> LogBatch:
    batch = session.get(LogBatch, batch_id)
    if batch is None:
        raise BatchNotFound
    return batch


def ingest(session: Session, service_id: int, filename: str, data: bytes) -> LogBatch:
    get_service(session, service_id)
    records, errors = parse_logs(data)
    batch = LogBatch(
        service_id=service_id,
        filename=filename,
        status="partial" if records and errors else "completed" if records else "rejected",
        accepted_count=len(records),
        rejected_count=len(errors),
    )
    try:
        session.add(batch)
        session.flush()
        session.add_all(
            [
                LogEvent(
                    batch_id=batch.id,
                    occurred_at=record.timestamp.replace(tzinfo=None),
                    severity=record.severity,
                    message=record.message,
                    source=record.source,
                    metadata_json=record.metadata,
                )
                for record in records
            ]
        )
        session.add_all(
            [
                IngestionError(batch_id=batch.id, line_number=number, reason=reason)
                for number, reason in errors
            ]
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    session.refresh(batch)
    return batch


def get_errors(session: Session, batch_id: int, offset: int, limit: int):
    get_batch(session, batch_id)
    return session.scalars(
        select(IngestionError)
        .where(IngestionError.batch_id == batch_id)
        .order_by(IngestionError.line_number)
        .offset(offset)
        .limit(limit)
    ).all()
