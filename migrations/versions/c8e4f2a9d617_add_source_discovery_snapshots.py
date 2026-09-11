"""add source discovery snapshots

Revision ID: c8e4f2a9d617
Revises: a5d2c8f1e736
Create Date: 2026-09-11

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c8e4f2a9d617"
down_revision: str | Sequence[str] | None = "a5d2c8f1e736"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create immutable source-discovery run and candidate snapshots."""
    op.create_table(
        "source_discovery_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("adapter_key", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "btrim(query) <> ''",
            name="ck_source_discovery_runs_query_non_blank",
        ),
        sa.CheckConstraint(
            "btrim(adapter_key) <> ''",
            name="ck_source_discovery_runs_adapter_key_non_blank",
        ),
        sa.CheckConstraint(
            "status IN ('SUCCEEDED', 'FAILED')",
            name="ck_source_discovery_runs_status",
        ),
        sa.CheckConstraint(
            "(status = 'SUCCEEDED' AND error_message IS NULL) "
            "OR (status = 'FAILED' AND error_message IS NOT NULL "
            "AND btrim(error_message) <> '')",
            name="ck_source_discovery_runs_lifecycle",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id",
            "status",
            name="uq_source_discovery_runs_id_status",
        ),
    )
    op.create_table(
        "source_candidates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_discovery_run_id", sa.Integer(), nullable=False),
        sa.Column("run_status", sa.String(length=20), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("location", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("publisher", sa.String(length=255), nullable=True),
        sa.Column("snippet", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "run_status = 'SUCCEEDED'",
            name="ck_source_candidates_run_status",
        ),
        sa.CheckConstraint(
            "position >= 0",
            name="ck_source_candidates_position_non_negative",
        ),
        sa.CheckConstraint(
            "btrim(location) <> ''",
            name="ck_source_candidates_location_non_blank",
        ),
        sa.CheckConstraint(
            "title IS NULL OR btrim(title) <> ''",
            name="ck_source_candidates_title_non_blank",
        ),
        sa.CheckConstraint(
            "publisher IS NULL OR btrim(publisher) <> ''",
            name="ck_source_candidates_publisher_non_blank",
        ),
        sa.CheckConstraint(
            "snippet IS NULL OR btrim(snippet) <> ''",
            name="ck_source_candidates_snippet_non_blank",
        ),
        sa.ForeignKeyConstraint(
            ["source_discovery_run_id", "run_status"],
            ["source_discovery_runs.id", "source_discovery_runs.status"],
            name="fk_source_candidates_run_status",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_discovery_run_id",
            "location",
            name="uq_source_candidates_run_location",
        ),
        sa.UniqueConstraint(
            "source_discovery_run_id",
            "position",
            name="uq_source_candidates_run_position",
        ),
    )


def downgrade() -> None:
    """Remove only source-discovery snapshot persistence."""
    op.drop_table("source_candidates")
    op.drop_table("source_discovery_runs")
