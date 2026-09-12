"""add immutable source fetch runs and snapshots

Revision ID: a9d3f6c2e841
Revises: f6b2d8c4a731
Create Date: 2026-09-12

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a9d3f6c2e841"
down_revision: str | Sequence[str] | None = "f6b2d8c4a731"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create terminal fetch attempts and immutable successful snapshots."""
    op.create_table(
        "source_fetch_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("requested_url", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("final_url", sa.Text(), nullable=True),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('SUCCEEDED', 'FAILED')",
            name="ck_source_fetch_runs_status",
        ),
        sa.CheckConstraint(
            "btrim(requested_url) <> ''",
            name="ck_source_fetch_runs_requested_url_non_blank",
        ),
        sa.CheckConstraint(
            "final_url IS NULL OR btrim(final_url) <> ''",
            name="ck_source_fetch_runs_final_url_non_blank",
        ),
        sa.CheckConstraint(
            "http_status IS NULL OR http_status BETWEEN 100 AND 599",
            name="ck_source_fetch_runs_http_status_range",
        ),
        sa.CheckConstraint(
            "error_code IS NULL OR (error_code ~ '^[A-Z][A-Z0-9_]*$' "
            "AND char_length(error_code) <= 100)",
            name="ck_source_fetch_runs_error_code_valid",
        ),
        sa.CheckConstraint(
            "status NOT IN ('SUCCEEDED', 'FAILED') "
            "OR (status = 'SUCCEEDED' "
            "AND final_url IS NOT NULL "
            "AND http_status BETWEEN 200 AND 299 "
            "AND error_code IS NULL) "
            "OR (status = 'FAILED' AND error_code IS NOT NULL)",
            name="ck_source_fetch_runs_terminal_lifecycle",
        ),
        sa.ForeignKeyConstraint(
            ["source_id", "requested_url"],
            ["sources.id", "sources.location"],
            name="fk_source_fetch_runs_source_requested_url",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id",
            "source_id",
            "requested_url",
            "status",
            "final_url",
            name="uq_source_fetch_runs_id_source_url_status",
        ),
    )
    op.create_index(
        "ix_source_fetch_runs_source_id",
        "source_fetch_runs",
        ["source_id"],
    )
    op.create_table(
        "source_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_fetch_run_id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("requested_url", sa.Text(), nullable=False),
        sa.Column("run_status", sa.String(length=20), nullable=False),
        sa.Column("final_url", sa.Text(), nullable=False),
        sa.Column("content_type", sa.String(length=255), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("content_bytes", sa.LargeBinary(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "run_status = 'SUCCEEDED'",
            name="ck_source_snapshots_run_status_succeeded",
        ),
        sa.CheckConstraint(
            "btrim(requested_url) <> ''",
            name="ck_source_snapshots_requested_url_non_blank",
        ),
        sa.CheckConstraint(
            "btrim(final_url) <> ''",
            name="ck_source_snapshots_final_url_non_blank",
        ),
        sa.CheckConstraint(
            "btrim(content_type) <> ''",
            name="ck_source_snapshots_content_type_non_blank",
        ),
        sa.CheckConstraint(
            "byte_size > 0",
            name="ck_source_snapshots_byte_size_positive",
        ),
        sa.CheckConstraint(
            "byte_size = octet_length(content_bytes)",
            name="ck_source_snapshots_byte_size_matches",
        ),
        sa.CheckConstraint(
            "sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_source_snapshots_sha256_lower_hex",
        ),
        sa.ForeignKeyConstraint(
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_fetch_run_id",
            name="uq_source_snapshots_source_fetch_run_id",
        ),
    )
    op.create_index(
        "ix_source_snapshots_source_id",
        "source_snapshots",
        ["source_id"],
    )


def downgrade() -> None:
    """Remove only T-053 fetch persistence and supporting objects."""
    op.drop_index("ix_source_snapshots_source_id", table_name="source_snapshots")
    op.drop_table("source_snapshots")
    op.drop_index("ix_source_fetch_runs_source_id", table_name="source_fetch_runs")
    op.drop_table("source_fetch_runs")
