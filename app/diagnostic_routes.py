"""Thin HTTP adapters for synchronous diagnostic runs and evidence."""

from typing import Annotated

from fastapi import APIRouter, Path

from app import diagnostics
from app.diagnostic_schemas import FindingRead, RunRead
from app.routes import Database
from app.search_schemas import SQLITE_MAX_INTEGER

router = APIRouter(tags=["diagnostics"])
Identifier = Annotated[int, Path(gt=0, le=SQLITE_MAX_INTEGER)]


@router.post(
    "/api/v1/log-batches/{batch_id}/diagnostic-runs", response_model=RunRead, status_code=201
)
def execute_run(batch_id: Identifier, session: Database):
    """Analyze one batch with ruleset 1.0.0, preserving previous runs."""
    return diagnostics.execute_run(session, batch_id)


@router.get("/api/v1/diagnostic-runs/{run_id}", response_model=RunRead)
def get_run(run_id: Identifier, session: Database):
    """Retrieve a completed historical run and its findings."""
    return diagnostics.get_run(session, run_id)


@router.get("/api/v1/findings/{finding_id}", response_model=FindingRead)
def get_finding(finding_id: Identifier, session: Database):
    """Retrieve a finding with chronologically ordered supporting evidence."""
    return diagnostics.get_finding(session, finding_id)
