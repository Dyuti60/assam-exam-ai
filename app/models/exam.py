from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.previous_paper import PreviousPaper
    from app.models.syllabus_version import SyllabusVersion


class Exam(Base):
    __tablename__ = "exams"
    __table_args__ = (
        UniqueConstraint("code", name="uq_exams_code"),
        UniqueConstraint("name", name="uq_exams_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    syllabus_versions: Mapped[list["SyllabusVersion"]] = relationship(
        back_populates="exam",
        passive_deletes=True,
    )
    previous_papers: Mapped[list["PreviousPaper"]] = relationship(
        back_populates="exam",
        passive_deletes=True,
    )
