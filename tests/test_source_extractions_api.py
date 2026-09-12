import base64
from collections.abc import Generator
from datetime import UTC, datetime
from hashlib import sha256
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
from sqlalchemy import delete, event, func, insert, select, update
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings, settings
from app.core.database import engine, get_db
from app.main import app
from app.models import (
    Claim,
    Evidence,
    NoteDraft,
    QuestionBankItem,
    Source,
    SourceChunk,
    SourceExtractionRun,
    SourceFetchRun,
    SourceSnapshot,
    Verification,
)
from app.repositories import KnowledgeRepository
from app.schemas.knowledge import SourceExtractionStatus, SourceFetchStatus
from app.services import KnowledgeService
from app.services.source_extractor import (
    CHUNK_OVERLAP_CHARACTERS,
    EXTRACTOR_KEY,
    MAX_CHUNK_CHARACTERS,
    chunk_text,
    extract_document,
    normalize_text,
)
from app.services.source_fetch_executor import SourceFetchExecutor, SourceFetchResult


@pytest.fixture
def db_connection() -> Generator[Connection, None, None]:
    database_name = engine.url.database or ""
    if not database_name.endswith("_test"):
        pytest.fail("Source extraction tests require a dedicated *_test database")
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


def _create_source(client: TestClient, suffix: str) -> dict:
    response = client.post(
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
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_snapshot(
    client: TestClient,
    content: bytes,
    content_type: str,
    suffix: str,
) -> tuple[dict, dict]:
    source = _create_source(client, suffix)
    response = client.post(
        f"/api/v1/sources/{source['id']}/fetch-runs",
        json={
            "status": "SUCCEEDED",
            "requested_url": source["location"],
            "final_url": source["location"],
            "http_status": 200,
            "content_type": content_type,
            "content_base64": base64.b64encode(content).decode("ascii"),
        },
    )
    assert response.status_code == 201, response.text
    return source, response.json()["snapshot"]


def _text_pdf(text: str, *, encrypted: bool = False) -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=200)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject(
                {NameObject("/F1"): writer._add_object(font)}
            )
        }
    )
    stream = DecodedStreamObject()
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream.set_data(f"BT /F1 12 Tf 20 100 Td ({escaped}) Tj ET".encode("ascii"))
    page[NameObject("/Contents")] = writer._add_object(stream)
    if encrypted:
        writer.encrypt("secret")
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def _blank_pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=200)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def _counts(connection: Connection) -> tuple[int, int]:
    return (
        connection.scalar(select(func.count()).select_from(SourceExtractionRun)),
        connection.scalar(select(func.count()).select_from(SourceChunk)),
    )


@pytest.mark.parametrize(
    ("content_type", "content", "expected_text"),
    [
        ("text/plain", b"\xef\xbb\xbfCafe\xcc\x81\r\n\r\n\r\nEnd\t \r", "Caf\u00e9\n\nEnd\n"),
        (
            "text/html",
            b"".join(
                (
                    b"<!doctype html><html><head><title>Hidden</title></head>",
                    b"<body><h1>Heading</h1><!--ignored-->",
                    b"<p>Visible <b>text</b></p><script>secret()</script>",
                    b"<style>.x{}</style></body></html>",
                )
            ),
            "Heading\n\nVisible text\n",
        ),
        (
            "application/json",
            b'{"first":"Alpha","nested":[2,true,null,{"last":"Omega"}]}',
            "Alpha\n2\ntrue\nnull\nOmega\n",
        ),
        (
            "application/xml",
            b"<root>Alpha<child>Beta</child>Gamma</root>",
            "AlphaBetaGamma\n",
        ),
        ("text/xml", b"<root>One<child>Two</child></root>", "OneTwo\n"),
        ("application/pdf", _text_pdf("PDF text"), "PDF text\n"),
    ],
)
def test_all_supported_types_persist_exact_deterministic_text_and_provenance(
    client: TestClient,
    db_connection: Connection,
    content_type: str,
    content: bytes,
    expected_text: str,
) -> None:
    source, snapshot = _create_snapshot(
        client,
        content,
        content_type,
        content_type.replace("/", "-"),
    )

    response = client.post(
        f"/api/v1/source-snapshots/{snapshot['id']}/extractions"
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["source_snapshot_id"] == snapshot["id"]
    assert body["source_id"] == source["id"]
    assert body["snapshot_sha256"] == snapshot["sha256"]
    assert body["extractor_key"] == EXTRACTOR_KEY
    assert body["status"] == "SUCCEEDED"
    assert body["error_code"] is None
    assert body["text_char_count"] == len(expected_text)
    assert body["text_sha256"] == sha256(expected_text.encode()).hexdigest()
    assert datetime.fromisoformat(body["created_at"]).utcoffset() == UTC.utcoffset(None)
    assert [chunk["position"] for chunk in body["chunks"]] == list(
        range(len(body["chunks"]))
    )
    rebuilt = body["chunks"][0]["text"]
    assert rebuilt == expected_text
    for chunk in body["chunks"]:
        assert chunk["source_extraction_run_id"] == body["id"]
        assert chunk["source_snapshot_id"] == snapshot["id"]
        assert chunk["source_id"] == source["id"]
        assert chunk["text"] == expected_text[chunk["char_start"] : chunk["char_end"]]
        assert chunk["sha256"] == sha256(chunk["text"].encode()).hexdigest()
        assert datetime.fromisoformat(chunk["created_at"]).utcoffset() == UTC.utcoffset(
            None
        )
    stored = db_connection.execute(
        select(
            SourceExtractionRun.source_snapshot_id,
            SourceExtractionRun.source_id,
            SourceExtractionRun.snapshot_sha256,
        ).where(SourceExtractionRun.id == body["id"])
    ).one()
    assert stored == (snapshot["id"], source["id"], snapshot["sha256"])


def test_chunking_uses_fixed_overlap_boundaries_offsets_and_stable_order() -> None:
    first = "A" * 700
    second = "B" * 700
    normalized = normalize_text(f"{first}\n\n{second}")
    chunks = chunk_text(normalized)

    assert chunks[0].char_start == 0
    assert chunks[-1].char_end == len(normalized)
    assert chunks[0].char_end == len(first) + 2
    assert chunks[1].char_start == chunks[0].char_end - CHUNK_OVERLAP_CHARACTERS
    assert [chunk.position for chunk in chunks] == list(range(len(chunks)))
    assert all(chunk.text == normalized[chunk.char_start : chunk.char_end] for chunk in chunks)
    assert all(len(chunk.text) <= MAX_CHUNK_CHARACTERS for chunk in chunks)
    assert chunks == chunk_text(normalized)
    assert extract_document(
        normalized.encode(),
        "text/plain",
        max_input_bytes=10_000,
        max_characters=10_000,
        max_chunks=10,
    ) == extract_document(
        normalized.encode(),
        "text/plain",
        max_input_bytes=10_000,
        max_characters=10_000,
        max_chunks=10,
    )


@pytest.mark.parametrize(
    ("content_type", "content", "error_code"),
    [
        ("text/plain", b"", "EXTRACTION_EMPTY_TEXT"),
        ("text/plain", b"\xff", "EXTRACTION_INVALID_ENCODING"),
        ("text/html", b"<script>only hidden</script>", "EXTRACTION_EMPTY_TEXT"),
        ("application/json", b"{broken", "EXTRACTION_INVALID_DOCUMENT"),
        (
            "application/xml",
            b'<!DOCTYPE x [<!ENTITY ext SYSTEM "https://evil.invalid/x">]><x>&ext;</x>',
            "EXTRACTION_INVALID_DOCUMENT",
        ),
        ("application/xml", b"<broken>", "EXTRACTION_INVALID_DOCUMENT"),
        ("application/pdf", _text_pdf("secret", encrypted=True), "EXTRACTION_ENCRYPTED_PDF"),
        ("application/pdf", _blank_pdf(), "EXTRACTION_EMPTY_TEXT"),
        ("application/pdf", b"not a pdf", "EXTRACTION_INVALID_DOCUMENT"),
    ],
)
def test_controlled_parser_failures_create_terminal_failed_run_without_chunks(
    client: TestClient,
    db_connection: Connection,
    content_type: str,
    content: bytes,
    error_code: str,
) -> None:
    source, snapshot = _create_snapshot(
        client,
        content or b" ",
        content_type,
        f"failed-{error_code.lower()}-{len(content)}",
    )
    response = client.post(
        f"/api/v1/source-snapshots/{snapshot['id']}/extractions"
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["source_id"] == source["id"]
    assert body["status"] == "FAILED"
    assert body["error_code"] == error_code
    assert body["text_char_count"] is None
    assert body["text_sha256"] is None
    assert body["chunks"] == []
    assert _counts(db_connection) == (1, 0)


def test_unsupported_content_type_is_a_controlled_failure(
    client: TestClient,
    db_connection: Connection,
) -> None:
    _, snapshot = _create_snapshot(client, b"binary", "text/plain", "unsupported")
    db_connection.execute(
        update(SourceSnapshot)
        .where(SourceSnapshot.id == snapshot["id"])
        .values(content_type="application/octet-stream")
    )

    response = client.post(
        f"/api/v1/source-snapshots/{snapshot['id']}/extractions"
    )

    assert response.status_code == 201
    assert response.json()["error_code"] == "EXTRACTION_UNSUPPORTED_CONTENT_TYPE"
    assert response.json()["chunks"] == []


@pytest.mark.parametrize(
    ("setting_name", "setting_value", "error_code"),
    [
        ("source_extraction_max_input_bytes", 2, "EXTRACTION_INPUT_TOO_LARGE"),
        ("source_extraction_max_characters", 2, "EXTRACTION_TEXT_TOO_LARGE"),
        ("source_extraction_max_chunks", 1, "EXTRACTION_CHUNK_LIMIT"),
    ],
)
def test_configured_limits_fail_before_partial_chunk_persistence(
    client: TestClient,
    db_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
    setting_name: str,
    setting_value: int,
    error_code: str,
) -> None:
    content = (
        ("A" * MAX_CHUNK_CHARACTERS)
        + "\n\n"
        + ("B" * MAX_CHUNK_CHARACTERS)
    ).encode()
    _, snapshot = _create_snapshot(client, content, "text/plain", setting_name)
    monkeypatch.setattr(settings, setting_name, setting_value)

    response = client.post(
        f"/api/v1/source-snapshots/{snapshot['id']}/extractions"
    )

    assert response.status_code == 201
    assert response.json()["status"] == "FAILED"
    assert response.json()["error_code"] == error_code
    assert _counts(db_connection) == (1, 0)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_extraction_max_input_bytes", 0),
        ("source_extraction_max_characters", -1),
        ("source_extraction_max_chunks", 0),
    ],
)
def test_extraction_configuration_limits_fail_fast(field: str, value: int) -> None:
    with pytest.raises(ValidationError):
        Settings(database_url="postgresql://example/test", **{field: value})


def test_extraction_input_limit_cannot_exceed_snapshot_limit() -> None:
    with pytest.raises(
        ValidationError,
        match="source extraction input limit cannot exceed source snapshot limit",
    ):
        Settings(
            database_url="postgresql://example/test",
            source_snapshot_max_bytes=10,
            source_fetch_response_max_bytes=10,
            source_extraction_max_input_bytes=11,
        )


def test_missing_duplicate_and_retrieval_contracts_are_stable(
    client: TestClient,
    db_connection: Connection,
) -> None:
    missing_snapshot = client.post("/api/v1/source-snapshots/999999/extractions")
    missing_run = client.get("/api/v1/source-extraction-runs/999999")
    assert missing_snapshot.status_code == 404
    assert missing_snapshot.json() == {"detail": "SourceSnapshot 999999 not found"}
    assert missing_run.status_code == 404
    assert missing_run.json() == {"detail": "SourceExtractionRun 999999 not found"}
    assert _counts(db_connection) == (0, 0)

    _, snapshot = _create_snapshot(client, b"stored text", "text/plain", "duplicate")
    created = client.post(
        f"/api/v1/source-snapshots/{snapshot['id']}/extractions"
    )
    assert created.status_code == 201
    read_once = client.get(f"/api/v1/source-extraction-runs/{created.json()['id']}")
    read_twice = client.get(f"/api/v1/source-extraction-runs/{created.json()['id']}")
    duplicate = client.post(
        f"/api/v1/source-snapshots/{snapshot['id']}/extractions"
    )
    assert read_once.status_code == read_twice.status_code == 200
    assert read_once.json() == read_twice.json() == created.json()
    assert duplicate.status_code == 409
    assert duplicate.json() == {
        "detail": (
            f"SourceSnapshot {snapshot['id']} already has extraction {EXTRACTOR_KEY}"
        )
    }
    assert _counts(db_connection) == (1, len(created.json()["chunks"]))


def test_parsing_has_no_open_transaction_and_snapshot_is_revalidated(
    client: TestClient,
    db_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, snapshot = _create_snapshot(client, b"race-safe", "text/plain", "revalidate")
    original_extract = extract_document
    service_session = Session(
        bind=db_connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    observed_transaction_state: list[bool] = []
    original_exact = KnowledgeRepository.get_source_snapshot_exact

    def inspect_parse(*args: object, **kwargs: object):
        observed_transaction_state.append(service_session.in_transaction())
        return original_extract(*args, **kwargs)

    def reject_revalidation(*args: object, **kwargs: object) -> None:
        del args, kwargs

    def capture_transaction(repository: KnowledgeRepository, *args: object, **kwargs: object):
        return original_exact(repository, *args, **kwargs)

    monkeypatch.setattr("app.services.knowledge.extract_document", inspect_parse)
    monkeypatch.setattr(KnowledgeRepository, "get_source_snapshot_exact", capture_transaction)
    try:
        success = KnowledgeService(service_session).create_source_extraction(snapshot["id"])
    finally:
        service_session.close()
    assert success.status == SourceExtractionStatus.SUCCEEDED
    assert observed_transaction_state == [False]

    _, changed_snapshot = _create_snapshot(client, b"change", "text/plain", "race")
    monkeypatch.setattr(KnowledgeRepository, "get_source_snapshot_exact", reject_revalidation)
    rejected = client.post(
        f"/api/v1/source-snapshots/{changed_snapshot['id']}/extractions"
    )
    assert rejected.status_code == 404
    assert rejected.json() == {
        "detail": f"SourceSnapshot {changed_snapshot['id']} not found"
    }


def test_manual_and_executor_snapshots_use_the_same_extraction_contract(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manual_source, manual_snapshot = _create_snapshot(
        client,
        b"identical text",
        "text/plain",
        "manual-contract",
    )
    executor_source = _create_source(client, "executor-contract")
    monkeypatch.setattr(
        SourceFetchExecutor,
        "fetch",
        lambda executor, requested_url: SourceFetchResult(
            status=SourceFetchStatus.SUCCEEDED,
            requested_url=requested_url,
            final_url=requested_url,
            http_status=200,
            error_code=None,
            content_type="text/plain",
            content_bytes=b"identical text",
        ),
    )
    executor_fetch = client.post(f"/api/v1/sources/{executor_source['id']}/fetch")
    assert executor_fetch.status_code == 201
    executor_snapshot = executor_fetch.json()["snapshot"]

    manual = client.post(
        f"/api/v1/source-snapshots/{manual_snapshot['id']}/extractions"
    ).json()
    executed = client.post(
        f"/api/v1/source-snapshots/{executor_snapshot['id']}/extractions"
    ).json()

    assert manual["source_id"] == manual_source["id"]
    assert executed["source_id"] == executor_source["id"]
    assert manual["status"] == executed["status"] == "SUCCEEDED"
    assert manual["text_char_count"] == executed["text_char_count"]
    assert manual["text_sha256"] == executed["text_sha256"]
    assert [
        (chunk["position"], chunk["char_start"], chunk["char_end"], chunk["text"], chunk["sha256"])
        for chunk in manual["chunks"]
    ] == [
        (chunk["position"], chunk["char_start"], chunk["char_end"], chunk["text"], chunk["sha256"])
        for chunk in executed["chunks"]
    ]


def test_success_commits_once_and_post_flush_failure_rolls_back_entire_aggregate(
    client: TestClient,
    db_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, snapshot = _create_snapshot(client, b"successful aggregate", "text/plain", "commit")
    commits = 0

    def count_commit(*args: object) -> None:
        nonlocal commits
        commits += 1

    event.listen(Session, "after_commit", count_commit)
    try:
        created = client.post(
            f"/api/v1/source-snapshots/{snapshot['id']}/extractions"
        )
    finally:
        event.remove(Session, "after_commit", count_commit)
    assert created.status_code == 201
    assert commits == 1

    _, failed_snapshot = _create_snapshot(
        client,
        b"   ",
        "text/plain",
        "failed-commit",
    )
    commits = 0
    event.listen(Session, "after_commit", count_commit)
    try:
        failed = client.post(
            f"/api/v1/source-snapshots/{failed_snapshot['id']}/extractions"
        )
    finally:
        event.remove(Session, "after_commit", count_commit)
    assert failed.status_code == 201
    assert failed.json()["status"] == "FAILED"
    assert commits == 1

    _, failing_snapshot = _create_snapshot(
        client,
        b"aggregate that must roll back",
        "text/plain",
        "rollback",
    )
    original_add = KnowledgeRepository.add_source_extraction_run

    def fail_after_flush(
        repository: KnowledgeRepository,
        extraction_run: SourceExtractionRun,
    ) -> SourceExtractionRun:
        original_add(repository, extraction_run)
        raise RuntimeError("injected after flush")

    monkeypatch.setattr(
        KnowledgeRepository,
        "add_source_extraction_run",
        fail_after_flush,
    )
    with pytest.raises(RuntimeError, match="injected after flush"):
        KnowledgeService(
            Session(
                bind=db_connection,
                expire_on_commit=False,
                join_transaction_mode="create_savepoint",
            )
        ).create_source_extraction(failing_snapshot["id"])
    assert db_connection.scalar(
        select(func.count())
        .select_from(SourceExtractionRun)
        .where(SourceExtractionRun.source_snapshot_id == failing_snapshot["id"])
    ) == 0
    assert db_connection.scalar(
        select(func.count())
        .select_from(SourceChunk)
        .where(SourceChunk.source_snapshot_id == failing_snapshot["id"])
    ) == 0


def test_retrieval_is_fixed_query_read_only_and_does_not_reparse(
    client: TestClient,
    db_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, snapshot = _create_snapshot(
        client,
        ("paragraph\n\n" * 300).encode(),
        "text/plain",
        "read-only",
    )
    created = client.post(
        f"/api/v1/source-snapshots/{snapshot['id']}/extractions"
    ).json()
    before = _counts(db_connection)
    statements: list[str] = []
    commits = 0
    flushes = 0

    def capture_sql(*args: object) -> None:
        statements.append(str(args[2]))

    def capture_commit(*args: object) -> None:
        nonlocal commits
        commits += 1

    def capture_flush(*args: object) -> None:
        nonlocal flushes
        flushes += 1

    def forbid_parse(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise AssertionError("retrieval reparsed the snapshot")

    monkeypatch.setattr("app.services.knowledge.extract_document", forbid_parse)
    event.listen(db_connection, "before_cursor_execute", capture_sql)
    event.listen(Session, "after_commit", capture_commit)
    event.listen(Session, "before_flush", capture_flush)
    try:
        response = client.get(f"/api/v1/source-extraction-runs/{created['id']}")
    finally:
        event.remove(db_connection, "before_cursor_execute", capture_sql)
        event.remove(Session, "after_commit", capture_commit)
        event.remove(Session, "before_flush", capture_flush)

    assert response.status_code == 200
    assert response.json() == created
    assert _counts(db_connection) == before
    assert commits == 0
    assert flushes == 0
    read_sql = [statement.upper() for statement in statements if statement.lstrip().upper().startswith("SELECT")]
    assert len(read_sql) == 2
    assert all("FOR UPDATE" not in statement for statement in read_sql)
    assert all(
        keyword not in " ".join(read_sql)
        for keyword in (" INSERT ", " UPDATE ", " DELETE ")
    )


def test_postgresql_constraints_reject_invalid_runs_chunks_and_deletions(
    client: TestClient,
    db_connection: Connection,
) -> None:
    first_source, snapshot = _create_snapshot(
        client,
        b"constraint text",
        "text/plain",
        "constraints-first",
    )
    second_source, second_snapshot = _create_snapshot(
        client,
        b"second text",
        "text/plain",
        "constraints-second",
    )
    valid_hash = sha256(b"normalized\n").hexdigest()
    base_run = {
        "source_snapshot_id": snapshot["id"],
        "source_id": first_source["id"],
        "snapshot_sha256": snapshot["sha256"],
        "extractor_key": EXTRACTOR_KEY,
        "status": "SUCCEEDED",
        "text_char_count": 11,
        "text_sha256": valid_hash,
    }
    invalid_runs = [
        ({"extractor_key": "other"}, "ck_source_extraction_runs_extractor_key"),
        ({"status": "PENDING"}, "ck_source_extraction_runs_status"),
        ({"snapshot_sha256": "A" * 64}, "ck_source_extraction_runs_snapshot_sha256"),
        ({"text_char_count": 0}, "ck_source_extraction_runs_terminal_metadata"),
        (
            {"status": "FAILED", "error_code": None, "text_char_count": None, "text_sha256": None},
            "ck_source_extraction_runs_terminal_metadata",
        ),
    ]
    for changes, constraint_name in invalid_runs:
        with pytest.raises(IntegrityError) as error, db_connection.begin_nested():
            db_connection.execute(
                insert(SourceExtractionRun).values({**base_run, **changes})
            )
        assert error.value.orig.diag.constraint_name == constraint_name

    for changes in (
        {"source_id": second_source["id"]},
        {"source_snapshot_id": second_snapshot["id"]},
        {"snapshot_sha256": second_snapshot["sha256"]},
    ):
        with pytest.raises(IntegrityError) as error, db_connection.begin_nested():
            db_connection.execute(
                insert(SourceExtractionRun).values({**base_run, **changes})
            )
        assert error.value.orig.diag.constraint_name == "fk_source_extraction_runs_snapshot_source_hash"

    run_id = db_connection.scalar(
        insert(SourceExtractionRun).values(**base_run).returning(SourceExtractionRun.id)
    )
    with pytest.raises(IntegrityError) as duplicate_run, db_connection.begin_nested():
        db_connection.execute(insert(SourceExtractionRun).values(**base_run))
    assert (
        duplicate_run.value.orig.diag.constraint_name
        == "uq_source_extraction_runs_snapshot_extractor"
    )
    base_chunk = {
        "source_extraction_run_id": run_id,
        "source_snapshot_id": snapshot["id"],
        "source_id": first_source["id"],
        "run_status": "SUCCEEDED",
        "position": 0,
        "char_start": 0,
        "char_end": 11,
        "text": "normalized\n",
        "sha256": valid_hash,
    }
    db_connection.execute(insert(SourceChunk).values(**base_chunk))
    invalid_chunks = [
        ({"position": -1}, "ck_source_chunks_position_non_negative"),
        (
            {"char_start": -1, "char_end": 10},
            "ck_source_chunks_start_non_negative",
        ),
        (
            {"char_end": 0},
            {
                "ck_source_chunks_valid_range",
                "ck_source_chunks_range_matches_text",
            },
        ),
        ({"text": " ", "char_end": 1}, "ck_source_chunks_text_non_blank"),
        ({"text": "\n", "char_end": 1}, "ck_source_chunks_text_non_blank"),
        (
            {"text": "too long", "char_start": 0, "char_end": 2},
            "ck_source_chunks_range_matches_text",
        ),
        (
            {"text": "x" * 1_001, "char_start": 0, "char_end": 1_001},
            "ck_source_chunks_text_max_length",
        ),
        ({"sha256": "A" * 64}, "ck_source_chunks_sha256_lower_hex"),
        ({"run_status": "FAILED"}, "ck_source_chunks_run_status_succeeded"),
    ]
    for index, (changes, constraint_name) in enumerate(invalid_chunks, start=1):
        values = {**base_chunk, "position": index, **changes}
        with pytest.raises(IntegrityError) as error, db_connection.begin_nested():
            db_connection.execute(insert(SourceChunk).values(values))
        actual_constraint = error.value.orig.diag.constraint_name
        if isinstance(constraint_name, set):
            assert actual_constraint in constraint_name
        else:
            assert actual_constraint == constraint_name

    for changes in (
        {"source_snapshot_id": second_snapshot["id"]},
        {"source_id": second_source["id"]},
    ):
        values = {
            **base_chunk,
            "position": 2,
            "char_start": 1,
            "char_end": 12,
            **changes,
        }
        with pytest.raises(IntegrityError) as error, db_connection.begin_nested():
            db_connection.execute(insert(SourceChunk).values(values))
        assert error.value.orig.diag.constraint_name == "fk_source_chunks_run_snapshot_source_status"

    with pytest.raises(IntegrityError) as duplicate_position, db_connection.begin_nested():
        db_connection.execute(
            insert(SourceChunk).values({**base_chunk, "char_start": 1, "char_end": 12})
        )
    assert duplicate_position.value.orig.diag.constraint_name == "uq_source_chunks_run_position"
    with pytest.raises(IntegrityError) as duplicate_range, db_connection.begin_nested():
        db_connection.execute(
            insert(SourceChunk).values({**base_chunk, "position": 1})
        )
    assert duplicate_range.value.orig.diag.constraint_name == "uq_source_chunks_run_range"
    with pytest.raises(IntegrityError), db_connection.begin_nested():
        db_connection.execute(delete(SourceSnapshot).where(SourceSnapshot.id == snapshot["id"]))
    with pytest.raises(IntegrityError), db_connection.begin_nested():
        db_connection.execute(delete(Source).where(Source.id == first_source["id"]))


def test_no_network_or_downstream_mutation_occurs(
    client: TestClient,
    db_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, snapshot = _create_snapshot(
        client,
        b'<html><body>Local only<img src="https://evil.invalid/x"></body></html>',
        "text/html",
        "no-network",
    )
    before_sources = db_connection.scalar(select(func.count()).select_from(Source))
    before_fetch_runs = db_connection.scalar(select(func.count()).select_from(SourceFetchRun))
    before_snapshots = db_connection.scalar(select(func.count()).select_from(SourceSnapshot))
    before_downstream = tuple(
        db_connection.scalar(select(func.count()).select_from(model))
        for model in (Evidence, Claim, Verification, NoteDraft, QuestionBankItem)
    )
    source_columns = (
        Source.title,
        Source.publisher,
        Source.location,
        Source.content_hash,
        Source.created_at,
    )
    source_values = db_connection.execute(
        select(*source_columns).where(Source.id == source["id"])
    ).one()
    snapshot_columns = (
        SourceSnapshot.source_fetch_run_id,
        SourceSnapshot.source_id,
        SourceSnapshot.requested_url,
        SourceSnapshot.final_url,
        SourceSnapshot.content_type,
        SourceSnapshot.byte_size,
        SourceSnapshot.sha256,
        SourceSnapshot.content_bytes,
        SourceSnapshot.created_at,
    )
    snapshot_values = db_connection.execute(
        select(*snapshot_columns).where(SourceSnapshot.id == snapshot["id"])
    ).one()
    monkeypatch.setattr("socket.create_connection", lambda *args, **kwargs: pytest.fail("network used"))

    response = client.post(
        f"/api/v1/source-snapshots/{snapshot['id']}/extractions"
    )

    assert response.status_code == 201
    assert response.json()["status"] == "SUCCEEDED"
    assert response.json()["source_id"] == source["id"]
    assert db_connection.scalar(select(func.count()).select_from(Source)) == before_sources
    assert db_connection.scalar(select(func.count()).select_from(SourceFetchRun)) == before_fetch_runs
    assert db_connection.scalar(select(func.count()).select_from(SourceSnapshot)) == before_snapshots
    assert tuple(
        db_connection.scalar(select(func.count()).select_from(model))
        for model in (Evidence, Claim, Verification, NoteDraft, QuestionBankItem)
    ) == before_downstream
    assert db_connection.execute(
        select(*source_columns).where(Source.id == source["id"])
    ).one() == source_values
    assert db_connection.execute(
        select(*snapshot_columns).where(SourceSnapshot.id == snapshot["id"])
    ).one() == snapshot_values
