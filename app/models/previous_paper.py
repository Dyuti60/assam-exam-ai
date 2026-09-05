from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.exam import Exam
    from app.models.previous_question import PreviousQuestion
    from app.models.source import Source


class PreviousPaper(Base):
    __tablename__ = "previous_papers"
    __table_args__ = (
        CheckConstraint("year > 0", name="ck_previous_papers_year_positive"),
        UniqueConstraint(
            "exam_id",
            "year",
            "label",
            name="uq_previous_papers_exam_year_label",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exam_id: Mapped[int] = mapped_column(
        ForeignKey("exams.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_id: Mapped[int] = mapped_column(
        ForeignKey("sources.id", ondelete="RESTRICT"),
        nullable=False,
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    exam: Mapped["Exam"] = relationship(back_populates="previous_papers")
    source: Mapped["Source"] = relationship()
    questions: Mapped[list["PreviousQuestion"]] = relationship(
        back_populates="previous_paper",
        order_by="PreviousQuestion.position",
        passive_deletes=True,
    )
