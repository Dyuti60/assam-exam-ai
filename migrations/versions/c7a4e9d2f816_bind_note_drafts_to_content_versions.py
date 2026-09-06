"""bind note drafts to content versions

Revision ID: c7a4e9d2f816
Revises: b3e7f1a9c462
Create Date: 2026-09-07

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c7a4e9d2f816"
down_revision: str | Sequence[str] | None = "b3e7f1a9c462"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add legacy-safe, same-Topic ContentVersion ownership to NoteDraft."""
    op.create_unique_constraint(
        "uq_content_versions_id_topic",
        "content_versions",
        ["id", "topic_id"],
    )
    op.add_column(
        "note_drafts",
        sa.Column("content_version_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_note_drafts_content_version_topic",
        "note_drafts",
        "content_versions",
        ["content_version_id", "topic_id"],
        ["id", "topic_id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    """Remove NoteDraft ContentVersion ownership without altering legacy data."""
    op.drop_constraint(
        "fk_note_drafts_content_version_topic",
        "note_drafts",
        type_="foreignkey",
    )
    op.drop_column("note_drafts", "content_version_id")
    op.drop_constraint(
        "uq_content_versions_id_topic",
        "content_versions",
        type_="unique",
    )
