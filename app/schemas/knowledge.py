from datetime import datetime
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


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


class SourceCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    publisher: str | None = Field(default=None, max_length=255)
    source_type: str = Field(min_length=1, max_length=100)
    authority_tier: int = Field(ge=1, le=4)
    location: str = Field(min_length=1)
    license_status: str = Field(min_length=1, max_length=100)
    content_hash: str | None = Field(default=None, max_length=128)


class SourceResponse(SourceCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


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


class ClaimResponse(ClaimCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    verification_status: str
    confidence: float | None
    created_at: datetime
    last_verified_at: datetime | None


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
