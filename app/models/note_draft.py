from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.note_draft_claim import NoteDraftClaim
    from app.models.topic import Topic


class NoteDraft(Base):
    __tablename__ = "note_drafts"
    __table_args__ = (
        CheckConstraint(
            "approval_status IN ('DRAFT', 'APPROVED', 'REJECTED')",
            name="ck_note_drafts_approval_status",
        ),
        ForeignKeyConstraint(
            ["content_version_id", "topic_id"],
            ["content_versions.id", "content_versions.topic_id"],
            name="fk_note_drafts_content_version_topic",
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    topic_id: Mapped[int] = mapped_column(
        ForeignKey("topics.id", ondelete="RESTRICT"),
        nullable=False,
    )
    content_version_id: Mapped[int | None] = mapped_column(Integer)
    markdown: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    approval_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="DRAFT",
        server_default="DRAFT",
    )
    approval_decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
    reviewer_note: Mapped[str | None] = mapped_column(Text)

    topic: Mapped["Topic"] = relationship()
    claim_links: Mapped[list["NoteDraftClaim"]] = relationship(
        back_populates="note_draft",
        cascade="all, delete-orphan",
        order_by="NoteDraftClaim.position",
    )
