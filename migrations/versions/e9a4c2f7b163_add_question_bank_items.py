"""add question bank items

Revision ID: e9a4c2f7b163
Revises: c5e7a9d2b814
Create Date: 2026-09-05

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e9a4c2f7b163"
down_revision: str | Sequence[str] | None = "c5e7a9d2b814"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create internal question candidates and ordered Claim provenance."""
    op.create_table(
        "question_bank_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("content_version_id", sa.Integer(), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("difficulty", sa.String(length=10), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "question_text ~ '\\S'",
            name="ck_question_bank_items_question_text_non_blank",
        ),
        sa.CheckConstraint(
            "explanation ~ '\\S'",
            name="ck_question_bank_items_explanation_non_blank",
        ),
        sa.CheckConstraint(
            "difficulty IN ('EASY', 'MEDIUM', 'HARD')",
            name="ck_question_bank_items_difficulty",
        ),
        sa.ForeignKeyConstraint(
            ["content_version_id"],
            ["content_versions.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "question_bank_item_claims",
        sa.Column("question_bank_item_id", sa.Integer(), nullable=False),
        sa.Column("claim_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "position >= 0",
            name="ck_question_bank_item_claims_position_non_negative",
        ),
        sa.ForeignKeyConstraint(
            ["question_bank_item_id"],
            ["question_bank_items.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["claim_id"],
            ["claims.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("question_bank_item_id", "claim_id"),
        sa.UniqueConstraint(
            "question_bank_item_id",
            "position",
            name="uq_question_bank_item_claims_item_position",
        ),
    )


def downgrade() -> None:
    """Remove question candidates and their Claim provenance."""
    op.drop_table("question_bank_item_claims")
    op.drop_table("question_bank_items")
