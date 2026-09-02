"""add verification evidence provenance

Revision ID: 92b13f7c4e61
Revises: 774778a8bb78
Create Date: 2026-09-02

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "92b13f7c4e61"
down_revision: str | Sequence[str] | None = "774778a8bb78"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the ordered evidence audit trail for verifications."""
    op.create_table(
        "verification_evidence",
        sa.Column("verification_id", sa.Integer(), nullable=False),
        sa.Column("evidence_id", sa.Integer(), nullable=False),
        sa.Column("evidence_role", sa.String(length=20), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "evidence_role IN ('SUPPORTS', 'CONTRADICTS', 'CONTEXT')",
            name="ck_verification_evidence_role",
        ),
        sa.CheckConstraint(
            "position >= 0",
            name="ck_verification_evidence_position_non_negative",
        ),
        sa.ForeignKeyConstraint(
            ["evidence_id"], ["evidence.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["verification_id"], ["verifications.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("verification_id", "evidence_id"),
        sa.UniqueConstraint(
            "verification_id",
            "position",
            name="uq_verification_evidence_verification_position",
        ),
    )


def downgrade() -> None:
    """Remove the verification evidence audit trail."""
    op.drop_table("verification_evidence")
