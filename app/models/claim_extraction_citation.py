from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.claim_extraction_claim import ClaimExtractionClaim
    from app.models.claim_extraction_evidence import ClaimExtractionEvidence


class ClaimExtractionCitation(Base):
    __tablename__ = "claim_extraction_citations"
    __table_args__ = (
        CheckConstraint(
            "position >= 0",
            name="ck_claim_extraction_citations_position_non_negative",
        ),
        UniqueConstraint(
            "claim_extraction_run_id",
            "claim_id",
            "position",
            name="uq_claim_extraction_citations_claim_position",
        ),
        ForeignKeyConstraint(
            ["claim_extraction_run_id", "claim_id"],
            [
                "claim_extraction_claims.claim_extraction_run_id",
                "claim_extraction_claims.claim_id",
            ],
            name="fk_claim_extraction_citations_claim",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["claim_extraction_run_id", "evidence_id"],
            [
                "claim_extraction_evidence.claim_extraction_run_id",
                "claim_extraction_evidence.evidence_id",
            ],
            name="fk_claim_extraction_citations_evidence",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["claim_id", "evidence_id"],
            ["claim_evidence.claim_id", "claim_evidence.evidence_id"],
            name="fk_claim_extraction_citations_claim_evidence",
            ondelete="RESTRICT",
        ),
    )

    claim_extraction_run_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    claim_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    evidence_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    claim_link: Mapped["ClaimExtractionClaim"] = relationship(
        back_populates="citation_links",
        foreign_keys=[claim_extraction_run_id, claim_id],
    )
    evidence_link: Mapped["ClaimExtractionEvidence"] = relationship(
        back_populates="citation_links",
        foreign_keys=[claim_extraction_run_id, evidence_id],
        overlaps="citation_links,claim_link",
    )
