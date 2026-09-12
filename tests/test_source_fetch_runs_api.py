import base64
from collections.abc import Generator
from datetime import UTC, datetime
from hashlib import sha256

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import delete, event, func, insert, select
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings, settings
from app.core.database import engine, get_db
from app.main import app
from app.models import Source, SourceFetchRun, SourceSnapshot
from app.repositories import KnowledgeRepository


@pytest.fixture
def db_connection() -> Generator[Connection, None, None]:
    database_name = engine.url.database or ""
    if not database_name.endswith("_test"):
        pytest.fail("Source fetch tests require a dedicated *_test database")
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


def _create_source(client: TestClient, location: str, title: str = "Source") -> dict:
    response = client.post(
        "/api/v1/sources",
        json={
            "title": title,
            "publisher": "Government publisher",
            "source_type": "OFFICIAL",
            "authority_tier": 1,
            "location": location,
            "license_status": "OFFICIAL_PUBLICATION",
            "content_hash": None,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _success_payload(location: str, content: bytes, content_type: str) -> dict:
    return {
        "status": "SUCCEEDED",
        "requested_url": location,
        "final_url": location,
        "http_status": 200,
        "content_type": content_type,
        "content_base64": base64.b64encode(content).decode("ascii"),
    }


def _failed_payload(location: str) -> dict:
    return {
        "status": "FAILED",
        "requested_url": location,
        "final_url": None,
        "http_status": None,
        "error_code": "FETCH_TIMEOUT",
    }


def _counts(connection: Connection) -> tuple[int, int]:
    return (
        connection.scalar(select(func.count()).select_from(SourceFetchRun)),
        connection.scalar(select(func.count()).select_from(SourceSnapshot)),
    )


@pytest.mark.parametrize(
    ("content", "content_type"),
    [
        (b"%PDF-1.4\nexact bytes\n%%EOF", "application/pdf"),
        ("অসমীয়া UTF-8 text".encode(), "text/plain"),
    ],
)
def test_success_persists_exact_snapshot_and_stable_retrieval(
    client: TestClient,
    db_connection: Connection,
    content: bytes,
    content_type: str,
) -> None:
    source = _create_source(client, f"https://example.gov/{content_type.replace('/', '-')}")
    commits = 0

    def record_commit(*args: object) -> None:
        nonlocal commits
        commits += 1

    event.listen(Session, "after_commit", record_commit)
    try:
        response = client.post(
            f"/api/v1/sources/{source['id']}/fetch-runs",
            json=_success_payload(source["location"], content, content_type.upper()),
        )
    finally:
        event.remove(Session, "after_commit", record_commit)

    assert response.status_code == 201, response.text
    body = response.json()
    assert commits == 1
    assert body["source_id"] == source["id"]
    assert body["requested_url"] == source["location"]
    assert body["status"] == "SUCCEEDED"
    assert body["final_url"] == source["location"]
    assert body["http_status"] == 200
    assert body["error_code"] is None
    assert datetime.fromisoformat(body["created_at"]).utcoffset() == UTC.utcoffset(None)
    snapshot = body["snapshot"]
    assert snapshot["source_fetch_run_id"] == body["id"]
    assert snapshot["source_id"] == source["id"]
    assert snapshot["requested_url"] == source["location"]
    assert snapshot["final_url"] == source["location"]
    assert snapshot["content_type"] == content_type
    assert snapshot["byte_size"] == len(content)
    assert snapshot["sha256"] == sha256(content).hexdigest()
    assert snapshot["sha256"] == snapshot["sha256"].lower()
    assert len(snapshot["sha256"]) == 64
    assert base64.b64decode(snapshot["content_base64"]) == content
    assert datetime.fromisoformat(snapshot["created_at"]).utcoffset() == UTC.utcoffset(
        None
    )
    assert _counts(db_connection) == (1, 1)
    assert db_connection.scalar(
        select(Source.content_hash).where(Source.id == source["id"])
    ) is None

    first_run_read = client.get(f"/api/v1/source-fetch-runs/{body['id']}")
    second_run_read = client.get(f"/api/v1/source-fetch-runs/{body['id']}")
    snapshot_read = client.get(f"/api/v1/source-snapshots/{snapshot['id']}")
    assert first_run_read.status_code == second_run_read.status_code == 200
    assert first_run_read.json() == second_run_read.json() == body
    assert snapshot_read.status_code == 200
    assert snapshot_read.json() == snapshot


def test_failed_run_has_no_snapshot_and_commits_once(
    client: TestClient,
    db_connection: Connection,
) -> None:
    source = _create_source(client, "https://example.gov/failed.pdf")
    commits = 0

    def record_commit(*args: object) -> None:
        nonlocal commits
        commits += 1

    event.listen(Session, "after_commit", record_commit)
    try:
        response = client.post(
            f"/api/v1/sources/{source['id']}/fetch-runs",
            json=_failed_payload(source["location"]),
        )
    finally:
        event.remove(Session, "after_commit", record_commit)

    assert response.status_code == 201, response.text
    assert response.json()["status"] == "FAILED"
    assert response.json()["error_code"] == "FETCH_TIMEOUT"
    assert response.json()["snapshot"] is None
    assert commits == 1
    assert _counts(db_connection) == (1, 0)


def test_snapshot_byte_limit_configuration_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            database_url="postgresql+psycopg://test/test",
            source_snapshot_max_bytes=0,
        )


def test_missing_resources_return_exact_404(client: TestClient) -> None:
    payload = _failed_payload("https://example.gov/missing")
    response = client.post("/api/v1/sources/999999/fetch-runs", json=payload)
    assert response.status_code == 404
    assert response.json() == {"detail": "Source 999999 not found"}

    run_response = client.get("/api/v1/source-fetch-runs/999999")
    assert run_response.status_code == 404
    assert run_response.json() == {"detail": "SourceFetchRun 999999 not found"}

    snapshot_response = client.get("/api/v1/source-snapshots/999999")
    assert snapshot_response.status_code == 404
    assert snapshot_response.json() == {"detail": "SourceSnapshot 999999 not found"}


@pytest.mark.parametrize(
    "payload",
    [
        {
            "status": "SUCCEEDED",
            "requested_url": "https://example.gov/document",
            "final_url": "https://example.gov/document",
            "http_status": 300,
            "content_type": "application/pdf",
            "content_base64": "eA==",
        },
        {
            "status": "SUCCEEDED",
            "requested_url": "https://example.gov/document",
            "final_url": "https://example.gov/document",
            "http_status": 200,
            "content_type": "application/octet-stream",
            "content_base64": "eA==",
        },
        {
            "status": "SUCCEEDED",
            "requested_url": "https://example.gov/document",
            "final_url": "https://example.gov/document",
            "http_status": 200,
            "content_type": " ",
            "content_base64": "eA==",
        },
        {
            "status": "SUCCEEDED",
            "requested_url": "https://example.gov/document",
            "final_url": "https://example.gov/document",
            "http_status": 200,
            "content_type": "application/pdf",
            "content_base64": "not-base64!",
        },
        {
            "status": "SUCCEEDED",
            "requested_url": "https://example.gov/document",
            "final_url": "https://example.gov/document",
            "http_status": 200,
            "content_type": "application/pdf",
            "content_base64": "",
        },
        {
            "status": "FAILED",
            "requested_url": "https://example.gov/document",
            "error_code": " ",
        },
        {
            "status": "FAILED",
            "requested_url": "https://example.gov/document",
            "error_code": "x" * 101,
        },
        {
            "status": "FAILED",
            "requested_url": "https://example.gov/document",
            "error_code": "FETCH_TIMEOUT",
            "content_base64": "eA==",
        },
        {
            "status": "SUCCEEDED",
            "requested_url": "https://example.gov/document",
            "final_url": "https://example.gov/document",
            "http_status": 200,
            "content_type": "application/pdf",
            "content_base64": "eA==",
            "error_code": "FETCH_TIMEOUT",
        },
        {"status": "PENDING", "requested_url": "https://example.gov/document"},
        {"requested_url": "https://example.gov/document"},
    ],
)
def test_invalid_terminal_requests_return_422_without_rows(
    client: TestClient,
    db_connection: Connection,
    payload: dict,
) -> None:
    source = _create_source(client, "https://example.gov/document")
    before = _counts(db_connection)
    response = client.post(
        f"/api/v1/sources/{source['id']}/fetch-runs",
        json=payload,
    )
    assert response.status_code == 422
    assert _counts(db_connection) == before


@pytest.mark.parametrize(
    "extra_field",
    ["id", "source_id", "byte_size", "sha256", "created_at", "title"],
)
def test_client_controlled_server_fields_are_rejected(
    client: TestClient,
    db_connection: Connection,
    extra_field: str,
) -> None:
    source = _create_source(client, "https://example.gov/server-fields")
    payload = _success_payload(source["location"], b"x", "application/pdf")
    payload[extra_field] = 1
    before = _counts(db_connection)
    response = client.post(
        f"/api/v1/sources/{source['id']}/fetch-runs",
        json=payload,
    )
    assert response.status_code == 422
    assert _counts(db_connection) == before


def test_requested_url_mismatch_and_oversized_bytes_return_422_without_rows(
    client: TestClient,
    db_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _create_source(client, "https://example.gov/exact-location")
    before = _counts(db_connection)
    mismatch = client.post(
        f"/api/v1/sources/{source['id']}/fetch-runs",
        json=_success_payload("https://example.gov/other", b"x", "application/pdf"),
    )
    assert mismatch.status_code == 422
    assert mismatch.json() == {
        "detail": f"requested_url must match Source {source['id']} location"
    }
    assert _counts(db_connection) == before

    monkeypatch.setattr(settings, "source_snapshot_max_bytes", 2)
    oversized = client.post(
        f"/api/v1/sources/{source['id']}/fetch-runs",
        json=_success_payload(source["location"], b"123", "application/pdf"),
    )
    assert oversized.status_code == 422
    assert oversized.json() == {
        "detail": "decoded source snapshot exceeds configured byte limit"
    }
    assert _counts(db_connection) == before


def test_repeated_attempts_and_promoted_source_are_compatible(
    client: TestClient,
    db_connection: Connection,
) -> None:
    direct = _create_source(client, "https://example.gov/direct")
    first = client.post(
        f"/api/v1/sources/{direct['id']}/fetch-runs",
        json=_success_payload(direct["location"], b"first", "text/plain"),
    )
    second = client.post(
        f"/api/v1/sources/{direct['id']}/fetch-runs",
        json=_success_payload(direct["location"], b"second", "text/plain"),
    )
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] != second.json()["id"]
    assert first.json()["snapshot"]["id"] != second.json()["snapshot"]["id"]

    candidate_response = client.post(
        "/api/v1/source-discovery-runs",
        json={
            "query": "promoted fetch source",
            "adapter_key": "manual-test-v1",
            "status": "SUCCEEDED",
            "error_message": None,
            "candidates": [{"location": "https://example.gov/promoted"}],
        },
    )
    candidate = candidate_response.json()["candidates"][0]
    approval = client.post(
        f"/api/v1/source-candidates/{candidate['id']}/approval",
        json={"approval_status": "APPROVED", "reviewer_note": "approved"},
    )
    assert approval.status_code == 200
    promotion = client.post(
        f"/api/v1/source-candidates/{candidate['id']}/promote",
        json={
            "title": "Promoted source",
            "publisher": "Government",
            "source_type": "OFFICIAL",
            "authority_tier": 1,
            "license_status": "OFFICIAL_PUBLICATION",
        },
    )
    assert promotion.status_code == 201, promotion.text
    promoted = promotion.json()["source"]
    fetched = client.post(
        f"/api/v1/sources/{promoted['id']}/fetch-runs",
        json=_failed_payload(promoted["location"]),
    )
    assert fetched.status_code == 201
    assert fetched.json()["source_id"] == promoted["id"]
    assert _counts(db_connection) == (3, 2)


def test_post_flush_failure_rolls_back_run_and_snapshot(
    client: TestClient,
    db_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _create_source(client, "https://example.gov/rollback")
    original_add = KnowledgeRepository.add_source_fetch_run
    commits = 0
    rollbacks = 0

    def fail_after_flush(
        repository: KnowledgeRepository,
        source_fetch_run: SourceFetchRun,
    ) -> SourceFetchRun:
        original_add(repository, source_fetch_run)
        raise RuntimeError("injected post-flush failure")

    def record_commit(*args: object) -> None:
        nonlocal commits
        commits += 1

    def record_rollback(*args: object) -> None:
        nonlocal rollbacks
        rollbacks += 1

    monkeypatch.setattr(KnowledgeRepository, "add_source_fetch_run", fail_after_flush)
    event.listen(Session, "after_commit", record_commit)
    event.listen(Session, "after_rollback", record_rollback)
    try:
        with pytest.raises(RuntimeError, match="injected post-flush failure"):
            client.post(
                f"/api/v1/sources/{source['id']}/fetch-runs",
                json=_success_payload(source["location"], b"rollback", "text/plain"),
            )
    finally:
        event.remove(Session, "after_commit", record_commit)
        event.remove(Session, "after_rollback", record_rollback)

    assert commits == 0
    assert rollbacks == 1
    assert _counts(db_connection) == (0, 0)


def test_retrieval_is_read_only_fixed_query_and_does_not_recompute(
    client: TestClient,
    db_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _create_source(client, "https://example.gov/read-only")
    created = client.post(
        f"/api/v1/sources/{source['id']}/fetch-runs",
        json=_success_payload(source["location"], b"stored", "text/plain"),
    ).json()
    before_counts = _counts(db_connection)
    statements: list[str] = []
    commits = 0
    flushes = 0

    def record_statement(
        connection: Connection,
        cursor: object,
        statement: str,
        parameters: object,
        context: object,
        executemany: bool,
    ) -> None:
        statements.append(statement)

    def record_commit(*args: object) -> None:
        nonlocal commits
        commits += 1

    def record_flush(*args: object) -> None:
        nonlocal flushes
        flushes += 1

    def unexpected_hash(*args: object, **kwargs: object) -> None:
        raise AssertionError("retrieval must not hash or reconstruct snapshots")

    monkeypatch.setattr("app.services.knowledge.sha256", unexpected_hash)
    event.listen(db_connection, "before_cursor_execute", record_statement)
    event.listen(Session, "after_commit", record_commit)
    event.listen(Session, "before_flush", record_flush)
    try:
        run_response = client.get(f"/api/v1/source-fetch-runs/{created['id']}")
        snapshot_response = client.get(
            f"/api/v1/source-snapshots/{created['snapshot']['id']}"
        )
    finally:
        event.remove(db_connection, "before_cursor_execute", record_statement)
        event.remove(Session, "after_commit", record_commit)
        event.remove(Session, "before_flush", record_flush)

    assert run_response.status_code == snapshot_response.status_code == 200
    assert run_response.json() == created
    assert snapshot_response.json() == created["snapshot"]
    normalized = [
        statement.upper()
        for statement in statements
        if statement.lstrip().upper().startswith("SELECT")
    ]
    assert len(normalized) == 2
    assert all("FOR UPDATE" not in statement for statement in normalized)
    assert all(
        keyword not in " ".join(normalized)
        for keyword in ("INSERT ", "UPDATE ", "DELETE ")
    )
    assert commits == 0
    assert flushes == 0
    assert _counts(db_connection) == before_counts


def test_postgresql_enforces_fetch_and_snapshot_constraints(
    client: TestClient,
    db_connection: Connection,
) -> None:
    first_source = _create_source(client, "https://example.gov/constraints-one")
    second_source = _create_source(client, "https://example.gov/constraints-two")
    success = client.post(
        f"/api/v1/sources/{first_source['id']}/fetch-runs",
        json=_success_payload(first_source["location"], b"valid", "text/plain"),
    ).json()
    failed = client.post(
        f"/api/v1/sources/{first_source['id']}/fetch-runs",
        json=_failed_payload(first_source["location"]),
    ).json()

    invalid_runs = [
        (
            {
                "source_id": first_source["id"],
                "requested_url": first_source["location"],
                "status": "PENDING",
                "error_code": "FETCH_TIMEOUT",
            },
            "ck_source_fetch_runs_status",
        ),
        (
            {
                "source_id": first_source["id"],
                "requested_url": " ",
                "status": "FAILED",
                "error_code": "FETCH_FAILED",
            },
            "ck_source_fetch_runs_requested_url_non_blank",
        ),
        (
            {
                "source_id": first_source["id"],
                "requested_url": first_source["location"],
                "status": "SUCCEEDED",
                "final_url": " ",
                "http_status": 200,
            },
            "ck_source_fetch_runs_final_url_non_blank",
        ),
        (
            {
                "source_id": first_source["id"],
                "requested_url": first_source["location"],
                "status": "SUCCEEDED",
                "final_url": first_source["location"],
                "http_status": 500,
            },
            "ck_source_fetch_runs_terminal_lifecycle",
        ),
        (
            {
                "source_id": first_source["id"],
                "requested_url": first_source["location"],
                "status": "FAILED",
                "error_code": " ",
            },
            "ck_source_fetch_runs_error_code_valid",
        ),
        (
            {
                "source_id": first_source["id"],
                "requested_url": first_source["location"],
                "status": "FAILED",
                "error_code": None,
            },
            "ck_source_fetch_runs_terminal_lifecycle",
        ),
        (
            {
                "source_id": first_source["id"],
                "requested_url": first_source["location"],
                "status": "FAILED",
                "http_status": 700,
                "error_code": "FETCH_FAILED",
            },
            "ck_source_fetch_runs_http_status_range",
        ),
    ]
    for values, constraint_name in invalid_runs:
        with pytest.raises(IntegrityError) as error, db_connection.begin_nested():
            db_connection.execute(insert(SourceFetchRun).values(**values))
        assert error.value.orig.diag.constraint_name == constraint_name

    with pytest.raises(IntegrityError) as mismatch, db_connection.begin_nested():
        db_connection.execute(
            insert(SourceFetchRun).values(
                source_id=first_source["id"],
                requested_url=second_source["location"],
                status="FAILED",
                error_code="FETCH_FAILED",
            )
        )
    assert (
        mismatch.value.orig.diag.constraint_name
        == "fk_source_fetch_runs_source_requested_url"
    )

    snapshot_values = {
        "source_fetch_run_id": failed["id"],
        "source_id": first_source["id"],
        "requested_url": first_source["location"],
        "run_status": "SUCCEEDED",
        "final_url": first_source["location"],
        "content_type": "text/plain",
        "byte_size": 1,
        "sha256": sha256(b"x").hexdigest(),
        "content_bytes": b"x",
    }
    with pytest.raises(IntegrityError) as failed_snapshot, db_connection.begin_nested():
        db_connection.execute(insert(SourceSnapshot).values(**snapshot_values))
    assert (
        failed_snapshot.value.orig.diag.constraint_name
        == "fk_source_snapshots_fetch_run_source_url_status"
    )

    for changes in (
        {"source_id": second_source["id"]},
        {"requested_url": second_source["location"]},
        {"final_url": second_source["location"]},
    ):
        bare_success_run_id = db_connection.scalar(
            insert(SourceFetchRun)
            .values(
                source_id=first_source["id"],
                requested_url=first_source["location"],
                status="SUCCEEDED",
                final_url=first_source["location"],
                http_status=200,
            )
            .returning(SourceFetchRun.id)
        )
        mismatched_snapshot_values = {
            **snapshot_values,
            "source_fetch_run_id": bare_success_run_id,
            **changes,
        }
        with pytest.raises(IntegrityError) as mismatch, db_connection.begin_nested():
            db_connection.execute(
                insert(SourceSnapshot).values(**mismatched_snapshot_values)
            )
        assert (
            mismatch.value.orig.diag.constraint_name
            == "fk_source_snapshots_fetch_run_source_url_status"
        )

    valid_snapshot = success["snapshot"]
    with pytest.raises(IntegrityError) as duplicate, db_connection.begin_nested():
        duplicate_values = {
            **snapshot_values,
            "source_fetch_run_id": success["id"],
        }
        db_connection.execute(
            insert(SourceSnapshot).values(**duplicate_values)
        )
    assert (
        duplicate.value.orig.diag.constraint_name
        == "uq_source_snapshots_source_fetch_run_id"
    )

    invalid_snapshots = [
        ({"run_status": "FAILED"}, "ck_source_snapshots_run_status_succeeded"),
        ({"requested_url": " "}, "ck_source_snapshots_requested_url_non_blank"),
        ({"final_url": " "}, "ck_source_snapshots_final_url_non_blank"),
        ({"content_type": " "}, "ck_source_snapshots_content_type_non_blank"),
        (
            {"byte_size": 0, "content_bytes": b""},
            "ck_source_snapshots_byte_size_positive",
        ),
        ({"byte_size": 2}, "ck_source_snapshots_byte_size_matches"),
        ({"sha256": "A" * 64}, "ck_source_snapshots_sha256_lower_hex"),
    ]
    for changes, constraint_name in invalid_snapshots:
        values = {
            **snapshot_values,
            "source_fetch_run_id": 999999,
            **changes,
        }
        with pytest.raises(IntegrityError) as error, db_connection.begin_nested():
            db_connection.execute(insert(SourceSnapshot).values(**values))
        assert error.value.orig.diag.constraint_name == constraint_name

    with pytest.raises(IntegrityError), db_connection.begin_nested():
        db_connection.execute(
            delete(SourceFetchRun).where(SourceFetchRun.id == success["id"])
        )
    with pytest.raises(IntegrityError), db_connection.begin_nested():
        db_connection.execute(delete(Source).where(Source.id == first_source["id"]))
    assert db_connection.scalar(
        select(SourceSnapshot.byte_size).where(SourceSnapshot.id == valid_snapshot["id"])
    ) == len(b"valid")
