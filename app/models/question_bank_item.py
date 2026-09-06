from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.question_bank_item_claim import QuestionBankItemClaim
    from app.models.question_bank_option import QuestionBankOption


class QuestionBankItem(Base):
    __tablename__ = "question_bank_items"
    __table_args__ = (
        CheckConstraint(
            "question_text ~ '\\S'",
            name="ck_question_bank_items_question_text_non_blank",
        ),
        CheckConstraint(
            "explanation ~ '\\S'",
            name="ck_question_bank_items_explanation_non_blank",
        ),
        CheckConstraint(
            "difficulty IN ('EASY', 'MEDIUM', 'HARD')",
            name="ck_question_bank_items_difficulty",
        ),
        CheckConstraint(
            "approval_status IN ('DRAFT', 'APPROVED', 'REJECTED')",
            name="ck_question_bank_items_approval_status",
        ),
        ForeignKeyConstraint(
            ["id", "correct_option_id"],
            [
                "question_bank_options.question_bank_item_id",
                "question_bank_options.id",
            ],
            name="fk_question_bank_items_correct_option",
            ondelete="RESTRICT",
            use_alter=True,
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement="ignore_fk",
    )
    content_version_id: Mapped[int] = mapped_column(
        ForeignKey("content_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    difficulty: Mapped[str] = mapped_column(String(10), nullable=False)
    correct_option_id: Mapped[int | None] = mapped_column(Integer)
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    claim_links: Mapped[list["QuestionBankItemClaim"]] = relationship(
        back_populates="question_bank_item",
        cascade="all, delete-orphan",
        order_by="QuestionBankItemClaim.position",
    )
    options: Mapped[list["QuestionBankOption"]] = relationship(
        back_populates="question_bank_item",
        cascade="all, delete-orphan",
        foreign_keys="QuestionBankOption.question_bank_item_id",
        order_by="QuestionBankOption.position",
    )
