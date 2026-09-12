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
    from app.models.source_snapshot import SourceSnapshot


class SourceFetchRun(Base):
    __tablename__ = "source_fetch_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('SUCCEEDED', 'FAILED')",
            name="ck_source_fetch_runs_status",
        ),
        CheckConstraint(
            "btrim(requested_url) <> ''",
            name="ck_source_fetch_runs_requested_url_non_blank",
        ),
        CheckConstraint(
            "final_url IS NULL OR btrim(final_url) <> ''",
            name="ck_source_fetch_runs_final_url_non_blank",
        ),
        CheckConstraint(
            "http_status IS NULL OR http_status BETWEEN 100 AND 599",
            name="ck_source_fetch_runs_http_status_range",
        ),
        CheckConstraint(
            "error_code IS NULL OR (error_code ~ '^[A-Z][A-Z0-9_]*$' "
            "AND char_length(error_code) <= 100)",
            name="ck_source_fetch_runs_error_code_valid",
        ),
        CheckConstraint(
            "status NOT IN ('SUCCEEDED', 'FAILED') "
            "OR (status = 'SUCCEEDED' "
            "AND final_url IS NOT NULL "
            "AND http_status BETWEEN 200 AND 299 "
            "AND error_code IS NULL) "
            "OR (status = 'FAILED' AND error_code IS NOT NULL)",
            name="ck_source_fetch_runs_terminal_lifecycle",
        ),
        UniqueConstraint(
            "id",
            "source_id",
            "requested_url",
            "status",
            "final_url",
            name="uq_source_fetch_runs_id_source_url_status",
        ),
        ForeignKeyConstraint(
            ["source_id", "requested_url"],
            ["sources.id", "sources.location"],
            name="fk_source_fetch_runs_source_requested_url",
            ondelete="RESTRICT",
        ),
        Index("ix_source_fetch_runs_source_id", "source_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False)
    requested_url: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    final_url: Mapped[str | None] = mapped_column(Text)
    http_status: Mapped[int | None] = mapped_column(Integer)
    error_code: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    snapshot: Mapped["SourceSnapshot | None"] = relationship(
        back_populates="fetch_run",
        uselist=False,
        foreign_keys=(
            "[SourceSnapshot.source_fetch_run_id, SourceSnapshot.source_id, "
            "SourceSnapshot.requested_url, SourceSnapshot.run_status, "
            "SourceSnapshot.final_url]"
        ),
    )
