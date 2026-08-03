from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

DEFAULT_TIERS = ("standard", "premium", "enterprise")


class LicenseCreate(BaseModel):
    customer_name: str = Field(min_length=1, max_length=255)
    email: EmailStr | None = None
    contact_name: str | None = Field(default=None, max_length=255)
    contact_email: EmailStr | None = None
    contact_phone: str | None = Field(default=None, max_length=255)
    tier: str = Field(default="standard", pattern="^[a-z0-9_-]+$")
    expires_at: datetime | None = None
    max_activations: int = Field(default=1, ge=1, le=10000)


class LicenseUpdate(BaseModel):
    customer_name: str | None = Field(default=None, min_length=1, max_length=255)
    email: EmailStr | None = None
    contact_name: str | None = Field(default=None, max_length=255)
    contact_email: EmailStr | None = None
    contact_phone: str | None = Field(default=None, max_length=255)
    tier: str | None = Field(default=None, pattern="^[a-z0-9_-]+$")
    expires_at: datetime | None = None
    max_activations: int | None = Field(default=None, ge=1, le=10000)
    revoked: bool | None = None


class LicenseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    customer_name: str
    email: EmailStr | None
    contact_name: str | None
    contact_email: EmailStr | None
    contact_phone: str | None
    tier: str
    expires_at: datetime | None
    max_activations: int
    revoked: bool
    created_at: datetime


class LicenseReadWithKey(LicenseRead):
    key: str
