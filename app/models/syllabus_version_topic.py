from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.syllabus_version import SyllabusVersion
    from app.models.topic import Topic


class SyllabusVersionTopic(Base):
    __tablename__ = "syllabus_version_topics"
    __table_args__ = (
        CheckConstraint(
            "position >= 0",
            name="ck_syllabus_version_topics_position_non_negative",
        ),
        UniqueConstraint(
            "syllabus_version_id",
            "position",
            name="uq_syllabus_version_topics_version_position",
        ),
    )

    syllabus_version_id: Mapped[int] = mapped_column(
        ForeignKey("syllabus_versions.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    topic_id: Mapped[int] = mapped_column(
        ForeignKey("topics.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    syllabus_version: Mapped["SyllabusVersion"] = relationship(
        back_populates="topic_links"
    )
    topic: Mapped["Topic"] = relationship()
