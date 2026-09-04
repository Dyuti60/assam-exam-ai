"""add note draft approval state

Revision ID: d4f8a1c7e592
Revises: b7d9e2f4a610
Create Date: 2026-09-05

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4f8a1c7e592"
down_revision: str | Sequence[str] | None = "b7d9e2f4a610"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add independent human-review state to stored note drafts."""
    op.add_column(
        "note_drafts",
        sa.Column(
            "approval_status",
            sa.String(length=20),
            server_default="DRAFT",
            nullable=False,
        ),
    )
    op.add_column(
        "note_drafts",
        sa.Column("approval_decided_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "note_drafts",
        sa.Column("reviewer_note", sa.Text(), nullable=True),
    )
    op.create_check_constraint(
        "ck_note_drafts_approval_status",
        "note_drafts",
        "approval_status IN ('DRAFT', 'APPROVED', 'REJECTED')",
    )


def downgrade() -> None:
    """Remove independent human-review state from note drafts."""
    op.drop_constraint(
        "ck_note_drafts_approval_status",
        "note_drafts",
        type_="check",
    )
    op.drop_column("note_drafts", "reviewer_note")
    op.drop_column("note_drafts", "approval_decided_at")
    op.drop_column("note_drafts", "approval_status")
