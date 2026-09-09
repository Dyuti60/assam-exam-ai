from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.content_document import ContentDocument


class PdfArtifact(Base):
    __tablename__ = "pdf_artifacts"
    __table_args__ = (
        CheckConstraint(
            "filename ~ '\\S' AND filename LIKE '%.pdf'",
            name="ck_pdf_artifacts_filename_pdf",
        ),
        CheckConstraint(
            "media_type = 'application/pdf'",
            name="ck_pdf_artifacts_media_type",
        ),
        CheckConstraint(
            "byte_size > 0",
            name="ck_pdf_artifacts_byte_size_positive",
        ),
        CheckConstraint(
            "byte_size = octet_length(pdf_bytes)",
            name="ck_pdf_artifacts_byte_size_matches",
        ),
        CheckConstraint(
            "sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_pdf_artifacts_sha256_lower_hex",
        ),
        CheckConstraint(
            "approval_status IN ('DRAFT', 'APPROVED', 'REJECTED')",
            name="ck_pdf_artifacts_approval_status",
        ),
        CheckConstraint(
            "approval_status NOT IN ('DRAFT', 'APPROVED', 'REJECTED') "
            "OR (approval_status = 'DRAFT' "
            "AND approval_decided_at IS NULL "
            "AND reviewer_note IS NULL) "
            "OR (approval_status IN ('APPROVED', 'REJECTED') "
            "AND approval_decided_at IS NOT NULL)",
            name="ck_pdf_artifacts_approval_lifecycle",
        ),
        UniqueConstraint(
            "content_document_id",
            name="uq_pdf_artifacts_content_document_id",
        ),
        ForeignKeyConstraint(
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
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    content_document_id: Mapped[int] = mapped_column(Integer, nullable=False)
    content_package_id: Mapped[int] = mapped_column(Integer, nullable=False)
    content_version_id: Mapped[int] = mapped_column(Integer, nullable=False)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    media_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="application/pdf",
    )
    pdf_bytes: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    approval_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="DRAFT",
        server_default="DRAFT",
    )
    approval_decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
    reviewer_note: Mapped[str | None] = mapped_column(Text)

    content_document: Mapped["ContentDocument"] = relationship(
        back_populates="pdf_artifact",
    )
