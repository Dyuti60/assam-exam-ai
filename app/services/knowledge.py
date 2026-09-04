from sqlalchemy.orm import Session

from app.models import Claim, Evidence, Source, Verification, VerificationEvidence
from app.repositories import KnowledgeRepository
from app.schemas.knowledge import (
    ClaimCreate,
    ClaimResponse,
    EvidenceCreate,
    SourceCreate,
    VerificationCreate,
    VerificationEvidenceResponse,
    VerificationResponse,
)


class ResourceNotFoundError(Exception):
    def __init__(self, resource: str, resource_id: int) -> None:
        self.resource = resource
        self.resource_id = resource_id
        super().__init__(f"{resource} {resource_id} not found")


class KnowledgeService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = KnowledgeRepository(session)

    def create_source(self, request: SourceCreate) -> Source:
        source = Source(**request.model_dump())
        return self._commit(self.repository.add_source(source))

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
        claim = Claim(**request.model_dump())
        return self._commit(self.repository.add_claim(claim))

    def get_claim(self, claim_id: int) -> ClaimResponse:
        claim = self.repository.get_claim(claim_id)
        if claim is None:
            raise ResourceNotFoundError("Claim", claim_id)
        return self._claim_response(claim)

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

    def _commit(self, instance: Source | Evidence | Claim | Verification):
        try:
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return instance

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
