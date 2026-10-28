"""HTTP adapters for log investigation queries."""

from typing import Annotated

from fastapi import APIRouter, Path, Query

from app import log_search
from app.routes import Database
from app.search_schemas import (
    SQLITE_MAX_INTEGER,
    EventPage,
    EventRead,
    EventSummary,
    SearchFilters,
    TimeFilters,
)

router = APIRouter(prefix="/api/v1/log-events", tags=["log search"])


@router.get("", response_model=EventPage)
def search_events(session: Database, filters: Annotated[SearchFilters, Query()]):
    return log_search.search_events(session, filters)


# Register the static path before the event ID path.
@router.get("/summary", response_model=EventSummary)
def summarize_events(session: Database, filters: Annotated[TimeFilters, Query()]):
    return log_search.summarize_events(session, filters)


@router.get("/{event_id}", response_model=EventRead)
def get_event(session: Database, event_id: Annotated[int, Path(gt=0, le=SQLITE_MAX_INTEGER)]):
    return log_search.get_event(session, event_id)
