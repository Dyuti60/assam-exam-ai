from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models import (
    AiExecutionRun,
    AiPromptVersion,
    ClaimExtractionClaim,
    ClaimExtractionEvidence,
    ClaimExtractionRun,
    SourceExtractionRun,
)


class ClaimExtractionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_source_extraction_run(
        self, source_extraction_run_id: int
    ) -> SourceExtractionRun | None:
        statement = (
            select(SourceExtractionRun)
            .options(selectinload(SourceExtractionRun.chunks))
            .where(SourceExtractionRun.id == source_extraction_run_id)
        )
        with self.session.no_autoflush:
            return self.session.scalar(statement)

    def get_prompt_version(self, prompt_id: int) -> AiPromptVersion | None:
        with self.session.no_autoflush:
            return self.session.scalar(
                select(AiPromptVersion).where(AiPromptVersion.id == prompt_id)
            )

    def get_source_extraction_exact(
        self,
        source_extraction_run_id: int,
        source_snapshot_id: int,
        source_id: int,
        snapshot_sha256: str,
        chunk_snapshots: tuple[
            tuple[int, int, int, int, int, int, int, str, str], ...
        ],
    ) -> SourceExtractionRun | None:
        statement = (
            select(SourceExtractionRun)
            .options(selectinload(SourceExtractionRun.chunks))
            .where(
                SourceExtractionRun.id == source_extraction_run_id,
                SourceExtractionRun.source_snapshot_id == source_snapshot_id,
                SourceExtractionRun.source_id == source_id,
                SourceExtractionRun.snapshot_sha256 == snapshot_sha256,
                SourceExtractionRun.status == "SUCCEEDED",
            )
        )
        with self.session.no_autoflush:
            extraction = self.session.scalar(statement)
        if extraction is None:
            return None
        current = tuple(
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
        return extraction if current == chunk_snapshots else None

    def get_ai_execution_exact(
        self,
        execution_id: int,
        prompt_id: int,
        prompt_key: str,
        prompt_version: int,
        prompt_checksum: str,
        provider_key: str,
        model_id: str,
        status: str,
    ) -> AiExecutionRun | None:
        statement = select(AiExecutionRun).where(
            AiExecutionRun.id == execution_id,
            AiExecutionRun.ai_prompt_version_id == prompt_id,
            AiExecutionRun.prompt_key == prompt_key,
            AiExecutionRun.prompt_version == prompt_version,
            AiExecutionRun.prompt_checksum == prompt_checksum,
            AiExecutionRun.provider_key == provider_key,
            AiExecutionRun.model_id == model_id,
            AiExecutionRun.status == status,
        )
        with self.session.no_autoflush:
            return self.session.scalar(statement)

    def add_run(self, run: ClaimExtractionRun) -> ClaimExtractionRun:
        self.session.add(run)
        self.session.flush()
        return run

    def flush(self) -> None:
        self.session.flush()

    def add_all(self, records: list[object]) -> None:
        self.session.add_all(records)

    def get_run(self, run_id: int) -> ClaimExtractionRun | None:
        statement = (
            select(ClaimExtractionRun)
            .options(
                joinedload(ClaimExtractionRun.ai_execution),
                selectinload(ClaimExtractionRun.evidence_links).joinedload(
                    ClaimExtractionEvidence.evidence
                ),
                selectinload(ClaimExtractionRun.claim_links).selectinload(
                    ClaimExtractionClaim.citation_links
                ),
            )
            .where(ClaimExtractionRun.id == run_id)
        )
        with self.session.no_autoflush:
            return self.session.scalar(statement)
