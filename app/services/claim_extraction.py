from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256

from pydantic import ValidationError
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import (
    AiPromptVersion,
    Claim,
    ClaimExtractionCitation,
    ClaimExtractionClaim,
    ClaimExtractionEvidence,
    ClaimExtractionRun,
    Evidence,
    SourceChunk,
    SourceExtractionRun,
)
from app.repositories import ClaimExtractionRepository
from app.schemas.ai import AiExecutionRunResponse
from app.schemas.claim_extraction import (
    CLAIM_EXTRACTION_INPUT_SCHEMA_KEY,
    CLAIM_EXTRACTION_OUTPUT_SCHEMA_KEY,
    CLAIM_EXTRACTION_SCHEMA_VERSION,
    ClaimExtractionClaimResponse,
    ClaimExtractionEvidenceResponse,
    ClaimExtractionRunResponse,
    GroundedClaimExtractionInput,
    GroundedClaimExtractionOutput,
)
from app.services.ai import (
    AiExecutionCoordinator,
    AiExecutionOptions,
    AiResourceNotFoundError,
    canonical_json,
)
from app.services.gemini import GeminiProvider

DOMAIN_GROUNDING_ERROR = "CLAIM_EXTRACTION_GROUNDING_INVALID"


class ClaimExtractionNotFoundError(Exception):
    def __init__(self, resource: str, resource_id: int) -> None:
        super().__init__(f"{resource} {resource_id} not found")


class ClaimExtractionConflictError(Exception):
    pass


@dataclass(frozen=True)
class _ChunkSnapshot:
    id: int
    position: int
    source_extraction_run_id: int
    source_snapshot_id: int
    source_id: int
    char_start: int
    char_end: int
    text: str
    sha256: str


@dataclass(frozen=True)
class _ExtractionSnapshot:
    id: int
    source_snapshot_id: int
    source_id: int
    snapshot_sha256: str
    chunks: tuple[_ChunkSnapshot, ...]


@dataclass(frozen=True)
class _PromptContract:
    id: int
    prompt_key: str
    version: int
    checksum: str
    input_schema_key: str
    input_schema_version: int
    output_schema_key: str
    output_schema_version: int


@dataclass(frozen=True)
class _GroundedCitation:
    chunk: _ChunkSnapshot
    char_start: int
    char_end: int
    text: str
    sha256: str


@dataclass(frozen=True)
class _GroundedClaim:
    statement: str
    subject: str | None
    predicate: str | None
    object_value: str | None
    citations: tuple[_GroundedCitation, ...]


class ClaimExtractionService:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        coordinator: AiExecutionCoordinator,
        *,
        max_chunks: int,
        max_input_characters: int,
        max_input_bytes: int,
        max_canonical_json_bytes: int,
        max_claims: int,
        max_citations_per_claim: int,
        max_evidence: int,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.coordinator = coordinator
        self.max_chunks = max_chunks
        self.max_input_characters = max_input_characters
        self.max_input_bytes = max_input_bytes
        self.max_canonical_json_bytes = max_canonical_json_bytes
        self.max_claims = max_claims
        self.max_citations_per_claim = max_citations_per_claim
        self.max_evidence = max_evidence
        self.clock = clock or (lambda: datetime.now(UTC))

    def create(
        self, source_extraction_run_id: int, ai_prompt_version_id: int
    ) -> ClaimExtractionRunResponse:
        extraction, prompt = self._load_inputs(
            source_extraction_run_id, ai_prompt_version_id
        )
        input_value = _input_value(extraction)
        try:
            execution = self.coordinator.execute(prompt.id, input_value)
        except AiResourceNotFoundError as error:
            raise ClaimExtractionConflictError(
                f"AiPromptVersion {prompt.id} changed during claim extraction"
            ) from error

        if execution.status != "SUCCEEDED":
            raise ClaimExtractionConflictError(
                f"AiExecutionRun {execution.id} failed claim extraction: "
                f"{execution.error_code}"
            )

        grounded: tuple[_GroundedClaim, ...] = ()
        domain_error = None
        try:
            grounded = self._validate_grounding(execution, extraction)
        except (ValidationError, ValueError, TypeError):
            domain_error = DOMAIN_GROUNDING_ERROR

        return self._persist(
            extraction,
            prompt,
            execution,
            grounded if domain_error is None else (),
            domain_error,
        )

    def get(self, claim_extraction_run_id: int) -> ClaimExtractionRunResponse:
        with self.session_factory() as session:
            run = ClaimExtractionRepository(session).get_run(claim_extraction_run_id)
            if run is None:
                raise ClaimExtractionNotFoundError(
                    "ClaimExtractionRun", claim_extraction_run_id
                )
            return _response(run)

    def _load_inputs(
        self, source_extraction_run_id: int, ai_prompt_version_id: int
    ) -> tuple[_ExtractionSnapshot, _PromptContract]:
        with self.session_factory() as session:
            repository = ClaimExtractionRepository(session)
            extraction = repository.get_source_extraction_run(source_extraction_run_id)
            if extraction is None:
                raise ClaimExtractionNotFoundError(
                    "SourceExtractionRun", source_extraction_run_id
                )
            if extraction.status != "SUCCEEDED":
                raise ClaimExtractionConflictError(
                    f"SourceExtractionRun {source_extraction_run_id} is not eligible "
                    "for claim extraction"
                )
            prompt = repository.get_prompt_version(ai_prompt_version_id)
            if prompt is None:
                raise ClaimExtractionNotFoundError(
                    "AiPromptVersion", ai_prompt_version_id
                )
            prompt_contract = _copy_prompt(prompt)
            if not _compatible_prompt(prompt_contract):
                raise ClaimExtractionConflictError(
                    f"AiPromptVersion {ai_prompt_version_id} is not compatible with "
                    "grounded claim extraction"
                )
            snapshot = _copy_extraction(extraction)

        positions = tuple(chunk.position for chunk in snapshot.chunks)
        canonical_input_bytes = canonical_json(_input_value(snapshot)).encode("utf-8")
        if (
            not snapshot.chunks
            or positions != tuple(range(len(snapshot.chunks)))
            or len(snapshot.chunks) > self.max_chunks
            or sum(len(chunk.text) for chunk in snapshot.chunks)
            > self.max_input_characters
            or sum(len(chunk.text.encode("utf-8")) for chunk in snapshot.chunks)
            > self.max_input_bytes
            or len(canonical_input_bytes) > self.max_canonical_json_bytes
        ):
            raise ClaimExtractionConflictError(
                f"SourceExtractionRun {source_extraction_run_id} exceeds claim "
                "extraction limits"
            )
        return snapshot, prompt_contract

    def _validate_grounding(
        self,
        execution: AiExecutionRunResponse,
        extraction: _ExtractionSnapshot,
    ) -> tuple[_GroundedClaim, ...]:
        output = GroundedClaimExtractionOutput.model_validate(
            execution.output_json, strict=True
        )
        if len(output.claims) > self.max_claims:
            raise ValueError("too many claims")
        chunks = {chunk.id: chunk for chunk in extraction.chunks}
        statements: set[str] = set()
        evidence_keys: set[tuple[int, int, int]] = set()
        grounded_claims: list[_GroundedClaim] = []
        for proposal in output.claims:
            if proposal.statement in statements:
                raise ValueError("duplicate claim")
            statements.add(proposal.statement)
            if len(proposal.citations) > self.max_citations_per_claim:
                raise ValueError("too many citations")
            seen: set[tuple[int, int, int]] = set()
            citations: list[_GroundedCitation] = []
            for citation in proposal.citations:
                key = (
                    citation.source_chunk_id,
                    citation.char_start,
                    citation.char_end,
                )
                if key in seen:
                    raise ValueError("duplicate citation")
                seen.add(key)
                evidence_keys.add(key)
                if len(evidence_keys) > self.max_evidence:
                    raise ValueError("too much evidence")
                chunk = chunks.get(citation.source_chunk_id)
                if chunk is None or not (
                    0 <= citation.char_start < citation.char_end <= len(chunk.text)
                ):
                    raise ValueError("invalid citation")
                text = chunk.text[citation.char_start : citation.char_end]
                if not text.strip():
                    raise ValueError("blank citation")
                citations.append(
                    _GroundedCitation(
                        chunk=chunk,
                        char_start=citation.char_start,
                        char_end=citation.char_end,
                        text=text,
                        sha256=sha256(text.encode("utf-8")).hexdigest(),
                    )
                )
            grounded_claims.append(
                _GroundedClaim(
                    statement=proposal.statement,
                    subject=proposal.subject,
                    predicate=proposal.predicate,
                    object_value=proposal.object_value,
                    citations=tuple(citations),
                )
            )
        return tuple(grounded_claims)

    def _persist(
        self,
        extraction: _ExtractionSnapshot,
        prompt: _PromptContract,
        execution: AiExecutionRunResponse,
        grounded_claims: tuple[_GroundedClaim, ...],
        error_code: str | None,
    ) -> ClaimExtractionRunResponse:
        with self.session_factory() as session:
            repository = ClaimExtractionRepository(session)
            try:
                chunk_identity = tuple(
                    (
                        chunk.id,
                        chunk.position,
                        chunk.source_extraction_run_id,
                        chunk.source_snapshot_id,
                        chunk.source_id,
                        chunk.char_start,
                        chunk.char_end,
                        chunk.text,
                        chunk.sha256,
                    )
                    for chunk in extraction.chunks
                )
                if (
                    repository.get_source_extraction_exact(
                        extraction.id,
                        extraction.source_snapshot_id,
                        extraction.source_id,
                        extraction.snapshot_sha256,
                        chunk_identity,
                    )
                    is None
                ):
                    raise ClaimExtractionConflictError(
                        f"SourceExtractionRun {extraction.id} changed during claim "
                        "extraction"
                    )
                ai_execution = repository.get_ai_execution_exact(
                    execution.id,
                    prompt.id,
                    prompt.prompt_key,
                    prompt.version,
                    prompt.checksum,
                    execution.provider_key,
                    execution.model_id,
                    execution.status,
                )
                if ai_execution is None:
                    raise ClaimExtractionConflictError(
                        f"AiExecutionRun {execution.id} changed during claim extraction"
                    )

                now = self.clock()
                status = "FAILED" if error_code is not None else "SUCCEEDED"
                run = ClaimExtractionRun(
                    source_extraction_run_id=extraction.id,
                    source_snapshot_id=extraction.source_snapshot_id,
                    source_id=extraction.source_id,
                    snapshot_sha256=extraction.snapshot_sha256,
                    source_extraction_status="SUCCEEDED",
                    ai_prompt_version_id=prompt.id,
                    prompt_key=prompt.prompt_key,
                    prompt_version=prompt.version,
                    prompt_checksum=prompt.checksum,
                    ai_execution_run_id=execution.id,
                    provider_key=execution.provider_key,
                    model_id=execution.model_id,
                    ai_execution_status=execution.status,
                    status=status,
                    error_code=error_code,
                    created_at=now,
                    completed_at=now,
                    ai_execution=ai_execution,
                )
                repository.add_run(run)
                if status == "SUCCEEDED":
                    self._add_grounded_records(repository, run, grounded_claims)
                response = _response(run)
                session.commit()
            except IntegrityError as error:
                session.rollback()
                if _constraint_name(error) == "uq_claim_extraction_runs_ai_execution":
                    raise ClaimExtractionConflictError(
                        f"AiExecutionRun {execution.id} already has claim extraction"
                    ) from error
                raise
            except Exception:
                session.rollback()
                raise
        return response

    @staticmethod
    def _add_grounded_records(
        repository: ClaimExtractionRepository,
        run: ClaimExtractionRun,
        grounded_claims: tuple[_GroundedClaim, ...],
    ) -> None:
        evidence_by_key: dict[tuple[int, int, int], Evidence] = {}
        evidence_links: list[ClaimExtractionEvidence] = []
        for grounded_claim in grounded_claims:
            for citation in grounded_claim.citations:
                key = (citation.chunk.id, citation.char_start, citation.char_end)
                if key in evidence_by_key:
                    continue
                evidence = Evidence(
                    source_id=run.source_id,
                    content=citation.text,
                    location_reference=_location_reference(
                        run.source_snapshot_id,
                        citation.chunk.id,
                        citation.char_start,
                        citation.char_end,
                    ),
                )
                evidence_by_key[key] = evidence
                evidence_links.append(
                    ClaimExtractionEvidence(
                        claim_extraction_run=run,
                        evidence=evidence,
                        source_chunk_id=citation.chunk.id,
                        source_extraction_run_id=run.source_extraction_run_id,
                        source_snapshot_id=run.source_snapshot_id,
                        source_id=run.source_id,
                        run_status="SUCCEEDED",
                        char_start=citation.char_start,
                        char_end=citation.char_end,
                        cited_text_sha256=citation.sha256,
                        position=len(evidence_links),
                    )
                )
        repository.add_all([*evidence_by_key.values(), *evidence_links])
        repository.flush()

        claim_links: list[ClaimExtractionClaim] = []
        citations: list[ClaimExtractionCitation] = []
        for claim_position, grounded_claim in enumerate(grounded_claims):
            supporting_evidence = [
                evidence_by_key[
                    (citation.chunk.id, citation.char_start, citation.char_end)
                ]
                for citation in grounded_claim.citations
            ]
            claim = Claim(
                statement=grounded_claim.statement,
                subject=grounded_claim.subject,
                predicate=grounded_claim.predicate,
                object_value=grounded_claim.object_value,
                topic_id=None,
                verification_status="UNVERIFIED",
                confidence=None,
                last_verified_at=None,
                approval_status="DRAFT",
                approval_decided_at=None,
                reviewer_note=None,
                relevant_evidence=supporting_evidence,
            )
            claim_link = ClaimExtractionClaim(
                claim_extraction_run=run,
                claim=claim,
                run_status="SUCCEEDED",
                position=claim_position,
            )
            claim_links.append(claim_link)
            for citation_position, evidence in enumerate(supporting_evidence):
                citations.append(
                    ClaimExtractionCitation(
                        claim_link=claim_link,
                        evidence_link=next(
                            link for link in evidence_links if link.evidence is evidence
                        ),
                        position=citation_position,
                    )
                )
        repository.add_all([*claim_links, *citations])
        repository.flush()


def build_claim_extraction_service(db: Session) -> ClaimExtractionService:
    bind = db.get_bind()
    session_factory = _session_factory(bind)
    provider = GeminiProvider(settings.gemini_api_key.get_secret_value())
    coordinator = AiExecutionCoordinator(
        session_factory,
        provider,
        AiExecutionOptions(
            settings.gemini_model,
            settings.ai_request_timeout_seconds,
            settings.ai_max_output_tokens,
            settings.ai_temperature,
            frozenset(filter(None, settings.ai_model_allowlist.split(","))),
        ),
        {
            (
                CLAIM_EXTRACTION_INPUT_SCHEMA_KEY,
                CLAIM_EXTRACTION_SCHEMA_VERSION,
            ): GroundedClaimExtractionInput
        },
        {
            (
                CLAIM_EXTRACTION_OUTPUT_SCHEMA_KEY,
                CLAIM_EXTRACTION_SCHEMA_VERSION,
            ): GroundedClaimExtractionOutput
        },
    )
    return ClaimExtractionService(
        session_factory,
        coordinator,
        max_chunks=settings.claim_extraction_max_chunks,
        max_input_characters=settings.claim_extraction_max_input_characters,
        max_input_bytes=settings.claim_extraction_max_input_bytes,
        max_canonical_json_bytes=(settings.claim_extraction_max_canonical_json_bytes),
        max_claims=settings.claim_extraction_max_claims,
        max_citations_per_claim=settings.claim_extraction_max_citations_per_claim,
        max_evidence=settings.claim_extraction_max_evidence,
    )


def _session_factory(bind: Connection | Engine) -> Callable[[], Session]:
    return lambda: Session(
        bind=bind,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
        close_resets_only=False,
    )


def _copy_prompt(prompt: AiPromptVersion) -> _PromptContract:
    return _PromptContract(
        id=prompt.id,
        prompt_key=prompt.prompt_key,
        version=prompt.version,
        checksum=prompt.checksum,
        input_schema_key=prompt.input_schema_key,
        input_schema_version=prompt.input_schema_version,
        output_schema_key=prompt.output_schema_key,
        output_schema_version=prompt.output_schema_version,
    )


def _compatible_prompt(prompt: _PromptContract) -> bool:
    return (
        prompt.input_schema_key == CLAIM_EXTRACTION_INPUT_SCHEMA_KEY
        and prompt.input_schema_version == CLAIM_EXTRACTION_SCHEMA_VERSION
        and prompt.output_schema_key == CLAIM_EXTRACTION_OUTPUT_SCHEMA_KEY
        and prompt.output_schema_version == CLAIM_EXTRACTION_SCHEMA_VERSION
    )


def _copy_extraction(extraction: SourceExtractionRun) -> _ExtractionSnapshot:
    return _ExtractionSnapshot(
        id=extraction.id,
        source_snapshot_id=extraction.source_snapshot_id,
        source_id=extraction.source_id,
        snapshot_sha256=extraction.snapshot_sha256,
        chunks=tuple(_copy_chunk(chunk) for chunk in extraction.chunks),
    )


def _copy_chunk(chunk: SourceChunk) -> _ChunkSnapshot:
    return _ChunkSnapshot(
        id=chunk.id,
        position=chunk.position,
        source_extraction_run_id=chunk.source_extraction_run_id,
        source_snapshot_id=chunk.source_snapshot_id,
        source_id=chunk.source_id,
        char_start=chunk.char_start,
        char_end=chunk.char_end,
        text=chunk.text,
        sha256=chunk.sha256,
    )


def _input_value(extraction: _ExtractionSnapshot) -> dict[str, object]:
    return {
        "source_extraction_run_id": extraction.id,
        "source_snapshot_id": extraction.source_snapshot_id,
        "source_id": extraction.source_id,
        "snapshot_sha256": extraction.snapshot_sha256,
        "chunks": [
            {
                "id": chunk.id,
                "position": chunk.position,
                "source_extraction_run_id": chunk.source_extraction_run_id,
                "source_snapshot_id": chunk.source_snapshot_id,
                "source_id": chunk.source_id,
                "char_start": chunk.char_start,
                "char_end": chunk.char_end,
                "text": chunk.text,
                "sha256": chunk.sha256,
            }
            for chunk in extraction.chunks
        ],
    }


def _location_reference(
    source_snapshot_id: int,
    source_chunk_id: int,
    char_start: int,
    char_end: int,
) -> str:
    return (
        f"source-snapshot:{source_snapshot_id}#chunk={source_chunk_id}"
        f"&chars={char_start}-{char_end}"
    )


def _response(run: ClaimExtractionRun) -> ClaimExtractionRunResponse:
    evidence = [
        ClaimExtractionEvidenceResponse(
            position=link.position,
            evidence_id=link.evidence_id,
            source_chunk_id=link.source_chunk_id,
            source_extraction_run_id=link.source_extraction_run_id,
            source_snapshot_id=link.source_snapshot_id,
            source_id=link.source_id,
            char_start=link.char_start,
            char_end=link.char_end,
            cited_text_sha256=link.cited_text_sha256,
            content=link.evidence.content,
            location_reference=link.evidence.location_reference or "",
        )
        for link in run.evidence_links
    ]
    claims = [
        ClaimExtractionClaimResponse(
            position=link.position,
            claim_id=link.claim_id,
            evidence_ids=[citation.evidence_id for citation in link.citation_links],
        )
        for link in run.claim_links
    ]
    return ClaimExtractionRunResponse(
        id=run.id,
        source_extraction_run_id=run.source_extraction_run_id,
        source_snapshot_id=run.source_snapshot_id,
        source_id=run.source_id,
        snapshot_sha256=run.snapshot_sha256,
        ai_prompt_version_id=run.ai_prompt_version_id,
        prompt_key=run.prompt_key,
        prompt_version=run.prompt_version,
        prompt_checksum=run.prompt_checksum,
        ai_execution_run_id=run.ai_execution_run_id,
        provider_key=run.provider_key,
        model_id=run.model_id,
        ai_execution_status=run.ai_execution_status,
        status=run.status,
        error_code=run.error_code,
        created_at=run.created_at,
        completed_at=run.completed_at,
        ai_execution=AiExecutionRunResponse.model_validate(run.ai_execution),
        evidence=evidence,
        claims=claims,
    )


def _constraint_name(error: IntegrityError) -> str | None:
    diagnostic = getattr(getattr(error, "orig", None), "diag", None)
    return getattr(diagnostic, "constraint_name", None)
