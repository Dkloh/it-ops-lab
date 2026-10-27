"""Raw-file upload and batch inspection HTTP adapters."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, field_validator
from starlette.concurrency import run_in_threadpool

from app import log_ingestion
from app.inventory import get_service
from app.log_parser import MAX_FILE_BYTES, InvalidUpload
from app.routes import Database

router = APIRouter(tags=["log ingestion"])


class BatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    service_id: int
    filename: str
    status: str
    accepted_count: int
    rejected_count: int
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def utc_timestamp(cls, value):
        return value.replace(tzinfo=UTC)


class ErrorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    line_number: int
    reason: str


@router.post(
    "/api/v1/services/{service_id}/log-batches",
    response_model=BatchRead,
    status_code=201,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {"application/x-ndjson": {"schema": {"type": "string", "format": "binary"}}},
        }
    },
)
async def upload_logs(
    service_id: int,
    request: Request,
    session: Database,
    filename: Annotated[str, Query(min_length=1, max_length=255)] = "logs.jsonl",
):
    if not filename.lower().endswith(".jsonl") or any(c in filename for c in ("/", "\\", "\x00")):
        raise HTTPException(400, "Provide a .jsonl filename without directory components")
    media_type = request.headers.get("content-type", "application/octet-stream").split(";")[0]
    if media_type not in {
        "application/x-ndjson",
        "application/jsonl",
        "application/octet-stream",
        "text/plain",
    }:
        raise HTTPException(415, "Send raw JSON Lines bytes, not multipart or a JSON wrapper")
    await run_in_threadpool(get_service, session, service_id)
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > MAX_FILE_BYTES:
            raise HTTPException(413, "File exceeds 1 MiB limit")
        data.extend(chunk)
    try:
        return await run_in_threadpool(
            log_ingestion.ingest, session, service_id, filename, bytes(data)
        )
    except InvalidUpload as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/api/v1/log-batches/{batch_id}", response_model=BatchRead)
def get_batch(batch_id: int, session: Database):
    return log_ingestion.get_batch(session, batch_id)


@router.get("/api/v1/log-batches/{batch_id}/errors", response_model=list[ErrorRead])
def get_errors(
    batch_id: int,
    session: Database,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    return log_ingestion.get_errors(session, batch_id, offset, limit)
