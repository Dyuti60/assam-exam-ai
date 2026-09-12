from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.source_fetch_run import SourceFetchRun


class SourceSnapshot(Base):
    __tablename__ = "source_snapshots"
    __table_args__ = (
        CheckConstraint(
            "run_status = 'SUCCEEDED'",
            name="ck_source_snapshots_run_status_succeeded",
        ),
        CheckConstraint(
            "btrim(requested_url) <> ''",
            name="ck_source_snapshots_requested_url_non_blank",
        ),
        CheckConstraint(
            "btrim(final_url) <> ''",
            name="ck_source_snapshots_final_url_non_blank",
        ),
        CheckConstraint(
            "btrim(content_type) <> ''",
            name="ck_source_snapshots_content_type_non_blank",
        ),
        CheckConstraint(
            "byte_size > 0",
            name="ck_source_snapshots_byte_size_positive",
        ),
        CheckConstraint(
            "byte_size = octet_length(content_bytes)",
            name="ck_source_snapshots_byte_size_matches",
        ),
        CheckConstraint(
            "sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_source_snapshots_sha256_lower_hex",
        ),
        UniqueConstraint(
            "source_fetch_run_id",
            name="uq_source_snapshots_source_fetch_run_id",
        ),
        ForeignKeyConstraint(
            [
                "source_fetch_run_id",
                "source_id",
                "requested_url",
                "run_status",
                "final_url",
            ],
            [
                "source_fetch_runs.id",
                "source_fetch_runs.source_id",
                "source_fetch_runs.requested_url",
                "source_fetch_runs.status",
                "source_fetch_runs.final_url",
            ],
            name="fk_source_snapshots_fetch_run_source_url_status",
            ondelete="RESTRICT",
        ),
        Index("ix_source_snapshots_source_id", "source_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_fetch_run_id: Mapped[int] = mapped_column(Integer, nullable=False)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False)
    requested_url: Mapped[str] = mapped_column(Text, nullable=False)
    run_status: Mapped[str] = mapped_column(String(20), nullable=False)
    final_url: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(String(255), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    content_bytes: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    fetch_run: Mapped["SourceFetchRun"] = relationship(
        back_populates="snapshot",
        foreign_keys=[
            source_fetch_run_id,
            source_id,
            requested_url,
            run_status,
            final_url,
        ],
    )
