"""add immutable render-ready content documents

Revision ID: c4d8f2a6b731
Revises: a8c4e2f9b671
Create Date: 2026-09-09

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c4d8f2a6b731"
down_revision: str | Sequence[str] | None = "a8c4e2f9b671"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create immutable render-ready content document snapshots."""
    op.create_table(
        "content_documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("content_package_id", sa.Integer(), nullable=False),
        sa.Column("content_version_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("markdown", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "title ~ '\\S'",
            name="ck_content_documents_title_non_blank",
        ),
        sa.CheckConstraint(
            "markdown ~ '\\S'",
            name="ck_content_documents_markdown_non_blank",
        ),
        sa.CheckConstraint(
            "sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_content_documents_sha256_lower_hex",
        ),
        sa.ForeignKeyConstraint(
            ["content_package_id", "content_version_id"],
            ["content_packages.id", "content_packages.content_version_id"],
            name="fk_content_documents_package_version",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "content_package_id",
            name="uq_content_documents_content_package_id",
        ),
    )


def downgrade() -> None:
    """Remove only immutable content document snapshots."""
    op.drop_table("content_documents")
