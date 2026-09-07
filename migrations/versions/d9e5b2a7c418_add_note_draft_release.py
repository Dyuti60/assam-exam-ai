"""add note draft release lifecycle

Revision ID: d9e5b2a7c418
Revises: c7a4e9d2f816
Create Date: 2026-09-07

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d9e5b2a7c418"
down_revision: str | Sequence[str] | None = "c7a4e9d2f816"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add controlled release and withdrawal state to note drafts."""
    op.add_column(
        "note_drafts",
        sa.Column(
            "release_status",
            sa.String(length=20),
            server_default="UNRELEASED",
            nullable=False,
        ),
    )
    op.add_column(
        "note_drafts",
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "note_drafts",
        sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "note_drafts",
        sa.Column("release_note", sa.Text(), nullable=True),
    )
    op.create_check_constraint(
        "ck_note_drafts_release_status",
        "note_drafts",
        "release_status IN ('UNRELEASED', 'RELEASED', 'WITHDRAWN')",
    )
    op.create_check_constraint(
        "ck_note_drafts_release_lifecycle",
        "note_drafts",
        "(release_status = 'UNRELEASED' "
        "AND released_at IS NULL "
        "AND withdrawn_at IS NULL "
        "AND release_note IS NULL) "
        "OR (release_status = 'RELEASED' "
        "AND released_at IS NOT NULL "
        "AND withdrawn_at IS NULL "
        "AND approval_status = 'APPROVED' "
        "AND content_version_id IS NOT NULL) "
        "OR (release_status = 'WITHDRAWN' "
        "AND released_at IS NOT NULL "
        "AND withdrawn_at IS NOT NULL "
        "AND content_version_id IS NOT NULL)",
    )
    op.alter_column(
        "note_drafts",
        "release_status",
        server_default=None,
    )


def downgrade() -> None:
    """Remove only the controlled NoteDraft release lifecycle."""
    op.drop_constraint(
        "ck_note_drafts_release_lifecycle",
        "note_drafts",
        type_="check",
    )
    op.drop_constraint(
        "ck_note_drafts_release_status",
        "note_drafts",
        type_="check",
    )
    op.drop_column("note_drafts", "release_note")
    op.drop_column("note_drafts", "withdrawn_at")
    op.drop_column("note_drafts", "released_at")
    op.drop_column("note_drafts", "release_status")
