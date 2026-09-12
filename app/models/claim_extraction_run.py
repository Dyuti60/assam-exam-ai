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
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.ai_execution_run import AiExecutionRun
    from app.models.claim_extraction_claim import ClaimExtractionClaim
    from app.models.claim_extraction_evidence import ClaimExtractionEvidence


class ClaimExtractionRun(Base):
    __tablename__ = "claim_extraction_runs"
    __table_args__ = (
        CheckConstraint(
            "source_extraction_status = 'SUCCEEDED'",
            name="ck_claim_extraction_runs_source_succeeded",
        ),
        CheckConstraint(
            "ai_execution_status IN ('SUCCEEDED', 'FAILED')",
            name="ck_claim_extraction_runs_ai_status",
        ),
        CheckConstraint(
            "status IN ('SUCCEEDED', 'FAILED')",
            name="ck_claim_extraction_runs_status",
        ),
        CheckConstraint(
            "error_code IS NULL OR (error_code ~ '^[A-Z][A-Z0-9_]*$' "
            "AND char_length(error_code) <= 100)",
            name="ck_claim_extraction_runs_error_code",
        ),
        CheckConstraint(
            "(status = 'SUCCEEDED' AND ai_execution_status = 'SUCCEEDED' "
            "AND error_code IS NULL) OR "
            "(status = 'FAILED' AND error_code IS NOT NULL)",
            name="ck_claim_extraction_runs_terminal_metadata",
        ),
        CheckConstraint(
            "ai_execution_status = 'SUCCEEDED' OR status = 'FAILED'",
            name="ck_claim_extraction_runs_ai_failure_terminal",
        ),
        CheckConstraint(
            "completed_at >= created_at",
            name="ck_claim_extraction_runs_timestamps",
        ),
        CheckConstraint(
            "snapshot_sha256 ~ '^[0-9a-f]{64}$' "
            "AND prompt_checksum ~ '^[0-9a-f]{64}$'",
            name="ck_claim_extraction_runs_checksums",
        ),
        CheckConstraint(
            "provider_key ~ '^[a-z][a-z0-9_.-]*$' "
            "AND char_length(provider_key) <= 50",
            name="ck_claim_extraction_runs_provider_key",
        ),
        CheckConstraint(
            "model_id ~ '^[A-Za-z0-9][A-Za-z0-9._:/-]*$' "
            "AND char_length(model_id) <= 128",
            name="ck_claim_extraction_runs_model_id",
        ),
        UniqueConstraint(
            "ai_execution_run_id",
            name="uq_claim_extraction_runs_ai_execution",
        ),
        UniqueConstraint(
            "id",
            "status",
            name="uq_claim_extraction_runs_id_status",
        ),
        UniqueConstraint(
            "id",
            "source_extraction_run_id",
            "source_snapshot_id",
            "source_id",
            "status",
            name="uq_claim_extraction_runs_provenance_status",
        ),
        ForeignKeyConstraint(
            [
                "source_extraction_run_id",
                "source_snapshot_id",
                "source_id",
                "snapshot_sha256",
                "source_extraction_status",
            ],
            [
                "source_extraction_runs.id",
                "source_extraction_runs.source_snapshot_id",
                "source_extraction_runs.source_id",
                "source_extraction_runs.snapshot_sha256",
                "source_extraction_runs.status",
            ],
            name="fk_claim_extraction_runs_source_extraction",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            [
                "ai_execution_run_id",
                "ai_prompt_version_id",
                "prompt_key",
                "prompt_version",
                "prompt_checksum",
                "provider_key",
                "model_id",
                "ai_execution_status",
            ],
            [
                "ai_execution_runs.id",
                "ai_execution_runs.ai_prompt_version_id",
                "ai_execution_runs.prompt_key",
                "ai_execution_runs.prompt_version",
                "ai_execution_runs.prompt_checksum",
                "ai_execution_runs.provider_key",
                "ai_execution_runs.model_id",
                "ai_execution_runs.status",
            ],
            name="fk_claim_extraction_runs_ai_execution",
            ondelete="RESTRICT",
        ),
        Index("ix_claim_extraction_runs_source_extraction", "source_extraction_run_id"),
        Index("ix_claim_extraction_runs_source_snapshot", "source_snapshot_id"),
        Index("ix_claim_extraction_runs_source", "source_id"),
        Index("ix_claim_extraction_runs_prompt", "ai_prompt_version_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_extraction_run_id: Mapped[int] = mapped_column(Integer, nullable=False)
    source_snapshot_id: Mapped[int] = mapped_column(Integer, nullable=False)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source_extraction_status: Mapped[str] = mapped_column(String(20), nullable=False)
    ai_prompt_version_id: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt_key: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_version: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    ai_execution_run_id: Mapped[int] = mapped_column(Integer, nullable=False)
    provider_key: Mapped[str] = mapped_column(String(50), nullable=False)
    model_id: Mapped[str] = mapped_column(String(128), nullable=False)
    ai_execution_status: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    evidence_links: Mapped[list["ClaimExtractionEvidence"]] = relationship(
        back_populates="claim_extraction_run",
        cascade="all, delete-orphan",
        order_by="ClaimExtractionEvidence.position",
        overlaps="evidence",
    )
    claim_links: Mapped[list["ClaimExtractionClaim"]] = relationship(
        back_populates="claim_extraction_run",
        cascade="all, delete-orphan",
        order_by="ClaimExtractionClaim.position",
    )
    ai_execution: Mapped["AiExecutionRun"] = relationship(
        foreign_keys=[
            ai_execution_run_id,
            ai_prompt_version_id,
            prompt_key,
            prompt_version,
            prompt_checksum,
            provider_key,
            model_id,
            ai_execution_status,
        ],
        overlaps="claim_extraction_run",
    )
