from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.content_package import ContentPackage


class ContentDocument(Base):
    __tablename__ = "content_documents"
    __table_args__ = (
        CheckConstraint(
            "title ~ '\\S'",
            name="ck_content_documents_title_non_blank",
        ),
        CheckConstraint(
            "markdown ~ '\\S'",
            name="ck_content_documents_markdown_non_blank",
        ),
        CheckConstraint(
            "sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_content_documents_sha256_lower_hex",
        ),
        UniqueConstraint(
            "content_package_id",
            name="uq_content_documents_content_package_id",
        ),
        ForeignKeyConstraint(
            ["content_package_id", "content_version_id"],
            ["content_packages.id", "content_packages.content_version_id"],
            name="fk_content_documents_package_version",
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    content_package_id: Mapped[int] = mapped_column(Integer, nullable=False)
    content_version_id: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    markdown: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    content_package: Mapped["ContentPackage"] = relationship(
        back_populates="content_document",
    )
