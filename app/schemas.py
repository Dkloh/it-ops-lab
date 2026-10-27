"""Service API contracts."""

from datetime import UTC, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator, model_validator

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Environment = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
Description = Annotated[str, StringConstraints(max_length=2000)]


class ServiceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Name
    environment: Environment
    description: Description | None = None


class ServicePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Name | None = None
    environment: Environment | None = None
    description: Description | None = None

    @model_validator(mode="after")
    def validate_patch(self):
        if not self.model_fields_set:
            raise ValueError("provide at least one field")
        for field in ("name", "environment"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class ServiceRead(ServiceCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def utc_timestamp(cls, value: datetime) -> datetime:
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
