from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.exam import Exam
    from app.models.source import Source
    from app.models.syllabus_version_topic import SyllabusVersionTopic


class SyllabusVersion(Base):
    __tablename__ = "syllabus_versions"
    __table_args__ = (
        UniqueConstraint(
            "exam_id",
            "label",
            name="uq_syllabus_versions_exam_label",
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
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    exam: Mapped["Exam"] = relationship(back_populates="syllabus_versions")
    source: Mapped["Source"] = relationship()
    topic_links: Mapped[list["SyllabusVersionTopic"]] = relationship(
        back_populates="syllabus_version",
        order_by="SyllabusVersionTopic.position",
        passive_deletes=True,
    )
