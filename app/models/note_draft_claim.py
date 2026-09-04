from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.claim import Claim
    from app.models.note_draft import NoteDraft


class NoteDraftClaim(Base):
    __tablename__ = "note_draft_claims"
    __table_args__ = (
        CheckConstraint(
            "position >= 0",
            name="ck_note_draft_claims_position_non_negative",
        ),
        UniqueConstraint(
            "note_draft_id",
            "position",
            name="uq_note_draft_claims_draft_position",
        ),
    )

    note_draft_id: Mapped[int] = mapped_column(
        ForeignKey("note_drafts.id", ondelete="CASCADE"),
        primary_key=True,
    )
    claim_id: Mapped[int] = mapped_column(
        ForeignKey("claims.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    note_draft: Mapped["NoteDraft"] = relationship(back_populates="claim_links")
    claim: Mapped["Claim"] = relationship()
