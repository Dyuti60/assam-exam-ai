from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.question_bank_item_claim import QuestionBankItemClaim


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
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    content_version_id: Mapped[int] = mapped_column(
        ForeignKey("content_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    difficulty: Mapped[str] = mapped_column(String(10), nullable=False)
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
