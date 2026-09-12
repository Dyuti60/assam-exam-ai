from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.ai_prompt_version import AiPromptVersion
    from app.models.claim_extraction_run import ClaimExtractionRun


class AiExecutionRun(Base):
    __tablename__ = "ai_execution_runs"
    __table_args__ = (
        CheckConstraint("status IN ('SUCCEEDED', 'FAILED')", name="ck_ai_execution_runs_status"),
        CheckConstraint(
            "provider_key ~ '^[a-z][a-z0-9_.-]*$' AND char_length(provider_key) <= 50",
            name="ck_ai_execution_runs_provider_key",
        ),
        CheckConstraint(
            "model_id ~ '^[A-Za-z0-9][A-Za-z0-9._:/-]*$' "
            "AND char_length(model_id) <= 128",
            name="ck_ai_execution_runs_model_id",
        ),
        CheckConstraint(
            "char_length(request_id) BETWEEN 1 AND 100 "
            "AND request_id = btrim(request_id) "
            "AND request_id !~ '[[:cntrl:]]' "
            "AND request_id !~ '^[[:space:]]' "
            "AND request_id !~ '[[:space:]]$'",
            name="ck_ai_execution_runs_request_id",
        ),
        CheckConstraint(
            "input_sha256 ~ '^[0-9a-f]{64}$' AND "
            "rendered_system_sha256 ~ '^[0-9a-f]{64}$' AND "
            "rendered_user_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_ai_execution_runs_request_hashes",
        ),
        CheckConstraint(
            "output_sha256 IS NULL OR output_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_ai_execution_runs_output_hash",
        ),
        CheckConstraint(
            "error_code IS NULL OR (error_code ~ '^[A-Z][A-Z0-9_]*$' "
            "AND char_length(error_code) <= 100)",
            name="ck_ai_execution_runs_error_code",
        ),
        CheckConstraint(
            "(status = 'SUCCEEDED' AND output_json IS NOT NULL "
            "AND output_sha256 IS NOT NULL AND error_code IS NULL) OR "
            "(status = 'FAILED' AND output_json IS NULL "
            "AND output_sha256 IS NULL AND error_code IS NOT NULL)",
            name="ck_ai_execution_runs_terminal_metadata",
        ),
        CheckConstraint(
            "completed_at >= started_at AND duration_ms >= 0",
            name="ck_ai_execution_runs_timing",
        ),
        CheckConstraint(
            "(input_tokens IS NULL OR input_tokens >= 0) AND "
            "(output_tokens IS NULL OR output_tokens >= 0) AND "
            "(total_tokens IS NULL OR total_tokens >= 0)",
            name="ck_ai_execution_runs_tokens_non_negative",
        ),
        CheckConstraint(
            "input_tokens IS NULL OR output_tokens IS NULL OR total_tokens IS NULL "
            "OR total_tokens = input_tokens + output_tokens",
            name="ck_ai_execution_runs_token_total",
        ),
        CheckConstraint(
            "(provider_cost IS NULL AND cost_currency IS NULL) OR "
            "(provider_cost IS NOT NULL AND provider_cost >= 0 "
            "AND cost_currency IS NOT NULL AND cost_currency ~ '^[A-Z]{3}$')",
            name="ck_ai_execution_runs_cost_metadata",
        ),
        CheckConstraint(
            "provider_request_id IS NULL OR char_length(provider_request_id) BETWEEN 1 AND 200",
            name="ck_ai_execution_runs_provider_request_id",
        ),
        CheckConstraint(
            "finish_reason IS NULL OR char_length(finish_reason) BETWEEN 1 AND 100",
            name="ck_ai_execution_runs_finish_reason",
        ),
        CheckConstraint(
            "safety_metadata IS NULL OR octet_length(safety_metadata::text) <= 4000",
            name="ck_ai_execution_runs_safety_metadata",
        ),
        UniqueConstraint("request_id", name="uq_ai_execution_runs_request_id"),
        UniqueConstraint(
            "id",
            "ai_prompt_version_id",
            "prompt_key",
            "prompt_version",
            "prompt_checksum",
            "provider_key",
            "model_id",
            "status",
            name="uq_ai_execution_runs_claim_extraction_provenance",
        ),
        ForeignKeyConstraint(
            ["ai_prompt_version_id", "prompt_key", "prompt_version", "prompt_checksum"],
            [
                "ai_prompt_versions.id",
                "ai_prompt_versions.prompt_key",
                "ai_prompt_versions.version",
                "ai_prompt_versions.checksum",
            ],
            name="fk_ai_execution_runs_prompt_snapshot",
            ondelete="RESTRICT",
        ),
        Index("ix_ai_execution_runs_prompt_version_id", "ai_prompt_version_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ai_prompt_version_id: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt_key: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_version: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_key: Mapped[str] = mapped_column(String(50), nullable=False)
    model_id: Mapped[str] = mapped_column(String(128), nullable=False)
    request_id: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    input_json: Mapped[dict[str, Any]] = mapped_column(JSONB(none_as_null=True), nullable=False)
    input_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    rendered_system_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    rendered_user_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    output_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    output_sha256: Mapped[str | None] = mapped_column(String(64))
    error_code: Mapped[str | None] = mapped_column(String(100))
    provider_request_id: Mapped[str | None] = mapped_column(String(200))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    total_tokens: Mapped[int | None] = mapped_column(Integer)
    provider_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    cost_currency: Mapped[str | None] = mapped_column(String(3))
    finish_reason: Mapped[str | None] = mapped_column(String(100))
    safety_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    prompt_version_record: Mapped["AiPromptVersion"] = relationship(
        back_populates="executions",
        foreign_keys=[ai_prompt_version_id, prompt_key, prompt_version, prompt_checksum],
    )
    claim_extraction_run: Mapped["ClaimExtractionRun | None"] = relationship(
        foreign_keys=(
            "[ClaimExtractionRun.ai_execution_run_id, "
            "ClaimExtractionRun.ai_prompt_version_id, ClaimExtractionRun.prompt_key, "
            "ClaimExtractionRun.prompt_version, ClaimExtractionRun.prompt_checksum, "
            "ClaimExtractionRun.provider_key, ClaimExtractionRun.model_id, "
            "ClaimExtractionRun.ai_execution_status]"
        ),
        uselist=False,
        overlaps="ai_execution",
    )
