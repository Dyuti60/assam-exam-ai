"""add PDF artifact release state

Revision ID: a5d2c8f1e736
Revises: f3c8a1d6e924
Create Date: 2026-09-10

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a5d2c8f1e736"
down_revision: str | Sequence[str] | None = "f3c8a1d6e924"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add controlled release metadata to PDF artifacts."""
    op.add_column(
        "pdf_artifacts",
        sa.Column(
            "release_status",
            sa.String(length=20),
            server_default="UNRELEASED",
            nullable=False,
        ),
    )
    op.add_column(
        "pdf_artifacts",
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "pdf_artifacts",
        sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "pdf_artifacts",
        sa.Column("release_note", sa.Text(), nullable=True),
    )
    op.create_check_constraint(
        "ck_pdf_artifacts_release_status",
        "pdf_artifacts",
        "release_status IN ('UNRELEASED', 'RELEASED', 'WITHDRAWN')",
    )
    op.create_check_constraint(
        "ck_pdf_artifacts_release_lifecycle",
        "pdf_artifacts",
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
    """Remove only PDF artifact release metadata."""
    op.drop_constraint(
        "ck_pdf_artifacts_release_lifecycle",
        "pdf_artifacts",
        type_="check",
    )
    op.drop_constraint(
        "ck_pdf_artifacts_release_status",
        "pdf_artifacts",
        type_="check",
    )
    op.drop_column("pdf_artifacts", "release_note")
    op.drop_column("pdf_artifacts", "withdrawn_at")
    op.drop_column("pdf_artifacts", "released_at")
    op.drop_column("pdf_artifacts", "release_status")
