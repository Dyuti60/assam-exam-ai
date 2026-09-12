from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.source_extraction_run import SourceExtractionRun


class SourceChunk(Base):
    __tablename__ = "source_chunks"
    __table_args__ = (
        CheckConstraint(
            "run_status = 'SUCCEEDED'",
            name="ck_source_chunks_run_status_succeeded",
        ),
        CheckConstraint("position >= 0", name="ck_source_chunks_position_non_negative"),
        CheckConstraint("char_start >= 0", name="ck_source_chunks_start_non_negative"),
        CheckConstraint("char_end > char_start", name="ck_source_chunks_valid_range"),
        CheckConstraint(
            "text ~ '[^[:space:]]'",
            name="ck_source_chunks_text_non_blank",
        ),
        CheckConstraint(
            "char_end - char_start = char_length(text)",
            name="ck_source_chunks_range_matches_text",
        ),
        CheckConstraint(
            "char_length(text) <= 1000",
            name="ck_source_chunks_text_max_length",
        ),
        CheckConstraint(
            "sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_source_chunks_sha256_lower_hex",
        ),
        UniqueConstraint(
            "source_extraction_run_id",
            "position",
            name="uq_source_chunks_run_position",
        ),
        UniqueConstraint(
            "source_extraction_run_id",
            "char_start",
            "char_end",
            name="uq_source_chunks_run_range",
        ),
        ForeignKeyConstraint(
            [
                "source_extraction_run_id",
                "source_snapshot_id",
                "source_id",
                "run_status",
            ],
            [
                "source_extraction_runs.id",
                "source_extraction_runs.source_snapshot_id",
                "source_extraction_runs.source_id",
                "source_extraction_runs.status",
            ],
            name="fk_source_chunks_run_snapshot_source_status",
            ondelete="CASCADE",
        ),
        Index("ix_source_chunks_source_snapshot_id", "source_snapshot_id"),
        Index("ix_source_chunks_source_id", "source_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_extraction_run_id: Mapped[int] = mapped_column(Integer, nullable=False)
    source_snapshot_id: Mapped[int] = mapped_column(Integer, nullable=False)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False)
    run_status: Mapped[str] = mapped_column(String(20), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    char_start: Mapped[int] = mapped_column(Integer, nullable=False)
    char_end: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    extraction_run: Mapped["SourceExtractionRun"] = relationship(
        back_populates="chunks",
        foreign_keys=[
            source_extraction_run_id,
            source_snapshot_id,
            source_id,
            run_status,
        ],
    )
