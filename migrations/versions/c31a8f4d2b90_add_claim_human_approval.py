"""add claim human approval state

Revision ID: c31a8f4d2b90
Revises: 92b13f7c4e61
Create Date: 2026-09-04

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c31a8f4d2b90"
down_revision: str | Sequence[str] | None = "92b13f7c4e61"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the explicit human approval state to claims."""
    op.add_column(
        "claims",
        sa.Column(
            "approval_status",
            sa.String(length=20),
            server_default="DRAFT",
            nullable=False,
        ),
    )
    op.add_column(
        "claims",
        sa.Column("approval_decided_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "claims",
        sa.Column("reviewer_note", sa.Text(), nullable=True),
    )
    op.create_check_constraint(
        "ck_claims_approval_status",
        "claims",
        "approval_status IN ('DRAFT', 'APPROVED', 'REJECTED')",
    )


def downgrade() -> None:
    """Remove the explicit human approval state from claims."""
    op.drop_constraint(
        "ck_claims_approval_status",
        "claims",
        type_="check",
    )
    op.drop_column("claims", "reviewer_note")
    op.drop_column("claims", "approval_decided_at")
    op.drop_column("claims", "approval_status")
