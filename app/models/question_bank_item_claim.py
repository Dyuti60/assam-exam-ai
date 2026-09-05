from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.claim import Claim
    from app.models.question_bank_item import QuestionBankItem


class QuestionBankItemClaim(Base):
    __tablename__ = "question_bank_item_claims"
    __table_args__ = (
        CheckConstraint(
            "position >= 0",
            name="ck_question_bank_item_claims_position_non_negative",
        ),
        UniqueConstraint(
            "question_bank_item_id",
            "position",
            name="uq_question_bank_item_claims_item_position",
        ),
    )

    question_bank_item_id: Mapped[int] = mapped_column(
        ForeignKey("question_bank_items.id", ondelete="CASCADE"),
        primary_key=True,
    )
    claim_id: Mapped[int] = mapped_column(
        ForeignKey("claims.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    question_bank_item: Mapped["QuestionBankItem"] = relationship(
        back_populates="claim_links"
    )
    claim: Mapped["Claim"] = relationship()
