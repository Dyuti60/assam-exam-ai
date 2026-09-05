"""add content versions

Revision ID: c5e7a9d2b814
Revises: a8c4e1d7f620
Create Date: 2026-09-05

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c5e7a9d2b814"
down_revision: str | Sequence[str] | None = "a8c4e1d7f620"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create canonical ContentVersion identities."""
    op.create_table(
        "content_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("syllabus_version_id", sa.Integer(), nullable=False),
        sa.Column("topic_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "version > 0",
            name="ck_content_versions_version_positive",
        ),
        sa.ForeignKeyConstraint(
            ["syllabus_version_id", "topic_id"],
            [
                "syllabus_version_topics.syllabus_version_id",
                "syllabus_version_topics.topic_id",
            ],
            name="fk_content_versions_syllabus_topic",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "syllabus_version_id",
            "topic_id",
            "version",
            name="uq_content_versions_mapping_version",
        ),
    )


def downgrade() -> None:
    """Remove canonical ContentVersion identities."""
    op.drop_table("content_versions")
