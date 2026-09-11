from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

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
    NoteDraftClaim,
    PdfArtifact,
    PreviousPaper,
    PreviousQuestion,
    QuestionBankItem,
    QuestionBankItemClaim,
    QuestionBankOption,
    Source,
    SourceCandidate,
    SourceCandidatePromotion,
    SourceDiscoveryRun,
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
    ContentDocumentApprovalCreate,
    ContentDocumentReleaseCreate,
    ContentDocumentReleaseDecision,
    ContentDocumentResponse,
    ContentPackageApprovalCreate,
    ContentPackageContentResponse,
    ContentPackageReleaseCreate,
    ContentPackageReleaseDecision,
    ContentPackageResponse,
    ContentVersionCreate,
    ContentVersionReleasedAssetsResponse,
    ContentVersionResponse,
    EvidenceCreate,
    ExamCreate,
    ExamResponse,
    NoteDraftApprovalCreate,
    NoteDraftCreate,
    NoteDraftPreviewResponse,
    NoteDraftReleaseCreate,
    NoteDraftReleaseDecision,
    NoteDraftResponse,
    OfficialSiteDiscoveryCreate,
    PdfArtifactApprovalCreate,
    PdfArtifactReleaseCreate,
    PdfArtifactReleaseDecision,
    PdfArtifactResponse,
    PreviousPaperCreate,
    PreviousPaperResponse,
    PreviousQuestionCreate,
    PreviousQuestionResponse,
    QuestionBankItemApprovalCreate,
    QuestionBankItemCreate,
    QuestionBankItemReleaseCreate,
    QuestionBankItemReleaseDecision,
    QuestionBankItemResponse,
    SourceCandidateApprovalCreate,
    SourceCandidateApprovalStatus,
    SourceCandidateCreate,
    SourceCandidatePromotionCreate,
    SourceCandidatePromotionResponse,
    SourceCandidateResponse,
    SourceCreate,
    SourceDiscoveryRunCreate,
    SourceDiscoveryRunResponse,
    SyllabusVersionCreate,
    SyllabusVersionResponse,
    TopicCreate,
    TopicPriorityBand,
    TopicPriorityReason,
    TopicPriorityResponse,
    VerificationCreate,
    VerificationEvidenceResponse,
    VerificationResponse,
)
from app.services.official_site_discovery import (
    OfficialDiscoveryError,
    OfficialSiteDiscoveryAdapter,
)
from app.services.pdf_renderer import render_content_document_pdf


class ResourceNotFoundError(Exception):
    def __init__(self, resource: str, resource_id: int) -> None:
        self.resource = resource
        self.resource_id = resource_id
        super().__init__(f"{resource} {resource_id} not found")


class ResourceConflictError(Exception):
    pass


@dataclass(frozen=True)
class PdfArtifactDownload:
    filename: str
    media_type: str
    byte_size: int
    pdf_bytes: bytes


class KnowledgeService:
    def __init__(
        self,
        session: Session,
        official_site_adapter: OfficialSiteDiscoveryAdapter | None = None,
    ) -> None:
        self.session = session
        self.repository = KnowledgeRepository(session)
        self.official_site_adapter = official_site_adapter or OfficialSiteDiscoveryAdapter()

    def create_source(self, request: SourceCreate) -> Source:
        source = Source(**request.model_dump())
        return self._commit(self.repository.add_source(source))

    def create_source_discovery_run(
        self,
        request: SourceDiscoveryRunCreate,
    ) -> SourceDiscoveryRunResponse:
        source_discovery_run = SourceDiscoveryRun(
            query=request.query,
            adapter_key=request.adapter_key,
            status=request.status.value,
            error_message=request.error_message,
            candidates=[
                SourceCandidate(
                    run_status="SUCCEEDED",
                    position=position,
                    **candidate.model_dump(),
                )
                for position, candidate in enumerate(request.candidates)
            ],
        )
        try:
            self.repository.add_source_discovery_run(source_discovery_run)
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            diagnostic = getattr(error.orig, "diag", None)
            constraint_name = getattr(diagnostic, "constraint_name", None)
            if constraint_name not in {
                "uq_source_candidates_run_position",
                "uq_source_candidates_run_location",
            }:
                raise
            raise ResourceConflictError(
                "SourceDiscoveryRun candidate positions or locations conflict"
            ) from error
        except Exception:
            self.session.rollback()
            raise

        stored_run = self.repository.get_source_discovery_run(source_discovery_run.id)
        if stored_run is None:
            raise RuntimeError(
                f"SourceDiscoveryRun {source_discovery_run.id} was not stored"
            )
        return self._source_discovery_run_response(stored_run)

    def discover_official_site(
        self,
        request: OfficialSiteDiscoveryCreate,
    ) -> SourceDiscoveryRunResponse:
        try:
            result = self.official_site_adapter.discover(
                request.query,
                request.site_root,
            )
        except OfficialDiscoveryError as error:
            run_request = SourceDiscoveryRunCreate(
                query=request.query,
                adapter_key=self.official_site_adapter.adapter_key,
                status="FAILED",
                error_message=error.code,
                candidates=[],
            )
        else:
            run_request = SourceDiscoveryRunCreate(
                query=request.query,
                adapter_key=self.official_site_adapter.adapter_key,
                status="SUCCEEDED",
                error_message=None,
                candidates=[
                    SourceCandidateCreate(
                        location=candidate.location,
                        title=candidate.title,
                        publisher=candidate.publisher,
                        snippet=candidate.snippet,
                    )
                    for candidate in result.candidates
                ],
            )
        return self.create_source_discovery_run(run_request)

    def get_source_discovery_run(
        self,
        source_discovery_run_id: int,
    ) -> SourceDiscoveryRunResponse:
        source_discovery_run = self.repository.get_source_discovery_run(
            source_discovery_run_id
        )
        if source_discovery_run is None:
            raise ResourceNotFoundError(
                "SourceDiscoveryRun",
                source_discovery_run_id,
            )
        return self._source_discovery_run_response(source_discovery_run)

    def record_source_candidate_approval(
        self,
        source_candidate_id: int,
        request: SourceCandidateApprovalCreate,
    ) -> SourceCandidateResponse:
        source_candidate = self.repository.get_source_candidate_for_update(
            source_candidate_id
        )
        if source_candidate is None:
            raise ResourceNotFoundError("SourceCandidate", source_candidate_id)

        is_draft = request.approval_status == SourceCandidateApprovalStatus.DRAFT
        try:
            self.repository.update_source_candidate_approval(
                source_candidate,
                request.approval_status.value,
                None if is_draft else request.reviewer_note,
                None if is_draft else datetime.now(UTC),
            )
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise

        stored_candidate = self.repository.get_source_candidate(source_candidate_id)
        if stored_candidate is None:
            raise RuntimeError(
                f"SourceCandidate {source_candidate_id} missing after successful review"
            )
        return self._source_candidate_response(stored_candidate)

    def get_approved_source_candidates(self) -> list[SourceCandidateResponse]:
        return [
            self._source_candidate_response(source_candidate)
            for source_candidate in self.repository.get_approved_source_candidates()
        ]

    def promote_source_candidate(
        self,
        source_candidate_id: int,
        request: SourceCandidatePromotionCreate,
    ) -> SourceCandidatePromotionResponse:
        source_candidate = self.repository.get_source_candidate_for_update(
            source_candidate_id
        )
        if source_candidate is None:
            raise ResourceNotFoundError("SourceCandidate", source_candidate_id)
        if source_candidate.approval_status != SourceCandidateApprovalStatus.APPROVED:
            raise ResourceConflictError(
                f"SourceCandidate {source_candidate_id} must be approved before promotion"
            )
        if (
            self.repository.get_source_candidate_promotion_by_candidate_id(
                source_candidate_id
            )
            is not None
        ):
            raise ResourceConflictError(
                f"SourceCandidate {source_candidate_id} already has a Source"
            )

        source = Source(
            title=request.title,
            publisher=request.publisher,
            source_type=request.source_type,
            authority_tier=request.authority_tier,
            location=source_candidate.location,
            license_status=request.license_status,
            content_hash=None,
        )
        promotion = SourceCandidatePromotion(
            source_candidate_id=source_candidate.id,
            source=source,
            location=source_candidate.location,
            candidate_approval_status=source_candidate.approval_status,
            candidate_approval_decided_at=source_candidate.approval_decided_at,
            candidate_reviewer_note=source_candidate.reviewer_note,
        )
        try:
            self.repository.add_source_candidate_promotion(promotion)
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            diagnostic = getattr(error.orig, "diag", None)
            constraint_name = getattr(diagnostic, "constraint_name", None)
            if constraint_name != "uq_source_candidate_promotions_source_candidate_id":
                raise
            raise ResourceConflictError(
                f"SourceCandidate {source_candidate_id} already has a Source"
            ) from error
        except Exception:
            self.session.rollback()
            raise

        stored_promotion = self.repository.get_source_candidate_promotion(promotion.id)
        if stored_promotion is None:
            raise RuntimeError(
                f"SourceCandidatePromotion {promotion.id} missing after successful commit"
            )
        return self._source_candidate_promotion_response(stored_promotion)

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

    def create_previous_paper(
        self,
        request: PreviousPaperCreate,
    ) -> PreviousPaperResponse:
        if self.repository.get_exam(request.exam_id) is None:
            raise ResourceNotFoundError("Exam", request.exam_id)
        if self.repository.get_source(request.source_id) is None:
            raise ResourceNotFoundError("Source", request.source_id)

        previous_paper = PreviousPaper(**request.model_dump())
        try:
            self._commit(self.repository.add_previous_paper(previous_paper))
        except IntegrityError as error:
            constraint_name = getattr(error.orig.diag, "constraint_name", None)
            if constraint_name != "uq_previous_papers_exam_year_label":
                raise
            raise ResourceConflictError(
                f"PreviousPaper label '{request.label}' already exists "
                f"for Exam {request.exam_id} in year {request.year}"
            ) from error
        return PreviousPaperResponse.model_validate(previous_paper)

    def create_previous_question(
        self,
        request: PreviousQuestionCreate,
    ) -> PreviousQuestionResponse:
        if self.repository.get_previous_paper(request.previous_paper_id) is None:
            raise ResourceNotFoundError(
                "PreviousPaper",
                request.previous_paper_id,
            )
        if self.repository.get_topic(request.topic_id) is None:
            raise ResourceNotFoundError("Topic", request.topic_id)

        previous_question = PreviousQuestion(**request.model_dump())
        try:
            self._commit(self.repository.add_previous_question(previous_question))
        except IntegrityError as error:
            constraint_name = getattr(error.orig.diag, "constraint_name", None)
            if constraint_name != "uq_previous_questions_paper_position":
                raise
            raise ResourceConflictError(
                f"PreviousQuestion position {request.position} already exists "
                f"for PreviousPaper {request.previous_paper_id}"
            ) from error
        return PreviousQuestionResponse.model_validate(previous_question)

    def get_topic_priority(
        self,
        syllabus_version_id: int,
        topic_id: int,
    ) -> TopicPriorityResponse:
        syllabus_version = self.repository.get_syllabus_version(syllabus_version_id)
        if syllabus_version is None:
            raise ResourceNotFoundError("SyllabusVersion", syllabus_version_id)
        if self.repository.get_topic(topic_id) is None:
            raise ResourceNotFoundError("Topic", topic_id)

        syllabus_covered = any(
            link.topic_id == topic_id for link in syllabus_version.topic_links
        )
        stats = self.repository.get_topic_occurrence_stats(
            syllabus_version.exam_id,
            topic_id,
        )
        coverage_reason = (
            TopicPriorityReason.DIRECT_SYLLABUS_COVERAGE
            if syllabus_covered
            else TopicPriorityReason.NOT_IN_SELECTED_SYLLABUS_VERSION
        )
        if stats.exam_paper_count == 0:
            occurrence_reason = TopicPriorityReason.NO_PREVIOUS_PAPER_DATA
        elif stats.matched_paper_count >= 2:
            occurrence_reason = TopicPriorityReason.REPEATED_IN_PREVIOUS_PAPERS
        elif stats.matched_paper_count == 1:
            occurrence_reason = TopicPriorityReason.APPEARED_IN_PREVIOUS_PAPER
        else:
            occurrence_reason = TopicPriorityReason.NO_RECORDED_PREVIOUS_OCCURRENCE

        if not syllabus_covered:
            priority_band = TopicPriorityBand.LOW
        elif stats.matched_paper_count >= 2:
            priority_band = TopicPriorityBand.HIGH
        else:
            priority_band = TopicPriorityBand.MEDIUM

        return TopicPriorityResponse(
            syllabus_version_id=syllabus_version.id,
            exam_id=syllabus_version.exam_id,
            topic_id=topic_id,
            syllabus_covered=syllabus_covered,
            exam_paper_count=stats.exam_paper_count,
            matched_question_count=stats.matched_question_count,
            matched_paper_count=stats.matched_paper_count,
            matched_years=stats.matched_years,
            priority_band=priority_band,
            rule_version="topic-priority-v1",
            reason_codes=[coverage_reason, occurrence_reason],
        )

    def create_content_version(
        self,
        request: ContentVersionCreate,
    ) -> ContentVersionResponse:
        syllabus_version = self.repository.get_syllabus_version(
            request.syllabus_version_id
        )
        if syllabus_version is None:
            raise ResourceNotFoundError(
                "SyllabusVersion",
                request.syllabus_version_id,
            )
        if self.repository.get_topic(request.topic_id) is None:
            raise ResourceNotFoundError("Topic", request.topic_id)
        if not any(
            link.topic_id == request.topic_id
            for link in syllabus_version.topic_links
        ):
            raise ResourceConflictError(
                f"Topic {request.topic_id} is not mapped to "
                f"SyllabusVersion {request.syllabus_version_id}"
            )

        content_version = ContentVersion(**request.model_dump())
        try:
            self._commit(self.repository.add_content_version(content_version))
        except IntegrityError as error:
            constraint_name = getattr(error.orig.diag, "constraint_name", None)
            if constraint_name == "uq_content_versions_mapping_version":
                detail = (
                    f"ContentVersion {request.version} already exists for "
                    f"SyllabusVersion {request.syllabus_version_id} and "
                    f"Topic {request.topic_id}"
                )
            elif constraint_name == "fk_content_versions_syllabus_topic":
                detail = (
                    f"Topic {request.topic_id} is not mapped to "
                    f"SyllabusVersion {request.syllabus_version_id}"
                )
            else:
                raise
            raise ResourceConflictError(detail) from error
        return ContentVersionResponse.model_validate(content_version)

    def get_content_version(
        self,
        content_version_id: int,
    ) -> ContentVersionResponse:
        content_version = self.repository.get_content_version(content_version_id)
        if content_version is None:
            raise ResourceNotFoundError("ContentVersion", content_version_id)
        return ContentVersionResponse.model_validate(content_version)

    def get_content_version_released_assets(
        self,
        content_version_id: int,
    ) -> ContentVersionReleasedAssetsResponse:
        content_version = self.repository.get_content_version(content_version_id)
        if content_version is None:
            raise ResourceNotFoundError("ContentVersion", content_version_id)
        return ContentVersionReleasedAssetsResponse(
            content_version=ContentVersionResponse.model_validate(content_version),
            note_drafts=[
                self._note_draft_response(note_draft)
                for note_draft in self.repository.get_released_note_drafts_by_content_version(
                    content_version_id
                )
            ],
            question_bank_items=[
                self._question_bank_item_response(question_bank_item)
                for question_bank_item in self.repository.get_released_question_bank_items_by_content_version(
                    content_version_id
                )
            ],
        )

    def create_content_package(
        self,
        content_version_id: int,
    ) -> ContentPackageResponse:
        content_version = self.repository.get_content_version_for_package_creation(
            content_version_id
        )
        if content_version is None:
            raise ResourceNotFoundError("ContentVersion", content_version_id)

        note_drafts = self.repository.get_released_note_drafts_for_package(
            content_version_id
        )
        question_bank_items = (
            self.repository.get_released_question_bank_items_for_package(
                content_version_id
            )
        )
        if not note_drafts and not question_bank_items:
            raise ResourceConflictError(
                f"ContentVersion {content_version_id} has no released assets to package"
            )

        content_package = ContentPackage(
            content_version_id=content_version_id,
            note_draft_links=[
                ContentPackageNoteDraft(
                    content_version_id=content_version_id,
                    note_draft_id=note_draft.id,
                    position=position,
                )
                for position, note_draft in enumerate(note_drafts)
            ],
            question_bank_item_links=[
                ContentPackageQuestionBankItem(
                    content_version_id=content_version_id,
                    question_bank_item_id=question_bank_item.id,
                    position=position,
                )
                for position, question_bank_item in enumerate(question_bank_items)
            ],
        )
        self._commit_content_package(content_package)
        stored_package = self.repository.get_content_package(content_package.id)
        if stored_package is None:
            raise RuntimeError(
                f"ContentPackage {content_package.id} missing after successful commit"
            )
        return self._content_package_response(stored_package)

    def get_content_package(
        self,
        content_package_id: int,
    ) -> ContentPackageResponse:
        content_package = self.repository.get_content_package(content_package_id)
        if content_package is None:
            raise ResourceNotFoundError("ContentPackage", content_package_id)
        return self._content_package_response(content_package)

    def get_released_content_packages(self) -> list[ContentPackageResponse]:
        return [
            self._content_package_response(content_package)
            for content_package in self.repository.get_released_content_packages()
        ]

    def get_content_package_content(
        self,
        content_package_id: int,
    ) -> ContentPackageContentResponse:
        content_package = self.repository.get_content_package(content_package_id)
        if content_package is None:
            raise ResourceNotFoundError("ContentPackage", content_package_id)

        package_response = self._content_package_response(content_package)
        note_drafts = self.repository.get_content_package_note_drafts(
            content_package_id
        )
        question_bank_items = (
            self.repository.get_content_package_question_bank_items(
                content_package_id
            )
        )
        if package_response.note_draft_ids != [
            note_draft.id for note_draft in note_drafts
        ] or package_response.question_bank_item_ids != [
            question_bank_item.id for question_bank_item in question_bank_items
        ]:
            raise RuntimeError(
                f"ContentPackage {content_package_id} membership could not be resolved"
            )

        return ContentPackageContentResponse(
            content_package=package_response,
            note_drafts=[
                self._note_draft_response(note_draft) for note_draft in note_drafts
            ],
            question_bank_items=[
                self._question_bank_item_response(question_bank_item)
                for question_bank_item in question_bank_items
            ],
        )

    def record_content_package_approval(
        self,
        content_package_id: int,
        request: ContentPackageApprovalCreate,
    ) -> ContentPackageResponse:
        content_package = self.repository.get_content_package_for_update(
            content_package_id
        )
        if content_package is None:
            raise ResourceNotFoundError("ContentPackage", content_package_id)

        if (
            content_package.release_status == "RELEASED"
            and request.approval_status
            in (ClaimApprovalStatus.DRAFT, ClaimApprovalStatus.REJECTED)
        ):
            raise ResourceConflictError(
                f"ContentPackage {content_package_id} must be withdrawn "
                "before changing approval"
            )

        is_draft = request.approval_status == ClaimApprovalStatus.DRAFT
        self._commit_content_package_approval(
            content_package,
            request.approval_status.value,
            None if is_draft else request.reviewer_note,
            None if is_draft else datetime.now(UTC),
        )
        stored_package = self.repository.get_content_package(content_package_id)
        if stored_package is None:
            raise RuntimeError(
                f"ContentPackage {content_package_id} missing after successful review"
            )
        return self._content_package_response(stored_package)

    def record_content_package_release(
        self,
        content_package_id: int,
        request: ContentPackageReleaseCreate,
    ) -> ContentPackageResponse:
        content_package = self.repository.get_content_package_for_update(
            content_package_id
        )
        if content_package is None:
            raise ResourceNotFoundError("ContentPackage", content_package_id)

        requested_status = request.release_status.value
        current_status = content_package.release_status
        if (
            request.release_status == ContentPackageReleaseDecision.RELEASED
            and current_status == "UNRELEASED"
        ):
            if content_package.approval_status != "APPROVED":
                raise ResourceConflictError(
                    f"ContentPackage {content_package_id} must be approved before release"
                )
            if not (
                content_package.note_draft_links
                or content_package.question_bank_item_links
            ):
                raise ResourceConflictError(
                    f"ContentPackage {content_package_id} has no retained members "
                    "to release"
                )
            released_at = datetime.now(UTC)
            withdrawn_at = None
        elif (
            request.release_status == ContentPackageReleaseDecision.WITHDRAWN
            and current_status == "RELEASED"
        ):
            released_at = content_package.released_at
            withdrawn_at = datetime.now(UTC)
        else:
            raise ResourceConflictError(
                f"ContentPackage {content_package_id} cannot transition "
                f"from {current_status} to {requested_status}"
            )

        self._commit_content_package_release(
            content_package,
            requested_status,
            released_at,
            withdrawn_at,
            request.release_note,
        )
        stored_package = self.repository.get_content_package(content_package_id)
        if stored_package is None:
            raise RuntimeError(
                f"ContentPackage {content_package_id} missing after successful release"
            )
        return self._content_package_response(stored_package)

    def create_content_document(
        self,
        content_package_id: int,
    ) -> ContentDocumentResponse:
        content_package = self.repository.get_content_package_for_update(
            content_package_id
        )
        if content_package is None:
            raise ResourceNotFoundError("ContentPackage", content_package_id)
        if content_package.release_status != "RELEASED":
            raise ResourceConflictError(
                f"ContentPackage {content_package_id} must be released "
                "before document creation"
            )
        if self.repository.get_content_document_by_package_id(content_package_id):
            raise ResourceConflictError(
                f"ContentPackage {content_package_id} already has a ContentDocument"
            )

        package_response = self._content_package_response(content_package)
        note_drafts = self.repository.get_content_package_note_drafts(
            content_package_id
        )
        question_bank_items = (
            self.repository.get_content_package_question_bank_items(
                content_package_id
            )
        )
        if package_response.note_draft_ids != [
            note_draft.id for note_draft in note_drafts
        ] or package_response.question_bank_item_ids != [
            question_bank_item.id for question_bank_item in question_bank_items
        ]:
            raise RuntimeError(
                f"ContentPackage {content_package_id} membership could not be resolved"
            )

        markdown = self._render_content_document_markdown(
            content_package_id,
            note_drafts,
            question_bank_items,
        )
        content_document = ContentDocument(
            content_package_id=content_package_id,
            content_version_id=content_package.content_version_id,
            title=f"Content Package {content_package_id}",
            markdown=markdown,
            sha256=sha256(markdown.encode("utf-8")).hexdigest(),
        )
        try:
            self.repository.add_content_document(content_document)
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            constraint_name = getattr(error.orig.diag, "constraint_name", None)
            if constraint_name == "uq_content_documents_content_package_id":
                raise ResourceConflictError(
                    f"ContentPackage {content_package_id} already has a ContentDocument"
                ) from error
            raise
        except Exception:
            self.session.rollback()
            raise

        stored_document = self.repository.get_content_document_by_package_id(
            content_package_id
        )
        if stored_document is None:
            raise RuntimeError(
                f"ContentDocument for ContentPackage {content_package_id} "
                "missing after successful commit"
            )
        return self._content_document_response(stored_document)

    def get_content_document(
        self,
        content_document_id: int,
    ) -> ContentDocumentResponse:
        content_document = self.repository.get_content_document(content_document_id)
        if content_document is None:
            raise ResourceNotFoundError("ContentDocument", content_document_id)
        return self._content_document_response(content_document)

    def get_released_content_documents(self) -> list[ContentDocumentResponse]:
        return [
            self._content_document_response(content_document)
            for content_document in self.repository.get_released_content_documents()
        ]

    def create_pdf_artifact(
        self,
        content_document_id: int,
    ) -> PdfArtifactResponse:
        content_document = self.repository.get_content_document_for_update(
            content_document_id
        )
        if content_document is None:
            raise ResourceNotFoundError("ContentDocument", content_document_id)
        if content_document.release_status != "RELEASED":
            raise ResourceConflictError(
                f"ContentDocument {content_document_id} must be released "
                "before PDF creation"
            )
        if self.repository.get_pdf_artifact_by_document_id(content_document_id):
            raise ResourceConflictError(
                f"ContentDocument {content_document_id} already has a PdfArtifact"
            )

        try:
            pdf_bytes = render_content_document_pdf(
                content_document.title,
                content_document.markdown,
            )
            pdf_artifact = PdfArtifact(
                content_document_id=content_document.id,
                content_package_id=content_document.content_package_id,
                content_version_id=content_document.content_version_id,
                filename=f"content-document-{content_document.id}.pdf",
                media_type="application/pdf",
                pdf_bytes=pdf_bytes,
                byte_size=len(pdf_bytes),
                sha256=sha256(pdf_bytes).hexdigest(),
            )
            self.repository.add_pdf_artifact(pdf_artifact)
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            diagnostic = getattr(error.orig, "diag", None)
            constraint_name = getattr(diagnostic, "constraint_name", None)
            if constraint_name == "uq_pdf_artifacts_content_document_id":
                raise ResourceConflictError(
                    f"ContentDocument {content_document_id} already has a PdfArtifact"
                ) from error
            raise
        except Exception:
            self.session.rollback()
            raise

        stored_artifact = self.repository.get_pdf_artifact_by_document_id(
            content_document_id
        )
        if stored_artifact is None:
            raise RuntimeError(
                f"PdfArtifact for ContentDocument {content_document_id} "
                "missing after successful commit"
            )
        return self._pdf_artifact_response(stored_artifact)

    def get_pdf_artifact(self, pdf_artifact_id: int) -> PdfArtifactResponse:
        pdf_artifact = self._get_pdf_artifact_or_raise(pdf_artifact_id)
        return self._pdf_artifact_response(pdf_artifact)

    def download_pdf_artifact(self, pdf_artifact_id: int) -> PdfArtifactDownload:
        pdf_artifact = self._get_pdf_artifact_or_raise(pdf_artifact_id)
        return PdfArtifactDownload(
            filename=pdf_artifact.filename,
            media_type=pdf_artifact.media_type,
            byte_size=pdf_artifact.byte_size,
            pdf_bytes=bytes(pdf_artifact.pdf_bytes),
        )

    def get_released_pdf_artifacts(self) -> list[PdfArtifactResponse]:
        return [
            self._pdf_artifact_response(pdf_artifact)
            for pdf_artifact in self.repository.get_released_pdf_artifacts()
        ]

    def download_released_pdf_artifact(
        self,
        pdf_artifact_id: int,
    ) -> PdfArtifactDownload:
        pdf_artifact = self.repository.get_released_pdf_artifact(pdf_artifact_id)
        if pdf_artifact is None:
            raise ResourceNotFoundError("PdfArtifact", pdf_artifact_id)
        return PdfArtifactDownload(
            filename=pdf_artifact.filename,
            media_type=pdf_artifact.media_type,
            byte_size=pdf_artifact.byte_size,
            pdf_bytes=bytes(pdf_artifact.pdf_bytes),
        )

    def record_pdf_artifact_approval(
        self,
        pdf_artifact_id: int,
        request: PdfArtifactApprovalCreate,
    ) -> PdfArtifactResponse:
        pdf_artifact = self.repository.get_pdf_artifact_for_update(pdf_artifact_id)
        if pdf_artifact is None:
            raise ResourceNotFoundError("PdfArtifact", pdf_artifact_id)

        if (
            pdf_artifact.release_status == "RELEASED"
            and request.approval_status
            in (ClaimApprovalStatus.DRAFT, ClaimApprovalStatus.REJECTED)
        ):
            raise ResourceConflictError(
                f"PdfArtifact {pdf_artifact_id} must be withdrawn "
                "before changing approval"
            )

        is_draft = request.approval_status == ClaimApprovalStatus.DRAFT
        try:
            self.repository.update_pdf_artifact_approval(
                pdf_artifact,
                request.approval_status.value,
                None if is_draft else request.reviewer_note,
                None if is_draft else datetime.now(UTC),
            )
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise

        stored_artifact = self.repository.get_pdf_artifact(pdf_artifact_id)
        if stored_artifact is None:
            raise RuntimeError(
                f"PdfArtifact {pdf_artifact_id} missing after successful review"
            )
        return self._pdf_artifact_response(stored_artifact)

    def record_pdf_artifact_release(
        self,
        pdf_artifact_id: int,
        request: PdfArtifactReleaseCreate,
    ) -> PdfArtifactResponse:
        pdf_artifact = self.repository.get_pdf_artifact_for_update(pdf_artifact_id)
        if pdf_artifact is None:
            raise ResourceNotFoundError("PdfArtifact", pdf_artifact_id)

        requested_status = request.release_status.value
        current_status = pdf_artifact.release_status
        if (
            request.release_status == PdfArtifactReleaseDecision.RELEASED
            and current_status == "UNRELEASED"
        ):
            if pdf_artifact.approval_status != "APPROVED":
                raise ResourceConflictError(
                    f"PdfArtifact {pdf_artifact_id} must be approved before release"
                )
            released_at = datetime.now(UTC)
            withdrawn_at = None
        elif (
            request.release_status == PdfArtifactReleaseDecision.WITHDRAWN
            and current_status == "RELEASED"
        ):
            released_at = pdf_artifact.released_at
            withdrawn_at = datetime.now(UTC)
        else:
            raise ResourceConflictError(
                f"PdfArtifact {pdf_artifact_id} cannot transition "
                f"from {current_status} to {requested_status}"
            )

        try:
            self.repository.update_pdf_artifact_release(
                pdf_artifact,
                requested_status,
                released_at,
                withdrawn_at,
                request.release_note,
            )
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise

        stored_artifact = self.repository.get_pdf_artifact(pdf_artifact_id)
        if stored_artifact is None:
            raise RuntimeError(
                f"PdfArtifact {pdf_artifact_id} missing after successful release"
            )
        return self._pdf_artifact_response(stored_artifact)

    def record_content_document_approval(
        self,
        content_document_id: int,
        request: ContentDocumentApprovalCreate,
    ) -> ContentDocumentResponse:
        content_document = self.repository.get_content_document_for_update(
            content_document_id
        )
        if content_document is None:
            raise ResourceNotFoundError("ContentDocument", content_document_id)

        if (
            content_document.release_status == "RELEASED"
            and request.approval_status
            in (ClaimApprovalStatus.DRAFT, ClaimApprovalStatus.REJECTED)
        ):
            raise ResourceConflictError(
                f"ContentDocument {content_document_id} must be withdrawn "
                "before changing approval"
            )

        is_draft = request.approval_status == ClaimApprovalStatus.DRAFT
        try:
            self.repository.update_content_document_approval(
                content_document,
                request.approval_status.value,
                None if is_draft else request.reviewer_note,
                None if is_draft else datetime.now(UTC),
            )
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise

        stored_document = self.repository.get_content_document(content_document_id)
        if stored_document is None:
            raise RuntimeError(
                f"ContentDocument {content_document_id} missing after successful review"
            )
        return self._content_document_response(stored_document)

    def record_content_document_release(
        self,
        content_document_id: int,
        request: ContentDocumentReleaseCreate,
    ) -> ContentDocumentResponse:
        content_document = self.repository.get_content_document_for_update(
            content_document_id
        )
        if content_document is None:
            raise ResourceNotFoundError("ContentDocument", content_document_id)

        requested_status = request.release_status.value
        current_status = content_document.release_status
        if (
            request.release_status == ContentDocumentReleaseDecision.RELEASED
            and current_status == "UNRELEASED"
        ):
            if content_document.approval_status != "APPROVED":
                raise ResourceConflictError(
                    f"ContentDocument {content_document_id} must be approved "
                    "before release"
                )
            released_at = datetime.now(UTC)
            withdrawn_at = None
        elif (
            request.release_status == ContentDocumentReleaseDecision.WITHDRAWN
            and current_status == "RELEASED"
        ):
            released_at = content_document.released_at
            withdrawn_at = datetime.now(UTC)
        else:
            raise ResourceConflictError(
                f"ContentDocument {content_document_id} cannot transition "
                f"from {current_status} to {requested_status}"
            )

        try:
            self.repository.update_content_document_release(
                content_document,
                requested_status,
                released_at,
                withdrawn_at,
                request.release_note,
            )
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise

        stored_document = self.repository.get_content_document(content_document_id)
        if stored_document is None:
            raise RuntimeError(
                f"ContentDocument {content_document_id} missing after successful release"
            )
        return self._content_document_response(stored_document)

    def create_question_bank_item(
        self,
        request: QuestionBankItemCreate,
    ) -> QuestionBankItemResponse:
        content_version = self.repository.get_content_version(
            request.content_version_id
        )
        if content_version is None:
            raise ResourceNotFoundError(
                "ContentVersion",
                request.content_version_id,
            )

        claims_by_id = {
            claim.id: claim
            for claim in self.repository.get_claims_for_question_bank_item(
                request.claim_ids
            )
        }
        claims: list[Claim] = []
        for claim_id in request.claim_ids:
            claim = claims_by_id.get(claim_id)
            if claim is None:
                raise ResourceNotFoundError("Claim", claim_id)
            if claim.approval_status != "APPROVED":
                raise ResourceConflictError(f"Claim {claim_id} is not approved")
            if claim.topic_id != content_version.topic_id:
                raise ResourceConflictError(
                    f"Claim {claim_id} does not match ContentVersion "
                    f"Topic {content_version.topic_id}"
                )
            claims.append(claim)

        question_bank_item = QuestionBankItem(
            content_version_id=request.content_version_id,
            question_text=request.question_text,
            explanation=request.explanation,
            difficulty=request.difficulty.value,
            claim_links=[
                QuestionBankItemClaim(claim=claim, position=position)
                for position, claim in enumerate(claims)
            ],
            options=[
                QuestionBankOption(option_text=text, position=position)
                for position, text in enumerate(request.options)
            ],
        )
        self._commit_question_bank_item(
            question_bank_item,
            request.correct_option_position,
        )
        return self.get_question_bank_item(question_bank_item.id)

    def get_question_bank_item(
        self,
        question_bank_item_id: int,
    ) -> QuestionBankItemResponse:
        question_bank_item = self.repository.get_question_bank_item(
            question_bank_item_id
        )
        if question_bank_item is None:
            raise ResourceNotFoundError(
                "QuestionBankItem",
                question_bank_item_id,
            )
        return self._question_bank_item_response(question_bank_item)

    def get_approved_question_bank_items(self) -> list[QuestionBankItemResponse]:
        return [
            self._question_bank_item_response(question_bank_item)
            for question_bank_item in self.repository.get_approved_question_bank_items()
        ]

    def get_released_question_bank_items(self) -> list[QuestionBankItemResponse]:
        return [
            self._question_bank_item_response(question_bank_item)
            for question_bank_item in self.repository.get_released_question_bank_items()
        ]

    def record_question_bank_item_approval(
        self,
        question_bank_item_id: int,
        request: QuestionBankItemApprovalCreate,
    ) -> QuestionBankItemResponse:
        question_bank_item = self.repository.get_question_bank_item_for_update(
            question_bank_item_id
        )
        if question_bank_item is None:
            raise ResourceNotFoundError(
                "QuestionBankItem",
                question_bank_item_id,
            )
        if (
            question_bank_item.release_status == "RELEASED"
            and request.approval_status != ClaimApprovalStatus.APPROVED
        ):
            raise ResourceConflictError(
                f"QuestionBankItem {question_bank_item_id} must be withdrawn "
                "before changing approval"
            )
        if (
            request.approval_status == ClaimApprovalStatus.APPROVED
            and not self._is_complete_question_bank_item(question_bank_item)
        ):
            raise ResourceConflictError(
                f"QuestionBankItem {question_bank_item_id} is incomplete "
                "and cannot be approved"
            )
        is_draft = request.approval_status == ClaimApprovalStatus.DRAFT
        self.repository.update_question_bank_item_approval(
            question_bank_item,
            request.approval_status.value,
            None if is_draft else request.reviewer_note,
            None if is_draft else datetime.now(UTC),
        )
        self._commit(question_bank_item)
        return self.get_question_bank_item(question_bank_item.id)

    def record_question_bank_item_release(
        self,
        question_bank_item_id: int,
        request: QuestionBankItemReleaseCreate,
    ) -> QuestionBankItemResponse:
        question_bank_item = self.repository.get_question_bank_item_for_update(
            question_bank_item_id
        )
        if question_bank_item is None:
            raise ResourceNotFoundError("QuestionBankItem", question_bank_item_id)

        requested_status = request.release_status.value
        current_status = question_bank_item.release_status
        if (
            request.release_status == QuestionBankItemReleaseDecision.RELEASED
            and current_status == "UNRELEASED"
        ):
            if question_bank_item.approval_status != "APPROVED":
                raise ResourceConflictError(
                    f"QuestionBankItem {question_bank_item_id} must be approved "
                    "before release"
                )
            if not self._is_complete_question_bank_item(question_bank_item):
                raise ResourceConflictError(
                    f"QuestionBankItem {question_bank_item_id} is incomplete "
                    "and cannot be released"
                )
            self.repository.update_question_bank_item_release(
                question_bank_item,
                requested_status,
                datetime.now(UTC),
                None,
                request.release_note,
            )
        elif (
            request.release_status == QuestionBankItemReleaseDecision.WITHDRAWN
            and current_status == "RELEASED"
        ):
            self.repository.update_question_bank_item_release(
                question_bank_item,
                requested_status,
                question_bank_item.released_at,
                datetime.now(UTC),
                request.release_note,
            )
        else:
            raise ResourceConflictError(
                f"QuestionBankItem {question_bank_item_id} cannot transition "
                f"from {current_status} to {requested_status}"
            )

        self._commit(question_bank_item)
        return self.get_question_bank_item(question_bank_item.id)

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

    def create_note_draft(
        self,
        topic_id: int,
        request: NoteDraftCreate,
    ) -> NoteDraftResponse:
        topic = self.repository.get_topic(topic_id)
        if topic is None:
            raise ResourceNotFoundError("Topic", topic_id)
        content_version = self.repository.get_content_version(
            request.content_version_id
        )
        if content_version is None:
            raise ResourceNotFoundError(
                "ContentVersion",
                request.content_version_id,
            )
        if content_version.topic_id != topic_id:
            raise ResourceConflictError(
                f"ContentVersion {content_version.id} does not belong to Topic {topic_id}"
            )
        claims = self.repository.get_approved_claims_by_topic(topic_id)
        if not claims:
            raise ResourceConflictError(
                f"Topic {topic_id} has no approved Claims"
            )
        note_draft = NoteDraft(
            topic_id=topic.id,
            content_version_id=content_version.id,
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
            content_version_id=note_draft.content_version_id,
            topic_name=topic.name,
            created_at=note_draft.created_at,
            claim_ids=[link.claim_id for link in note_draft.claim_links],
            markdown=note_draft.markdown,
            approval_status=note_draft.approval_status,
            approval_decided_at=note_draft.approval_decided_at,
            reviewer_note=note_draft.reviewer_note,
            release_status=note_draft.release_status,
            released_at=note_draft.released_at,
            withdrawn_at=note_draft.withdrawn_at,
            release_note=note_draft.release_note,
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

    def get_released_note_drafts(self) -> list[NoteDraftResponse]:
        return [
            self._note_draft_response(note_draft)
            for note_draft in self.repository.get_released_note_drafts()
        ]

    def record_note_draft_approval(
        self,
        note_draft_id: int,
        request: NoteDraftApprovalCreate,
    ) -> NoteDraftResponse:
        note_draft = self.repository.get_note_draft_for_update(note_draft_id)
        if note_draft is None:
            raise ResourceNotFoundError("NoteDraft", note_draft_id)
        if (
            note_draft.release_status == "RELEASED"
            and request.approval_status != ClaimApprovalStatus.APPROVED
        ):
            raise ResourceConflictError(
                f"NoteDraft {note_draft_id} must be withdrawn "
                "before changing approval"
            )
        is_draft = request.approval_status == ClaimApprovalStatus.DRAFT
        self.repository.update_note_draft_approval(
            note_draft,
            request.approval_status.value,
            None if is_draft else request.reviewer_note,
            None if is_draft else datetime.now(UTC),
        )
        self._commit(note_draft)
        return self.get_note_draft(note_draft.id)

    def record_note_draft_release(
        self,
        note_draft_id: int,
        request: NoteDraftReleaseCreate,
    ) -> NoteDraftResponse:
        note_draft = self.repository.get_note_draft_for_update(note_draft_id)
        if note_draft is None:
            raise ResourceNotFoundError("NoteDraft", note_draft_id)

        requested_status = request.release_status.value
        current_status = note_draft.release_status
        if (
            request.release_status == NoteDraftReleaseDecision.RELEASED
            and current_status == "UNRELEASED"
        ):
            if note_draft.approval_status != "APPROVED":
                raise ResourceConflictError(
                    f"NoteDraft {note_draft_id} must be approved before release"
                )
            if note_draft.content_version_id is None:
                raise ResourceConflictError(
                    f"NoteDraft {note_draft_id} must have a ContentVersion "
                    "before release"
                )
            self.repository.update_note_draft_release(
                note_draft,
                requested_status,
                datetime.now(UTC),
                None,
                request.release_note,
            )
        elif (
            request.release_status == NoteDraftReleaseDecision.WITHDRAWN
            and current_status == "RELEASED"
        ):
            self.repository.update_note_draft_release(
                note_draft,
                requested_status,
                note_draft.released_at,
                datetime.now(UTC),
                request.release_note,
            )
        else:
            raise ResourceConflictError(
                f"NoteDraft {note_draft_id} cannot transition "
                f"from {current_status} to {requested_status}"
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
            | ContentVersion
            | Exam
            | SyllabusVersion
            | PreviousPaper
            | PreviousQuestion
            | Topic
            | Evidence
            | Claim
            | Verification
            | NoteDraft
            | QuestionBankItem
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

    def _commit_content_package(self, content_package: ContentPackage) -> None:
        try:
            self.repository.add_content_package(content_package)
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise

    def _commit_content_package_approval(
        self,
        content_package: ContentPackage,
        approval_status: str,
        reviewer_note: str | None,
        decided_at: datetime | None,
    ) -> None:
        try:
            self.repository.update_content_package_approval(
                content_package,
                approval_status,
                reviewer_note,
                decided_at,
            )
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise

    def _commit_content_package_release(
        self,
        content_package: ContentPackage,
        release_status: str,
        released_at: datetime | None,
        withdrawn_at: datetime | None,
        release_note: str | None,
    ) -> None:
        try:
            self.repository.update_content_package_release(
                content_package,
                release_status,
                released_at,
                withdrawn_at,
                release_note,
            )
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise

    def _commit_question_bank_item(
        self,
        question_bank_item: QuestionBankItem,
        correct_option_position: int,
    ) -> None:
        try:
            self.repository.add_question_bank_item(question_bank_item)
            question_bank_item.correct_option_id = question_bank_item.options[
                correct_option_position
            ].id
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise

    @staticmethod
    def _content_package_response(
        content_package: ContentPackage,
    ) -> ContentPackageResponse:
        return ContentPackageResponse(
            id=content_package.id,
            content_version_id=content_package.content_version_id,
            created_at=content_package.created_at,
            note_draft_ids=[
                link.note_draft_id for link in content_package.note_draft_links
            ],
            question_bank_item_ids=[
                link.question_bank_item_id
                for link in content_package.question_bank_item_links
            ],
            approval_status=content_package.approval_status,
            approval_decided_at=content_package.approval_decided_at,
            reviewer_note=content_package.reviewer_note,
            release_status=content_package.release_status,
            released_at=content_package.released_at,
            withdrawn_at=content_package.withdrawn_at,
            release_note=content_package.release_note,
        )

    @staticmethod
    def _content_document_response(
        content_document: ContentDocument,
    ) -> ContentDocumentResponse:
        return ContentDocumentResponse(
            id=content_document.id,
            content_package_id=content_document.content_package_id,
            content_version_id=content_document.content_version_id,
            title=content_document.title,
            markdown=content_document.markdown,
            sha256=content_document.sha256,
            created_at=content_document.created_at,
            approval_status=content_document.approval_status,
            approval_decided_at=content_document.approval_decided_at,
            reviewer_note=content_document.reviewer_note,
            release_status=content_document.release_status,
            released_at=content_document.released_at,
            withdrawn_at=content_document.withdrawn_at,
            release_note=content_document.release_note,
        )

    @staticmethod
    def _source_discovery_run_response(
        source_discovery_run: SourceDiscoveryRun,
    ) -> SourceDiscoveryRunResponse:
        return SourceDiscoveryRunResponse.model_validate(source_discovery_run)

    @staticmethod
    def _source_candidate_response(
        source_candidate: SourceCandidate,
    ) -> SourceCandidateResponse:
        return SourceCandidateResponse.model_validate(source_candidate)

    @staticmethod
    def _source_candidate_promotion_response(
        promotion: SourceCandidatePromotion,
    ) -> SourceCandidatePromotionResponse:
        return SourceCandidatePromotionResponse.model_validate(promotion)

    @staticmethod
    def _pdf_artifact_response(pdf_artifact: PdfArtifact) -> PdfArtifactResponse:
        return PdfArtifactResponse(
            id=pdf_artifact.id,
            content_document_id=pdf_artifact.content_document_id,
            content_package_id=pdf_artifact.content_package_id,
            content_version_id=pdf_artifact.content_version_id,
            filename=pdf_artifact.filename,
            media_type=pdf_artifact.media_type,
            byte_size=pdf_artifact.byte_size,
            sha256=pdf_artifact.sha256,
            created_at=pdf_artifact.created_at,
            approval_status=pdf_artifact.approval_status,
            approval_decided_at=pdf_artifact.approval_decided_at,
            reviewer_note=pdf_artifact.reviewer_note,
            release_status=pdf_artifact.release_status,
            released_at=pdf_artifact.released_at,
            withdrawn_at=pdf_artifact.withdrawn_at,
            release_note=pdf_artifact.release_note,
        )

    def _get_pdf_artifact_or_raise(self, pdf_artifact_id: int) -> PdfArtifact:
        pdf_artifact = self.repository.get_pdf_artifact(pdf_artifact_id)
        if pdf_artifact is None:
            raise ResourceNotFoundError("PdfArtifact", pdf_artifact_id)
        return pdf_artifact

    @staticmethod
    def _render_content_document_markdown(
        content_package_id: int,
        note_drafts: list[NoteDraft],
        question_bank_items: list[QuestionBankItem],
    ) -> str:
        sections = [f"# Content Package {content_package_id}"]
        if note_drafts:
            sections.append("## Notes")
            sections.extend(note_draft.markdown.rstrip("\n") for note_draft in note_drafts)
        if question_bank_items:
            sections.append("## Practice Questions")
            for question_number, question_bank_item in enumerate(
                question_bank_items,
                start=1,
            ):
                if len(question_bank_item.options) > 26:
                    raise RuntimeError(
                        f"QuestionBankItem {question_bank_item.id} has more than "
                        "26 options"
                    )
                option_lines = [
                    f"{chr(ord('A') + position)}. {option.option_text}"
                    for position, option in enumerate(question_bank_item.options)
                ]
                correct_position = next(
                    (
                        position
                        for position, option in enumerate(
                            question_bank_item.options
                        )
                        if option.id == question_bank_item.correct_option_id
                    ),
                    None,
                )
                if correct_position is None:
                    raise RuntimeError(
                        f"QuestionBankItem {question_bank_item.id} has no resolvable "
                        "correct option"
                    )
                correct_option = question_bank_item.options[correct_position]
                answer_label = chr(ord("A") + correct_position)
                question_lines = [
                    f"### Question {question_number}",
                    question_bank_item.question_text,
                    "\n".join(option_lines),
                    f"**Answer:** {answer_label}. {correct_option.option_text}",
                    f"**Explanation:** {question_bank_item.explanation}",
                ]
                sections.append("\n\n".join(question_lines))
        return "\n\n".join(sections) + "\n"

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
            content_version_id=note_draft.content_version_id,
            topic_name=note_draft.topic.name,
            created_at=note_draft.created_at,
            claim_ids=[link.claim_id for link in note_draft.claim_links],
            markdown=note_draft.markdown,
            approval_status=note_draft.approval_status,
            approval_decided_at=note_draft.approval_decided_at,
            reviewer_note=note_draft.reviewer_note,
            release_status=note_draft.release_status,
            released_at=note_draft.released_at,
            withdrawn_at=note_draft.withdrawn_at,
            release_note=note_draft.release_note,
        )

    @staticmethod
    def _question_bank_item_response(
        question_bank_item: QuestionBankItem,
    ) -> QuestionBankItemResponse:
        correct_option_position = next(
            (
                option.position
                for option in question_bank_item.options
                if option.id == question_bank_item.correct_option_id
            ),
            None,
        )
        return QuestionBankItemResponse(
            id=question_bank_item.id,
            content_version_id=question_bank_item.content_version_id,
            question_text=question_bank_item.question_text,
            explanation=question_bank_item.explanation,
            difficulty=question_bank_item.difficulty,
            created_at=question_bank_item.created_at,
            claim_ids=[link.claim_id for link in question_bank_item.claim_links],
            options=[option.option_text for option in question_bank_item.options],
            correct_option_position=correct_option_position,
            approval_status=question_bank_item.approval_status,
            approval_decided_at=question_bank_item.approval_decided_at,
            reviewer_note=question_bank_item.reviewer_note,
            release_status=question_bank_item.release_status,
            released_at=question_bank_item.released_at,
            withdrawn_at=question_bank_item.withdrawn_at,
            release_note=question_bank_item.release_note,
        )

    @staticmethod
    def _is_complete_question_bank_item(
        question_bank_item: QuestionBankItem,
    ) -> bool:
        return len(question_bank_item.options) >= 2 and any(
            option.id == question_bank_item.correct_option_id
            for option in question_bank_item.options
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
