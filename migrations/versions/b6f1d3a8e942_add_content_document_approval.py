"""add content document approval state

Revision ID: b6f1d3a8e942
Revises: c4d8f2a6b731
Create Date: 2026-09-09

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b6f1d3a8e942"
down_revision: str | Sequence[str] | None = "c4d8f2a6b731"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add independent human review metadata to content documents."""
    op.add_column(
        "content_documents",
        sa.Column(
            "approval_status",
            sa.String(length=20),
            server_default="DRAFT",
            nullable=False,
        ),
    )
    op.add_column(
        "content_documents",
        sa.Column("approval_decided_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "content_documents",
        sa.Column("reviewer_note", sa.Text(), nullable=True),
    )
    op.create_check_constraint(
        "ck_content_documents_approval_status",
        "content_documents",
        "approval_status IN ('DRAFT', 'APPROVED', 'REJECTED')",
    )
    op.create_check_constraint(
        "ck_content_documents_approval_lifecycle",
        "content_documents",
        "approval_status NOT IN ('DRAFT', 'APPROVED', 'REJECTED') "
        "OR (approval_status = 'DRAFT' "
        "AND approval_decided_at IS NULL "
        "AND reviewer_note IS NULL) "
        "OR (approval_status IN ('APPROVED', 'REJECTED') "
        "AND approval_decided_at IS NOT NULL)",
    )


def downgrade() -> None:
    """Remove only content document review metadata."""
    op.drop_constraint(
        "ck_content_documents_approval_lifecycle",
        "content_documents",
        type_="check",
    )
    op.drop_constraint(
        "ck_content_documents_approval_status",
        "content_documents",
        type_="check",
    )
    op.drop_column("content_documents", "reviewer_note")
    op.drop_column("content_documents", "approval_decided_at")
    op.drop_column("content_documents", "approval_status")
