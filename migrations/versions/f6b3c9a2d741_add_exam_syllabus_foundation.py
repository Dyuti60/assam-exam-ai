"""add exam syllabus foundation

Revision ID: f6b3c9a2d741
Revises: d4f8a1c7e592
Create Date: 2026-09-05

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f6b3c9a2d741"
down_revision: str | Sequence[str] | None = "d4f8a1c7e592"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create exams, sourced syllabus versions, and ordered Topic mappings."""
    op.create_table(
        "exams",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_exams_code"),
        sa.UniqueConstraint("name", name="uq_exams_name"),
    )
    op.create_table(
        "syllabus_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("exam_id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
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
            "label",
            name="uq_syllabus_versions_exam_label",
        ),
    )
    op.create_table(
        "syllabus_version_topics",
        sa.Column("syllabus_version_id", sa.Integer(), nullable=False),
        sa.Column("topic_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "position >= 0",
            name="ck_syllabus_version_topics_position_non_negative",
        ),
        sa.ForeignKeyConstraint(
            ["syllabus_version_id"],
            ["syllabus_versions.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["topic_id"],
            ["topics.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("syllabus_version_id", "topic_id"),
        sa.UniqueConstraint(
            "syllabus_version_id",
            "position",
            name="uq_syllabus_version_topics_version_position",
        ),
    )


def downgrade() -> None:
    """Remove ordered syllabus mappings, versions, and exams."""
    op.drop_table("syllabus_version_topics")
    op.drop_table("syllabus_versions")
    op.drop_table("exams")
