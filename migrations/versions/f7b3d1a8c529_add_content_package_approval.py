"""add content package approval state

Revision ID: f7b3d1a8c529
Revises: e2c6f8a1d943
Create Date: 2026-09-09

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f7b3d1a8c529"
down_revision: str | Sequence[str] | None = "e2c6f8a1d943"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add independent human-review state to content packages."""
    op.add_column(
        "content_packages",
        sa.Column(
            "approval_status",
            sa.String(length=20),
            server_default="DRAFT",
            nullable=False,
        ),
    )
    op.add_column(
        "content_packages",
        sa.Column(
            "approval_decided_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "content_packages",
        sa.Column("reviewer_note", sa.Text(), nullable=True),
    )
    op.create_check_constraint(
        "ck_content_packages_approval_status",
        "content_packages",
        "approval_status IN ('DRAFT', 'APPROVED', 'REJECTED')",
    )
    op.create_check_constraint(
        "ck_content_packages_approval_lifecycle",
        "content_packages",
        "(approval_status = 'DRAFT' "
        "AND approval_decided_at IS NULL "
        "AND reviewer_note IS NULL) "
        "OR (approval_status IN ('APPROVED', 'REJECTED') "
        "AND approval_decided_at IS NOT NULL)",
    )


def downgrade() -> None:
    """Remove only content package human-review state."""
    op.drop_constraint(
        "ck_content_packages_approval_lifecycle",
        "content_packages",
        type_="check",
    )
    op.drop_constraint(
        "ck_content_packages_approval_status",
        "content_packages",
        type_="check",
    )
    op.drop_column("content_packages", "reviewer_note")
    op.drop_column("content_packages", "approval_decided_at")
    op.drop_column("content_packages", "approval_status")
