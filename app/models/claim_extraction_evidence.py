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
    from app.models.claim_extraction_citation import ClaimExtractionCitation
    from app.models.claim_extraction_run import ClaimExtractionRun
    from app.models.evidence import Evidence


class ClaimExtractionEvidence(Base):
    __tablename__ = "claim_extraction_evidence"
    __table_args__ = (
        CheckConstraint(
            "run_status = 'SUCCEEDED'",
            name="ck_claim_extraction_evidence_run_succeeded",
        ),
        CheckConstraint(
            "position >= 0 AND char_start >= 0 AND char_end > char_start",
            name="ck_claim_extraction_evidence_position_range",
        ),
        CheckConstraint(
            "cited_text_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_claim_extraction_evidence_checksum",
        ),
        UniqueConstraint(
            "claim_extraction_run_id",
            "position",
            name="uq_claim_extraction_evidence_run_position",
        ),
        UniqueConstraint(
            "claim_extraction_run_id",
            "source_chunk_id",
            "char_start",
            "char_end",
            name="uq_claim_extraction_evidence_run_citation",
        ),
        ForeignKeyConstraint(
            [
                "claim_extraction_run_id",
                "source_extraction_run_id",
                "source_snapshot_id",
                "source_id",
                "run_status",
            ],
            [
                "claim_extraction_runs.id",
                "claim_extraction_runs.source_extraction_run_id",
                "claim_extraction_runs.source_snapshot_id",
                "claim_extraction_runs.source_id",
                "claim_extraction_runs.status",
            ],
            name="fk_claim_extraction_evidence_run_provenance",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            [
                "source_chunk_id",
                "source_extraction_run_id",
                "source_snapshot_id",
                "source_id",
            ],
            [
                "source_chunks.id",
                "source_chunks.source_extraction_run_id",
                "source_chunks.source_snapshot_id",
                "source_chunks.source_id",
            ],
            name="fk_claim_extraction_evidence_source_chunk",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["evidence_id", "source_id"],
            ["evidence.id", "evidence.source_id"],
            name="fk_claim_extraction_evidence_evidence_source",
            ondelete="RESTRICT",
        ),
    )

    claim_extraction_run_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    evidence_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_chunk_id: Mapped[int] = mapped_column(Integer, nullable=False)
    source_extraction_run_id: Mapped[int] = mapped_column(Integer, nullable=False)
    source_snapshot_id: Mapped[int] = mapped_column(Integer, nullable=False)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False)
    run_status: Mapped[str] = mapped_column(String(20), nullable=False)
    char_start: Mapped[int] = mapped_column(Integer, nullable=False)
    char_end: Mapped[int] = mapped_column(Integer, nullable=False)
    cited_text_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    claim_extraction_run: Mapped["ClaimExtractionRun"] = relationship(
        back_populates="evidence_links",
        foreign_keys=[
            claim_extraction_run_id,
            source_extraction_run_id,
            source_snapshot_id,
            source_id,
            run_status,
        ],
    )
    evidence: Mapped["Evidence"] = relationship(
        foreign_keys=[evidence_id, source_id],
        overlaps="claim_extraction_run,evidence_links",
    )
    citation_links: Mapped[list["ClaimExtractionCitation"]] = relationship(
        back_populates="evidence_link",
        cascade="all, delete-orphan",
        overlaps="citation_links,claim_link",
    )
