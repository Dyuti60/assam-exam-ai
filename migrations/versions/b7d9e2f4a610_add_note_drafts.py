"""add note drafts

Revision ID: b7d9e2f4a610
Revises: e4a6c8d1f203
Create Date: 2026-09-05

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7d9e2f4a610"
down_revision: str | Sequence[str] | None = "e4a6c8d1f203"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create internal note drafts and their ordered Claim provenance."""
    op.create_table(
        "note_drafts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("topic_id", sa.Integer(), nullable=False),
        sa.Column("markdown", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["topic_id"],
            ["topics.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "note_draft_claims",
        sa.Column("note_draft_id", sa.Integer(), nullable=False),
        sa.Column("claim_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "position >= 0",
            name="ck_note_draft_claims_position_non_negative",
        ),
        sa.ForeignKeyConstraint(
            ["claim_id"],
            ["claims.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["note_draft_id"],
            ["note_drafts.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("note_draft_id", "claim_id"),
        sa.UniqueConstraint(
            "note_draft_id",
            "position",
            name="uq_note_draft_claims_draft_position",
        ),
    )


def downgrade() -> None:
    """Remove internal note drafts and their Claim provenance."""
    op.drop_table("note_draft_claims")
    op.drop_table("note_drafts")
