from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import and_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models import (
    Claim,
    ContentDocument,
    ContentPackage,
    ContentPackageNoteDraft,
    ContentPackageQuestionBankItem,
    ContentVersion,
    Evidence,
    Exam,
    NoteDraft,
    PdfArtifact,
    PreviousPaper,
    PreviousQuestion,
    QuestionBankItem,
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

    def add_content_version(
        self,
        content_version: ContentVersion,
    ) -> ContentVersion:
        self.session.add(content_version)
        self.session.flush()
        return content_version

    def get_content_version(self, content_version_id: int) -> ContentVersion | None:
        return self.session.get(ContentVersion, content_version_id)

    def get_content_version_for_package_creation(
        self,
        content_version_id: int,
    ) -> ContentVersion | None:
        statement = (
            select(ContentVersion)
            .where(ContentVersion.id == content_version_id)
            .with_for_update()
        )
        return self.session.scalar(statement)

    def get_released_note_drafts_for_package(
        self,
        content_version_id: int,
    ) -> list[NoteDraft]:
        statement = (
            select(NoteDraft)
            .where(
                NoteDraft.content_version_id == content_version_id,
                NoteDraft.release_status == "RELEASED",
            )
            .order_by(NoteDraft.id)
            .with_for_update()
        )
        return list(self.session.scalars(statement))

    def get_released_question_bank_items_for_package(
        self,
        content_version_id: int,
    ) -> list[QuestionBankItem]:
        statement = (
            select(QuestionBankItem)
            .where(
                QuestionBankItem.content_version_id == content_version_id,
                QuestionBankItem.release_status == "RELEASED",
            )
            .order_by(QuestionBankItem.id)
            .with_for_update()
        )
        return list(self.session.scalars(statement))

    def add_content_package(
        self,
        content_package: ContentPackage,
    ) -> ContentPackage:
        self.session.add(content_package)
        self.session.flush()
        return content_package

    def get_content_document_by_package_id(
        self,
        content_package_id: int,
    ) -> ContentDocument | None:
        statement = select(ContentDocument).where(
            ContentDocument.content_package_id == content_package_id
        )
        return self.session.scalar(statement)

    def get_content_document(
        self,
        content_document_id: int,
    ) -> ContentDocument | None:
        statement = select(ContentDocument).where(
            ContentDocument.id == content_document_id
        )
        with self.session.no_autoflush:
            return self.session.scalar(statement)

    def get_released_content_documents(self) -> list[ContentDocument]:
        statement = (
            select(ContentDocument)
            .where(ContentDocument.release_status == "RELEASED")
            .order_by(ContentDocument.id)
        )
        with self.session.no_autoflush:
            return list(self.session.scalars(statement))

    def get_pdf_artifact_by_document_id(
        self,
        content_document_id: int,
    ) -> PdfArtifact | None:
        statement = select(PdfArtifact).where(
            PdfArtifact.content_document_id == content_document_id
        )
        with self.session.no_autoflush:
            return self.session.scalar(statement)

    def get_pdf_artifact(self, pdf_artifact_id: int) -> PdfArtifact | None:
        statement = select(PdfArtifact).where(PdfArtifact.id == pdf_artifact_id)
        with self.session.no_autoflush:
            return self.session.scalar(statement)

    def add_pdf_artifact(self, pdf_artifact: PdfArtifact) -> PdfArtifact:
        self.session.add(pdf_artifact)
        self.session.flush()
        return pdf_artifact

    def get_content_document_for_update(
        self,
        content_document_id: int,
    ) -> ContentDocument | None:
        statement = (
            select(ContentDocument)
            .where(ContentDocument.id == content_document_id)
            .with_for_update(of=ContentDocument)
        )
        return self.session.scalar(statement)

    def update_content_document_approval(
        self,
        content_document: ContentDocument,
        approval_status: str,
        reviewer_note: str | None,
        decided_at: datetime | None,
    ) -> None:
        content_document.approval_status = approval_status
        content_document.approval_decided_at = decided_at
        content_document.reviewer_note = reviewer_note

    def update_content_document_release(
        self,
        content_document: ContentDocument,
        release_status: str,
        released_at: datetime | None,
        withdrawn_at: datetime | None,
        release_note: str | None,
    ) -> None:
        content_document.release_status = release_status
        content_document.released_at = released_at
        content_document.withdrawn_at = withdrawn_at
        content_document.release_note = release_note

    def add_content_document(
        self,
        content_document: ContentDocument,
    ) -> ContentDocument:
        self.session.add(content_document)
        self.session.flush()
        return content_document

    def get_content_package(self, content_package_id: int) -> ContentPackage | None:
        statement = (
            select(ContentPackage)
            .options(
                selectinload(ContentPackage.note_draft_links),
                selectinload(ContentPackage.question_bank_item_links),
            )
            .where(ContentPackage.id == content_package_id)
        )
        return self.session.scalar(statement)

    def get_released_content_packages(self) -> list[ContentPackage]:
        statement = (
            select(ContentPackage)
            .options(
                selectinload(ContentPackage.note_draft_links),
                selectinload(ContentPackage.question_bank_item_links),
            )
            .where(ContentPackage.release_status == "RELEASED")
            .order_by(ContentPackage.id)
        )
        return list(self.session.scalars(statement))

    def get_content_package_for_update(
        self,
        content_package_id: int,
    ) -> ContentPackage | None:
        statement = (
            select(ContentPackage)
            .options(
                selectinload(ContentPackage.note_draft_links),
                selectinload(ContentPackage.question_bank_item_links),
            )
            .where(ContentPackage.id == content_package_id)
            .with_for_update(of=ContentPackage)
        )
        return self.session.scalar(statement)

    def update_content_package_approval(
        self,
        content_package: ContentPackage,
        approval_status: str,
        reviewer_note: str | None,
        decided_at: datetime | None,
    ) -> None:
        content_package.approval_status = approval_status
        content_package.approval_decided_at = decided_at
        content_package.reviewer_note = reviewer_note

    def update_content_package_release(
        self,
        content_package: ContentPackage,
        release_status: str,
        released_at: datetime | None,
        withdrawn_at: datetime | None,
        release_note: str | None,
    ) -> None:
        content_package.release_status = release_status
        content_package.released_at = released_at
        content_package.withdrawn_at = withdrawn_at
        content_package.release_note = release_note

    def get_content_package_note_drafts(
        self,
        content_package_id: int,
    ) -> list[NoteDraft]:
        statement = (
            select(NoteDraft)
            .join(
                ContentPackageNoteDraft,
                ContentPackageNoteDraft.note_draft_id == NoteDraft.id,
            )
            .options(
                joinedload(NoteDraft.topic),
                selectinload(NoteDraft.claim_links),
            )
            .where(
                ContentPackageNoteDraft.content_package_id == content_package_id
            )
            .order_by(ContentPackageNoteDraft.position)
        )
        return list(self.session.scalars(statement))

    def get_content_package_question_bank_items(
        self,
        content_package_id: int,
    ) -> list[QuestionBankItem]:
        statement = (
            select(QuestionBankItem)
            .join(
                ContentPackageQuestionBankItem,
                ContentPackageQuestionBankItem.question_bank_item_id
                == QuestionBankItem.id,
            )
            .options(
                selectinload(QuestionBankItem.claim_links),
                selectinload(QuestionBankItem.options),
            )
            .where(
                ContentPackageQuestionBankItem.content_package_id
                == content_package_id
            )
            .order_by(ContentPackageQuestionBankItem.position)
        )
        return list(self.session.scalars(statement))

    def get_released_question_bank_items_by_content_version(
        self,
        content_version_id: int,
    ) -> list[QuestionBankItem]:
        statement = (
            select(QuestionBankItem)
            .options(
                selectinload(QuestionBankItem.claim_links),
                selectinload(QuestionBankItem.options),
            )
            .where(
                QuestionBankItem.content_version_id == content_version_id,
                QuestionBankItem.release_status == "RELEASED",
            )
            .order_by(QuestionBankItem.id)
        )
        return list(self.session.scalars(statement))

    def add_question_bank_item(
        self,
        question_bank_item: QuestionBankItem,
    ) -> QuestionBankItem:
        self.session.add(question_bank_item)
        self.session.flush()
        return question_bank_item

    def get_question_bank_item(
        self,
        question_bank_item_id: int,
    ) -> QuestionBankItem | None:
        statement = (
            select(QuestionBankItem)
            .options(
                selectinload(QuestionBankItem.claim_links),
                selectinload(QuestionBankItem.options),
            )
            .where(QuestionBankItem.id == question_bank_item_id)
        )
        return self.session.scalar(statement)

    def get_question_bank_item_for_update(
        self,
        question_bank_item_id: int,
    ) -> QuestionBankItem | None:
        statement = (
            select(QuestionBankItem)
            .options(
                selectinload(QuestionBankItem.claim_links),
                selectinload(QuestionBankItem.options),
            )
            .where(QuestionBankItem.id == question_bank_item_id)
            .with_for_update()
        )
        return self.session.scalar(statement)

    def get_approved_question_bank_items(self) -> list[QuestionBankItem]:
        statement = (
            select(QuestionBankItem)
            .options(
                selectinload(QuestionBankItem.claim_links),
                selectinload(QuestionBankItem.options),
            )
            .where(QuestionBankItem.approval_status == "APPROVED")
            .order_by(QuestionBankItem.id)
        )
        return list(self.session.scalars(statement))

    def get_released_question_bank_items(self) -> list[QuestionBankItem]:
        statement = (
            select(QuestionBankItem)
            .options(
                selectinload(QuestionBankItem.claim_links),
                selectinload(QuestionBankItem.options),
            )
            .where(QuestionBankItem.release_status == "RELEASED")
            .order_by(QuestionBankItem.id)
        )
        return list(self.session.scalars(statement))

    def get_claims_for_question_bank_item(self, claim_ids: list[int]) -> list[Claim]:
        statement = select(Claim).where(Claim.id.in_(claim_ids)).with_for_update()
        return list(self.session.scalars(statement))

    def update_question_bank_item_approval(
        self,
        question_bank_item: QuestionBankItem,
        approval_status: str,
        reviewer_note: str | None,
        decided_at: datetime | None,
    ) -> None:
        question_bank_item.approval_status = approval_status
        question_bank_item.approval_decided_at = decided_at
        question_bank_item.reviewer_note = reviewer_note

    def update_question_bank_item_release(
        self,
        question_bank_item: QuestionBankItem,
        release_status: str,
        released_at: datetime | None,
        withdrawn_at: datetime | None,
        release_note: str | None,
    ) -> None:
        question_bank_item.release_status = release_status
        question_bank_item.released_at = released_at
        question_bank_item.withdrawn_at = withdrawn_at
        question_bank_item.release_note = release_note

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

    def get_note_draft_for_update(self, note_draft_id: int) -> NoteDraft | None:
        statement = (
            select(NoteDraft)
            .options(
                joinedload(NoteDraft.topic),
                selectinload(NoteDraft.claim_links),
            )
            .where(NoteDraft.id == note_draft_id)
            .with_for_update(of=NoteDraft)
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

    def get_released_note_drafts(self) -> list[NoteDraft]:
        statement = (
            select(NoteDraft)
            .options(
                joinedload(NoteDraft.topic),
                selectinload(NoteDraft.claim_links),
            )
            .where(NoteDraft.release_status == "RELEASED")
            .order_by(NoteDraft.id)
        )
        return list(self.session.scalars(statement))

    def get_released_note_drafts_by_content_version(
        self,
        content_version_id: int,
    ) -> list[NoteDraft]:
        statement = (
            select(NoteDraft)
            .options(
                joinedload(NoteDraft.topic),
                selectinload(NoteDraft.claim_links),
            )
            .where(
                NoteDraft.content_version_id == content_version_id,
                NoteDraft.release_status == "RELEASED",
            )
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

    def update_note_draft_release(
        self,
        note_draft: NoteDraft,
        release_status: str,
        released_at: datetime | None,
        withdrawn_at: datetime | None,
        release_note: str | None,
    ) -> None:
        note_draft.release_status = release_status
        note_draft.released_at = released_at
        note_draft.withdrawn_at = withdrawn_at
        note_draft.release_note = release_note

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
