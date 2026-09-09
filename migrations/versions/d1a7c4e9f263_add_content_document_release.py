"""add content document release state

Revision ID: d1a7c4e9f263
Revises: b6f1d3a8e942
Create Date: 2026-09-09

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d1a7c4e9f263"
down_revision: str | Sequence[str] | None = "b6f1d3a8e942"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add controlled release metadata to content documents."""
    op.add_column(
        "content_documents",
        sa.Column(
            "release_status",
            sa.String(length=20),
            server_default="UNRELEASED",
            nullable=False,
        ),
    )
    op.add_column(
        "content_documents",
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "content_documents",
        sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "content_documents",
        sa.Column("release_note", sa.Text(), nullable=True),
    )
    op.create_check_constraint(
        "ck_content_documents_release_status",
        "content_documents",
        "release_status IN ('UNRELEASED', 'RELEASED', 'WITHDRAWN')",
    )
    op.create_check_constraint(
        "ck_content_documents_release_lifecycle",
        "content_documents",
        "release_status NOT IN ('UNRELEASED', 'RELEASED', 'WITHDRAWN') "
        "OR (release_status = 'UNRELEASED' "
        "AND released_at IS NULL "
        "AND withdrawn_at IS NULL "
        "AND release_note IS NULL) "
        "OR (release_status = 'RELEASED' "
        "AND released_at IS NOT NULL "
        "AND withdrawn_at IS NULL "
        "AND approval_status = 'APPROVED') "
        "OR (release_status = 'WITHDRAWN' "
        "AND released_at IS NOT NULL "
        "AND withdrawn_at IS NOT NULL)",
    )


def downgrade() -> None:
    """Remove only content document release metadata."""
    op.drop_constraint(
        "ck_content_documents_release_lifecycle",
        "content_documents",
        type_="check",
    )
    op.drop_constraint(
        "ck_content_documents_release_status",
        "content_documents",
        type_="check",
    )
    op.drop_column("content_documents", "release_note")
    op.drop_column("content_documents", "withdrawn_at")
    op.drop_column("content_documents", "released_at")
    op.drop_column("content_documents", "release_status")
