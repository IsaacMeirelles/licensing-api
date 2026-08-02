from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.activation import Activation


class License(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "licenses"

    key: Mapped[str] = mapped_column(Text, unique=True, index=True)
    customer_name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tier: Mapped[str] = mapped_column(String(32), default="standard")
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    max_activations: Mapped[int] = mapped_column(Integer, default=1)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)

    activations: Mapped[list["Activation"]] = relationship(
        back_populates="license", cascade="all, delete-orphan"
    )
