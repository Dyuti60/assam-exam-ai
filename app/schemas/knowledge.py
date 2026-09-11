from datetime import datetime
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class EvidenceRole(StrEnum):
    SUPPORTS = "SUPPORTS"
    CONTRADICTS = "CONTRADICTS"
    CONTEXT = "CONTEXT"


class VerificationVerdict(StrEnum):
    SUPPORTED = "SUPPORTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    UNVERIFIED = "UNVERIFIED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    OUTDATED = "OUTDATED"
    CONFLICTING = "CONFLICTING"
    NEEDS_HUMAN_REVIEW = "NEEDS_HUMAN_REVIEW"


class ClaimApprovalStatus(StrEnum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class SourceDiscoveryStatus(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class SourceCandidateApprovalStatus(StrEnum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class SourceCandidateCreate(BaseModel):
    location: str = Field(min_length=1)
    title: str | None = None
    publisher: str | None = Field(default=None, max_length=255)
    snippet: str | None = None

    @field_validator("location")
    @classmethod
    def normalize_location(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("location must not be blank")
        return normalized

    @field_validator("title", "publisher", "snippet")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("supplied optional text must not be blank")
        return normalized


class SourceDiscoveryRunCreate(BaseModel):
    query: str = Field(min_length=1)
    adapter_key: str = Field(min_length=1, max_length=100)
    status: SourceDiscoveryStatus
    error_message: str | None = None
    candidates: list[SourceCandidateCreate] = Field(default_factory=list)

    @field_validator("query", "adapter_key")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be blank")
        return normalized

    @field_validator("error_message")
    @classmethod
    def normalize_error_message(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("error_message must not be blank")
        return normalized

    @model_validator(mode="after")
    def validate_lifecycle_and_candidates(self) -> Self:
        if self.status == SourceDiscoveryStatus.SUCCEEDED and self.error_message:
            raise ValueError("SUCCEEDED runs must not have an error_message")
        if self.status == SourceDiscoveryStatus.FAILED:
            if self.error_message is None:
                raise ValueError("FAILED runs require an error_message")
            if self.candidates:
                raise ValueError("FAILED runs must not have candidates")
        locations = [candidate.location for candidate in self.candidates]
        if len(locations) != len(set(locations)):
            raise ValueError("candidate locations must be unique")
        return self


class OfficialSiteDiscoveryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=500)
    site_root: str = Field(min_length=1, max_length=2_048)

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("query must not be blank")
        return normalized

    @field_validator("site_root")
    @classmethod
    def normalize_site_root(cls, value: str) -> str:
        from app.services.official_site_discovery import canonicalize_site_root

        return canonicalize_site_root(value)


class SourceCandidateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_discovery_run_id: int
    run_status: SourceDiscoveryStatus
    position: int
    location: str
    title: str | None
    publisher: str | None
    snippet: str | None
    created_at: datetime
    approval_status: SourceCandidateApprovalStatus
    approval_decided_at: datetime | None
    reviewer_note: str | None


class SourceCandidateApprovalCreate(BaseModel):
    approval_status: SourceCandidateApprovalStatus
    reviewer_note: str | None = None


class SourceDiscoveryRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    query: str
    adapter_key: str
    status: SourceDiscoveryStatus
    error_message: str | None
    created_at: datetime
    candidates: list[SourceCandidateResponse]


class SourceCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    publisher: str | None = Field(default=None, max_length=255)
    source_type: str = Field(min_length=1, max_length=100)
    authority_tier: int = Field(ge=1, le=4)
    location: str = Field(min_length=1)
    license_status: str = Field(min_length=1, max_length=100)
    content_hash: str | None = Field(default=None, max_length=128)


class SourceCandidatePromotionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=500)
    publisher: str | None = Field(default=None, max_length=255)
    source_type: str = Field(min_length=1, max_length=100)
    authority_tier: int = Field(ge=1, le=4)
    license_status: str = Field(min_length=1, max_length=100)

    @field_validator("title", "source_type", "license_status")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be blank")
        return normalized

    @field_validator("publisher")
    @classmethod
    def normalize_optional_publisher(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("publisher must not be blank")
        return normalized


class SourceResponse(SourceCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class SourceCandidatePromotionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_candidate_id: int
    source_id: int
    location: str
    candidate_approval_status: SourceCandidateApprovalStatus
    candidate_approval_decided_at: datetime
    candidate_reviewer_note: str | None
    created_at: datetime
    source: SourceResponse


class TopicCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class TopicResponse(TopicCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class ExamCreate(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=255)


class ExamResponse(ExamCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class SyllabusVersionCreate(BaseModel):
    exam_id: int = Field(gt=0)
    source_id: int = Field(gt=0)
    label: str = Field(min_length=1, max_length=255)
    topic_ids: list[int] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_topic_ids(self) -> Self:
        if any(topic_id <= 0 for topic_id in self.topic_ids):
            raise ValueError("topic_id values must be positive")
        if len(self.topic_ids) != len(set(self.topic_ids)):
            raise ValueError("topic_id values must be unique")
        return self


class SyllabusVersionResponse(BaseModel):
    id: int
    exam_id: int
    source_id: int
    label: str
    created_at: datetime
    topic_ids: list[int]


class ContentVersionCreate(BaseModel):
    syllabus_version_id: int = Field(gt=0)
    topic_id: int = Field(gt=0)
    version: int = Field(gt=0)


class ContentVersionResponse(ContentVersionCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class QuestionDifficulty(StrEnum):
    EASY = "EASY"
    MEDIUM = "MEDIUM"
    HARD = "HARD"


class QuestionBankItemReleaseStatus(StrEnum):
    UNRELEASED = "UNRELEASED"
    RELEASED = "RELEASED"
    WITHDRAWN = "WITHDRAWN"


class QuestionBankItemReleaseDecision(StrEnum):
    RELEASED = "RELEASED"
    WITHDRAWN = "WITHDRAWN"


class QuestionBankItemCreate(BaseModel):
    content_version_id: int = Field(gt=0)
    question_text: str = Field(min_length=1)
    explanation: str = Field(min_length=1)
    difficulty: QuestionDifficulty
    claim_ids: list[int] = Field(min_length=1)
    options: list[str] = Field(min_length=2)
    correct_option_position: int = Field(ge=0)

    @field_validator("question_text", "explanation")
    @classmethod
    def validate_non_blank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must not be blank")
        return value

    @model_validator(mode="after")
    def validate_claim_ids(self) -> Self:
        if any(claim_id <= 0 for claim_id in self.claim_ids):
            raise ValueError("claim_id values must be positive")
        if len(self.claim_ids) != len(set(self.claim_ids)):
            raise ValueError("claim_id values must be unique")
        if any(not option.strip() for option in self.options):
            raise ValueError("option values must not be blank")
        if self.correct_option_position >= len(self.options):
            raise ValueError("correct_option_position must reference an option")
        return self


class QuestionBankItemResponse(BaseModel):
    id: int
    content_version_id: int
    question_text: str
    explanation: str
    difficulty: QuestionDifficulty
    created_at: datetime
    claim_ids: list[int]
    options: list[str]
    correct_option_position: int | None
    approval_status: ClaimApprovalStatus
    approval_decided_at: datetime | None
    reviewer_note: str | None
    release_status: QuestionBankItemReleaseStatus
    released_at: datetime | None
    withdrawn_at: datetime | None
    release_note: str | None


class QuestionBankItemApprovalCreate(BaseModel):
    approval_status: ClaimApprovalStatus
    reviewer_note: str | None = None


class QuestionBankItemReleaseCreate(BaseModel):
    release_status: QuestionBankItemReleaseDecision
    release_note: str | None = None


class PreviousPaperCreate(BaseModel):
    exam_id: int = Field(gt=0)
    source_id: int = Field(gt=0)
    year: int = Field(gt=0)
    label: str = Field(min_length=1, max_length=255)


class PreviousPaperResponse(PreviousPaperCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class PreviousQuestionCreate(BaseModel):
    previous_paper_id: int = Field(gt=0)
    topic_id: int = Field(gt=0)
    position: int = Field(ge=0)
    question_text: str = Field(min_length=1)
    source_location_reference: str | None = None

    @field_validator("question_text")
    @classmethod
    def validate_question_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("question_text must not be blank")
        return value


class PreviousQuestionResponse(PreviousQuestionCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class TopicPriorityBand(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class TopicPriorityReason(StrEnum):
    DIRECT_SYLLABUS_COVERAGE = "DIRECT_SYLLABUS_COVERAGE"
    NOT_IN_SELECTED_SYLLABUS_VERSION = "NOT_IN_SELECTED_SYLLABUS_VERSION"
    REPEATED_IN_PREVIOUS_PAPERS = "REPEATED_IN_PREVIOUS_PAPERS"
    APPEARED_IN_PREVIOUS_PAPER = "APPEARED_IN_PREVIOUS_PAPER"
    NO_RECORDED_PREVIOUS_OCCURRENCE = "NO_RECORDED_PREVIOUS_OCCURRENCE"
    NO_PREVIOUS_PAPER_DATA = "NO_PREVIOUS_PAPER_DATA"


class TopicPriorityResponse(BaseModel):
    syllabus_version_id: int
    exam_id: int
    topic_id: int
    syllabus_covered: bool
    exam_paper_count: int
    matched_question_count: int
    matched_paper_count: int
    matched_years: list[int]
    priority_band: TopicPriorityBand
    rule_version: str
    reason_codes: list[TopicPriorityReason]


class NoteDraftPreviewResponse(BaseModel):
    topic_id: int
    topic_name: str
    claim_ids: list[int]
    markdown: str


class NoteDraftCreate(BaseModel):
    content_version_id: int = Field(gt=0)


class NoteDraftReleaseStatus(StrEnum):
    UNRELEASED = "UNRELEASED"
    RELEASED = "RELEASED"
    WITHDRAWN = "WITHDRAWN"


class NoteDraftReleaseDecision(StrEnum):
    RELEASED = "RELEASED"
    WITHDRAWN = "WITHDRAWN"


class NoteDraftResponse(NoteDraftPreviewResponse):
    id: int
    content_version_id: int | None
    created_at: datetime
    approval_status: ClaimApprovalStatus
    approval_decided_at: datetime | None
    reviewer_note: str | None
    release_status: NoteDraftReleaseStatus
    released_at: datetime | None
    withdrawn_at: datetime | None
    release_note: str | None


class NoteDraftApprovalCreate(BaseModel):
    approval_status: ClaimApprovalStatus
    reviewer_note: str | None = None


class NoteDraftReleaseCreate(BaseModel):
    release_status: NoteDraftReleaseDecision
    release_note: str | None = None


class ContentVersionReleasedAssetsResponse(BaseModel):
    content_version: ContentVersionResponse
    note_drafts: list[NoteDraftResponse]
    question_bank_items: list[QuestionBankItemResponse]


class ContentPackageReleaseStatus(StrEnum):
    UNRELEASED = "UNRELEASED"
    RELEASED = "RELEASED"
    WITHDRAWN = "WITHDRAWN"


class ContentPackageReleaseDecision(StrEnum):
    RELEASED = "RELEASED"
    WITHDRAWN = "WITHDRAWN"


class ContentDocumentReleaseStatus(StrEnum):
    UNRELEASED = "UNRELEASED"
    RELEASED = "RELEASED"
    WITHDRAWN = "WITHDRAWN"


class ContentDocumentReleaseDecision(StrEnum):
    RELEASED = "RELEASED"
    WITHDRAWN = "WITHDRAWN"


class PdfArtifactReleaseStatus(StrEnum):
    UNRELEASED = "UNRELEASED"
    RELEASED = "RELEASED"
    WITHDRAWN = "WITHDRAWN"


class PdfArtifactReleaseDecision(StrEnum):
    RELEASED = "RELEASED"
    WITHDRAWN = "WITHDRAWN"


class ContentPackageResponse(BaseModel):
    id: int
    content_version_id: int
    created_at: datetime
    note_draft_ids: list[int]
    question_bank_item_ids: list[int]
    approval_status: ClaimApprovalStatus
    approval_decided_at: datetime | None
    reviewer_note: str | None
    release_status: ContentPackageReleaseStatus
    released_at: datetime | None
    withdrawn_at: datetime | None
    release_note: str | None


class ContentPackageApprovalCreate(BaseModel):
    approval_status: ClaimApprovalStatus
    reviewer_note: str | None = None


class ContentPackageReleaseCreate(BaseModel):
    release_status: ContentPackageReleaseDecision
    release_note: str | None = None


class ContentPackageContentResponse(BaseModel):
    content_package: ContentPackageResponse
    note_drafts: list[NoteDraftResponse]
    question_bank_items: list[QuestionBankItemResponse]


class ContentDocumentResponse(BaseModel):
    id: int
    content_package_id: int
    content_version_id: int
    title: str
    markdown: str
    sha256: str
    created_at: datetime
    approval_status: ClaimApprovalStatus
    approval_decided_at: datetime | None
    reviewer_note: str | None
    release_status: ContentDocumentReleaseStatus
    released_at: datetime | None
    withdrawn_at: datetime | None
    release_note: str | None


class ContentDocumentApprovalCreate(BaseModel):
    approval_status: ClaimApprovalStatus
    reviewer_note: str | None = None


class ContentDocumentReleaseCreate(BaseModel):
    release_status: ContentDocumentReleaseDecision
    release_note: str | None = None


class PdfArtifactResponse(BaseModel):
    id: int
    content_document_id: int
    content_package_id: int
    content_version_id: int
    filename: str
    media_type: str
    byte_size: int
    sha256: str
    created_at: datetime
    approval_status: ClaimApprovalStatus
    approval_decided_at: datetime | None
    reviewer_note: str | None
    release_status: PdfArtifactReleaseStatus
    released_at: datetime | None
    withdrawn_at: datetime | None
    release_note: str | None


class PdfArtifactApprovalCreate(BaseModel):
    approval_status: ClaimApprovalStatus
    reviewer_note: str | None = None


class PdfArtifactReleaseCreate(BaseModel):
    release_status: PdfArtifactReleaseDecision
    release_note: str | None = None


class EvidenceCreate(BaseModel):
    source_id: int = Field(gt=0)
    content: str = Field(min_length=1)
    location_reference: str | None = None


class EvidenceResponse(EvidenceCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int


class ClaimCreate(BaseModel):
    statement: str = Field(min_length=1)
    subject: str | None = None
    predicate: str | None = None
    object_value: str | None = None
    topic_id: int | None = Field(default=None, gt=0)


class ClaimResponse(ClaimCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    verification_status: str
    confidence: float | None
    created_at: datetime
    last_verified_at: datetime | None
    relevant_evidence_ids: list[int] = Field(default_factory=list)
    approval_status: ClaimApprovalStatus
    approval_decided_at: datetime | None
    reviewer_note: str | None


class ClaimApprovalCreate(BaseModel):
    approval_status: ClaimApprovalStatus
    reviewer_note: str | None = None


class VerificationEvidenceCreate(BaseModel):
    evidence_id: int = Field(gt=0)
    evidence_role: EvidenceRole
    position: int = Field(ge=0)


class VerificationCreate(BaseModel):
    claim_id: int = Field(gt=0)
    verdict: VerificationVerdict
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str | None = None
    evidence: list[VerificationEvidenceCreate] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_evidence_and_positions(self) -> Self:
        evidence_ids = [item.evidence_id for item in self.evidence]
        positions = [item.position for item in self.evidence]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("evidence_id values must be unique")
        if len(positions) != len(set(positions)):
            raise ValueError("evidence positions must be unique")
        return self


class VerificationEvidenceResponse(BaseModel):
    evidence_id: int
    source_id: int
    content: str
    location_reference: str | None
    evidence_role: EvidenceRole
    position: int


class VerificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    verdict: VerificationVerdict
    confidence: float
    reasoning: str | None
    created_at: datetime
    claim: ClaimResponse
    evidence: list[VerificationEvidenceResponse]
