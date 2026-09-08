from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.content_package_note_draft import ContentPackageNoteDraft
    from app.models.content_package_question_bank_item import (
        ContentPackageQuestionBankItem,
    )


class ContentPackage(Base):
    __tablename__ = "content_packages"
    __table_args__ = (
        UniqueConstraint(
            "id",
            "content_version_id",
            name="uq_content_packages_id_content_version",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    content_version_id: Mapped[int] = mapped_column(
        ForeignKey("content_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    note_draft_links: Mapped[list["ContentPackageNoteDraft"]] = relationship(
        back_populates="content_package",
        cascade="all, delete-orphan",
        order_by="ContentPackageNoteDraft.position",
    )
    question_bank_item_links: Mapped[
        list["ContentPackageQuestionBankItem"]
    ] = relationship(
        back_populates="content_package",
        cascade="all, delete-orphan",
        order_by="ContentPackageQuestionBankItem.position",
    )
