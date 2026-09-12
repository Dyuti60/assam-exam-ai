import base64
import json
import threading
from collections.abc import Callable, Generator
from datetime import UTC, datetime
from hashlib import sha256

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import delete, event, func, insert, select, update
from sqlalchemy import text as sql_text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.routes import claim_extraction as claim_extraction_routes
from app.core.config import (
    CLAIM_EXTRACTION_MAX_CANONICAL_JSON_BYTES_LIMIT,
    CLAIM_EXTRACTION_MAX_CHUNKS_LIMIT,
    CLAIM_EXTRACTION_MAX_CITATIONS_PER_CLAIM_LIMIT,
    CLAIM_EXTRACTION_MAX_CLAIMS_LIMIT,
    CLAIM_EXTRACTION_MAX_EVIDENCE_LIMIT,
    CLAIM_EXTRACTION_MAX_INPUT_BYTES_LIMIT,
    CLAIM_EXTRACTION_MAX_INPUT_CHARACTERS_LIMIT,
    Settings,
)
from app.core.database import engine, get_db
from app.main import app
from app.models import (
    AiExecutionRun,
    AiPromptVersion,
    Claim,
    ClaimExtractionCitation,
    ClaimExtractionClaim,
    ClaimExtractionEvidence,
    ClaimExtractionRun,
    Evidence,
    Source,
    SourceChunk,
    SourceExtractionRun,
    SourceFetchRun,
    SourceSnapshot,
)
from app.models.claim_evidence import claim_evidence
from app.schemas.claim_extraction import (
    CLAIM_EXTRACTION_INPUT_SCHEMA_KEY,
    CLAIM_EXTRACTION_OUTPUT_SCHEMA_KEY,
    CLAIM_EXTRACTION_SCHEMA_VERSION,
    POSTGRES_INTEGER_MAX,
    ClaimExtractionCreate,
    GroundedClaimExtractionInput,
    GroundedClaimExtractionOutput,
)
from app.services.ai import (
    AiExecutionCoordinator,
    AiExecutionOptions,
    AiProviderError,
    AiProviderRequest,
    AiProviderResult,
    canonical_json,
    sha256_text,
)
from app.services.claim_extraction import (
    ClaimExtractionNotFoundError,
    ClaimExtractionService,
    build_claim_extraction_service,
)


@pytest.fixture
def db_connection() -> Generator[Connection, None, None]:
    if not (engine.url.database or "").endswith("_test"):
        pytest.fail("Claim extraction tests require a dedicated *_test database")
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            yield connection
        finally:
            if transaction.is_active:
                transaction.rollback()


@pytest.fixture
def client(db_connection: Connection) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        with Session(
            bind=db_connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        ) as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)


class FakeProvider:
    key = "fake"

    def __init__(
        self,
        output: dict | None = None,
        error_code: str | None = None,
        before_generate: Callable[[], None] | None = None,
    ) -> None:
        self.output = output
        self.error_code = error_code
        self.before_generate = before_generate
        self.calls: list[AiProviderRequest] = []

    def generate(self, request: AiProviderRequest) -> AiProviderResult:
        self.calls.append(request)
        if self.before_generate is not None:
            self.before_generate()
        if self.error_code is not None:
            raise AiProviderError(self.error_code)
        return AiProviderResult(
            json.dumps(self.output, separators=(",", ":")),
            provider_request_id="fake-request",
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
        )


class TrackingSessionFactory:
    def __init__(self, connection: Connection) -> None:
        self.connection = connection
        self.open_sessions = 0
        self.commits = 0
        self.rollbacks = 0
        self.post_commit_sql = 0

    def __call__(self) -> Session:
        owner = self

        class TrackedSession(Session):
            committed = False

            def commit(self) -> None:
                super().commit()
                owner.commits += 1
                self.committed = True

            def execute(self, *args: object, **kwargs: object) -> object:
                if self.committed:
                    owner.post_commit_sql += 1
                return super().execute(*args, **kwargs)

            def rollback(self) -> None:
                owner.rollbacks += 1
                super().rollback()

            def close(self) -> None:
                try:
                    super().close()
                finally:
                    owner.open_sessions -= 1

        owner.open_sessions += 1
        return TrackedSession(
            bind=self.connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
            close_resets_only=False,
        )


def _session_factory(connection: Connection) -> Callable[[], Session]:
    return lambda: Session(
        bind=connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
        close_resets_only=False,
    )


def _install_service(
    monkeypatch: pytest.MonkeyPatch,
    connection: Connection,
    provider: FakeProvider,
    *,
    max_chunks: int = 50,
    max_input_characters: int = 50_000,
    max_input_bytes: int = 200_000,
    max_canonical_json_bytes: int = 250_000,
    max_claims: int = 25,
    max_citations: int = 5,
    max_evidence: int = 125,
    factory: Callable[[], Session] | None = None,
    request_id_prefix: str = "t057-request",
) -> ClaimExtractionService:
    ids = iter(f"{request_id_prefix}-{number}" for number in range(100))
    times = iter(
        datetime(2026, 9, 12, 12, 0, second=second, tzinfo=UTC) for second in range(100)
    )
    session_factory = factory or _session_factory(connection)
    coordinator = AiExecutionCoordinator(
        session_factory,
        provider,
        AiExecutionOptions("models/test", 5, 512, 0),
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
        clock=lambda: next(times),
        request_id_factory=lambda: next(ids),
    )
    service = ClaimExtractionService(
        session_factory,
        coordinator,
        max_chunks=max_chunks,
        max_input_characters=max_input_characters,
        max_input_bytes=max_input_bytes,
        max_canonical_json_bytes=max_canonical_json_bytes,
        max_claims=max_claims,
        max_citations_per_claim=max_citations,
        max_evidence=max_evidence,
        clock=lambda: next(times),
    )
    monkeypatch.setattr(
        claim_extraction_routes,
        "build_claim_extraction_service",
        lambda _db: service,
    )
    return service


def _seed_extraction(client: TestClient, suffix: str, text: str) -> dict:
    source = client.post(
        "/api/v1/sources",
        json={
            "title": f"Source {suffix}",
            "publisher": "Official publisher",
            "source_type": "OFFICIAL",
            "authority_tier": 1,
            "location": f"https://example.gov.in/{suffix}",
            "license_status": "OFFICIAL_PUBLICATION",
            "content_hash": None,
        },
    ).json()
    fetch = client.post(
        f"/api/v1/sources/{source['id']}/fetch-runs",
        json={
            "status": "SUCCEEDED",
            "requested_url": source["location"],
            "final_url": source["location"],
            "http_status": 200,
            "content_type": "text/plain",
            "content_base64": base64.b64encode(text.encode()).decode(),
        },
    )
    assert fetch.status_code == 201, fetch.text
    extraction = client.post(
        f"/api/v1/source-snapshots/{fetch.json()['snapshot']['id']}/extractions"
    )
    assert extraction.status_code == 201, extraction.text
    return extraction.json()


def _seed_failed_extraction(client: TestClient, suffix: str) -> dict:
    source = client.post(
        "/api/v1/sources",
        json={
            "title": f"Source {suffix}",
            "publisher": "Official publisher",
            "source_type": "OFFICIAL",
            "authority_tier": 1,
            "location": f"https://example.gov.in/{suffix}",
            "license_status": "OFFICIAL_PUBLICATION",
            "content_hash": None,
        },
    ).json()
    fetch = client.post(
        f"/api/v1/sources/{source['id']}/fetch-runs",
        json={
            "status": "SUCCEEDED",
            "requested_url": source["location"],
            "final_url": source["location"],
            "http_status": 200,
            "content_type": "text/plain",
            "content_base64": base64.b64encode(b"\xff").decode(),
        },
    ).json()
    response = client.post(
        f"/api/v1/source-snapshots/{fetch['snapshot']['id']}/extractions"
    )
    assert response.status_code == 201
    assert response.json()["status"] == "FAILED"
    return response.json()


def _seed_prompt(client: TestClient, suffix: str = "valid", **changes: object) -> dict:
    payload = {
        "prompt_key": f"claim.extract.{suffix}",
        "version": 1,
        "system_template": "Use only supplied chunks.",
        "user_template": "Extract grounded claims from {chunks}.",
        "input_schema_key": CLAIM_EXTRACTION_INPUT_SCHEMA_KEY,
        "input_schema_version": CLAIM_EXTRACTION_SCHEMA_VERSION,
        "output_schema_key": CLAIM_EXTRACTION_OUTPUT_SCHEMA_KEY,
        "output_schema_version": CLAIM_EXTRACTION_SCHEMA_VERSION,
        **changes,
    }
    response = client.post("/api/v1/ai-prompt-versions", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _output(chunk_id: int, text: str) -> dict:
    start = text.index("Assam")
    end = start + len("Assam")
    return {
        "claims": [
            {
                "statement": "Assam is named in the stored source.",
                "subject": "Assam",
                "predicate": "is named in",
                "object_value": "the stored source",
                "citations": [
                    {
                        "source_chunk_id": chunk_id,
                        "char_start": start,
                        "char_end": end,
                    }
                ],
            }
        ]
    }


def _domain_counts(connection: Connection) -> tuple[int, int, int, int, int, int]:
    return tuple(
        connection.scalar(select(func.count()).select_from(model))
        for model in (
            ClaimExtractionRun,
            ClaimExtractionEvidence,
            ClaimExtractionClaim,
            ClaimExtractionCitation,
            Evidence,
            Claim,
        )
    )


def _assert_integrity_constraint(
    connection: Connection, statement: object, expected_name: str
) -> None:
    with pytest.raises(IntegrityError) as captured, connection.begin_nested():
        connection.execute(statement)
    assert captured.value.orig.diag.constraint_name == expected_name


def _expected_input(extraction: dict) -> dict:
    return {
        "source_extraction_run_id": extraction["id"],
        "source_snapshot_id": extraction["source_snapshot_id"],
        "source_id": extraction["source_id"],
        "snapshot_sha256": extraction["snapshot_sha256"],
        "chunks": [
            {
                "id": chunk["id"],
                "position": chunk["position"],
                "source_extraction_run_id": extraction["id"],
                "source_snapshot_id": extraction["source_snapshot_id"],
                "source_id": extraction["source_id"],
                "char_start": chunk["char_start"],
                "char_end": chunk["char_end"],
                "text": chunk["text"],
                "sha256": chunk["sha256"],
            }
            for chunk in extraction["chunks"]
        ],
    }


@pytest.mark.parametrize(
    ("field", "maximum"),
    [
        ("claim_extraction_max_chunks", CLAIM_EXTRACTION_MAX_CHUNKS_LIMIT),
        (
            "claim_extraction_max_input_characters",
            CLAIM_EXTRACTION_MAX_INPUT_CHARACTERS_LIMIT,
        ),
        ("claim_extraction_max_input_bytes", CLAIM_EXTRACTION_MAX_INPUT_BYTES_LIMIT),
        (
            "claim_extraction_max_canonical_json_bytes",
            CLAIM_EXTRACTION_MAX_CANONICAL_JSON_BYTES_LIMIT,
        ),
        ("claim_extraction_max_claims", CLAIM_EXTRACTION_MAX_CLAIMS_LIMIT),
        (
            "claim_extraction_max_citations_per_claim",
            CLAIM_EXTRACTION_MAX_CITATIONS_PER_CLAIM_LIMIT,
        ),
        ("claim_extraction_max_evidence", CLAIM_EXTRACTION_MAX_EVIDENCE_LIMIT),
    ],
)
def test_claim_extraction_settings_are_strict_positive_and_bounded(
    field: str, maximum: int
) -> None:
    base = {"_env_file": None, "database_url": "postgresql://unused/unused"}
    assert getattr(Settings(**base, **{field: maximum}), field) == maximum
    assert getattr(Settings(**base, **{field: str(maximum)}), field) == maximum
    for invalid in (0, -1, True, maximum + 1, " 1", "1 ", "1.0"):
        with pytest.raises(PydanticValidationError):
            Settings(**base, **{field: invalid})


def test_claim_extraction_identifiers_are_positive_strict_and_bounded(
    client: TestClient,
) -> None:
    assert ClaimExtractionCreate(ai_prompt_version_id=POSTGRES_INTEGER_MAX)
    for invalid in (0, -1, True, "1", POSTGRES_INTEGER_MAX + 1):
        with pytest.raises(PydanticValidationError):
            ClaimExtractionCreate(ai_prompt_version_id=invalid)
    assert (
        client.get(
            f"/api/v1/claim-extraction-runs/{POSTGRES_INTEGER_MAX + 1}"
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"/api/v1/source-extraction-runs/{POSTGRES_INTEGER_MAX + 1}/claim-extractions",
            json={"ai_prompt_version_id": 1},
        ).status_code
        == 422
    )


def test_canonical_json_is_stable_unicode_preserving_and_order_sensitive() -> None:
    first = {"nested": {"অসম": 1, "a": 2}, "chunks": [1, 2]}
    reordered = {"chunks": [1, 2], "nested": {"a": 2, "অসম": 1}}
    reversed_chunks = {"nested": {"a": 2, "অসম": 1}, "chunks": [2, 1]}
    assert canonical_json(first) == canonical_json(reordered)
    assert sha256_text(canonical_json(first)) == sha256_text(canonical_json(reordered))
    assert canonical_json(first) == '{"chunks":[1,2],"nested":{"a":2,"অসম":1}}'
    assert sha256_text(canonical_json(first)) != sha256_text(
        canonical_json(reversed_chunks)
    )


def test_grounded_claim_extraction_persists_exact_provenance_and_draft_claims(
    client: TestClient,
    db_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    extraction = _seed_extraction(client, "grounded", "Assam is in India.\n")
    prompt = _seed_prompt(client)
    chunk = extraction["chunks"][0]
    provider = FakeProvider(_output(chunk["id"], chunk["text"]))
    _install_service(monkeypatch, db_connection, provider)

    response = client.post(
        f"/api/v1/source-extraction-runs/{extraction['id']}/claim-extractions",
        json={"ai_prompt_version_id": prompt["id"]},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "SUCCEEDED"
    assert body["error_code"] is None
    assert body["source_extraction_run_id"] == extraction["id"]
    assert body["source_snapshot_id"] == extraction["source_snapshot_id"]
    assert body["source_id"] == extraction["source_id"]
    assert body["snapshot_sha256"] == extraction["snapshot_sha256"]
    assert body["ai_prompt_version_id"] == prompt["id"]
    assert body["prompt_key"] == prompt["prompt_key"]
    assert body["prompt_version"] == prompt["version"]
    assert body["prompt_checksum"] == prompt["checksum"]
    assert body["provider_key"] == "fake"
    assert body["model_id"] == "models/test"
    assert body["ai_execution_status"] == "SUCCEEDED"
    assert body["ai_execution"]["id"] == body["ai_execution_run_id"]
    assert len(provider.calls) == 1
    assert provider.calls[0].model_id == "models/test"
    assert (
        provider.calls[0].output_schema
        == GroundedClaimExtractionOutput.model_json_schema()
    )
    assert provider.calls[0].user_prompt.startswith("Extract grounded claims from ")
    expected_input = _expected_input(extraction)
    stored_input, stored_input_sha256 = db_connection.execute(
        select(AiExecutionRun.input_json, AiExecutionRun.input_sha256).where(
            AiExecutionRun.id == body["ai_execution_run_id"]
        )
    ).one()
    assert stored_input == expected_input
    assert stored_input_sha256 == sha256_text(canonical_json(expected_input))

    evidence = body["evidence"]
    assert len(evidence) == 1
    assert evidence[0]["position"] == 0
    assert evidence[0]["source_chunk_id"] == chunk["id"]
    assert evidence[0]["content"] == "Assam"
    assert evidence[0]["cited_text_sha256"] == sha256(b"Assam").hexdigest()
    assert evidence[0]["location_reference"] == (
        f"source-snapshot:{extraction['source_snapshot_id']}#chunk={chunk['id']}"
        f"&chars={evidence[0]['char_start']}-{evidence[0]['char_end']}"
    )

    claim = body["claims"][0]
    assert claim["position"] == 0
    assert claim["evidence_ids"] == [evidence[0]["evidence_id"]]
    stored_claim = client.get(f"/api/v1/claims/{claim['claim_id']}").json()
    assert stored_claim["relevant_evidence_ids"] == claim["evidence_ids"]
    assert stored_claim["approval_status"] == "DRAFT"
    assert stored_claim["approval_decided_at"] is None
    assert stored_claim["reviewer_note"] is None
    assert stored_claim["verification_status"] == "UNVERIFIED"
    assert stored_claim["confidence"] is None
    assert stored_claim["last_verified_at"] is None

    first = client.get(f"/api/v1/claim-extraction-runs/{body['id']}")
    second = client.get(f"/api/v1/claim-extraction-runs/{body['id']}")
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json() == body
    assert _domain_counts(db_connection) == (1, 1, 1, 1, 1, 1)


def test_repeated_stored_input_has_identical_canonical_audit(
    client: TestClient,
    db_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    extraction = _seed_extraction(client, "canonical-repeat", "অসম and 😀.\n")
    prompt = _seed_prompt(client, "canonical-repeat")
    chunk = extraction["chunks"][0]
    output = {
        "claims": [
            {
                "statement": "The stored chunk contains Assamese text.",
                "citations": [
                    {
                        "source_chunk_id": chunk["id"],
                        "char_start": 0,
                        "char_end": len("অসম"),
                    }
                ],
            }
        ]
    }
    provider = FakeProvider(output)
    _install_service(monkeypatch, db_connection, provider)
    responses = [
        client.post(
            f"/api/v1/source-extraction-runs/{extraction['id']}/claim-extractions",
            json={"ai_prompt_version_id": prompt["id"]},
        ).json()
        for _ in range(2)
    ]
    audits = [
        db_connection.execute(
            select(AiExecutionRun.input_json, AiExecutionRun.input_sha256).where(
                AiExecutionRun.id == response["ai_execution_run_id"]
            )
        ).one()
        for response in responses
    ]
    assert audits[0].input_json == audits[1].input_json == _expected_input(extraction)
    assert audits[0].input_sha256 == audits[1].input_sha256
    assert len(provider.calls) == 2


@pytest.mark.parametrize(
    ("text", "target"),
    [
        ("অসমীয়া ভাষা।\n", "অসমীয়া"),
        ("A\u0301 is normalized deterministically.\n", "Á"),
        ("Emoji 😀 is visible.\n", "😀"),
        ("first line\nsecond line\n", "line\nsecond"),
    ],
)
def test_citations_use_python_unicode_code_point_offsets(
    client: TestClient,
    db_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
    text: str,
    target: str,
) -> None:
    suffix = sha256(text.encode()).hexdigest()[:12]
    extraction = _seed_extraction(client, f"unicode-{suffix}", text)
    prompt = _seed_prompt(client, f"unicode-{suffix}")
    chunk = extraction["chunks"][0]
    start = chunk["text"].index(target)
    end = start + len(target)
    provider = FakeProvider(
        {
            "claims": [
                {
                    "statement": "The exact Unicode slice is grounded.",
                    "citations": [
                        {
                            "source_chunk_id": chunk["id"],
                            "char_start": start,
                            "char_end": end,
                        }
                    ],
                }
            ]
        }
    )
    _install_service(monkeypatch, db_connection, provider)
    body = client.post(
        f"/api/v1/source-extraction-runs/{extraction['id']}/claim-extractions",
        json={"ai_prompt_version_id": prompt["id"]},
    ).json()
    assert body["status"] == "SUCCEEDED"
    assert body["evidence"][0]["content"] == target
    assert (
        body["evidence"][0]["cited_text_sha256"]
        == sha256(target.encode("utf-8")).hexdigest()
    )


def test_overlap_chunk_citation_uses_selected_chunk_relative_offsets(
    client: TestClient,
    db_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    text = f"{'A' * 990}\nOVERLAP 😀 TARGET\n{'B' * 300}\n"
    extraction = _seed_extraction(client, "overlap-codepoints", text)
    chunk = next(
        item for item in extraction["chunks"] if "OVERLAP 😀 TARGET" in item["text"]
    )
    target = "😀 TARGET"
    start = chunk["text"].index(target)
    end = start + len(target)
    prompt = _seed_prompt(client, "overlap-codepoints")
    provider = FakeProvider(
        {
            "claims": [
                {
                    "statement": "An overlap-region slice is grounded.",
                    "citations": [
                        {
                            "source_chunk_id": chunk["id"],
                            "char_start": start,
                            "char_end": end,
                        }
                    ],
                }
            ]
        }
    )
    _install_service(monkeypatch, db_connection, provider)
    body = client.post(
        f"/api/v1/source-extraction-runs/{extraction['id']}/claim-extractions",
        json={"ai_prompt_version_id": prompt["id"]},
    ).json()
    assert body["status"] == "SUCCEEDED"
    assert body["evidence"][0]["source_chunk_id"] == chunk["id"]
    assert body["evidence"][0]["content"] == target


def test_claim_extraction_errors_are_stable_and_pre_provider(
    client: TestClient,
    db_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = FakeProvider({"claims": []})
    _install_service(monkeypatch, db_connection, provider)
    assert client.post(
        "/api/v1/source-extraction-runs/999999/claim-extractions",
        json={"ai_prompt_version_id": 1},
    ).json() == {"detail": "SourceExtractionRun 999999 not found"}
    assert client.get("/api/v1/claim-extraction-runs/999999").json() == {
        "detail": "ClaimExtractionRun 999999 not found"
    }

    extraction = _seed_extraction(client, "errors", "Assam.\n")
    missing_prompt = client.post(
        f"/api/v1/source-extraction-runs/{extraction['id']}/claim-extractions",
        json={"ai_prompt_version_id": 999999},
    )
    assert missing_prompt.status_code == 404
    assert missing_prompt.json() == {"detail": "AiPromptVersion 999999 not found"}
    incompatible = _seed_prompt(
        client, "incompatible", output_schema_key="different.output"
    )
    rejected = client.post(
        f"/api/v1/source-extraction-runs/{extraction['id']}/claim-extractions",
        json={"ai_prompt_version_id": incompatible["id"]},
    )
    assert rejected.status_code == 409
    assert rejected.json() == {
        "detail": (
            f"AiPromptVersion {incompatible['id']} is not compatible with "
            "grounded claim extraction"
        )
    }
    for payload in ({}, {"ai_prompt_version_id": 0}, {"ai_prompt_version_id": "1"}):
        assert (
            client.post(
                f"/api/v1/source-extraction-runs/{extraction['id']}/claim-extractions",
                json=payload,
            ).status_code
            == 422
        )
    assert provider.calls == []
    assert _domain_counts(db_connection) == (0, 0, 0, 0, 0, 0)


def test_failed_source_extraction_and_input_limits_block_provider(
    client: TestClient,
    db_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    extraction = _seed_extraction(client, "limit", "Assam input.\n")
    prompt = _seed_prompt(client, "limit")
    provider = FakeProvider(
        _output(extraction["chunks"][0]["id"], extraction["chunks"][0]["text"])
    )
    _install_service(
        monkeypatch,
        db_connection,
        provider,
        max_input_characters=1,
    )
    limited = client.post(
        f"/api/v1/source-extraction-runs/{extraction['id']}/claim-extractions",
        json={"ai_prompt_version_id": prompt["id"]},
    )
    assert limited.status_code == 409
    assert limited.json() == {
        "detail": f"SourceExtractionRun {extraction['id']} exceeds claim extraction limits"
    }

    failed_extraction = _seed_failed_extraction(client, "failed-input")
    failed = client.post(
        f"/api/v1/source-extraction-runs/{failed_extraction['id']}/claim-extractions",
        json={"ai_prompt_version_id": prompt["id"]},
    )
    assert failed.status_code == 409
    assert provider.calls == []
    assert _domain_counts(db_connection) == (0, 0, 0, 0, 0, 0)


def test_all_input_bounds_and_contiguous_positions_block_provider_before_io(
    client: TestClient,
    db_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prompt = _seed_prompt(client, "all-input-limits")
    cases = [
        ("input-bytes", "অসম।\n", {"max_input_bytes": 1}),
        ("input-json", "Assam.\n", {"max_canonical_json_bytes": 1}),
        ("input-chunks", f"{'x' * 1200}\n", {"max_chunks": 1}),
    ]
    for suffix, text, limits in cases:
        extraction = _seed_extraction(client, suffix, text)
        provider = FakeProvider({"claims": []})
        _install_service(monkeypatch, db_connection, provider, **limits)
        response = client.post(
            f"/api/v1/source-extraction-runs/{extraction['id']}/claim-extractions",
            json={"ai_prompt_version_id": prompt["id"]},
        )
        assert response.status_code == 409
        assert provider.calls == []

    extraction = _seed_extraction(client, "position-gap", "Assam.\n")
    db_connection.execute(
        update(SourceChunk)
        .where(SourceChunk.id == extraction["chunks"][0]["id"])
        .values(position=2)
    )
    provider = FakeProvider({"claims": []})
    _install_service(monkeypatch, db_connection, provider)
    response = client.post(
        f"/api/v1/source-extraction-runs/{extraction['id']}/claim-extractions",
        json={"ai_prompt_version_id": prompt["id"]},
    )
    assert response.status_code == 409
    assert response.json() == {
        "detail": (
            f"SourceExtractionRun {extraction['id']} exceeds claim extraction limits"
        )
    }
    assert provider.calls == []
    assert _domain_counts(db_connection) == (0, 0, 0, 0, 0, 0)


def test_provider_failure_persists_audit_without_domain_rows(
    client: TestClient,
    db_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    extraction = _seed_extraction(client, "provider-failure", "Assam.\n")
    prompt = _seed_prompt(client, "provider-failure")
    provider = FakeProvider(error_code="AI_PROVIDER_TIMEOUT")
    _install_service(monkeypatch, db_connection, provider)

    response = client.post(
        f"/api/v1/source-extraction-runs/{extraction['id']}/claim-extractions",
        json={"ai_prompt_version_id": prompt["id"]},
    )
    assert response.status_code == 409, response.text
    assert response.json()["detail"].endswith(
        "failed claim extraction: AI_PROVIDER_TIMEOUT"
    )
    assert len(provider.calls) == 1
    assert _domain_counts(db_connection) == (0, 0, 0, 0, 0, 0)
    assert db_connection.scalar(select(func.count()).select_from(AiExecutionRun)) == 1


@pytest.mark.parametrize(
    "mutate",
    [
        lambda output, _other: output["claims"][0]["citations"][0].update(
            source_chunk_id=999999
        ),
        lambda output, _other: output["claims"][0]["citations"][0].update(
            char_end=999999
        ),
        lambda output, _other: output["claims"][0]["citations"].append(
            dict(output["claims"][0]["citations"][0])
        ),
        lambda output, other: output["claims"][0]["citations"][0].update(
            source_chunk_id=other
        ),
        lambda output, _other: output["claims"][0]["citations"][0].update(
            char_start=1, char_end=1
        ),
        lambda output, _other: output["claims"][0]["citations"][0].update(
            char_start=6, char_end=7
        ),
    ],
)
def test_ungrounded_outputs_create_no_domain_records(
    client: TestClient,
    db_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
    mutate: Callable[[dict, int], None],
) -> None:
    extraction = _seed_extraction(client, f"ungrounded-{id(mutate)}", "Assam.\n")
    other = _seed_extraction(client, f"other-{id(mutate)}", "Other.\n")
    prompt = _seed_prompt(client, f"ungrounded-{id(mutate)}")
    chunk = extraction["chunks"][0]
    output = _output(chunk["id"], chunk["text"])
    mutate(output, other["chunks"][0]["id"])
    provider = FakeProvider(output)
    _install_service(monkeypatch, db_connection, provider)

    response = client.post(
        f"/api/v1/source-extraction-runs/{extraction['id']}/claim-extractions",
        json={"ai_prompt_version_id": prompt["id"]},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "FAILED"
    assert body["error_code"] == "CLAIM_EXTRACTION_GROUNDING_INVALID"
    assert body["ai_execution_status"] == "SUCCEEDED"
    assert body["evidence"] == body["claims"] == []
    assert _domain_counts(db_connection) == (1, 0, 0, 0, 0, 0)


@pytest.mark.parametrize(
    "output",
    [
        {"claims": [{"statement": " ", "citations": []}]},
        {"claims": [{"statement": "Claim", "citations": []}]},
        {
            "claims": [
                {
                    "statement": "Claim",
                    "citations": [
                        {"source_chunk_id": 1, "char_start": -1, "char_end": 1}
                    ],
                }
            ]
        },
        {
            "claims": [
                {
                    "statement": "Claim",
                    "citations": [
                        {
                            "source_chunk_id": 1,
                            "char_start": 0,
                            "char_end": 1,
                            "text": "fabricated",
                        }
                    ],
                }
            ]
        },
        {"claims": [], "provider": "fabricated"},
    ],
)
def test_structurally_hostile_outputs_leave_no_t057_rows(
    client: TestClient,
    db_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
    output: dict,
) -> None:
    suffix = sha256(canonical_json(output).encode()).hexdigest()[:12]
    extraction = _seed_extraction(client, f"hostile-{suffix}", "Assam.\n")
    prompt = _seed_prompt(client, f"hostile-{suffix}")
    provider = FakeProvider(output)
    _install_service(monkeypatch, db_connection, provider)
    response = client.post(
        f"/api/v1/source-extraction-runs/{extraction['id']}/claim-extractions",
        json={"ai_prompt_version_id": prompt["id"]},
    )
    assert response.status_code == 409
    assert response.json()["detail"].endswith(
        "failed claim extraction: AI_OUTPUT_SCHEMA_INVALID"
    )
    assert len(provider.calls) == 1
    assert _domain_counts(db_connection) == (0, 0, 0, 0, 0, 0)


def test_output_claim_citation_and_evidence_limits_fail_without_domain_content(
    client: TestClient,
    db_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    extraction = _seed_extraction(client, "output-limits", "Assam and India.\n")
    prompt = _seed_prompt(client, "output-limits")
    chunk = extraction["chunks"][0]
    output = {
        "claims": [
            {
                "statement": "First.",
                "citations": [
                    {"source_chunk_id": chunk["id"], "char_start": 0, "char_end": 5},
                    {
                        "source_chunk_id": chunk["id"],
                        "char_start": 10,
                        "char_end": 15,
                    },
                ],
            },
            {
                "statement": "Second.",
                "citations": [
                    {"source_chunk_id": chunk["id"], "char_start": 0, "char_end": 5}
                ],
            },
        ]
    }
    for index, limits in enumerate(
        (
            {"max_claims": 1},
            {"max_citations": 1},
            {"max_evidence": 1},
        )
    ):
        provider = FakeProvider(output)
        _install_service(
            monkeypatch,
            db_connection,
            provider,
            request_id_prefix=f"t057-output-limit-{index}",
            **limits,
        )
        body = client.post(
            f"/api/v1/source-extraction-runs/{extraction['id']}/claim-extractions",
            json={"ai_prompt_version_id": prompt["id"]},
        ).json()
        assert body["status"] == "FAILED"
        assert body["error_code"] == "CLAIM_EXTRACTION_GROUNDING_INVALID"
        assert body["evidence"] == body["claims"] == []
        assert len(provider.calls) == 1


def test_claim_review_and_source_changes_do_not_rewrite_extraction_snapshot(
    client: TestClient,
    db_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    extraction = _seed_extraction(client, "immutable", "Assam.\n")
    prompt = _seed_prompt(client, "immutable")
    chunk = extraction["chunks"][0]
    provider = FakeProvider(_output(chunk["id"], chunk["text"]))
    _install_service(monkeypatch, db_connection, provider)
    created = client.post(
        f"/api/v1/source-extraction-runs/{extraction['id']}/claim-extractions",
        json={"ai_prompt_version_id": prompt["id"]},
    ).json()

    claim_id = created["claims"][0]["claim_id"]
    approved = client.post(
        f"/api/v1/claims/{claim_id}/approval",
        json={"approval_status": "APPROVED", "reviewer_note": "Reviewed"},
    )
    assert approved.status_code == 200
    stored = client.get(f"/api/v1/claim-extraction-runs/{created['id']}").json()
    assert stored["id"] == created["id"]
    assert stored["source_extraction_run_id"] == created["source_extraction_run_id"]
    assert stored["snapshot_sha256"] == created["snapshot_sha256"]
    assert (
        client.get(f"/api/v1/claims/{claim_id}").json()["approval_status"] == "APPROVED"
    )
    assert stored == created
    assert stored["claims"][0]["evidence_ids"] == created["claims"][0]["evidence_ids"]
    assert stored["evidence"] == created["evidence"]


def test_retrieval_is_lock_free_read_only_and_does_not_rehash(
    client: TestClient,
    db_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    extraction = _seed_extraction(client, "read-only", "Assam.\n")
    prompt = _seed_prompt(client, "read-only")
    chunk = extraction["chunks"][0]
    provider = FakeProvider(_output(chunk["id"], chunk["text"]))
    _install_service(monkeypatch, db_connection, provider)
    created = client.post(
        f"/api/v1/source-extraction-runs/{extraction['id']}/claim-extractions",
        json={"ai_prompt_version_id": prompt["id"]},
    ).json()
    before = _domain_counts(db_connection)
    statements: list[str] = []

    def capture(
        _conn: Connection,
        _cursor: object,
        statement: str,
        _parameters: object,
        _context: object,
        _executemany: bool,
    ) -> None:
        statements.append(statement)

    event.listen(db_connection, "before_cursor_execute", capture)
    try:
        response = client.get(f"/api/v1/claim-extraction-runs/{created['id']}")
    finally:
        event.remove(db_connection, "before_cursor_execute", capture)
    assert response.status_code == 200
    assert response.json() == created
    assert _domain_counts(db_connection) == before
    sql = "\n".join(statements).upper()
    assert "FOR UPDATE" not in sql
    assert "INSERT " not in sql
    assert "UPDATE " not in sql
    assert "DELETE " not in sql
    assert (
        sum(statement.lstrip().upper().startswith("SELECT") for statement in statements)
        == 4
    )


def test_success_and_controlled_failure_have_exact_commit_boundaries(
    client: TestClient,
    db_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    extraction = _seed_extraction(client, "transaction-success", "Assam.\n")
    prompt = _seed_prompt(client, "transaction-success")
    chunk = extraction["chunks"][0]
    tracker = TrackingSessionFactory(db_connection)
    baseline_checked_out = engine.pool.checkedout()
    provider = FakeProvider(
        _output(chunk["id"], chunk["text"]),
        before_generate=lambda: (
            tracker.open_sessions == 0
            and engine.pool.checkedout() == baseline_checked_out
            or pytest.fail("owned database session remained open during provider I/O")
        ),
    )
    _install_service(
        monkeypatch,
        db_connection,
        provider,
        factory=tracker,
    )
    response = client.post(
        f"/api/v1/source-extraction-runs/{extraction['id']}/claim-extractions",
        json={"ai_prompt_version_id": prompt["id"]},
    )
    assert response.status_code == 201
    assert response.json()["status"] == "SUCCEEDED"
    assert len(provider.calls) == 1
    assert tracker.open_sessions == 0
    assert tracker.commits == 2
    assert tracker.rollbacks == 0
    assert tracker.post_commit_sql == 0

    failed_extraction = _seed_extraction(client, "transaction-failed", "Assam.\n")
    failed_prompt = _seed_prompt(client, "transaction-failed")
    failure_tracker = TrackingSessionFactory(db_connection)
    failed_provider = FakeProvider(
        error_code="AI_PROVIDER_TIMEOUT",
        before_generate=lambda: (
            failure_tracker.open_sessions == 0
            and engine.pool.checkedout() == baseline_checked_out
            or pytest.fail("owned database session remained open during provider I/O")
        ),
    )
    _install_service(
        monkeypatch,
        db_connection,
        failed_provider,
        factory=failure_tracker,
        request_id_prefix="t057-failed-request",
    )
    failed = client.post(
        f"/api/v1/source-extraction-runs/{failed_extraction['id']}/claim-extractions",
        json={"ai_prompt_version_id": failed_prompt["id"]},
    )
    assert failed.status_code == 409
    assert failed.json()["detail"].endswith(
        "failed claim extraction: AI_PROVIDER_TIMEOUT"
    )
    assert len(failed_provider.calls) == 1
    assert failure_tracker.open_sessions == 0
    assert failure_tracker.commits == 1
    assert failure_tracker.rollbacks == 0
    assert failure_tracker.post_commit_sql == 0


def test_service_does_not_mutate_or_close_caller_owned_session(
    db_connection: Connection,
) -> None:
    caller = Session(
        bind=db_connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
        close_resets_only=False,
    )
    pending = Claim(
        statement="Caller-owned pending claim.",
        verification_status="UNVERIFIED",
        approval_status="DRAFT",
    )
    caller.add(pending)
    transaction = caller.get_transaction()
    service = build_claim_extraction_service(caller)
    with pytest.raises(
        ClaimExtractionNotFoundError, match="ClaimExtractionRun 2147483647 not found"
    ):
        service.get(POSTGRES_INTEGER_MAX)
    assert pending in caller.new
    assert caller.get_transaction() is transaction
    assert caller.is_active
    caller.close()


def test_schema_failure_records_failed_audits_without_domain_content(
    client: TestClient,
    db_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    extraction = _seed_extraction(client, "schema-failure", "Assam.\n")
    prompt = _seed_prompt(client, "schema-failure")
    provider = FakeProvider({"claims": [{"statement": "missing citations"}]})
    _install_service(monkeypatch, db_connection, provider)
    response = client.post(
        f"/api/v1/source-extraction-runs/{extraction['id']}/claim-extractions",
        json={"ai_prompt_version_id": prompt["id"]},
    )
    assert response.status_code == 409
    assert response.json()["detail"].endswith(
        "failed claim extraction: AI_OUTPUT_SCHEMA_INVALID"
    )
    assert _domain_counts(db_connection) == (0, 0, 0, 0, 0, 0)


def test_independent_claim_and_citation_order_with_shared_evidence(
    client: TestClient,
    db_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    extraction = _seed_extraction(client, "ordering", "Assam and India.\n")
    prompt = _seed_prompt(client, "ordering")
    chunk = extraction["chunks"][0]
    output = {
        "claims": [
            {
                "statement": "First proposal.",
                "citations": [
                    {"source_chunk_id": chunk["id"], "char_start": 0, "char_end": 5},
                    {"source_chunk_id": chunk["id"], "char_start": 10, "char_end": 15},
                ],
            },
            {
                "statement": "Second proposal.",
                "citations": [
                    {"source_chunk_id": chunk["id"], "char_start": 10, "char_end": 15}
                ],
            },
        ]
    }
    _install_service(monkeypatch, db_connection, FakeProvider(output))
    body = client.post(
        f"/api/v1/source-extraction-runs/{extraction['id']}/claim-extractions",
        json={"ai_prompt_version_id": prompt["id"]},
    ).json()
    assert [item["position"] for item in body["evidence"]] == [0, 1]
    assert [item["content"] for item in body["evidence"]] == ["Assam", "India"]
    assert [item["position"] for item in body["claims"]] == [0, 1]
    assert body["claims"][0]["evidence_ids"] == [
        body["evidence"][0]["evidence_id"],
        body["evidence"][1]["evidence_id"],
    ]
    assert body["claims"][1]["evidence_ids"] == [body["evidence"][1]["evidence_id"]]


def test_post_flush_failure_rolls_back_complete_domain_aggregate(
    client: TestClient,
    db_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    extraction = _seed_extraction(client, "rollback", "Assam.\n")
    prompt = _seed_prompt(client, "rollback")
    chunk = extraction["chunks"][0]
    provider = FakeProvider(_output(chunk["id"], chunk["text"]))
    tracker = TrackingSessionFactory(db_connection)
    service = _install_service(
        monkeypatch,
        db_connection,
        provider,
        factory=tracker,
    )
    original = service._add_grounded_records

    def fail_after_flush(*args: object, **kwargs: object) -> None:
        original(*args, **kwargs)
        raise RuntimeError("injected persistence failure")

    monkeypatch.setattr(service, "_add_grounded_records", fail_after_flush)
    with pytest.raises(RuntimeError, match="injected persistence failure"):
        service.create(extraction["id"], prompt["id"])
    assert len(provider.calls) == 1
    assert tracker.commits == 1
    assert tracker.rollbacks == 1
    assert tracker.open_sessions == 0
    assert _domain_counts(db_connection) == (0, 0, 0, 0, 0, 0)
    assert db_connection.scalar(select(func.count()).select_from(AiExecutionRun)) == 1


def test_source_chunk_identity_is_revalidated_after_provider_io(
    client: TestClient,
    db_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    extraction = _seed_extraction(client, "revalidation", "Assam.\n")
    prompt = _seed_prompt(client, "revalidation")
    chunk = extraction["chunks"][0]

    def change_chunk_after_input_copy() -> None:
        db_connection.execute(
            update(SourceChunk)
            .where(SourceChunk.id == chunk["id"])
            .values(sha256="0" * 64)
        )

    provider = FakeProvider(
        _output(chunk["id"], chunk["text"]),
        before_generate=change_chunk_after_input_copy,
    )
    _install_service(monkeypatch, db_connection, provider)
    response = client.post(
        f"/api/v1/source-extraction-runs/{extraction['id']}/claim-extractions",
        json={"ai_prompt_version_id": prompt["id"]},
    )
    assert response.status_code == 409
    assert response.json() == {
        "detail": (
            f"SourceExtractionRun {extraction['id']} changed during claim extraction"
        )
    }
    assert len(provider.calls) == 1
    assert _domain_counts(db_connection) == (0, 0, 0, 0, 0, 0)
    assert db_connection.scalar(select(func.count()).select_from(AiExecutionRun)) == 1


def test_postgresql_constraints_reject_invalid_domain_provenance(
    client: TestClient,
    db_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    extraction = _seed_extraction(client, "constraints", "Assam and India.\n")
    prompt = _seed_prompt(client, "constraints")
    chunk = extraction["chunks"][0]
    provider = FakeProvider(
        {
            "claims": [
                {
                    "statement": "First constraint claim.",
                    "citations": [
                        {
                            "source_chunk_id": chunk["id"],
                            "char_start": 0,
                            "char_end": 5,
                        },
                        {
                            "source_chunk_id": chunk["id"],
                            "char_start": 10,
                            "char_end": 15,
                        },
                    ],
                },
                {
                    "statement": "Second constraint claim.",
                    "citations": [
                        {
                            "source_chunk_id": chunk["id"],
                            "char_start": 10,
                            "char_end": 15,
                        }
                    ],
                },
            ]
        }
    )
    _install_service(monkeypatch, db_connection, provider)
    created = client.post(
        f"/api/v1/source-extraction-runs/{extraction['id']}/claim-extractions",
        json={"ai_prompt_version_id": prompt["id"]},
    ).json()
    other = _seed_extraction(client, "constraints-other", "Other.\n")

    run_id = created["id"]
    probes = [
        (
            "ck_claim_extraction_runs_terminal_metadata",
            insert(ClaimExtractionRun).values(
                source_extraction_run_id=created["source_extraction_run_id"],
                source_snapshot_id=created["source_snapshot_id"],
                source_id=created["source_id"],
                snapshot_sha256=created["snapshot_sha256"],
                source_extraction_status="SUCCEEDED",
                ai_prompt_version_id=created["ai_prompt_version_id"],
                prompt_key=created["prompt_key"],
                prompt_version=created["prompt_version"],
                prompt_checksum=created["prompt_checksum"],
                ai_execution_run_id=created["ai_execution_run_id"],
                provider_key=created["provider_key"],
                model_id=created["model_id"],
                ai_execution_status="SUCCEEDED",
                status="FAILED",
                error_code=None,
                created_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
            ),
        ),
        (
            "uq_claim_extraction_runs_ai_execution",
            insert(ClaimExtractionRun).values(
                source_extraction_run_id=created["source_extraction_run_id"],
                source_snapshot_id=created["source_snapshot_id"],
                source_id=created["source_id"],
                snapshot_sha256=created["snapshot_sha256"],
                source_extraction_status="SUCCEEDED",
                ai_prompt_version_id=created["ai_prompt_version_id"],
                prompt_key=created["prompt_key"],
                prompt_version=created["prompt_version"],
                prompt_checksum=created["prompt_checksum"],
                ai_execution_run_id=created["ai_execution_run_id"],
                provider_key=created["provider_key"],
                model_id=created["model_id"],
                ai_execution_status="SUCCEEDED",
                status="SUCCEEDED",
                error_code=None,
                created_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
            ),
        ),
        (
            "ck_claim_extraction_runs_source_succeeded",
            update(ClaimExtractionRun)
            .where(ClaimExtractionRun.id == run_id)
            .values(source_extraction_status="FAILED"),
        ),
        (
            "ck_claim_extraction_runs_ai_status",
            update(ClaimExtractionRun)
            .where(ClaimExtractionRun.id == run_id)
            .values(
                ai_execution_status="INVALID",
                status="FAILED",
                error_code="CLAIM_EXTRACTION_GROUNDING_INVALID",
            ),
        ),
        (
            "ck_claim_extraction_runs_status",
            update(ClaimExtractionRun)
            .where(ClaimExtractionRun.id == run_id)
            .values(status="INVALID"),
        ),
        (
            "ck_claim_extraction_runs_error_code",
            update(ClaimExtractionRun)
            .where(ClaimExtractionRun.id == run_id)
            .values(status="FAILED", error_code="invalid"),
        ),
        (
            "ck_claim_extraction_runs_timestamps",
            update(ClaimExtractionRun)
            .where(ClaimExtractionRun.id == run_id)
            .values(completed_at=datetime(2020, 1, 1, tzinfo=UTC)),
        ),
        (
            "ck_claim_extraction_runs_checksums",
            update(ClaimExtractionRun)
            .where(ClaimExtractionRun.id == run_id)
            .values(snapshot_sha256="A" * 64),
        ),
        (
            "ck_claim_extraction_runs_provider_key",
            update(ClaimExtractionRun)
            .where(ClaimExtractionRun.id == run_id)
            .values(provider_key="INVALID"),
        ),
        (
            "ck_claim_extraction_runs_model_id",
            update(ClaimExtractionRun)
            .where(ClaimExtractionRun.id == run_id)
            .values(model_id="bad model"),
        ),
        (
            "ck_claim_extraction_evidence_position_range",
            update(ClaimExtractionEvidence)
            .where(ClaimExtractionEvidence.claim_extraction_run_id == created["id"])
            .values(char_end=0),
        ),
        (
            "fk_claim_extraction_evidence_source_chunk",
            update(ClaimExtractionEvidence)
            .where(ClaimExtractionEvidence.claim_extraction_run_id == created["id"])
            .values(source_chunk_id=other["chunks"][0]["id"]),
        ),
        (
            "ck_claim_extraction_evidence_checksum",
            update(ClaimExtractionEvidence)
            .where(ClaimExtractionEvidence.claim_extraction_run_id == created["id"])
            .values(cited_text_sha256="A" * 64),
        ),
        (
            "uq_claim_extraction_evidence_run_position",
            update(ClaimExtractionEvidence)
            .where(
                ClaimExtractionEvidence.claim_extraction_run_id == created["id"],
                ClaimExtractionEvidence.position == 1,
            )
            .values(position=0),
        ),
        (
            "uq_claim_extraction_evidence_run_citation",
            update(ClaimExtractionEvidence)
            .where(
                ClaimExtractionEvidence.claim_extraction_run_id == created["id"],
                ClaimExtractionEvidence.position == 1,
            )
            .values(char_start=0, char_end=5),
        ),
        (
            "ck_claim_extraction_claims_position_non_negative",
            update(ClaimExtractionClaim)
            .where(ClaimExtractionClaim.claim_extraction_run_id == created["id"])
            .values(position=-1),
        ),
        (
            "uq_claim_extraction_claims_run_position",
            update(ClaimExtractionClaim)
            .where(
                ClaimExtractionClaim.claim_extraction_run_id == created["id"],
                ClaimExtractionClaim.position == 1,
            )
            .values(position=0),
        ),
        (
            "ck_claim_extraction_citations_position_non_negative",
            update(ClaimExtractionCitation)
            .where(ClaimExtractionCitation.claim_extraction_run_id == created["id"])
            .values(position=-1),
        ),
        (
            "uq_claim_extraction_citations_claim_position",
            update(ClaimExtractionCitation)
            .where(
                ClaimExtractionCitation.claim_extraction_run_id == created["id"],
                ClaimExtractionCitation.claim_id == created["claims"][0]["claim_id"],
                ClaimExtractionCitation.position == 1,
            )
            .values(position=0),
        ),
        (
            "fk_claim_extraction_citations_claim_evidence",
            update(ClaimExtractionCitation)
            .where(
                ClaimExtractionCitation.claim_extraction_run_id == created["id"],
                ClaimExtractionCitation.claim_id == created["claims"][1]["claim_id"],
            )
            .values(evidence_id=created["evidence"][0]["evidence_id"]),
        ),
    ]
    for constraint_name, probe in probes:
        _assert_integrity_constraint(db_connection, probe, constraint_name)

    with pytest.raises(IntegrityError), db_connection.begin_nested():
        db_connection.execute(delete(SourceChunk).where(SourceChunk.id == chunk["id"]))
    with pytest.raises(IntegrityError), db_connection.begin_nested():
        db_connection.execute(
            delete(AiExecutionRun).where(
                AiExecutionRun.id == created["ai_execution_run_id"]
            )
        )
    with pytest.raises(IntegrityError), db_connection.begin_nested():
        db_connection.execute(
            delete(SourceExtractionRun).where(
                SourceExtractionRun.id == created["source_extraction_run_id"]
            )
        )
    with pytest.raises(IntegrityError), db_connection.begin_nested():
        db_connection.execute(
            delete(Evidence).where(Evidence.id == created["evidence"][0]["evidence_id"])
        )
    with pytest.raises(IntegrityError), db_connection.begin_nested():
        db_connection.execute(
            delete(Claim).where(Claim.id == created["claims"][0]["claim_id"])
        )
    with pytest.raises(IntegrityError), db_connection.begin_nested():
        db_connection.execute(
            delete(claim_evidence).where(
                claim_evidence.c.claim_id == created["claims"][0]["claim_id"],
                claim_evidence.c.evidence_id == created["evidence"][0]["evidence_id"],
            )
        )


def test_postgresql_concurrent_domain_run_uniqueness_is_final_authority(
    client: TestClient,
    db_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    extraction = _seed_extraction(client, "concurrent-domain-run", "Assam.\n")
    prompt = _seed_prompt(client, "concurrent-domain-run")
    chunk = extraction["chunks"][0]

    def invalidate_after_provider_input() -> None:
        db_connection.execute(
            update(SourceChunk)
            .where(SourceChunk.id == chunk["id"])
            .values(sha256="0" * 64)
        )

    provider = FakeProvider(
        _output(chunk["id"], chunk["text"]),
        before_generate=invalidate_after_provider_input,
    )
    _install_service(
        monkeypatch,
        db_connection,
        provider,
        request_id_prefix="t057-concurrent-domain-run",
    )
    response = client.post(
        f"/api/v1/source-extraction-runs/{extraction['id']}/claim-extractions",
        json={"ai_prompt_version_id": prompt["id"]},
    )
    assert response.status_code == 409
    db_connection.execute(
        update(SourceChunk)
        .where(SourceChunk.id == chunk["id"])
        .values(sha256=chunk["sha256"])
    )
    execution = db_connection.execute(
        select(
            AiExecutionRun.id,
            AiExecutionRun.provider_key,
            AiExecutionRun.model_id,
            AiExecutionRun.status,
        ).where(AiExecutionRun.ai_prompt_version_id == prompt["id"])
    ).one()
    snapshot_fetch_run_id = db_connection.scalar(
        select(SourceSnapshot.source_fetch_run_id).where(
            SourceSnapshot.id == extraction["source_snapshot_id"]
        )
    )
    db_connection.commit()

    values = {
        "source_extraction_run_id": extraction["id"],
        "source_snapshot_id": extraction["source_snapshot_id"],
        "source_id": extraction["source_id"],
        "snapshot_sha256": extraction["snapshot_sha256"],
        "source_extraction_status": "SUCCEEDED",
        "ai_prompt_version_id": prompt["id"],
        "prompt_key": prompt["prompt_key"],
        "prompt_version": prompt["version"],
        "prompt_checksum": prompt["checksum"],
        "ai_execution_run_id": execution.id,
        "provider_key": execution.provider_key,
        "model_id": execution.model_id,
        "ai_execution_status": execution.status,
        "status": "SUCCEEDED",
        "error_code": None,
        "created_at": datetime.now(UTC),
        "completed_at": datetime.now(UTC),
    }
    loser_started = threading.Event()
    loser_constraints: list[str | None] = []

    with engine.connect() as winner_connection:
        winner_transaction = winner_connection.begin()
        winner_connection.execute(insert(ClaimExtractionRun).values(**values))

        def insert_loser() -> None:
            with engine.connect() as loser_connection:
                loser_transaction = loser_connection.begin()
                loser_connection.execute(
                    sql_text("SET LOCAL application_name = 't057_concurrency_loser'")
                )
                loser_started.set()
                try:
                    loser_connection.execute(
                        insert(ClaimExtractionRun).values(**values)
                    )
                    loser_transaction.commit()
                except IntegrityError as error:
                    loser_transaction.rollback()
                    loser_constraints.append(error.orig.diag.constraint_name)

        thread = threading.Thread(target=insert_loser)
        thread.start()
        assert loser_started.wait(timeout=5)
        with engine.connect() as observer_connection:
            blocked = False
            for _ in range(100):
                blocked = bool(
                    observer_connection.scalar(
                        sql_text(
                            "SELECT EXISTS (SELECT 1 FROM pg_stat_activity "
                            "WHERE application_name = 't057_concurrency_loser' "
                            "AND wait_event_type = 'Lock')"
                        )
                    )
                )
                if blocked:
                    break
            assert blocked, "losing insert never overlapped the winning transaction"
        winner_transaction.commit()
        thread.join(timeout=5)
        assert not thread.is_alive()

    assert loser_constraints == ["uq_claim_extraction_runs_ai_execution"]
    with engine.connect() as verification_connection:
        assert (
            verification_connection.scalar(
                select(func.count())
                .select_from(ClaimExtractionRun)
                .where(ClaimExtractionRun.ai_execution_run_id == execution.id)
            )
            == 1
        )

    with engine.begin() as cleanup_connection:
        cleanup_connection.execute(
            delete(ClaimExtractionRun).where(
                ClaimExtractionRun.ai_execution_run_id == execution.id
            )
        )
        cleanup_connection.execute(
            delete(AiExecutionRun).where(AiExecutionRun.id == execution.id)
        )
        cleanup_connection.execute(
            delete(AiPromptVersion).where(AiPromptVersion.id == prompt["id"])
        )
        cleanup_connection.execute(
            delete(SourceChunk).where(
                SourceChunk.source_extraction_run_id == extraction["id"]
            )
        )
        cleanup_connection.execute(
            delete(SourceExtractionRun).where(
                SourceExtractionRun.id == extraction["id"]
            )
        )
        cleanup_connection.execute(
            delete(SourceSnapshot).where(
                SourceSnapshot.id == extraction["source_snapshot_id"]
            )
        )
        cleanup_connection.execute(
            delete(SourceFetchRun).where(SourceFetchRun.id == snapshot_fetch_run_id)
        )
        cleanup_connection.execute(
            delete(Source).where(Source.id == extraction["source_id"])
        )
