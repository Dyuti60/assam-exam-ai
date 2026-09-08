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


class ContentPackageQuestionBankItem(Base):
    __tablename__ = "content_package_question_bank_items"
    __table_args__ = (
        PrimaryKeyConstraint(
            "content_package_id",
            "question_bank_item_id",
            name="pk_content_package_question_bank_items",
        ),
        UniqueConstraint(
            "content_package_id",
            "position",
            name="uq_content_package_question_bank_items_package_position",
        ),
        CheckConstraint(
            "position >= 0",
            name="ck_content_package_question_bank_items_position_non_negative",
        ),
        ForeignKeyConstraint(
            ["content_package_id", "content_version_id"],
            ["content_packages.id", "content_packages.content_version_id"],
            name="fk_content_package_question_bank_items_package",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["question_bank_item_id", "content_version_id"],
            ["question_bank_items.id", "question_bank_items.content_version_id"],
            name="fk_content_package_question_bank_items_item",
            ondelete="RESTRICT",
        ),
    )

    content_package_id: Mapped[int] = mapped_column(Integer, nullable=False)
    content_version_id: Mapped[int] = mapped_column(Integer, nullable=False)
    question_bank_item_id: Mapped[int] = mapped_column(Integer, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    content_package: Mapped["ContentPackage"] = relationship(
        back_populates="question_bank_item_links",
    )
