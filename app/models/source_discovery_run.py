from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.source_candidate import SourceCandidate


class SourceDiscoveryRun(Base):
    __tablename__ = "source_discovery_runs"
    __table_args__ = (
        CheckConstraint(
            "btrim(query) <> ''",
            name="ck_source_discovery_runs_query_non_blank",
        ),
        CheckConstraint(
            "btrim(adapter_key) <> ''",
            name="ck_source_discovery_runs_adapter_key_non_blank",
        ),
        CheckConstraint(
            "status IN ('SUCCEEDED', 'FAILED')",
            name="ck_source_discovery_runs_status",
        ),
        CheckConstraint(
            "(status = 'SUCCEEDED' AND error_message IS NULL) "
            "OR (status = 'FAILED' AND error_message IS NOT NULL "
            "AND btrim(error_message) <> '')",
            name="ck_source_discovery_runs_lifecycle",
        ),
        UniqueConstraint(
            "id",
            "status",
            name="uq_source_discovery_runs_id_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    adapter_key: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    candidates: Mapped[list["SourceCandidate"]] = relationship(
        back_populates="source_discovery_run",
        order_by="SourceCandidate.position",
    )
