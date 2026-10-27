"""Thin HTTP adapters for the service inventory."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app import inventory
from app.database import get_session
from app.schemas import ServiceCreate, ServicePatch, ServiceRead

router = APIRouter(prefix="/api/v1/services", tags=["services"])
Database = Annotated[Session, Depends(get_session)]


@router.post("", response_model=ServiceRead, status_code=201)
def create_service(payload: ServiceCreate, session: Database):
    return inventory.create_service(session, payload)


@router.get("", response_model=list[ServiceRead])
def list_services(
    session: Database,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    return inventory.list_services(session, offset, limit)


@router.get("/{service_id}", response_model=ServiceRead)
def get_service(service_id: int, session: Database):
    return inventory.get_service(session, service_id)


@router.patch("/{service_id}", response_model=ServiceRead)
def update_service(service_id: int, payload: ServicePatch, session: Database):
    return inventory.update_service(session, service_id, payload)
