from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AiExecutionStatus(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class AiPromptVersionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    prompt_key: str = Field(pattern=r"^[a-z][a-z0-9_.-]*$", max_length=100)
    version: int = Field(gt=0)
    system_template: str = Field(min_length=1, max_length=20_000)
    user_template: str = Field(min_length=1, max_length=20_000)
    input_schema_key: str = Field(pattern=r"^[a-z][a-z0-9_.-]*$", max_length=100)
    input_schema_version: int = Field(gt=0)
    output_schema_key: str = Field(pattern=r"^[a-z][a-z0-9_.-]*$", max_length=100)
    output_schema_version: int = Field(gt=0)

    @field_validator("system_template", "user_template")
    @classmethod
    def reject_blank_template(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("template must not be blank")
        return value


class AiPromptVersionResponse(AiPromptVersionCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    checksum: str
    created_at: datetime


class AiExecutionRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ai_prompt_version_id: int
    prompt_key: str
    prompt_version: int
    prompt_checksum: str
    provider_key: str
    model_id: str
    request_id: str
    status: AiExecutionStatus
    input_json: dict[str, Any]
    input_sha256: str
    rendered_system_sha256: str
    rendered_user_sha256: str
    output_json: dict[str, Any] | None
    output_sha256: str | None
    error_code: str | None
    provider_request_id: str | None
    started_at: datetime
    completed_at: datetime
    duration_ms: int
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    provider_cost: Decimal | None
    cost_currency: str | None
    finish_reason: str | None
    safety_metadata: dict[str, Any] | None
    created_at: datetime
