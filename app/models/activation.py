from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin

if TYPE_CHECKING:
    from app.models.license import License


class Activation(Base, UUIDMixin):
    __tablename__ = "activations"
    __table_args__ = (
        UniqueConstraint("license_id", "machine_id", name="uq_license_machine"),
    )

    license_id: Mapped[UUID] = mapped_column(
        ForeignKey("licenses.id", ondelete="CASCADE"), index=True
    )
    machine_id: Mapped[str] = mapped_column(String(255))
    hostname: Mapped[str | None] = mapped_column(String(255), nullable=True)

    activated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)

    license: Mapped["License"] = relationship(back_populates="activations")
