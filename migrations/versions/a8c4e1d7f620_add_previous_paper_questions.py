"""add previous paper questions

Revision ID: a8c4e1d7f620
Revises: f6b3c9a2d741
Create Date: 2026-09-05

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a8c4e1d7f620"
down_revision: str | Sequence[str] | None = "f6b3c9a2d741"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create sourced previous papers and Topic-linked questions."""
    op.create_table(
        "previous_papers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("exam_id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("year > 0", name="ck_previous_papers_year_positive"),
        sa.ForeignKeyConstraint(
            ["exam_id"],
            ["exams.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["sources.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "exam_id",
            "year",
            "label",
            name="uq_previous_papers_exam_year_label",
        ),
    )
    op.create_table(
        "previous_questions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("previous_paper_id", sa.Integer(), nullable=False),
        sa.Column("topic_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("source_location_reference", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "position >= 0",
            name="ck_previous_questions_position_non_negative",
        ),
        sa.CheckConstraint(
            "length(btrim(question_text)) > 0",
            name="ck_previous_questions_text_non_blank",
        ),
        sa.ForeignKeyConstraint(
            ["previous_paper_id"],
            ["previous_papers.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["topic_id"],
            ["topics.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "previous_paper_id",
            "position",
            name="uq_previous_questions_paper_position",
        ),
    )


def downgrade() -> None:
    """Remove previous questions and papers in dependency order."""
    op.drop_table("previous_questions")
    op.drop_table("previous_papers")
