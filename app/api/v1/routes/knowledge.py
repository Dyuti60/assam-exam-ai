from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.knowledge import (
    ClaimApprovalCreate,
    ClaimCreate,
    ClaimResponse,
    ContentDocumentApprovalCreate,
    ContentDocumentReleaseCreate,
    ContentDocumentResponse,
    ContentPackageApprovalCreate,
    ContentPackageContentResponse,
    ContentPackageReleaseCreate,
    ContentPackageResponse,
    ContentVersionCreate,
    ContentVersionReleasedAssetsResponse,
    ContentVersionResponse,
    EvidenceCreate,
    EvidenceResponse,
    ExamCreate,
    ExamResponse,
    NoteDraftApprovalCreate,
    NoteDraftCreate,
    NoteDraftPreviewResponse,
    NoteDraftReleaseCreate,
    NoteDraftResponse,
    PreviousPaperCreate,
    PreviousPaperResponse,
    PreviousQuestionCreate,
    PreviousQuestionResponse,
    QuestionBankItemApprovalCreate,
    QuestionBankItemCreate,
    QuestionBankItemReleaseCreate,
    QuestionBankItemResponse,
    SourceCreate,
    SourceResponse,
    SyllabusVersionCreate,
    SyllabusVersionResponse,
    TopicCreate,
    TopicPriorityResponse,
    TopicResponse,
    VerificationCreate,
    VerificationResponse,
)
from app.services import KnowledgeService, ResourceConflictError, ResourceNotFoundError

router = APIRouter()

DatabaseSession = Annotated[Session, Depends(get_db)]


def _not_found(error: ResourceNotFoundError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))


def _conflict(error: ResourceConflictError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))


@router.post("/sources", response_model=SourceResponse, status_code=201)
def create_source(request: SourceCreate, db: DatabaseSession) -> SourceResponse:
    return KnowledgeService(db).create_source(request)


@router.post("/exams", response_model=ExamResponse, status_code=201)
def create_exam(request: ExamCreate, db: DatabaseSession) -> ExamResponse:
    try:
        return KnowledgeService(db).create_exam(request)
    except ResourceConflictError as error:
        raise _conflict(error) from error


@router.post(
    "/syllabus-versions",
    response_model=SyllabusVersionResponse,
    status_code=201,
)
def create_syllabus_version(
    request: SyllabusVersionCreate,
    db: DatabaseSession,
) -> SyllabusVersionResponse:
    try:
        return KnowledgeService(db).create_syllabus_version(request)
    except ResourceNotFoundError as error:
        raise _not_found(error) from error
    except ResourceConflictError as error:
        raise _conflict(error) from error


@router.get(
    "/syllabus-versions/{syllabus_version_id}/topics/{topic_id}/priority",
    response_model=TopicPriorityResponse,
)
def get_topic_priority(
    syllabus_version_id: int,
    topic_id: int,
    db: DatabaseSession,
) -> TopicPriorityResponse:
    try:
        return KnowledgeService(db).get_topic_priority(syllabus_version_id, topic_id)
    except ResourceNotFoundError as error:
        raise _not_found(error) from error


@router.post(
    "/content-versions",
    response_model=ContentVersionResponse,
    status_code=201,
)
def create_content_version(
    request: ContentVersionCreate,
    db: DatabaseSession,
) -> ContentVersionResponse:
    try:
        return KnowledgeService(db).create_content_version(request)
    except ResourceNotFoundError as error:
        raise _not_found(error) from error
    except ResourceConflictError as error:
        raise _conflict(error) from error


@router.get(
    "/content-versions/{content_version_id}",
    response_model=ContentVersionResponse,
)
def get_content_version(
    content_version_id: int,
    db: DatabaseSession,
) -> ContentVersionResponse:
    try:
        return KnowledgeService(db).get_content_version(content_version_id)
    except ResourceNotFoundError as error:
        raise _not_found(error) from error


@router.get(
    "/content-versions/{content_version_id}/released-assets",
    response_model=ContentVersionReleasedAssetsResponse,
)
def get_content_version_released_assets(
    content_version_id: int,
    db: DatabaseSession,
) -> ContentVersionReleasedAssetsResponse:
    try:
        return KnowledgeService(db).get_content_version_released_assets(
            content_version_id
        )
    except ResourceNotFoundError as error:
        raise _not_found(error) from error


@router.post(
    "/content-versions/{content_version_id}/content-packages",
    response_model=ContentPackageResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_content_package(
    content_version_id: int,
    db: DatabaseSession,
) -> ContentPackageResponse:
    try:
        return KnowledgeService(db).create_content_package(content_version_id)
    except ResourceNotFoundError as error:
        raise _not_found(error) from error
    except ResourceConflictError as error:
        raise _conflict(error) from error


@router.get(
    "/content-packages/{content_package_id}/content",
    response_model=ContentPackageContentResponse,
)
def get_content_package_content(
    content_package_id: int,
    db: DatabaseSession,
) -> ContentPackageContentResponse:
    try:
        return KnowledgeService(db).get_content_package_content(content_package_id)
    except ResourceNotFoundError as error:
        raise _not_found(error) from error


@router.get(
    "/content-packages/released",
    response_model=list[ContentPackageResponse],
)
def get_released_content_packages(
    db: DatabaseSession,
) -> list[ContentPackageResponse]:
    return KnowledgeService(db).get_released_content_packages()


@router.get(
    "/content-packages/{content_package_id}",
    response_model=ContentPackageResponse,
)
def get_content_package(
    content_package_id: int,
    db: DatabaseSession,
) -> ContentPackageResponse:
    try:
        return KnowledgeService(db).get_content_package(content_package_id)
    except ResourceNotFoundError as error:
        raise _not_found(error) from error


@router.post(
    "/content-packages/{content_package_id}/approval",
    response_model=ContentPackageResponse,
)
def record_content_package_approval(
    content_package_id: int,
    request: ContentPackageApprovalCreate,
    db: DatabaseSession,
) -> ContentPackageResponse:
    try:
        return KnowledgeService(db).record_content_package_approval(
            content_package_id,
            request,
        )
    except ResourceNotFoundError as error:
        raise _not_found(error) from error
    except ResourceConflictError as error:
        raise _conflict(error) from error


@router.post(
    "/content-packages/{content_package_id}/release",
    response_model=ContentPackageResponse,
)
def record_content_package_release(
    content_package_id: int,
    request: ContentPackageReleaseCreate,
    db: DatabaseSession,
) -> ContentPackageResponse:
    try:
        return KnowledgeService(db).record_content_package_release(
            content_package_id,
            request,
        )
    except ResourceNotFoundError as error:
        raise _not_found(error) from error
    except ResourceConflictError as error:
        raise _conflict(error) from error


@router.post(
    "/content-packages/{content_package_id}/content-documents",
    response_model=ContentDocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_content_document(
    content_package_id: int,
    db: DatabaseSession,
) -> ContentDocumentResponse:
    try:
        return KnowledgeService(db).create_content_document(content_package_id)
    except ResourceNotFoundError as error:
        raise _not_found(error) from error
    except ResourceConflictError as error:
        raise _conflict(error) from error


@router.get(
    "/content-documents/released",
    response_model=list[ContentDocumentResponse],
)
def get_released_content_documents(
    db: DatabaseSession,
) -> list[ContentDocumentResponse]:
    return KnowledgeService(db).get_released_content_documents()


@router.get(
    "/content-documents/{content_document_id}",
    response_model=ContentDocumentResponse,
)
def get_content_document(
    content_document_id: int,
    db: DatabaseSession,
) -> ContentDocumentResponse:
    try:
        return KnowledgeService(db).get_content_document(content_document_id)
    except ResourceNotFoundError as error:
        raise _not_found(error) from error


@router.post(
    "/content-documents/{content_document_id}/approval",
    response_model=ContentDocumentResponse,
)
def record_content_document_approval(
    content_document_id: int,
    request: ContentDocumentApprovalCreate,
    db: DatabaseSession,
) -> ContentDocumentResponse:
    try:
        return KnowledgeService(db).record_content_document_approval(
            content_document_id,
            request,
        )
    except ResourceNotFoundError as error:
        raise _not_found(error) from error
    except ResourceConflictError as error:
        raise _conflict(error) from error


@router.post(
    "/content-documents/{content_document_id}/release",
    response_model=ContentDocumentResponse,
)
def record_content_document_release(
    content_document_id: int,
    request: ContentDocumentReleaseCreate,
    db: DatabaseSession,
) -> ContentDocumentResponse:
    try:
        return KnowledgeService(db).record_content_document_release(
            content_document_id,
            request,
        )
    except ResourceNotFoundError as error:
        raise _not_found(error) from error
    except ResourceConflictError as error:
        raise _conflict(error) from error


@router.post(
    "/question-bank-items",
    response_model=QuestionBankItemResponse,
    status_code=201,
)
def create_question_bank_item(
    request: QuestionBankItemCreate,
    db: DatabaseSession,
) -> QuestionBankItemResponse:
    try:
        return KnowledgeService(db).create_question_bank_item(request)
    except ResourceNotFoundError as error:
        raise _not_found(error) from error
    except ResourceConflictError as error:
        raise _conflict(error) from error


@router.get(
    "/question-bank-items/approved",
    response_model=list[QuestionBankItemResponse],
)
def get_approved_question_bank_items(
    db: DatabaseSession,
) -> list[QuestionBankItemResponse]:
    return KnowledgeService(db).get_approved_question_bank_items()


@router.get(
    "/question-bank-items/released",
    response_model=list[QuestionBankItemResponse],
)
def get_released_question_bank_items(
    db: DatabaseSession,
) -> list[QuestionBankItemResponse]:
    return KnowledgeService(db).get_released_question_bank_items()


@router.get(
    "/question-bank-items/{question_bank_item_id}",
    response_model=QuestionBankItemResponse,
)
def get_question_bank_item(
    question_bank_item_id: int,
    db: DatabaseSession,
) -> QuestionBankItemResponse:
    try:
        return KnowledgeService(db).get_question_bank_item(question_bank_item_id)
    except ResourceNotFoundError as error:
        raise _not_found(error) from error


@router.post(
    "/question-bank-items/{question_bank_item_id}/approval",
    response_model=QuestionBankItemResponse,
)
def record_question_bank_item_approval(
    question_bank_item_id: int,
    request: QuestionBankItemApprovalCreate,
    db: DatabaseSession,
) -> QuestionBankItemResponse:
    try:
        return KnowledgeService(db).record_question_bank_item_approval(
            question_bank_item_id,
            request,
        )
    except ResourceNotFoundError as error:
        raise _not_found(error) from error
    except ResourceConflictError as error:
        raise _conflict(error) from error


@router.post(
    "/question-bank-items/{question_bank_item_id}/release",
    response_model=QuestionBankItemResponse,
)
def record_question_bank_item_release(
    question_bank_item_id: int,
    request: QuestionBankItemReleaseCreate,
    db: DatabaseSession,
) -> QuestionBankItemResponse:
    try:
        return KnowledgeService(db).record_question_bank_item_release(
            question_bank_item_id,
            request,
        )
    except ResourceNotFoundError as error:
        raise _not_found(error) from error
    except ResourceConflictError as error:
        raise _conflict(error) from error


@router.post(
    "/previous-papers",
    response_model=PreviousPaperResponse,
    status_code=201,
)
def create_previous_paper(
    request: PreviousPaperCreate,
    db: DatabaseSession,
) -> PreviousPaperResponse:
    try:
        return KnowledgeService(db).create_previous_paper(request)
    except ResourceNotFoundError as error:
        raise _not_found(error) from error
    except ResourceConflictError as error:
        raise _conflict(error) from error


@router.post(
    "/previous-questions",
    response_model=PreviousQuestionResponse,
    status_code=201,
)
def create_previous_question(
    request: PreviousQuestionCreate,
    db: DatabaseSession,
) -> PreviousQuestionResponse:
    try:
        return KnowledgeService(db).create_previous_question(request)
    except ResourceNotFoundError as error:
        raise _not_found(error) from error
    except ResourceConflictError as error:
        raise _conflict(error) from error


@router.post("/topics", response_model=TopicResponse, status_code=201)
def create_topic(request: TopicCreate, db: DatabaseSession) -> TopicResponse:
    try:
        return KnowledgeService(db).create_topic(request)
    except ResourceConflictError as error:
        raise _conflict(error) from error


@router.get("/topics/{topic_id}/claims/approved", response_model=list[ClaimResponse])
def get_approved_claims_by_topic(
    topic_id: int,
    db: DatabaseSession,
) -> list[ClaimResponse]:
    try:
        return KnowledgeService(db).get_approved_claims_by_topic(topic_id)
    except ResourceNotFoundError as error:
        raise _not_found(error) from error


@router.post(
    "/topics/{topic_id}/note-draft-preview",
    response_model=NoteDraftPreviewResponse,
)
def create_note_draft_preview(
    topic_id: int,
    db: DatabaseSession,
) -> NoteDraftPreviewResponse:
    try:
        return KnowledgeService(db).create_note_draft_preview(topic_id)
    except ResourceNotFoundError as error:
        raise _not_found(error) from error
    except ResourceConflictError as error:
        raise _conflict(error) from error


@router.post(
    "/topics/{topic_id}/note-drafts",
    response_model=NoteDraftResponse,
    status_code=201,
)
def create_note_draft(
    topic_id: int,
    request: NoteDraftCreate,
    db: DatabaseSession,
) -> NoteDraftResponse:
    try:
        return KnowledgeService(db).create_note_draft(topic_id, request)
    except ResourceNotFoundError as error:
        raise _not_found(error) from error
    except ResourceConflictError as error:
        raise _conflict(error) from error


@router.get("/note-drafts/approved", response_model=list[NoteDraftResponse])
def get_approved_note_drafts(db: DatabaseSession) -> list[NoteDraftResponse]:
    return KnowledgeService(db).get_approved_note_drafts()


@router.get("/note-drafts/released", response_model=list[NoteDraftResponse])
def get_released_note_drafts(db: DatabaseSession) -> list[NoteDraftResponse]:
    return KnowledgeService(db).get_released_note_drafts()


@router.get("/note-drafts/{note_draft_id}", response_model=NoteDraftResponse)
def get_note_draft(
    note_draft_id: int,
    db: DatabaseSession,
) -> NoteDraftResponse:
    try:
        return KnowledgeService(db).get_note_draft(note_draft_id)
    except ResourceNotFoundError as error:
        raise _not_found(error) from error


@router.post(
    "/note-drafts/{note_draft_id}/approval",
    response_model=NoteDraftResponse,
)
def record_note_draft_approval(
    note_draft_id: int,
    request: NoteDraftApprovalCreate,
    db: DatabaseSession,
) -> NoteDraftResponse:
    try:
        return KnowledgeService(db).record_note_draft_approval(
            note_draft_id,
            request,
        )
    except ResourceNotFoundError as error:
        raise _not_found(error) from error
    except ResourceConflictError as error:
        raise _conflict(error) from error


@router.post(
    "/note-drafts/{note_draft_id}/release",
    response_model=NoteDraftResponse,
)
def record_note_draft_release(
    note_draft_id: int,
    request: NoteDraftReleaseCreate,
    db: DatabaseSession,
) -> NoteDraftResponse:
    try:
        return KnowledgeService(db).record_note_draft_release(
            note_draft_id,
            request,
        )
    except ResourceNotFoundError as error:
        raise _not_found(error) from error
    except ResourceConflictError as error:
        raise _conflict(error) from error


@router.post("/evidence", response_model=EvidenceResponse, status_code=201)
def create_evidence(request: EvidenceCreate, db: DatabaseSession) -> EvidenceResponse:
    try:
        return KnowledgeService(db).create_evidence(request)
    except ResourceNotFoundError as error:
        raise _not_found(error) from error


@router.get("/evidence/{evidence_id}", response_model=EvidenceResponse)
def get_evidence(evidence_id: int, db: DatabaseSession) -> EvidenceResponse:
    try:
        return KnowledgeService(db).get_evidence(evidence_id)
    except ResourceNotFoundError as error:
        raise _not_found(error) from error


@router.post("/claims", response_model=ClaimResponse, status_code=201)
def create_claim(request: ClaimCreate, db: DatabaseSession) -> ClaimResponse:
    try:
        return KnowledgeService(db).create_claim(request)
    except ResourceNotFoundError as error:
        raise _not_found(error) from error


@router.get("/claims/approved", response_model=list[ClaimResponse])
def get_approved_claims(db: DatabaseSession) -> list[ClaimResponse]:
    return KnowledgeService(db).get_approved_claims()


@router.get("/claims/{claim_id}", response_model=ClaimResponse)
def get_claim(claim_id: int, db: DatabaseSession) -> ClaimResponse:
    try:
        return KnowledgeService(db).get_claim(claim_id)
    except ResourceNotFoundError as error:
        raise _not_found(error) from error


@router.post(
    "/claims/{claim_id}/evidence/{evidence_id}",
    response_model=ClaimResponse,
)
def link_claim_evidence(
    claim_id: int,
    evidence_id: int,
    db: DatabaseSession,
) -> ClaimResponse:
    try:
        return KnowledgeService(db).link_claim_evidence(claim_id, evidence_id)
    except ResourceNotFoundError as error:
        raise _not_found(error) from error


@router.post("/claims/{claim_id}/approval", response_model=ClaimResponse)
def record_claim_approval(
    claim_id: int,
    request: ClaimApprovalCreate,
    db: DatabaseSession,
) -> ClaimResponse:
    try:
        return KnowledgeService(db).record_claim_approval(claim_id, request)
    except ResourceNotFoundError as error:
        raise _not_found(error) from error


@router.post("/verifications", response_model=VerificationResponse, status_code=201)
def create_verification(
    request: VerificationCreate,
    db: DatabaseSession,
) -> VerificationResponse:
    try:
        return KnowledgeService(db).create_verification(request)
    except ResourceNotFoundError as error:
        raise _not_found(error) from error


@router.get("/verifications/{verification_id}", response_model=VerificationResponse)
def get_verification(verification_id: int, db: DatabaseSession) -> VerificationResponse:
    try:
        return KnowledgeService(db).get_verification(verification_id)
    except ResourceNotFoundError as error:
        raise _not_found(error) from error
