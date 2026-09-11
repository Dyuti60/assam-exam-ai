"""add source candidate promotions

Revision ID: f6b2d8c4a731
Revises: d4a7c2e9f518
Create Date: 2026-09-11

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f6b2d8c4a731"
down_revision: str | Sequence[str] | None = "d4a7c2e9f518"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add immutable provenance for controlled candidate promotion."""
    op.create_unique_constraint(
        "uq_source_candidates_id_location",
        "source_candidates",
        ["id", "location"],
    )
    op.create_unique_constraint(
        "uq_sources_id_location",
        "sources",
        ["id", "location"],
    )
    op.create_table(
        "source_candidate_promotions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_candidate_id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("location", sa.Text(), nullable=False),
        sa.Column(
            "candidate_approval_status",
            sa.String(length=20),
            nullable=False,
        ),
        sa.Column(
            "candidate_approval_decided_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("candidate_reviewer_note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "btrim(location) <> ''",
            name="ck_source_candidate_promotions_location_non_blank",
        ),
        sa.CheckConstraint(
            "candidate_approval_status = 'APPROVED'",
            name="ck_source_candidate_promotions_approval_status",
        ),
        sa.CheckConstraint(
            "candidate_approval_decided_at IS NOT NULL",
            name="ck_source_candidate_promotions_approval_decided_at",
        ),
        sa.ForeignKeyConstraint(
            ["source_candidate_id", "location"],
            ["source_candidates.id", "source_candidates.location"],
            name="fk_source_candidate_promotions_candidate_location",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_id", "location"],
            ["sources.id", "sources.location"],
            name="fk_source_candidate_promotions_source_location",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_candidate_id",
            name="uq_source_candidate_promotions_source_candidate_id",
        ),
        sa.UniqueConstraint(
            "source_id",
            name="uq_source_candidate_promotions_source_id",
        ),
    )


def downgrade() -> None:
    """Remove only candidate promotion provenance and supporting keys."""
    op.drop_table("source_candidate_promotions")
    op.drop_constraint(
        "uq_sources_id_location",
        "sources",
        type_="unique",
    )
    op.drop_constraint(
        "uq_source_candidates_id_location",
        "source_candidates",
        type_="unique",
    )
