"""add PDF artifact approval state

Revision ID: f3c8a1d6e924
Revises: e7b4c9d2a615
Create Date: 2026-09-09

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f3c8a1d6e924"
down_revision: str | Sequence[str] | None = "e7b4c9d2a615"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add independent human review metadata to PDF artifacts."""
    op.add_column(
        "pdf_artifacts",
        sa.Column(
            "approval_status",
            sa.String(length=20),
            server_default="DRAFT",
            nullable=False,
        ),
    )
    op.add_column(
        "pdf_artifacts",
        sa.Column("approval_decided_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "pdf_artifacts",
        sa.Column("reviewer_note", sa.Text(), nullable=True),
    )
    op.create_check_constraint(
        "ck_pdf_artifacts_approval_status",
        "pdf_artifacts",
        "approval_status IN ('DRAFT', 'APPROVED', 'REJECTED')",
    )
    op.create_check_constraint(
        "ck_pdf_artifacts_approval_lifecycle",
        "pdf_artifacts",
        "approval_status NOT IN ('DRAFT', 'APPROVED', 'REJECTED') "
        "OR (approval_status = 'DRAFT' "
        "AND approval_decided_at IS NULL "
        "AND reviewer_note IS NULL) "
        "OR (approval_status IN ('APPROVED', 'REJECTED') "
        "AND approval_decided_at IS NOT NULL)",
    )


def downgrade() -> None:
    """Remove only PDF artifact review metadata."""
    op.drop_constraint(
        "ck_pdf_artifacts_approval_lifecycle",
        "pdf_artifacts",
        type_="check",
    )
    op.drop_constraint(
        "ck_pdf_artifacts_approval_status",
        "pdf_artifacts",
        type_="check",
    )
    op.drop_column("pdf_artifacts", "reviewer_note")
    op.drop_column("pdf_artifacts", "approval_decided_at")
    op.drop_column("pdf_artifacts", "approval_status")
