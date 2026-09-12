from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.claim_extraction import (
    POSTGRES_INTEGER_MAX,
    ClaimExtractionCreate,
    ClaimExtractionRunResponse,
)
from app.services.ai import AiExecutionRejectedError
from app.services.claim_extraction import (
    ClaimExtractionConflictError,
    ClaimExtractionNotFoundError,
    build_claim_extraction_service,
)

router = APIRouter()
DatabaseSession = Annotated[Session, Depends(get_db)]
BoundedDatabaseId = Annotated[int, Path(gt=0, le=POSTGRES_INTEGER_MAX)]


@router.post(
    "/source-extraction-runs/{source_extraction_run_id}/claim-extractions",
    response_model=ClaimExtractionRunResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_claim_extraction(
    source_extraction_run_id: BoundedDatabaseId,
    request: ClaimExtractionCreate,
    db: DatabaseSession,
) -> ClaimExtractionRunResponse:
    try:
        return build_claim_extraction_service(db).create(
            source_extraction_run_id,
            request.ai_prompt_version_id,
        )
    except ClaimExtractionNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(error)
        ) from error
    except (ClaimExtractionConflictError, AiExecutionRejectedError) as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(error)
        ) from error


@router.get(
    "/claim-extraction-runs/{claim_extraction_run_id}",
    response_model=ClaimExtractionRunResponse,
)
def get_claim_extraction(
    claim_extraction_run_id: BoundedDatabaseId,
    db: DatabaseSession,
) -> ClaimExtractionRunResponse:
    try:
        return build_claim_extraction_service(db).get(claim_extraction_run_id)
    except ClaimExtractionNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(error)
        ) from error
