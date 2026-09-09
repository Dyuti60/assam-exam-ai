"""add content package release lifecycle

Revision ID: a8c4e2f9b671
Revises: f7b3d1a8c529
Create Date: 2026-09-09

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a8c4e2f9b671"
down_revision: str | Sequence[str] | None = "f7b3d1a8c529"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add controlled release state to content packages."""
    op.add_column(
        "content_packages",
        sa.Column(
            "release_status",
            sa.String(length=20),
            server_default="UNRELEASED",
            nullable=False,
        ),
    )
    op.add_column(
        "content_packages",
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "content_packages",
        sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "content_packages",
        sa.Column("release_note", sa.Text(), nullable=True),
    )
    op.create_check_constraint(
        "ck_content_packages_release_status",
        "content_packages",
        "release_status IN ('UNRELEASED', 'RELEASED', 'WITHDRAWN')",
    )
    op.create_check_constraint(
        "ck_content_packages_release_lifecycle",
        "content_packages",
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
    """Remove only content package release state."""
    op.drop_constraint(
        "ck_content_packages_release_lifecycle",
        "content_packages",
        type_="check",
    )
    op.drop_constraint(
        "ck_content_packages_release_status",
        "content_packages",
        type_="check",
    )
    op.drop_column("content_packages", "release_note")
    op.drop_column("content_packages", "withdrawn_at")
    op.drop_column("content_packages", "released_at")
    op.drop_column("content_packages", "release_status")
