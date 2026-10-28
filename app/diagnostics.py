"""Synchronous batch diagnostics and atomic persistence of historical evidence."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import diagnostic_rules
from app.diagnostic_schemas import EvidenceRead, FindingRead, FindingSummary, RunRead
from app.log_ingestion import get_batch
from app.log_parser import MAX_RECORDS
from app.models import DiagnosticRun, Finding, FindingEvent, LogEvent


class RunNotFound(Exception):
    pass


class FindingNotFound(Exception):
    pass


def evidence(session: Session, finding_id: int):
    return session.scalars(
        select(LogEvent)
        .join(FindingEvent, FindingEvent.event_id == LogEvent.id)
        .where(FindingEvent.finding_id == finding_id)
        .order_by(LogEvent.occurred_at, LogEvent.id)
        .limit(MAX_RECORDS)
    ).all()


def finding_summary(session: Session, finding: Finding) -> FindingSummary:
    fields = {column.name: getattr(finding, column.name) for column in Finding.__table__.columns}
    return FindingSummary(**fields, event_ids=[event.id for event in evidence(session, finding.id)])


def get_run(session: Session, run_id: int) -> RunRead:
    run = session.get(DiagnosticRun, run_id)
    if run is None:
        raise RunNotFound
    batch = get_batch(session, run.batch_id)
    findings = session.scalars(
        select(Finding)
        .where(Finding.run_id == run_id)
        .order_by(Finding.rule_code, Finding.id)
        .limit(MAX_RECORDS)
    ).all()
    return RunRead(
        id=run.id,
        batch_id=run.batch_id,
        service_id=batch.service_id,
        ruleset_version=run.ruleset_version,
        status=run.status,
        started_at=run.started_at,
        finished_at=run.finished_at,
        findings=[finding_summary(session, finding) for finding in findings],
        finding_count=len(findings),
    )


def get_finding(session: Session, finding_id: int) -> FindingRead:
    finding = session.get(Finding, finding_id)
    if finding is None:
        raise FindingNotFound
    run = session.get(DiagnosticRun, finding.run_id)
    batch = get_batch(session, run.batch_id)
    summary = finding_summary(session, finding)
    return FindingRead(
        **summary.model_dump(),
        batch_id=batch.id,
        service_id=batch.service_id,
        evidence=[EvidenceRead.model_validate(event) for event in evidence(session, finding_id)],
    )


def execute_run(session: Session, batch_id: int) -> RunRead:
    try:
        get_batch(session, batch_id)
        run = DiagnosticRun(
            batch_id=batch_id,
            ruleset_version=diagnostic_rules.RULESET_VERSION,
            status="running",
            started_at=datetime.now(UTC).replace(tzinfo=None),
        )
        session.add(run)
        session.flush()
        rows = session.scalars(
            select(LogEvent)
            .where(LogEvent.batch_id == batch_id)
            .order_by(LogEvent.occurred_at, LogEvent.id)
            .limit(MAX_RECORDS + 1)
        ).all()
        if len(rows) > MAX_RECORDS:
            raise ValueError("Batch exceeds diagnostic processing limit")
        events = [
            diagnostic_rules.Event(row.id, row.occurred_at, row.severity, row.message)
            for row in rows
        ]
        for detection in diagnostic_rules.analyze(events):
            rule, support = detection.rule, detection.events
            finding = Finding(
                run_id=run.id,
                rule_code=rule.code,
                severity=rule.severity,
                summary=rule.summary,
                explanation=rule.explanation,
                suggested_action=rule.suggested_action,
                first_seen_at=support[0].occurred_at,
                last_seen_at=support[-1].occurred_at,
                event_count=len(support),
            )
            session.add(finding)
            session.flush()
            session.add_all(
                [FindingEvent(finding_id=finding.id, event_id=event.id) for event in support]
            )
        run.status = "completed"
        run.finished_at = datetime.now(UTC).replace(tzinfo=None)
        session.flush()
        # Serialize before committing so response construction failures also roll back.
        result = get_run(session, run.id)
        session.commit()
        return result
    except Exception:
        session.rollback()
        raise
