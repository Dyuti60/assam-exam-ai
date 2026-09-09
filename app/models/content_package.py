from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
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
        CheckConstraint(
            "approval_status IN ('DRAFT', 'APPROVED', 'REJECTED')",
            name="ck_content_packages_approval_status",
        ),
        CheckConstraint(
            "(approval_status = 'DRAFT' "
            "AND approval_decided_at IS NULL "
            "AND reviewer_note IS NULL) "
            "OR (approval_status IN ('APPROVED', 'REJECTED') "
            "AND approval_decided_at IS NOT NULL)",
            name="ck_content_packages_approval_lifecycle",
        ),
        CheckConstraint(
            "release_status IN ('UNRELEASED', 'RELEASED', 'WITHDRAWN')",
            name="ck_content_packages_release_status",
        ),
        CheckConstraint(
            "(release_status = 'UNRELEASED' "
            "AND released_at IS NULL "
            "AND withdrawn_at IS NULL "
            "AND release_note IS NULL) "
            "OR (release_status = 'RELEASED' "
            "AND released_at IS NOT NULL "
            "AND withdrawn_at IS NULL "
            "AND approval_status = 'APPROVED') "
            "OR (release_status = 'WITHDRAWN' "
            "AND released_at IS NOT NULL "
            "AND withdrawn_at IS NOT NULL)",
            name="ck_content_packages_release_lifecycle",
        ),
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
    release_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="UNRELEASED",
        server_default="UNRELEASED",
    )
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    release_note: Mapped[str | None] = mapped_column(Text)

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
