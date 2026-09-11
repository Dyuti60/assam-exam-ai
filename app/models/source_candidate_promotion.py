from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.source import Source


class SourceCandidatePromotion(Base):
    __tablename__ = "source_candidate_promotions"
    __table_args__ = (
        CheckConstraint(
            "btrim(location) <> ''",
            name="ck_source_candidate_promotions_location_non_blank",
        ),
        CheckConstraint(
            "candidate_approval_status = 'APPROVED'",
            name="ck_source_candidate_promotions_approval_status",
        ),
        CheckConstraint(
            "candidate_approval_decided_at IS NOT NULL",
            name="ck_source_candidate_promotions_approval_decided_at",
        ),
        UniqueConstraint(
            "source_candidate_id",
            name="uq_source_candidate_promotions_source_candidate_id",
        ),
        UniqueConstraint(
            "source_id",
            name="uq_source_candidate_promotions_source_id",
        ),
        ForeignKeyConstraint(
            ["source_candidate_id", "location"],
            ["source_candidates.id", "source_candidates.location"],
            name="fk_source_candidate_promotions_candidate_location",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["source_id", "location"],
            ["sources.id", "sources.location"],
            name="fk_source_candidate_promotions_source_location",
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_candidate_id: Mapped[int] = mapped_column(Integer, nullable=False)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False)
    location: Mapped[str] = mapped_column(Text, nullable=False)
    candidate_approval_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    candidate_approval_decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    candidate_reviewer_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    source: Mapped["Source"] = relationship(
        foreign_keys=[source_id],
    )
