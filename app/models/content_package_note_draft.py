from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    ForeignKeyConstraint,
    Integer,
    PrimaryKeyConstraint,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.content_package import ContentPackage


class ContentPackageNoteDraft(Base):
    __tablename__ = "content_package_note_drafts"
    __table_args__ = (
        PrimaryKeyConstraint(
            "content_package_id",
            "note_draft_id",
            name="pk_content_package_note_drafts",
        ),
        UniqueConstraint(
            "content_package_id",
            "position",
            name="uq_content_package_note_drafts_package_position",
        ),
        CheckConstraint(
            "position >= 0",
            name="ck_content_package_note_drafts_position_non_negative",
        ),
        ForeignKeyConstraint(
            ["content_package_id", "content_version_id"],
            ["content_packages.id", "content_packages.content_version_id"],
            name="fk_content_package_note_drafts_package",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["note_draft_id", "content_version_id"],
            ["note_drafts.id", "note_drafts.content_version_id"],
            name="fk_content_package_note_drafts_note_draft",
            ondelete="RESTRICT",
        ),
    )

    content_package_id: Mapped[int] = mapped_column(Integer, nullable=False)
    content_version_id: Mapped[int] = mapped_column(Integer, nullable=False)
    note_draft_id: Mapped[int] = mapped_column(Integer, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    content_package: Mapped["ContentPackage"] = relationship(
        back_populates="note_draft_links",
    )
