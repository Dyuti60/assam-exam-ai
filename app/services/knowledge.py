from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    Claim,
    Evidence,
    Exam,
    NoteDraft,
    NoteDraftClaim,
    Source,
    SyllabusVersion,
    SyllabusVersionTopic,
    Topic,
    Verification,
    VerificationEvidence,
)
from app.repositories import KnowledgeRepository
from app.schemas.knowledge import (
    ClaimApprovalCreate,
    ClaimApprovalStatus,
    ClaimCreate,
    ClaimResponse,
    EvidenceCreate,
    ExamCreate,
    ExamResponse,
    NoteDraftApprovalCreate,
    NoteDraftPreviewResponse,
    NoteDraftResponse,
    SourceCreate,
    SyllabusVersionCreate,
    SyllabusVersionResponse,
    TopicCreate,
    VerificationCreate,
    VerificationEvidenceResponse,
    VerificationResponse,
)


class ResourceNotFoundError(Exception):
    def __init__(self, resource: str, resource_id: int) -> None:
        self.resource = resource
        self.resource_id = resource_id
        super().__init__(f"{resource} {resource_id} not found")


class ResourceConflictError(Exception):
    pass


class KnowledgeService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = KnowledgeRepository(session)

    def create_source(self, request: SourceCreate) -> Source:
        source = Source(**request.model_dump())
        return self._commit(self.repository.add_source(source))

    def create_exam(self, request: ExamCreate) -> ExamResponse:
        exam = Exam(**request.model_dump())
        try:
            self._commit(self.repository.add_exam(exam))
        except IntegrityError as error:
            constraint_name = getattr(error.orig.diag, "constraint_name", None)
            if constraint_name == "uq_exams_code":
                detail = f"Exam code '{request.code}' already exists"
            elif constraint_name == "uq_exams_name":
                detail = f"Exam name '{request.name}' already exists"
            else:
                raise
            raise ResourceConflictError(detail) from error
        return ExamResponse.model_validate(exam)

    def create_syllabus_version(
        self,
        request: SyllabusVersionCreate,
    ) -> SyllabusVersionResponse:
        if self.repository.get_exam(request.exam_id) is None:
            raise ResourceNotFoundError("Exam", request.exam_id)
        if self.repository.get_source(request.source_id) is None:
            raise ResourceNotFoundError("Source", request.source_id)

        topics = []
        for topic_id in request.topic_ids:
            topic = self.repository.get_topic(topic_id)
            if topic is None:
                raise ResourceNotFoundError("Topic", topic_id)
            topics.append(topic)

        syllabus_version = SyllabusVersion(
            exam_id=request.exam_id,
            source_id=request.source_id,
            label=request.label,
            topic_links=[
                SyllabusVersionTopic(topic=topic, position=position)
                for position, topic in enumerate(topics)
            ],
        )
        try:
            self._commit(self.repository.add_syllabus_version(syllabus_version))
        except IntegrityError as error:
            constraint_name = getattr(error.orig.diag, "constraint_name", None)
            if constraint_name != "uq_syllabus_versions_exam_label":
                raise
            raise ResourceConflictError(
                f"SyllabusVersion label '{request.label}' already exists "
                f"for Exam {request.exam_id}"
            ) from error
        return SyllabusVersionResponse(
            id=syllabus_version.id,
            exam_id=syllabus_version.exam_id,
            source_id=syllabus_version.source_id,
            label=syllabus_version.label,
            created_at=syllabus_version.created_at,
            topic_ids=[link.topic_id for link in syllabus_version.topic_links],
        )

    def create_topic(self, request: TopicCreate) -> Topic:
        topic = Topic(**request.model_dump())
        try:
            return self._commit(self.repository.add_topic(topic))
        except IntegrityError as error:
            self.session.rollback()
            raise ResourceConflictError(
                f"Topic name '{request.name}' already exists"
            ) from error

    def create_evidence(self, request: EvidenceCreate) -> Evidence:
        if self.repository.get_source(request.source_id) is None:
            raise ResourceNotFoundError("Source", request.source_id)
        evidence = Evidence(**request.model_dump())
        return self._commit(self.repository.add_evidence(evidence))

    def get_evidence(self, evidence_id: int) -> Evidence:
        evidence = self.repository.get_evidence(evidence_id)
        if evidence is None:
            raise ResourceNotFoundError("Evidence", evidence_id)
        return evidence

    def create_claim(self, request: ClaimCreate) -> Claim:
        if request.topic_id is not None and self.repository.get_topic(
            request.topic_id
        ) is None:
            raise ResourceNotFoundError("Topic", request.topic_id)
        claim = Claim(**request.model_dump())
        return self._commit(self.repository.add_claim(claim))

    def get_claim(self, claim_id: int) -> ClaimResponse:
        claim = self.repository.get_claim(claim_id)
        if claim is None:
            raise ResourceNotFoundError("Claim", claim_id)
        return self._claim_response(claim)

    def get_approved_claims(self) -> list[ClaimResponse]:
        return [
            self._claim_response(claim)
            for claim in self.repository.get_approved_claims()
        ]

    def get_approved_claims_by_topic(self, topic_id: int) -> list[ClaimResponse]:
        if self.repository.get_topic(topic_id) is None:
            raise ResourceNotFoundError("Topic", topic_id)
        return [
            self._claim_response(claim)
            for claim in self.repository.get_approved_claims_by_topic(topic_id)
        ]

    def create_note_draft_preview(self, topic_id: int) -> NoteDraftPreviewResponse:
        topic = self.repository.get_topic(topic_id)
        if topic is None:
            raise ResourceNotFoundError("Topic", topic_id)
        claims = self.repository.get_approved_claims_by_topic(topic_id)
        if not claims:
            raise ResourceConflictError(
                f"Topic {topic_id} has no approved Claims"
            )
        return NoteDraftPreviewResponse(
            topic_id=topic.id,
            topic_name=topic.name,
            claim_ids=[claim.id for claim in claims],
            markdown=self._render_note_markdown(topic.name, claims),
        )

    def create_note_draft(self, topic_id: int) -> NoteDraftResponse:
        topic = self.repository.get_topic(topic_id)
        if topic is None:
            raise ResourceNotFoundError("Topic", topic_id)
        claims = self.repository.get_approved_claims_by_topic(topic_id)
        if not claims:
            raise ResourceConflictError(
                f"Topic {topic_id} has no approved Claims"
            )
        note_draft = NoteDraft(
            topic_id=topic.id,
            markdown=self._render_note_markdown(topic.name, claims),
            claim_links=[
                NoteDraftClaim(claim=claim, position=position)
                for position, claim in enumerate(claims)
            ],
        )
        self._commit_note_draft(note_draft)
        return NoteDraftResponse(
            id=note_draft.id,
            topic_id=topic.id,
            topic_name=topic.name,
            created_at=note_draft.created_at,
            claim_ids=[link.claim_id for link in note_draft.claim_links],
            markdown=note_draft.markdown,
            approval_status=note_draft.approval_status,
            approval_decided_at=note_draft.approval_decided_at,
            reviewer_note=note_draft.reviewer_note,
        )

    def get_note_draft(self, note_draft_id: int) -> NoteDraftResponse:
        note_draft = self.repository.get_note_draft(note_draft_id)
        if note_draft is None:
            raise ResourceNotFoundError("NoteDraft", note_draft_id)
        return self._note_draft_response(note_draft)

    def get_approved_note_drafts(self) -> list[NoteDraftResponse]:
        return [
            self._note_draft_response(note_draft)
            for note_draft in self.repository.get_approved_note_drafts()
        ]

    def record_note_draft_approval(
        self,
        note_draft_id: int,
        request: NoteDraftApprovalCreate,
    ) -> NoteDraftResponse:
        note_draft = self.repository.get_note_draft(note_draft_id)
        if note_draft is None:
            raise ResourceNotFoundError("NoteDraft", note_draft_id)
        is_draft = request.approval_status == ClaimApprovalStatus.DRAFT
        self.repository.update_note_draft_approval(
            note_draft,
            request.approval_status.value,
            None if is_draft else request.reviewer_note,
            None if is_draft else datetime.now(UTC),
        )
        self._commit(note_draft)
        return self.get_note_draft(note_draft.id)

    def link_claim_evidence(self, claim_id: int, evidence_id: int) -> ClaimResponse:
        claim = self.repository.get_claim(claim_id)
        if claim is None:
            raise ResourceNotFoundError("Claim", claim_id)
        evidence = self.repository.get_evidence(evidence_id)
        if evidence is None:
            raise ResourceNotFoundError("Evidence", evidence_id)
        self.repository.link_claim_evidence(claim.id, evidence.id)
        self._commit(claim)
        refreshed_claim = self.repository.get_claim(claim.id)
        if refreshed_claim is None:
            raise ResourceNotFoundError("Claim", claim.id)
        return self._claim_response(refreshed_claim)

    def record_claim_approval(
        self,
        claim_id: int,
        request: ClaimApprovalCreate,
    ) -> ClaimResponse:
        claim = self.repository.get_claim(claim_id)
        if claim is None:
            raise ResourceNotFoundError("Claim", claim_id)
        is_draft = request.approval_status == ClaimApprovalStatus.DRAFT
        self.repository.update_claim_approval(
            claim,
            request.approval_status.value,
            None if is_draft else request.reviewer_note,
            None if is_draft else datetime.now(UTC),
        )
        self._commit(claim)
        return self._claim_response(claim)

    def create_verification(self, request: VerificationCreate) -> VerificationResponse:
        claim = self.repository.get_claim(request.claim_id)
        if claim is None:
            raise ResourceNotFoundError("Claim", request.claim_id)

        evidence_by_id: dict[int, Evidence] = {}
        for item in request.evidence:
            evidence = self.repository.get_evidence(item.evidence_id)
            if evidence is None:
                raise ResourceNotFoundError("Evidence", item.evidence_id)
            evidence_by_id[item.evidence_id] = evidence

        verification = Verification(
            claim_id=request.claim_id,
            verdict=request.verdict.value,
            confidence=request.confidence,
            reasoning=request.reasoning,
        )
        verification.evidence_links = [
            VerificationEvidence(
                evidence=evidence_by_id[item.evidence_id],
                evidence_role=item.evidence_role.value,
                position=item.position,
            )
            for item in request.evidence
        ]
        self._commit_verification(verification, claim)
        return self.get_verification(verification.id)

    def get_verification(self, verification_id: int) -> VerificationResponse:
        verification = self.repository.get_verification(verification_id)
        if verification is None:
            raise ResourceNotFoundError("Verification", verification_id)
        evidence = [
            VerificationEvidenceResponse(
                evidence_id=link.evidence.id,
                source_id=link.evidence.source_id,
                content=link.evidence.content,
                location_reference=link.evidence.location_reference,
                evidence_role=link.evidence_role,
                position=link.position,
            )
            for link in verification.evidence_links
        ]
        return VerificationResponse(
            id=verification.id,
            verdict=verification.verdict,
            confidence=verification.confidence,
            reasoning=verification.reasoning,
            created_at=verification.created_at,
            claim=verification.claim,
            evidence=evidence,
        )

    def _commit(
        self,
        instance: (
            Source
            | Exam
            | SyllabusVersion
            | Topic
            | Evidence
            | Claim
            | Verification
            | NoteDraft
        ),
    ):
        try:
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return instance

    def _commit_note_draft(self, note_draft: NoteDraft) -> None:
        try:
            self.repository.add_note_draft(note_draft)
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise

    @staticmethod
    def _render_note_markdown(topic_name: str, claims: list[Claim]) -> str:
        return f"# {topic_name}\n\n" + "\n".join(
            f"- {claim.statement}" for claim in claims
        )

    @staticmethod
    def _claim_response(claim: Claim) -> ClaimResponse:
        response = ClaimResponse.model_validate(claim)
        return response.model_copy(
            update={
                "relevant_evidence_ids": [
                    evidence.id
                    for evidence in sorted(
                        claim.relevant_evidence,
                        key=lambda item: item.id,
                    )
                ]
            }
        )

    @staticmethod
    def _note_draft_response(note_draft: NoteDraft) -> NoteDraftResponse:
        return NoteDraftResponse(
            id=note_draft.id,
            topic_id=note_draft.topic_id,
            topic_name=note_draft.topic.name,
            created_at=note_draft.created_at,
            claim_ids=[link.claim_id for link in note_draft.claim_links],
            markdown=note_draft.markdown,
            approval_status=note_draft.approval_status,
            approval_decided_at=note_draft.approval_decided_at,
            reviewer_note=note_draft.reviewer_note,
        )

    def _commit_verification(
        self,
        verification: Verification,
        claim: Claim,
    ) -> None:
        try:
            self.repository.add_verification(verification)
            self.repository.update_claim_verification_summary(claim, verification)
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
