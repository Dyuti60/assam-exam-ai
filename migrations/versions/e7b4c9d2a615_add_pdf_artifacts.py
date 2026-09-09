"""add immutable deterministic PDF artifacts

Revision ID: e7b4c9d2a615
Revises: d1a7c4e9f263
Create Date: 2026-09-09

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e7b4c9d2a615"
down_revision: str | Sequence[str] | None = "d1a7c4e9f263"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create immutable PDF artifacts with exact document ownership."""
    op.create_unique_constraint(
        "uq_content_documents_id_package_version",
        "content_documents",
        ["id", "content_package_id", "content_version_id"],
    )
    op.create_table(
        "pdf_artifacts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("content_document_id", sa.Integer(), nullable=False),
        sa.Column("content_package_id", sa.Integer(), nullable=False),
        sa.Column("content_version_id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("media_type", sa.String(length=50), nullable=False),
        sa.Column("pdf_bytes", sa.LargeBinary(), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "filename ~ '\\S' AND filename LIKE '%.pdf'",
            name="ck_pdf_artifacts_filename_pdf",
        ),
        sa.CheckConstraint(
            "media_type = 'application/pdf'",
            name="ck_pdf_artifacts_media_type",
        ),
        sa.CheckConstraint(
            "byte_size > 0",
            name="ck_pdf_artifacts_byte_size_positive",
        ),
        sa.CheckConstraint(
            "byte_size = octet_length(pdf_bytes)",
            name="ck_pdf_artifacts_byte_size_matches",
        ),
        sa.CheckConstraint(
            "sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_pdf_artifacts_sha256_lower_hex",
        ),
        sa.ForeignKeyConstraint(
            [
                "content_document_id",
                "content_package_id",
                "content_version_id",
            ],
            [
                "content_documents.id",
                "content_documents.content_package_id",
                "content_documents.content_version_id",
            ],
            name="fk_pdf_artifacts_document_package_version",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "content_document_id",
            name="uq_pdf_artifacts_content_document_id",
        ),
    )


def downgrade() -> None:
    """Remove only PDF artifacts and their supporting document key."""
    op.drop_table("pdf_artifacts")
    op.drop_constraint(
        "uq_content_documents_id_package_version",
        "content_documents",
        type_="unique",
    )
