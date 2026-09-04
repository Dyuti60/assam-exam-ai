from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.knowledge import (
    ClaimApprovalCreate,
    ClaimCreate,
    ClaimResponse,
    EvidenceCreate,
    EvidenceResponse,
    NoteDraftPreviewResponse,
    NoteDraftResponse,
    SourceCreate,
    SourceResponse,
    TopicCreate,
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
    db: DatabaseSession,
) -> NoteDraftResponse:
    try:
        return KnowledgeService(db).create_note_draft(topic_id)
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
