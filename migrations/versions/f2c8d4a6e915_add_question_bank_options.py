"""add question bank options and correct answer

Revision ID: f2c8d4a6e915
Revises: e9a4c2f7b163
Create Date: 2026-09-06

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f2c8d4a6e915"
down_revision: str | Sequence[str] | None = "e9a4c2f7b163"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add ordered options and a same-item correct-option reference."""
    op.create_table(
        "question_bank_options",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("question_bank_item_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("option_text", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "position >= 0",
            name="ck_question_bank_options_position_non_negative",
        ),
        sa.CheckConstraint(
            "option_text ~ '\\S'",
            name="ck_question_bank_options_text_non_blank",
        ),
        sa.ForeignKeyConstraint(
            ["question_bank_item_id"],
            ["question_bank_items.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "question_bank_item_id",
            "position",
            name="uq_question_bank_options_item_position",
        ),
        sa.UniqueConstraint(
            "question_bank_item_id",
            "id",
            name="uq_question_bank_options_item_id",
        ),
    )
    op.add_column(
        "question_bank_items",
        sa.Column("correct_option_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_question_bank_items_correct_option",
        "question_bank_items",
        "question_bank_options",
        ["id", "correct_option_id"],
        ["question_bank_item_id", "id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    """Remove correct-answer references and ordered options."""
    op.drop_constraint(
        "fk_question_bank_items_correct_option",
        "question_bank_items",
        type_="foreignkey",
    )
    op.drop_column("question_bank_items", "correct_option_id")
    op.drop_table("question_bank_options")
