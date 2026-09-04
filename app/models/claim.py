from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.verification import Verification


class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    statement: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    subject: Mapped[str | None] = mapped_column(Text)

    predicate: Mapped[str | None] = mapped_column(Text)

    object_value: Mapped[str | None] = mapped_column(Text)

    verification_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="UNVERIFIED",
    )

    confidence: Mapped[float | None] = mapped_column(
        Float,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    last_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    verifications: Mapped[list["Verification"]] = relationship(
        back_populates="claim",
        passive_deletes=True,
    )
