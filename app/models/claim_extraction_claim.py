from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.claim import Claim
    from app.models.claim_extraction_citation import ClaimExtractionCitation
    from app.models.claim_extraction_run import ClaimExtractionRun


class ClaimExtractionClaim(Base):
    __tablename__ = "claim_extraction_claims"
    __table_args__ = (
        CheckConstraint(
            "run_status = 'SUCCEEDED'",
            name="ck_claim_extraction_claims_run_succeeded",
        ),
        CheckConstraint(
            "position >= 0",
            name="ck_claim_extraction_claims_position_non_negative",
        ),
        UniqueConstraint(
            "claim_extraction_run_id",
            "position",
            name="uq_claim_extraction_claims_run_position",
        ),
        ForeignKeyConstraint(
            ["claim_extraction_run_id", "run_status"],
            ["claim_extraction_runs.id", "claim_extraction_runs.status"],
            name="fk_claim_extraction_claims_run_status",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["claim_id"],
            ["claims.id"],
            name="fk_claim_extraction_claims_claim",
            ondelete="RESTRICT",
        ),
    )

    claim_extraction_run_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    claim_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_status: Mapped[str] = mapped_column(String(20), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    claim_extraction_run: Mapped["ClaimExtractionRun"] = relationship(
        back_populates="claim_links",
        foreign_keys=[claim_extraction_run_id, run_status],
    )
    claim: Mapped["Claim"] = relationship(foreign_keys=[claim_id])
    citation_links: Mapped[list["ClaimExtractionCitation"]] = relationship(
        back_populates="claim_link",
        cascade="all, delete-orphan",
        order_by="ClaimExtractionCitation.position",
        overlaps="evidence_link",
    )
