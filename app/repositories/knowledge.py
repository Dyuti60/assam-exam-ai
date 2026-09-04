from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models import (
    Claim,
    Evidence,
    NoteDraft,
    Source,
    Topic,
    Verification,
    VerificationEvidence,
    claim_evidence,
)


class KnowledgeRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add_source(self, source: Source) -> Source:
        self.session.add(source)
        self.session.flush()
        return source

    def get_source(self, source_id: int) -> Source | None:
        return self.session.get(Source, source_id)

    def add_topic(self, topic: Topic) -> Topic:
        self.session.add(topic)
        self.session.flush()
        return topic

    def get_topic(self, topic_id: int) -> Topic | None:
        return self.session.get(Topic, topic_id)

    def add_evidence(self, evidence: Evidence) -> Evidence:
        self.session.add(evidence)
        self.session.flush()
        return evidence

    def get_evidence(self, evidence_id: int) -> Evidence | None:
        return self.session.get(Evidence, evidence_id)

    def add_claim(self, claim: Claim) -> Claim:
        self.session.add(claim)
        self.session.flush()
        return claim

    def get_claim(self, claim_id: int) -> Claim | None:
        statement = (
            select(Claim)
            .options(selectinload(Claim.relevant_evidence))
            .execution_options(populate_existing=True)
            .where(Claim.id == claim_id)
        )
        return self.session.scalar(statement)

    def get_approved_claims(self) -> list[Claim]:
        statement = (
            select(Claim)
            .options(selectinload(Claim.relevant_evidence))
            .where(Claim.approval_status == "APPROVED")
            .order_by(Claim.id)
        )
        return list(self.session.scalars(statement))

    def get_approved_claims_by_topic(self, topic_id: int) -> list[Claim]:
        statement = (
            select(Claim)
            .options(selectinload(Claim.relevant_evidence))
            .where(
                Claim.topic_id == topic_id,
                Claim.approval_status == "APPROVED",
            )
            .order_by(Claim.id)
        )
        return list(self.session.scalars(statement))

    def add_note_draft(self, note_draft: NoteDraft) -> NoteDraft:
        self.session.add(note_draft)
        self.session.flush()
        return note_draft

    def link_claim_evidence(self, claim_id: int, evidence_id: int) -> None:
        statement = (
            insert(claim_evidence)
            .values(claim_id=claim_id, evidence_id=evidence_id)
            .on_conflict_do_nothing(
                index_elements=[
                    claim_evidence.c.claim_id,
                    claim_evidence.c.evidence_id,
                ]
            )
        )
        self.session.execute(statement)

    def update_claim_approval(
        self,
        claim: Claim,
        approval_status: str,
        reviewer_note: str | None,
        decided_at: datetime | None,
    ) -> None:
        claim.approval_status = approval_status
        claim.approval_decided_at = decided_at
        claim.reviewer_note = reviewer_note

    def add_verification(self, verification: Verification) -> Verification:
        self.session.add(verification)
        self.session.flush()
        return verification

    def update_claim_verification_summary(
        self,
        claim: Claim,
        verification: Verification,
    ) -> None:
        claim.verification_status = verification.verdict
        claim.confidence = verification.confidence
        claim.last_verified_at = verification.created_at

    def get_verification(self, verification_id: int) -> Verification | None:
        statement = (
            select(Verification)
            .options(
                joinedload(Verification.claim),
                selectinload(Verification.evidence_links).joinedload(
                    VerificationEvidence.evidence
                ),
            )
            .where(Verification.id == verification_id)
        )
        return self.session.scalar(statement)
