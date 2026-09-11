"""add source candidate approval state

Revision ID: d4a7c2e9f518
Revises: c8e4f2a9d617
Create Date: 2026-09-11

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4a7c2e9f518"
down_revision: str | Sequence[str] | None = "c8e4f2a9d617"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add independent human-review state to source candidates."""
    op.add_column(
        "source_candidates",
        sa.Column(
            "approval_status",
            sa.String(length=20),
            server_default="DRAFT",
            nullable=False,
        ),
    )
    op.add_column(
        "source_candidates",
        sa.Column(
            "approval_decided_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "source_candidates",
        sa.Column("reviewer_note", sa.Text(), nullable=True),
    )
    op.create_check_constraint(
        "ck_source_candidates_approval_status",
        "source_candidates",
        "approval_status IN ('DRAFT', 'APPROVED', 'REJECTED')",
    )
    op.create_check_constraint(
        "ck_source_candidates_approval_lifecycle",
        "source_candidates",
        "approval_status NOT IN ('DRAFT', 'APPROVED', 'REJECTED') "
        "OR (approval_status = 'DRAFT' "
        "AND approval_decided_at IS NULL "
        "AND reviewer_note IS NULL) "
        "OR (approval_status IN ('APPROVED', 'REJECTED') "
        "AND approval_decided_at IS NOT NULL)",
    )


def downgrade() -> None:
    """Remove only source candidate human-review state."""
    op.drop_constraint(
        "ck_source_candidates_approval_lifecycle",
        "source_candidates",
        type_="check",
    )
    op.drop_constraint(
        "ck_source_candidates_approval_status",
        "source_candidates",
        type_="check",
    )
    op.drop_column("source_candidates", "reviewer_note")
    op.drop_column("source_candidates", "approval_decided_at")
    op.drop_column("source_candidates", "approval_status")
