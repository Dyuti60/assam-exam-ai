from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.previous_paper import PreviousPaper
    from app.models.topic import Topic


class PreviousQuestion(Base):
    __tablename__ = "previous_questions"
    __table_args__ = (
        CheckConstraint(
            "position >= 0",
            name="ck_previous_questions_position_non_negative",
        ),
        CheckConstraint(
            "length(btrim(question_text)) > 0",
            name="ck_previous_questions_text_non_blank",
        ),
        UniqueConstraint(
            "previous_paper_id",
            "position",
            name="uq_previous_questions_paper_position",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    previous_paper_id: Mapped[int] = mapped_column(
        ForeignKey("previous_papers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    topic_id: Mapped[int] = mapped_column(
        ForeignKey("topics.id", ondelete="RESTRICT"),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_location_reference: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    previous_paper: Mapped["PreviousPaper"] = relationship(
        back_populates="questions"
    )
    topic: Mapped["Topic"] = relationship()
