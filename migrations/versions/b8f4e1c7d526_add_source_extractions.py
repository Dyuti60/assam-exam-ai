"""add deterministic source extraction runs and chunks

Revision ID: b8f4e1c7d526
Revises: a9d3f6c2e841
Create Date: 2026-09-12

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b8f4e1c7d526"
down_revision: str | Sequence[str] | None = "a9d3f6c2e841"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create terminal extraction attempts and immutable ordered chunks."""
    op.create_unique_constraint(
        "uq_source_snapshots_id_source_sha256",
        "source_snapshots",
        ["id", "source_id", "sha256"],
    )
    op.create_table(
        "source_extraction_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_sha256", sa.String(length=64), nullable=False),
        sa.Column("extractor_key", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("text_char_count", sa.Integer(), nullable=True),
        sa.Column("text_sha256", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "extractor_key = 'deterministic-text-v1'",
            name="ck_source_extraction_runs_extractor_key",
        ),
        sa.CheckConstraint(
            "status IN ('SUCCEEDED', 'FAILED')",
            name="ck_source_extraction_runs_status",
        ),
        sa.CheckConstraint(
            "error_code IS NULL OR (error_code ~ '^[A-Z][A-Z0-9_]*$' "
            "AND char_length(error_code) <= 100)",
            name="ck_source_extraction_runs_error_code_valid",
        ),
        sa.CheckConstraint(
            "snapshot_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_source_extraction_runs_snapshot_sha256",
        ),
        sa.CheckConstraint(
            "text_sha256 IS NULL OR text_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_source_extraction_runs_text_sha256",
        ),
        sa.CheckConstraint(
            "(status = 'SUCCEEDED' AND error_code IS NULL "
            "AND text_char_count > 0 AND text_sha256 IS NOT NULL) "
            "OR (status = 'FAILED' AND error_code IS NOT NULL "
            "AND text_char_count IS NULL AND text_sha256 IS NULL)",
            name="ck_source_extraction_runs_terminal_metadata",
        ),
        sa.ForeignKeyConstraint(
            ["source_snapshot_id", "source_id", "snapshot_sha256"],
            ["source_snapshots.id", "source_snapshots.source_id", "source_snapshots.sha256"],
            name="fk_source_extraction_runs_snapshot_source_hash",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_snapshot_id",
            "extractor_key",
            name="uq_source_extraction_runs_snapshot_extractor",
        ),
        sa.UniqueConstraint(
            "id",
            "source_snapshot_id",
            "source_id",
            "status",
            name="uq_source_extraction_runs_id_snapshot_source_status",
        ),
    )
    op.create_index(
        "ix_source_extraction_runs_source_id",
        "source_extraction_runs",
        ["source_id"],
    )
    op.create_table(
        "source_chunks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_extraction_run_id", sa.Integer(), nullable=False),
        sa.Column("source_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("run_status", sa.String(length=20), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("char_start", sa.Integer(), nullable=False),
        sa.Column("char_end", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "run_status = 'SUCCEEDED'",
            name="ck_source_chunks_run_status_succeeded",
        ),
        sa.CheckConstraint(
            "position >= 0",
            name="ck_source_chunks_position_non_negative",
        ),
        sa.CheckConstraint(
            "char_start >= 0",
            name="ck_source_chunks_start_non_negative",
        ),
        sa.CheckConstraint(
            "char_end > char_start",
            name="ck_source_chunks_valid_range",
        ),
        sa.CheckConstraint(
            "text ~ '[^[:space:]]'",
            name="ck_source_chunks_text_non_blank",
        ),
        sa.CheckConstraint(
            "char_end - char_start = char_length(text)",
            name="ck_source_chunks_range_matches_text",
        ),
        sa.CheckConstraint(
            "char_length(text) <= 1000",
            name="ck_source_chunks_text_max_length",
        ),
        sa.CheckConstraint(
            "sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_source_chunks_sha256_lower_hex",
        ),
        sa.ForeignKeyConstraint(
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_extraction_run_id",
            "position",
            name="uq_source_chunks_run_position",
        ),
        sa.UniqueConstraint(
            "source_extraction_run_id",
            "char_start",
            "char_end",
            name="uq_source_chunks_run_range",
        ),
    )
    op.create_index(
        "ix_source_chunks_source_snapshot_id",
        "source_chunks",
        ["source_snapshot_id"],
    )
    op.create_index(
        "ix_source_chunks_source_id",
        "source_chunks",
        ["source_id"],
    )


def downgrade() -> None:
    """Remove only T-055 extraction persistence and supporting uniqueness."""
    op.drop_index("ix_source_chunks_source_id", table_name="source_chunks")
    op.drop_index("ix_source_chunks_source_snapshot_id", table_name="source_chunks")
    op.drop_table("source_chunks")
    op.drop_index(
        "ix_source_extraction_runs_source_id",
        table_name="source_extraction_runs",
    )
    op.drop_table("source_extraction_runs")
    op.drop_constraint(
        "uq_source_snapshots_id_source_sha256",
        "source_snapshots",
        type_="unique",
    )
