from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import and_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models import (
    Claim,
    Evidence,
    Exam,
    NoteDraft,
    PreviousPaper,
    PreviousQuestion,
    Source,
    SyllabusVersion,
    Topic,
    Verification,
    VerificationEvidence,
    claim_evidence,
)


@dataclass(frozen=True)
class TopicOccurrenceStats:
    exam_paper_count: int
    matched_question_count: int
    matched_paper_count: int
    matched_years: list[int]


class KnowledgeRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add_source(self, source: Source) -> Source:
        self.session.add(source)
        self.session.flush()
        return source

    def get_source(self, source_id: int) -> Source | None:
        return self.session.get(Source, source_id)

    def add_exam(self, exam: Exam) -> Exam:
        self.session.add(exam)
        self.session.flush()
        return exam

    def get_exam(self, exam_id: int) -> Exam | None:
        return self.session.get(Exam, exam_id)

    def add_syllabus_version(
        self,
        syllabus_version: SyllabusVersion,
    ) -> SyllabusVersion:
        self.session.add(syllabus_version)
        self.session.flush()
        return syllabus_version

    def get_syllabus_version(
        self,
        syllabus_version_id: int,
    ) -> SyllabusVersion | None:
        statement = (
            select(SyllabusVersion)
            .options(selectinload(SyllabusVersion.topic_links))
            .where(SyllabusVersion.id == syllabus_version_id)
        )
        return self.session.scalar(statement)

    def get_topic_occurrence_stats(
        self,
        exam_id: int,
        topic_id: int,
    ) -> TopicOccurrenceStats:
        statement = (
            select(
                PreviousPaper.id,
                PreviousPaper.year,
                PreviousQuestion.id,
            )
            .outerjoin(
                PreviousQuestion,
                and_(
                    PreviousQuestion.previous_paper_id == PreviousPaper.id,
                    PreviousQuestion.topic_id == topic_id,
                ),
            )
            .where(PreviousPaper.exam_id == exam_id)
        )
        rows = self.session.execute(statement).all()
        paper_ids = {row[0] for row in rows}
        matched_rows = [row for row in rows if row[2] is not None]
        matched_paper_ids = {row[0] for row in matched_rows}
        return TopicOccurrenceStats(
            exam_paper_count=len(paper_ids),
            matched_question_count=len(matched_rows),
            matched_paper_count=len(matched_paper_ids),
            matched_years=sorted({row[1] for row in matched_rows}),
        )

    def add_previous_paper(self, previous_paper: PreviousPaper) -> PreviousPaper:
        self.session.add(previous_paper)
        self.session.flush()
        return previous_paper

    def get_previous_paper(self, previous_paper_id: int) -> PreviousPaper | None:
        return self.session.get(PreviousPaper, previous_paper_id)

    def add_previous_question(
        self,
        previous_question: PreviousQuestion,
    ) -> PreviousQuestion:
        self.session.add(previous_question)
        self.session.flush()
        return previous_question

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

    def get_note_draft(self, note_draft_id: int) -> NoteDraft | None:
        statement = (
            select(NoteDraft)
            .options(
                joinedload(NoteDraft.topic),
                selectinload(NoteDraft.claim_links),
            )
            .where(NoteDraft.id == note_draft_id)
        )
        return self.session.scalar(statement)

    def get_approved_note_drafts(self) -> list[NoteDraft]:
        statement = (
            select(NoteDraft)
            .options(
                joinedload(NoteDraft.topic),
                selectinload(NoteDraft.claim_links),
            )
            .where(NoteDraft.approval_status == "APPROVED")
            .order_by(NoteDraft.id)
        )
        return list(self.session.scalars(statement))

    def update_note_draft_approval(
        self,
        note_draft: NoteDraft,
        approval_status: str,
        reviewer_note: str | None,
        decided_at: datetime | None,
    ) -> None:
        note_draft.approval_status = approval_status
        note_draft.approval_decided_at = decided_at
        note_draft.reviewer_note = reviewer_note

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
