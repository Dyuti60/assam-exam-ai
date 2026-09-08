"""add content package membership snapshots

Revision ID: e2c6f8a1d943
Revises: d9e5b2a7c418
Create Date: 2026-09-08

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e2c6f8a1d943"
down_revision: str | Sequence[str] | None = "d9e5b2a7c418"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add immutable ContentPackage identities and ordered memberships."""
    op.create_unique_constraint(
        "uq_note_drafts_id_content_version",
        "note_drafts",
        ["id", "content_version_id"],
    )
    op.create_unique_constraint(
        "uq_question_bank_items_id_content_version",
        "question_bank_items",
        ["id", "content_version_id"],
    )
    op.create_table(
        "content_packages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("content_version_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["content_version_id"],
            ["content_versions.id"],
            name="fk_content_packages_content_version",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_content_packages"),
        sa.UniqueConstraint(
            "id",
            "content_version_id",
            name="uq_content_packages_id_content_version",
        ),
    )
    op.create_table(
        "content_package_note_drafts",
        sa.Column("content_package_id", sa.Integer(), nullable=False),
        sa.Column("content_version_id", sa.Integer(), nullable=False),
        sa.Column("note_draft_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "position >= 0",
            name="ck_content_package_note_drafts_position_non_negative",
        ),
        sa.ForeignKeyConstraint(
            ["content_package_id", "content_version_id"],
            ["content_packages.id", "content_packages.content_version_id"],
            name="fk_content_package_note_drafts_package",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["note_draft_id", "content_version_id"],
            ["note_drafts.id", "note_drafts.content_version_id"],
            name="fk_content_package_note_drafts_note_draft",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "content_package_id",
            "note_draft_id",
            name="pk_content_package_note_drafts",
        ),
        sa.UniqueConstraint(
            "content_package_id",
            "position",
            name="uq_content_package_note_drafts_package_position",
        ),
    )
    op.create_table(
        "content_package_question_bank_items",
        sa.Column("content_package_id", sa.Integer(), nullable=False),
        sa.Column("content_version_id", sa.Integer(), nullable=False),
        sa.Column("question_bank_item_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "position >= 0",
            name="ck_content_package_question_bank_items_position_non_negative",
        ),
        sa.ForeignKeyConstraint(
            ["content_package_id", "content_version_id"],
            ["content_packages.id", "content_packages.content_version_id"],
            name="fk_content_package_question_bank_items_package",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["question_bank_item_id", "content_version_id"],
            ["question_bank_items.id", "question_bank_items.content_version_id"],
            name="fk_content_package_question_bank_items_item",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "content_package_id",
            "question_bank_item_id",
            name="pk_content_package_question_bank_items",
        ),
        sa.UniqueConstraint(
            "content_package_id",
            "position",
            name="uq_content_package_question_bank_items_package_position",
        ),
    )


def downgrade() -> None:
    """Remove only ContentPackage identities and membership support."""
    op.drop_table("content_package_question_bank_items")
    op.drop_table("content_package_note_drafts")
    op.drop_table("content_packages")
    op.drop_constraint(
        "uq_question_bank_items_id_content_version",
        "question_bank_items",
        type_="unique",
    )
    op.drop_constraint(
        "uq_note_drafts_id_content_version",
        "note_drafts",
        type_="unique",
    )
