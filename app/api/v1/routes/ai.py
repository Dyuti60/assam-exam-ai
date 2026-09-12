from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.ai import (
    AiExecutionRunResponse,
    AiPromptVersionCreate,
    AiPromptVersionResponse,
)
from app.services.ai import (
    AiAuditService,
    AiPromptService,
    AiResourceConflictError,
    AiResourceNotFoundError,
)

router = APIRouter()
DatabaseSession = Annotated[Session, Depends(get_db)]


def _not_found(error: AiResourceNotFoundError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))


@router.post(
    "/ai-prompt-versions",
    response_model=AiPromptVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_ai_prompt_version(
    request: AiPromptVersionCreate, db: DatabaseSession
) -> AiPromptVersionResponse:
    try:
        return AiPromptService(db).create(request)
    except AiResourceConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(error)
        ) from error


@router.get(
    "/ai-prompt-versions/{ai_prompt_version_id}",
    response_model=AiPromptVersionResponse,
)
def get_ai_prompt_version(
    ai_prompt_version_id: int, db: DatabaseSession
) -> AiPromptVersionResponse:
    try:
        return AiPromptService(db).get(ai_prompt_version_id)
    except AiResourceNotFoundError as error:
        raise _not_found(error) from error


@router.get(
    "/ai-execution-runs/{ai_execution_run_id}",
    response_model=AiExecutionRunResponse,
)
def get_ai_execution_run(
    ai_execution_run_id: int, db: DatabaseSession
) -> AiExecutionRunResponse:
    try:
        return AiAuditService(db).get(ai_execution_run_id)
    except AiResourceNotFoundError as error:
        raise _not_found(error) from error
