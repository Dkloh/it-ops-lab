"""Service inventory database operations."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Service
from app.schemas import ServiceCreate, ServicePatch


class DuplicateService(Exception):
    pass


class ServiceNotFound(Exception):
    pass


def get_service(session: Session, service_id: int) -> Service:
    service = session.get(Service, service_id)
    if service is None:
        raise ServiceNotFound
    return service


def list_services(session: Session, offset: int, limit: int):
    return session.scalars(select(Service).order_by(Service.id).offset(offset).limit(limit)).all()


def save(session: Session, service: Service) -> Service:
    session.add(service)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        if getattr(exc.orig, "sqlite_errorname", None) == "SQLITE_CONSTRAINT_UNIQUE":
            raise DuplicateService from exc
        raise
    session.refresh(service)
    return service


def create_service(session: Session, payload: ServiceCreate) -> Service:
    return save(session, Service(**payload.model_dump()))


def update_service(session: Session, service_id: int, payload: ServicePatch) -> Service:
    service = get_service(session, service_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(service, field, value)
    return save(session, service)
