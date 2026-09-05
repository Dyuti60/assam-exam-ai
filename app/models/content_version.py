from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ContentVersion(Base):
    __tablename__ = "content_versions"
    __table_args__ = (
        CheckConstraint("version > 0", name="ck_content_versions_version_positive"),
        UniqueConstraint(
            "syllabus_version_id",
            "topic_id",
            "version",
            name="uq_content_versions_mapping_version",
        ),
        ForeignKeyConstraint(
            ["syllabus_version_id", "topic_id"],
            [
                "syllabus_version_topics.syllabus_version_id",
                "syllabus_version_topics.topic_id",
            ],
            name="fk_content_versions_syllabus_topic",
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    syllabus_version_id: Mapped[int] = mapped_column(Integer, nullable=False)
    topic_id: Mapped[int] = mapped_column(Integer, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
