from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.source_chunk import SourceChunk


class SourceExtractionRun(Base):
    __tablename__ = "source_extraction_runs"
    __table_args__ = (
        CheckConstraint(
            "extractor_key = 'deterministic-text-v1'",
            name="ck_source_extraction_runs_extractor_key",
        ),
        CheckConstraint(
            "status IN ('SUCCEEDED', 'FAILED')",
            name="ck_source_extraction_runs_status",
        ),
        CheckConstraint(
            "error_code IS NULL OR (error_code ~ '^[A-Z][A-Z0-9_]*$' "
            "AND char_length(error_code) <= 100)",
            name="ck_source_extraction_runs_error_code_valid",
        ),
        CheckConstraint(
            "snapshot_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_source_extraction_runs_snapshot_sha256",
        ),
        CheckConstraint(
            "text_sha256 IS NULL OR text_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_source_extraction_runs_text_sha256",
        ),
        CheckConstraint(
            "(status = 'SUCCEEDED' AND error_code IS NULL "
            "AND text_char_count > 0 AND text_sha256 IS NOT NULL) "
            "OR (status = 'FAILED' AND error_code IS NOT NULL "
            "AND text_char_count IS NULL AND text_sha256 IS NULL)",
            name="ck_source_extraction_runs_terminal_metadata",
        ),
        UniqueConstraint(
            "source_snapshot_id",
            "extractor_key",
            name="uq_source_extraction_runs_snapshot_extractor",
        ),
        UniqueConstraint(
            "id",
            "source_snapshot_id",
            "source_id",
            "status",
            name="uq_source_extraction_runs_id_snapshot_source_status",
        ),
        ForeignKeyConstraint(
            ["source_snapshot_id", "source_id", "snapshot_sha256"],
            ["source_snapshots.id", "source_snapshots.source_id", "source_snapshots.sha256"],
            name="fk_source_extraction_runs_snapshot_source_hash",
            ondelete="RESTRICT",
        ),
        Index("ix_source_extraction_runs_source_id", "source_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_snapshot_id: Mapped[int] = mapped_column(Integer, nullable=False)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    extractor_key: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(100))
    text_char_count: Mapped[int | None] = mapped_column(Integer)
    text_sha256: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    chunks: Mapped[list["SourceChunk"]] = relationship(
        back_populates="extraction_run",
        cascade="all, delete-orphan",
        order_by="SourceChunk.position",
        foreign_keys=(
            "[SourceChunk.source_extraction_run_id, SourceChunk.source_snapshot_id, "
            "SourceChunk.source_id, SourceChunk.run_status]"
        ),
    )
