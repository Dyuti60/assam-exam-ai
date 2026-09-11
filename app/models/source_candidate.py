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
    from app.models.source_discovery_run import SourceDiscoveryRun


class SourceCandidate(Base):
    __tablename__ = "source_candidates"
    __table_args__ = (
        CheckConstraint(
            "run_status = 'SUCCEEDED'",
            name="ck_source_candidates_run_status",
        ),
        CheckConstraint(
            "position >= 0",
            name="ck_source_candidates_position_non_negative",
        ),
        CheckConstraint(
            "btrim(location) <> ''",
            name="ck_source_candidates_location_non_blank",
        ),
        CheckConstraint(
            "title IS NULL OR btrim(title) <> ''",
            name="ck_source_candidates_title_non_blank",
        ),
        CheckConstraint(
            "publisher IS NULL OR btrim(publisher) <> ''",
            name="ck_source_candidates_publisher_non_blank",
        ),
        CheckConstraint(
            "snippet IS NULL OR btrim(snippet) <> ''",
            name="ck_source_candidates_snippet_non_blank",
        ),
        UniqueConstraint(
            "source_discovery_run_id",
            "position",
            name="uq_source_candidates_run_position",
        ),
        UniqueConstraint(
            "source_discovery_run_id",
            "location",
            name="uq_source_candidates_run_location",
        ),
        ForeignKeyConstraint(
            ["source_discovery_run_id", "run_status"],
            ["source_discovery_runs.id", "source_discovery_runs.status"],
            name="fk_source_candidates_run_status",
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_discovery_run_id: Mapped[int] = mapped_column(Integer, nullable=False)
    run_status: Mapped[str] = mapped_column(String(20), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    location: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    publisher: Mapped[str | None] = mapped_column(String(255))
    snippet: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    source_discovery_run: Mapped["SourceDiscoveryRun"] = relationship(
        back_populates="candidates",
    )
