"""add question bank item approval state

Revision ID: a6d1e8c3f247
Revises: f2c8d4a6e915
Create Date: 2026-09-06

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a6d1e8c3f247"
down_revision: str | Sequence[str] | None = "f2c8d4a6e915"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add independent human-review state to question candidates."""
    op.add_column(
        "question_bank_items",
        sa.Column("approval_status", sa.String(length=20), server_default="DRAFT", nullable=False),
    )
    op.add_column(
        "question_bank_items",
        sa.Column("approval_decided_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "question_bank_items",
        sa.Column("reviewer_note", sa.Text(), nullable=True),
    )
    op.create_check_constraint(
        "ck_question_bank_items_approval_status",
        "question_bank_items",
        "approval_status IN ('DRAFT', 'APPROVED', 'REJECTED')",
    )


def downgrade() -> None:
    """Remove independent human-review state from question candidates."""
    op.drop_constraint(
        "ck_question_bank_items_approval_status",
        "question_bank_items",
        type_="check",
    )
    op.drop_column("question_bank_items", "reviewer_note")
    op.drop_column("question_bank_items", "approval_decided_at")
    op.drop_column("question_bank_items", "approval_status")
