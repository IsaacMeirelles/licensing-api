from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ActivateRequest(BaseModel):
    license_key: str = Field(min_length=1)
    machine_id: str = Field(min_length=1, max_length=255)
    hostname: str | None = Field(default=None, max_length=255)


class ValidateRequest(BaseModel):
    license_key: str = Field(min_length=1)


class ActivationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    license_id: UUID
    machine_id: str
    hostname: str | None
    activated_at: datetime
    last_seen_at: datetime
    revoked: bool


class ValidateResponse(BaseModel):
    valid: bool
    reason: str | None = None
    customer_name: str | None = None
    tier: str | None = None
    expires_at: datetime | None = None
    max_activations: int | None = None
    active_activations: int | None = None
