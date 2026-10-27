"""Bounded JSON Lines parsing, independent of HTTP and persistence."""

import json
import math
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

MAX_FILE_BYTES = 1024 * 1024
MAX_LINE_BYTES = 16 * 1024
MAX_RECORDS = 10_000


class LogRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    timestamp: datetime
    severity: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    message: str = Field(min_length=1, max_length=8000)
    source: str | None = Field(default=None, max_length=255)
    metadata: dict | None = None

    @field_validator("timestamp", mode="before")
    @classmethod
    def timestamp_utc(cls, value):
        if not isinstance(value, str):
            raise ValueError("timestamp must be an ISO 8601 string")
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("timestamp requires a timezone")
        return parsed.astimezone(UTC)


class InvalidUpload(ValueError):
    pass


def reject_constant(value):
    raise ValueError("non-finite JSON number")


def finite_float(value):
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError("non-finite JSON number")
    return parsed


def validate_unicode(value):
    if isinstance(value, str):
        value.encode("utf-8")
    elif isinstance(value, dict):
        for key, item in value.items():
            validate_unicode(key)
            validate_unicode(item)
    elif isinstance(value, list):
        for item in value:
            validate_unicode(item)


def parse_logs(data: bytes) -> tuple[list[LogRecord], list[tuple[int, str]]]:
    if len(data) > MAX_FILE_BYTES:
        raise InvalidUpload("File exceeds 1 MiB limit")
    data = data.removeprefix(b"\xef\xbb\xbf")
    lines = data.split(b"\n")
    if lines[-1] == b"":
        lines.pop()  # A conventional final newline is not an extra record.
    if not lines or not data.strip():
        raise InvalidUpload("File contains no records")
    if len(lines) > MAX_RECORDS:
        raise InvalidUpload("File exceeds 10000 record limit")
    records, errors = [], []
    for number, line in enumerate(lines, 1):
        if len(line) > MAX_LINE_BYTES:
            errors.append((number, "Record exceeds 16 KiB limit"))
            continue
        try:
            decoded = line.decode("utf-8")
        except UnicodeDecodeError:
            errors.append((number, "Record is not valid UTF-8"))
            continue
        try:
            value = json.loads(decoded, parse_constant=reject_constant, parse_float=finite_float)
        except (ValueError, RecursionError):
            errors.append((number, "Malformed JSON"))
            continue
        try:
            validate_unicode(value)
            records.append(LogRecord.model_validate(value))
        except ValidationError as exc:
            error = exc.errors(include_input=False, include_context=False)[0]
            field = error["loc"][0] if error["loc"] else None
            if field in LogRecord.model_fields:
                reason = (
                    f"Missing required field: {field}"
                    if error["type"] == "missing"
                    else (f"Invalid field: {field}")
                )
            else:
                reason = "Expected an object with only documented fields"
            errors.append((number, reason))
        except (ValueError, OverflowError, RecursionError):
            errors.append((number, "Invalid record value"))
    return records, errors
