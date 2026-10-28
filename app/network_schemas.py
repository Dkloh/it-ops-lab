"""Registered network targets and bounded historical observation contracts."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.diagnostic_schemas import UTCDateTime
from app.network_security import hostname


class TargetCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    name: str = Field(min_length=1, max_length=100)
    check_type: Literal["DNS", "TCP", "HTTP"]
    host: str
    port: int | None = Field(default=None, ge=1, le=65535)
    scheme: Literal["http", "https"] | None = None
    path: str | None = Field(default=None, max_length=2048)
    enabled: bool = True

    @field_validator("host")
    @classmethod
    def valid_host(cls, value):
        return hostname(value)

    @field_validator("name")
    @classmethod
    def valid_name(cls, value):
        if not value.strip():
            raise ValueError("Name cannot be blank")
        return value.strip()

    @model_validator(mode="after")
    def valid_destination(self):
        if self.check_type == "DNS":
            if self.port is not None or self.path is not None or self.scheme is not None:
                raise ValueError("DNS targets do not use port, path or scheme")
        elif self.check_type == "TCP":
            if self.port is None or self.path is not None or self.scheme is not None:
                raise ValueError("TCP requires a port and does not use path or scheme")
        else:
            self.scheme = self.scheme or "https"
            self.port = self.port or (443 if self.scheme == "https" else 80)
            self.path = self.path if self.path is not None else "/"
            if (
                not self.path.startswith("/")
                or self.path.startswith("//")
                or any(ord(char) < 33 or ord(char) > 126 for char in self.path)
                or any(char in self.path for char in ("\\", "#", "?", "%"))
            ):
                raise ValueError(
                    "HTTP path must be a plain absolute ASCII path without query or fragment"
                )
        return self


class TargetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    service_id: int
    name: str
    check_type: Literal["DNS", "TCP", "HTTP"]
    host: str
    port: int | None
    scheme: str | None
    path: str | None
    enabled: bool
    created_at: UTCDateTime


class ResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    target_id: int
    outcome: Literal["success", "failure"]
    duration_ms: float
    error_code: str | None
    status_code: int | None
    details_json: dict
    checked_at: UTCDateTime


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
