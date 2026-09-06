"""add question bank item release lifecycle

Revision ID: b3e7f1a9c462
Revises: a6d1e8c3f247
Create Date: 2026-09-06

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b3e7f1a9c462"
down_revision: str | Sequence[str] | None = "a6d1e8c3f247"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add controlled release and withdrawal state to question candidates."""
    op.add_column(
        "question_bank_items",
        sa.Column(
            "release_status",
            sa.String(length=20),
            server_default="UNRELEASED",
            nullable=False,
        ),
    )
    op.add_column(
        "question_bank_items",
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "question_bank_items",
        sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "question_bank_items",
        sa.Column("release_note", sa.Text(), nullable=True),
    )
    op.create_check_constraint(
        "ck_question_bank_items_release_status",
        "question_bank_items",
        "release_status IN ('UNRELEASED', 'RELEASED', 'WITHDRAWN')",
    )
    op.create_check_constraint(
        "ck_question_bank_items_release_lifecycle",
        "question_bank_items",
        "(release_status = 'UNRELEASED' "
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
    """Remove only the controlled release lifecycle fields and constraints."""
    op.drop_constraint(
        "ck_question_bank_items_release_lifecycle",
        "question_bank_items",
        type_="check",
    )
    op.drop_constraint(
        "ck_question_bank_items_release_status",
        "question_bank_items",
        type_="check",
    )
    op.drop_column("question_bank_items", "release_note")
    op.drop_column("question_bank_items", "withdrawn_at")
    op.drop_column("question_bank_items", "released_at")
    op.drop_column("question_bank_items", "release_status")
