from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.question_bank_item import QuestionBankItem


class QuestionBankOption(Base):
    __tablename__ = "question_bank_options"
    __table_args__ = (
        CheckConstraint(
            "position >= 0",
            name="ck_question_bank_options_position_non_negative",
        ),
        CheckConstraint(
            "option_text ~ '\\S'",
            name="ck_question_bank_options_text_non_blank",
        ),
        UniqueConstraint(
            "question_bank_item_id",
            "position",
            name="uq_question_bank_options_item_position",
        ),
        UniqueConstraint(
            "question_bank_item_id",
            "id",
            name="uq_question_bank_options_item_id",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question_bank_item_id: Mapped[int] = mapped_column(
        ForeignKey("question_bank_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    option_text: Mapped[str] = mapped_column(Text, nullable=False)

    question_bank_item: Mapped["QuestionBankItem"] = relationship(
        back_populates="options",
        foreign_keys=[question_bank_item_id],
    )
