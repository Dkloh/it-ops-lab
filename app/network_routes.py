"""HTTP adapters for explicitly initiated network observations."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request

from app import network_targets
from app.network_schemas import ResultRead, RunRequest, TargetCreate, TargetRead
from app.routes import Database
from app.search_schemas import SQLITE_MAX_INTEGER

router = APIRouter(tags=["network diagnostics"])
Identifier = Annotated[int, Path(gt=0, le=SQLITE_MAX_INTEGER)]


def pagination(
    offset: Annotated[int, Query(ge=0, le=SQLITE_MAX_INTEGER)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    return offset, limit


Page = Annotated[tuple[int, int], Depends(pagination)]


@router.post(
    "/api/v1/services/{service_id}/check-targets", response_model=TargetRead, status_code=201
)
def create_target(service_id: Identifier, payload: TargetCreate, session: Database):
    return network_targets.create_target(session, service_id, payload)


@router.get("/api/v1/services/{service_id}/check-targets", response_model=list[TargetRead])
def list_targets(service_id: Identifier, session: Database, page: Page):
    return network_targets.list_targets(session, service_id, *page)


@router.post("/api/v1/check-targets/{target_id}/runs", response_model=ResultRead, status_code=201)
def run_check(
    target_id: Identifier, session: Database, request: Request, payload: RunRequest | None = None
):
    return network_targets.run_check(
        session, target_id, request.app.state.settings.network_timeout_seconds
    )


@router.get("/api/v1/check-targets/{target_id}/results", response_model=list[ResultRead])
def list_results(target_id: Identifier, session: Database, page: Page):
    return network_targets.list_results(session, target_id, *page)


@router.get("/api/v1/check-results/{result_id}", response_model=ResultRead)
def get_result(result_id: Identifier, session: Database):
    return network_targets.get_result(session, result_id)
