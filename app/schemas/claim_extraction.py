from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.ai import AiExecutionRunResponse

CLAIM_EXTRACTION_INPUT_SCHEMA_KEY = "grounded-claim-extraction.input"
CLAIM_EXTRACTION_OUTPUT_SCHEMA_KEY = "grounded-claim-extraction.output"
CLAIM_EXTRACTION_SCHEMA_VERSION = 1
CLAIM_EXTRACTION_CONTRACT_MAX_CLAIMS = 50
CLAIM_EXTRACTION_CONTRACT_MAX_CITATIONS_PER_CLAIM = 10
POSTGRES_INTEGER_MAX = 2_147_483_647


class ClaimExtractionStatus(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class ClaimExtractionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    ai_prompt_version_id: int = Field(gt=0, le=POSTGRES_INTEGER_MAX)


class GroundedSourceChunkInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    id: int = Field(gt=0, le=POSTGRES_INTEGER_MAX)
    position: int = Field(ge=0)
    source_extraction_run_id: int = Field(gt=0, le=POSTGRES_INTEGER_MAX)
    source_snapshot_id: int = Field(gt=0, le=POSTGRES_INTEGER_MAX)
    source_id: int = Field(gt=0, le=POSTGRES_INTEGER_MAX)
    char_start: int = Field(ge=0)
    char_end: int = Field(gt=0)
    text: str = Field(min_length=1, max_length=1_000)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class GroundedClaimExtractionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    source_extraction_run_id: int = Field(gt=0, le=POSTGRES_INTEGER_MAX)
    source_snapshot_id: int = Field(gt=0, le=POSTGRES_INTEGER_MAX)
    source_id: int = Field(gt=0, le=POSTGRES_INTEGER_MAX)
    snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    chunks: list[GroundedSourceChunkInput] = Field(min_length=1, max_length=100)


class GroundedClaimCitationOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    source_chunk_id: int = Field(gt=0, le=POSTGRES_INTEGER_MAX)
    char_start: int = Field(
        ge=0,
        description="Inclusive Python Unicode code-point offset within chunk text.",
    )
    char_end: int = Field(
        gt=0,
        description="Exclusive Python Unicode code-point offset within chunk text.",
    )


class GroundedClaimProposalOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    statement: str = Field(min_length=1, max_length=2_000)
    subject: str | None = Field(default=None, max_length=500)
    predicate: str | None = Field(default=None, max_length=500)
    object_value: str | None = Field(default=None, max_length=1_000)
    citations: list[GroundedClaimCitationOutput] = Field(
        min_length=1,
        max_length=CLAIM_EXTRACTION_CONTRACT_MAX_CITATIONS_PER_CLAIM,
    )

    @field_validator("statement")
    @classmethod
    def statement_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("claim statement must not be blank")
        return value

    @field_validator("subject", "predicate", "object_value")
    @classmethod
    def optional_text_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("optional claim text must not be blank")
        return value


class GroundedClaimExtractionOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    claims: list[GroundedClaimProposalOutput] = Field(
        min_length=1,
        max_length=CLAIM_EXTRACTION_CONTRACT_MAX_CLAIMS,
    )


class ClaimExtractionEvidenceResponse(BaseModel):
    position: int
    evidence_id: int
    source_chunk_id: int
    source_extraction_run_id: int
    source_snapshot_id: int
    source_id: int
    char_start: int
    char_end: int
    cited_text_sha256: str
    content: str
    location_reference: str


class ClaimExtractionClaimResponse(BaseModel):
    position: int
    claim_id: int
    evidence_ids: list[int]


class ClaimExtractionRunResponse(BaseModel):
    id: int
    source_extraction_run_id: int
    source_snapshot_id: int
    source_id: int
    snapshot_sha256: str
    ai_prompt_version_id: int
    prompt_key: str
    prompt_version: int
    prompt_checksum: str
    ai_execution_run_id: int
    provider_key: str
    model_id: str
    ai_execution_status: str
    status: ClaimExtractionStatus
    error_code: str | None
    created_at: datetime
    completed_at: datetime
    ai_execution: AiExecutionRunResponse
    evidence: list[ClaimExtractionEvidenceResponse]
    claims: list[ClaimExtractionClaimResponse]
