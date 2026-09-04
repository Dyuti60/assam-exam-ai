from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.note_draft_claim import NoteDraftClaim
    from app.models.topic import Topic


class NoteDraft(Base):
    __tablename__ = "note_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    topic_id: Mapped[int] = mapped_column(
        ForeignKey("topics.id", ondelete="RESTRICT"),
        nullable=False,
    )
    markdown: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    topic: Mapped["Topic"] = relationship()
    claim_links: Mapped[list["NoteDraftClaim"]] = relationship(
        back_populates="note_draft",
        cascade="all, delete-orphan",
        order_by="NoteDraftClaim.position",
    )
