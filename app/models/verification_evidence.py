from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.evidence import Evidence
    from app.models.verification import Verification


class VerificationEvidence(Base):
    __tablename__ = "verification_evidence"
    __table_args__ = (
        CheckConstraint(
            "evidence_role IN ('SUPPORTS', 'CONTRADICTS', 'CONTEXT')",
            name="ck_verification_evidence_role",
        ),
        CheckConstraint(
            "position >= 0",
            name="ck_verification_evidence_position_non_negative",
        ),
        UniqueConstraint(
            "verification_id",
            "position",
            name="uq_verification_evidence_verification_position",
        ),
    )

    verification_id: Mapped[int] = mapped_column(
        ForeignKey("verifications.id", ondelete="CASCADE"),
        primary_key=True,
    )
    evidence_id: Mapped[int] = mapped_column(
        ForeignKey("evidence.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    evidence_role: Mapped[str] = mapped_column(String(20), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    verification: Mapped["Verification"] = relationship(
        back_populates="evidence_links"
    )
    evidence: Mapped["Evidence"] = relationship(
        back_populates="verification_links"
    )
