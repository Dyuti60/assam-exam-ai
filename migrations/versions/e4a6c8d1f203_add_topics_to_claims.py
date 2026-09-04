"""add topics to claims

Revision ID: e4a6c8d1f203
Revises: c31a8f4d2b90
Create Date: 2026-09-04

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e4a6c8d1f203"
down_revision: str | Sequence[str] | None = "c31a8f4d2b90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create topics and add optional topic classification to claims."""
    op.create_table(
        "topics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.add_column("claims", sa.Column("topic_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_claims_topic_id_topics",
        "claims",
        "topics",
        ["topic_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Remove optional topic classification from claims."""
    op.drop_constraint(
        "fk_claims_topic_id_topics",
        "claims",
        type_="foreignkey",
    )
    op.drop_column("claims", "topic_id")
    op.drop_table("topics")
