from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    publisher: Mapped[str | None] = mapped_column(
        String(255),
    )

    source_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    authority_tier: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    location: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    license_status: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    content_hash: Mapped[str | None] = mapped_column(
        String(128),
        unique=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )