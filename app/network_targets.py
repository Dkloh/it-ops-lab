"""Registered targets and historical result persistence."""

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import network_checks
from app.inventory import get_service
from app.models import CheckResult, CheckTarget
from app.network_schemas import TargetCreate


class TargetNotFound(Exception):
    pass


class ResultNotFound(Exception):
    pass


class TargetInvalid(Exception):
    pass


class TargetDisabled(Exception):
    pass


def create_target(session: Session, service_id: int, payload: TargetCreate):
    get_service(session, service_id)
    target = CheckTarget(service_id=service_id, **payload.model_dump())
    try:
        session.add(target)
        session.commit()
    except Exception:
        session.rollback()
        raise
    session.refresh(target)
    return target


def list_targets(session: Session, service_id: int, offset: int, limit: int):
    get_service(session, service_id)
    return session.scalars(
        select(CheckTarget)
        .where(CheckTarget.service_id == service_id)
        .order_by(CheckTarget.id)
        .offset(offset)
        .limit(limit)
    ).all()


def get_target(session: Session, target_id: int):
    target = session.get(CheckTarget, target_id)
    if target is None:
        raise TargetNotFound
    return target


def run_check(session: Session, target_id: int, timeout: float):
    target = get_target(session, target_id)
    if not target.enabled:
        raise TargetDisabled
    # Revalidate stored fields, too; registration alone is not a security boundary.
    try:
        config = TargetCreate(**{key: getattr(target, key) for key in TargetCreate.model_fields})
    except ValidationError as exc:
        raise TargetInvalid from exc
    observation = network_checks.check(
        network_checks.Target(
            config.check_type, config.host, config.port, config.scheme, config.path
        ),
        timeout,
    )
    result = CheckResult(
        target_id=target.id,
        outcome=observation.outcome,
        duration_ms=observation.duration_ms,
        error_code=observation.error_code,
        status_code=observation.status_code,
        details_json=observation.details,
    )
    try:
        session.add(result)
        session.commit()
    except Exception:
        session.rollback()
        raise
    session.refresh(result)
    return result


def list_results(session: Session, target_id: int, offset: int, limit: int):
    get_target(session, target_id)
    return session.scalars(
        select(CheckResult)
        .where(CheckResult.target_id == target_id)
        .order_by(CheckResult.checked_at.desc(), CheckResult.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()


def get_result(session: Session, result_id: int):
    result = session.get(CheckResult, result_id)
    if result is None:
        raise ResultNotFound
    return result
