"""Add grounded claim extraction provenance.

Revision ID: d7e3a9c5f218
Revises: c9f2a6d4e817
Create Date: 2026-09-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d7e3a9c5f218"
down_revision: str | None = "c9f2a6d4e817"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_ai_execution_runs_claim_extraction_provenance",
        "ai_execution_runs",
        [
            "id",
            "ai_prompt_version_id",
            "prompt_key",
            "prompt_version",
            "prompt_checksum",
            "provider_key",
            "model_id",
            "status",
        ],
    )
    op.create_unique_constraint(
        "uq_source_extraction_runs_claim_extraction_provenance",
        "source_extraction_runs",
        ["id", "source_snapshot_id", "source_id", "snapshot_sha256", "status"],
    )
    op.create_unique_constraint(
        "uq_source_chunks_claim_extraction_provenance",
        "source_chunks",
        ["id", "source_extraction_run_id", "source_snapshot_id", "source_id"],
    )
    op.create_unique_constraint(
        "uq_evidence_id_source",
        "evidence",
        ["id", "source_id"],
    )

    op.create_table(
        "claim_extraction_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_extraction_run_id", sa.Integer(), nullable=False),
        sa.Column("source_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_sha256", sa.String(length=64), nullable=False),
        sa.Column("source_extraction_status", sa.String(length=20), nullable=False),
        sa.Column("ai_prompt_version_id", sa.Integer(), nullable=False),
        sa.Column("prompt_key", sa.String(length=100), nullable=False),
        sa.Column("prompt_version", sa.Integer(), nullable=False),
        sa.Column("prompt_checksum", sa.String(length=64), nullable=False),
        sa.Column("ai_execution_run_id", sa.Integer(), nullable=False),
        sa.Column("provider_key", sa.String(length=50), nullable=False),
        sa.Column("model_id", sa.String(length=128), nullable=False),
        sa.Column("ai_execution_status", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "source_extraction_status = 'SUCCEEDED'",
            name="ck_claim_extraction_runs_source_succeeded",
        ),
        sa.CheckConstraint(
            "ai_execution_status IN ('SUCCEEDED', 'FAILED')",
            name="ck_claim_extraction_runs_ai_status",
        ),
        sa.CheckConstraint(
            "status IN ('SUCCEEDED', 'FAILED')",
            name="ck_claim_extraction_runs_status",
        ),
        sa.CheckConstraint(
            "error_code IS NULL OR (error_code ~ '^[A-Z][A-Z0-9_]*$' "
            "AND char_length(error_code) <= 100)",
            name="ck_claim_extraction_runs_error_code",
        ),
        sa.CheckConstraint(
            "(status = 'SUCCEEDED' AND ai_execution_status = 'SUCCEEDED' "
            "AND error_code IS NULL) OR "
            "(status = 'FAILED' AND error_code IS NOT NULL)",
            name="ck_claim_extraction_runs_terminal_metadata",
        ),
        sa.CheckConstraint(
            "ai_execution_status = 'SUCCEEDED' OR status = 'FAILED'",
            name="ck_claim_extraction_runs_ai_failure_terminal",
        ),
        sa.CheckConstraint(
            "completed_at >= created_at",
            name="ck_claim_extraction_runs_timestamps",
        ),
        sa.CheckConstraint(
            "snapshot_sha256 ~ '^[0-9a-f]{64}$' "
            "AND prompt_checksum ~ '^[0-9a-f]{64}$'",
            name="ck_claim_extraction_runs_checksums",
        ),
        sa.CheckConstraint(
            "provider_key ~ '^[a-z][a-z0-9_.-]*$' "
            "AND char_length(provider_key) <= 50",
            name="ck_claim_extraction_runs_provider_key",
        ),
        sa.CheckConstraint(
            "model_id ~ '^[A-Za-z0-9][A-Za-z0-9._:/-]*$' "
            "AND char_length(model_id) <= 128",
            name="ck_claim_extraction_runs_model_id",
        ),
        sa.UniqueConstraint(
            "ai_execution_run_id",
            name="uq_claim_extraction_runs_ai_execution",
        ),
        sa.UniqueConstraint("id", "status", name="uq_claim_extraction_runs_id_status"),
        sa.UniqueConstraint(
            "id",
            "source_extraction_run_id",
            "source_snapshot_id",
            "source_id",
            "status",
            name="uq_claim_extraction_runs_provenance_status",
        ),
        sa.ForeignKeyConstraint(
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
        sa.ForeignKeyConstraint(
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
    )
    op.create_index(
        "ix_claim_extraction_runs_source_extraction",
        "claim_extraction_runs",
        ["source_extraction_run_id"],
    )
    op.create_index(
        "ix_claim_extraction_runs_source_snapshot",
        "claim_extraction_runs",
        ["source_snapshot_id"],
    )
    op.create_index(
        "ix_claim_extraction_runs_source",
        "claim_extraction_runs",
        ["source_id"],
    )
    op.create_index(
        "ix_claim_extraction_runs_prompt",
        "claim_extraction_runs",
        ["ai_prompt_version_id"],
    )

    op.create_table(
        "claim_extraction_evidence",
        sa.Column("claim_extraction_run_id", sa.Integer(), primary_key=True),
        sa.Column("evidence_id", sa.Integer(), primary_key=True),
        sa.Column("source_chunk_id", sa.Integer(), nullable=False),
        sa.Column("source_extraction_run_id", sa.Integer(), nullable=False),
        sa.Column("source_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("run_status", sa.String(length=20), nullable=False),
        sa.Column("char_start", sa.Integer(), nullable=False),
        sa.Column("char_end", sa.Integer(), nullable=False),
        sa.Column("cited_text_sha256", sa.String(length=64), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "run_status = 'SUCCEEDED'",
            name="ck_claim_extraction_evidence_run_succeeded",
        ),
        sa.CheckConstraint(
            "position >= 0 AND char_start >= 0 AND char_end > char_start",
            name="ck_claim_extraction_evidence_position_range",
        ),
        sa.CheckConstraint(
            "cited_text_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_claim_extraction_evidence_checksum",
        ),
        sa.UniqueConstraint(
            "claim_extraction_run_id",
            "position",
            name="uq_claim_extraction_evidence_run_position",
        ),
        sa.UniqueConstraint(
            "claim_extraction_run_id",
            "source_chunk_id",
            "char_start",
            "char_end",
            name="uq_claim_extraction_evidence_run_citation",
        ),
        sa.ForeignKeyConstraint(
            [
                "claim_extraction_run_id",
                "source_extraction_run_id",
                "source_snapshot_id",
                "source_id",
                "run_status",
            ],
            [
                "claim_extraction_runs.id",
                "claim_extraction_runs.source_extraction_run_id",
                "claim_extraction_runs.source_snapshot_id",
                "claim_extraction_runs.source_id",
                "claim_extraction_runs.status",
            ],
            name="fk_claim_extraction_evidence_run_provenance",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            [
                "source_chunk_id",
                "source_extraction_run_id",
                "source_snapshot_id",
                "source_id",
            ],
            [
                "source_chunks.id",
                "source_chunks.source_extraction_run_id",
                "source_chunks.source_snapshot_id",
                "source_chunks.source_id",
            ],
            name="fk_claim_extraction_evidence_source_chunk",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["evidence_id", "source_id"],
            ["evidence.id", "evidence.source_id"],
            name="fk_claim_extraction_evidence_evidence_source",
            ondelete="RESTRICT",
        ),
    )

    op.create_table(
        "claim_extraction_claims",
        sa.Column("claim_extraction_run_id", sa.Integer(), primary_key=True),
        sa.Column("claim_id", sa.Integer(), primary_key=True),
        sa.Column("run_status", sa.String(length=20), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "run_status = 'SUCCEEDED'",
            name="ck_claim_extraction_claims_run_succeeded",
        ),
        sa.CheckConstraint(
            "position >= 0",
            name="ck_claim_extraction_claims_position_non_negative",
        ),
        sa.UniqueConstraint(
            "claim_extraction_run_id",
            "position",
            name="uq_claim_extraction_claims_run_position",
        ),
        sa.ForeignKeyConstraint(
            ["claim_extraction_run_id", "run_status"],
            ["claim_extraction_runs.id", "claim_extraction_runs.status"],
            name="fk_claim_extraction_claims_run_status",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["claim_id"],
            ["claims.id"],
            name="fk_claim_extraction_claims_claim",
            ondelete="RESTRICT",
        ),
    )

    op.create_table(
        "claim_extraction_citations",
        sa.Column("claim_extraction_run_id", sa.Integer(), primary_key=True),
        sa.Column("claim_id", sa.Integer(), primary_key=True),
        sa.Column("evidence_id", sa.Integer(), primary_key=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "position >= 0",
            name="ck_claim_extraction_citations_position_non_negative",
        ),
        sa.UniqueConstraint(
            "claim_extraction_run_id",
            "claim_id",
            "position",
            name="uq_claim_extraction_citations_claim_position",
        ),
        sa.ForeignKeyConstraint(
            ["claim_extraction_run_id", "claim_id"],
            [
                "claim_extraction_claims.claim_extraction_run_id",
                "claim_extraction_claims.claim_id",
            ],
            name="fk_claim_extraction_citations_claim",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["claim_extraction_run_id", "evidence_id"],
            [
                "claim_extraction_evidence.claim_extraction_run_id",
                "claim_extraction_evidence.evidence_id",
            ],
            name="fk_claim_extraction_citations_evidence",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["claim_id", "evidence_id"],
            ["claim_evidence.claim_id", "claim_evidence.evidence_id"],
            name="fk_claim_extraction_citations_claim_evidence",
            ondelete="RESTRICT",
        ),
    )


def downgrade() -> None:
    op.drop_table("claim_extraction_citations")
    op.drop_table("claim_extraction_claims")
    op.drop_table("claim_extraction_evidence")
    op.drop_index("ix_claim_extraction_runs_prompt", table_name="claim_extraction_runs")
    op.drop_index("ix_claim_extraction_runs_source", table_name="claim_extraction_runs")
    op.drop_index(
        "ix_claim_extraction_runs_source_snapshot", table_name="claim_extraction_runs"
    )
    op.drop_index(
        "ix_claim_extraction_runs_source_extraction", table_name="claim_extraction_runs"
    )
    op.drop_table("claim_extraction_runs")
    op.drop_constraint("uq_evidence_id_source", "evidence", type_="unique")
    op.drop_constraint(
        "uq_source_chunks_claim_extraction_provenance",
        "source_chunks",
        type_="unique",
    )
    op.drop_constraint(
        "uq_source_extraction_runs_claim_extraction_provenance",
        "source_extraction_runs",
        type_="unique",
    )
    op.drop_constraint(
        "uq_ai_execution_runs_claim_extraction_provenance",
        "ai_execution_runs",
        type_="unique",
    )
