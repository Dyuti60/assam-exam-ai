from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, event, func, insert, select
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import engine, get_db
from app.main import app
from app.models import Source, SourceCandidate, SourceDiscoveryRun
from app.repositories import KnowledgeRepository


@pytest.fixture
def db_connection() -> Generator[Connection, None, None]:
    database_name = engine.url.database or ""
    if not database_name.endswith("_test"):
        pytest.fail("Source discovery tests require a dedicated *_test database")
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            yield connection
        finally:
            if transaction.is_active:
                transaction.rollback()


@pytest.fixture
def db_session(db_connection: Connection) -> Generator[Session, None, None]:
    with Session(
        bind=db_connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    ) as session:
        yield session
        session.rollback()


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


def _counts(connection: Connection) -> tuple[int, int]:
    return (
        connection.scalar(select(func.count()).select_from(SourceDiscoveryRun)),
        connection.scalar(select(func.count()).select_from(SourceCandidate)),
    )


def _candidate(
    location: str = "https://example.gov/assam/geography",
) -> dict:
    return {
        "location": location,
        "title": "Official Assam Geography",
        "publisher": "Government of Assam",
        "snippet": "Official geographic reference",
    }


def _run_payload(*, candidates: list[dict] | None = None) -> dict:
    return {
        "query": "Assam government official geography resources",
        "adapter_key": "manual-test-v1",
        "status": "SUCCEEDED",
        "error_message": None,
        "candidates": candidates or [],
    }


def _post_run(client: TestClient, payload: dict) -> dict:
    response = client.post("/api/v1/source-discovery-runs", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_succeeded_runs_store_zero_or_ordered_normalized_candidates(
    client: TestClient,
    db_connection: Connection,
) -> None:
    source_count = db_connection.scalar(select(func.count()).select_from(Source))
    empty = _post_run(client, _run_payload())
    assert empty["status"] == "SUCCEEDED"
    assert empty["error_message"] is None
    assert empty["candidates"] == []
    assert datetime.fromisoformat(empty["created_at"]).utcoffset() == UTC.utcoffset(None)

    payload = {
        "query": "  Assam official resources  ",
        "adapter_key": "  manual-test-v1  ",
        "status": "SUCCEEDED",
        "candidates": [
            {
                "location": "  https://example.gov/second  ",
                "title": "  Second title  ",
                "publisher": "  Government of Assam  ",
                "snippet": "  Second result  ",
            },
            {
                "location": " https://example.gov/first ",
                "title": None,
                "publisher": None,
                "snippet": None,
            },
        ],
    }
    created = _post_run(client, payload)
    assert created["query"] == "Assam official resources"
    assert created["adapter_key"] == "manual-test-v1"
    assert [candidate["position"] for candidate in created["candidates"]] == [0, 1]
    assert [candidate["location"] for candidate in created["candidates"]] == [
        "https://example.gov/second",
        "https://example.gov/first",
    ]
    assert created["candidates"][0]["title"] == "Second title"
    assert created["candidates"][0]["publisher"] == "Government of Assam"
    assert created["candidates"][0]["snippet"] == "Second result"
    assert all(
        candidate["source_discovery_run_id"] == created["id"]
        and candidate["run_status"] == "SUCCEEDED"
        for candidate in created["candidates"]
    )

    retrieved = client.get(f"/api/v1/source-discovery-runs/{created['id']}")
    assert retrieved.status_code == 200
    assert retrieved.json() == created
    assert db_connection.scalar(select(func.count()).select_from(Source)) == source_count


def test_failed_run_and_repeated_audit_events_are_retained(client: TestClient) -> None:
    failed = _post_run(
        client,
        {
            "query": "  failed discovery  ",
            "adapter_key": "  manual-test-v1  ",
            "status": "FAILED",
            "error_message": "  upstream unavailable  ",
            "candidates": [],
        },
    )
    assert failed["query"] == "failed discovery"
    assert failed["error_message"] == "upstream unavailable"
    assert failed["candidates"] == []

    repeated_payload = _run_payload(candidates=[_candidate()])
    first = _post_run(client, repeated_payload)
    second = _post_run(client, repeated_payload)
    assert first["id"] != second["id"]
    assert first["query"] == second["query"]
    assert first["adapter_key"] == second["adapter_key"]
    assert first["candidates"][0]["location"] == second["candidates"][0][
        "location"
    ]


@pytest.mark.parametrize(
    "payload",
    [
        {**_run_payload(), "query": "   "},
        {**_run_payload(), "adapter_key": "\t"},
        _run_payload(candidates=[{**_candidate(), "location": "  "}]),
        _run_payload(candidates=[{**_candidate(), "title": "  "}]),
        _run_payload(candidates=[{**_candidate(), "publisher": "\n"}]),
        _run_payload(candidates=[{**_candidate(), "snippet": "\t"}]),
        _run_payload(candidates=[{**_candidate(), "publisher": "x" * 256}]),
        {**_run_payload(), "status": "UNKNOWN"},
        {**_run_payload(), "status": "SUCCEEDED", "error_message": "error"},
        {**_run_payload(), "status": "FAILED", "error_message": None},
        {
            **_run_payload(candidates=[_candidate()]),
            "status": "FAILED",
            "error_message": "failed",
        },
    ],
)
def test_invalid_request_shapes_return_422_without_persistence(
    client: TestClient,
    db_connection: Connection,
    payload: dict,
) -> None:
    before = _counts(db_connection)
    response = client.post("/api/v1/source-discovery-runs", json=payload)
    assert response.status_code == 422
    assert _counts(db_connection) == before


def test_duplicate_locations_after_trimming_return_422_without_persistence(
    client: TestClient,
    db_connection: Connection,
) -> None:
    before = _counts(db_connection)
    response = client.post(
        "/api/v1/source-discovery-runs",
        json=_run_payload(
            candidates=[
                _candidate("https://example.gov/duplicate"),
                _candidate("  https://example.gov/duplicate  "),
            ]
        ),
    )
    assert response.status_code == 422
    assert _counts(db_connection) == before


def test_missing_run_is_stable_and_read_only(
    client: TestClient,
    db_connection: Connection,
) -> None:
    before = _counts(db_connection)
    response = client.get("/api/v1/source-discovery-runs/999999")
    assert response.status_code == 404
    assert response.json() == {"detail": "SourceDiscoveryRun 999999 not found"}
    assert _counts(db_connection) == before


def test_creation_commits_once_and_database_uniqueness_conflict_is_atomic(
    client: TestClient,
    db_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commits = 0
    original_commit = Session.commit

    def count_commit(session: Session) -> None:
        nonlocal commits
        commits += 1
        original_commit(session)

    monkeypatch.setattr(Session, "commit", count_commit)
    _post_run(client, _run_payload(candidates=[_candidate()]))
    assert commits == 1

    before = _counts(db_connection)
    original_add = KnowledgeRepository.add_source_discovery_run

    def force_duplicate_position(
        repository: KnowledgeRepository,
        run: SourceDiscoveryRun,
    ) -> SourceDiscoveryRun:
        run.candidates[1].position = run.candidates[0].position
        return original_add(repository, run)

    monkeypatch.setattr(
        KnowledgeRepository,
        "add_source_discovery_run",
        force_duplicate_position,
    )
    conflict = client.post(
        "/api/v1/source-discovery-runs",
        json=_run_payload(
            candidates=[
                _candidate("https://example.gov/one"),
                _candidate("https://example.gov/two"),
            ]
        ),
    )
    assert conflict.status_code == 409
    assert conflict.json() == {
        "detail": "SourceDiscoveryRun candidate positions or locations conflict"
    }
    assert commits == 1
    assert _counts(db_connection) == before


def test_failure_after_flushed_aggregate_rolls_back_every_row(
    client: TestClient,
    db_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = _counts(db_connection)
    rollbacks = 0
    commits = 0
    original_add = KnowledgeRepository.add_source_discovery_run
    original_rollback = Session.rollback
    original_commit = Session.commit

    def fail_after_flush(
        repository: KnowledgeRepository,
        run: SourceDiscoveryRun,
    ) -> SourceDiscoveryRun:
        original_add(repository, run)
        raise RuntimeError("injected discovery persistence failure")

    def count_rollback(session: Session) -> None:
        nonlocal rollbacks
        rollbacks += 1
        original_rollback(session)

    def count_commit(session: Session) -> None:
        nonlocal commits
        commits += 1
        original_commit(session)

    monkeypatch.setattr(
        KnowledgeRepository,
        "add_source_discovery_run",
        fail_after_flush,
    )
    monkeypatch.setattr(Session, "rollback", count_rollback)
    monkeypatch.setattr(Session, "commit", count_commit)
    with pytest.raises(RuntimeError, match="injected discovery persistence failure"):
        client.post(
            "/api/v1/source-discovery-runs",
            json=_run_payload(candidates=[_candidate()]),
        )
    assert rollbacks == 1
    assert commits == 0
    assert _counts(db_connection) == before


def test_get_eagerly_loads_ordered_candidates_without_locks_or_writes(
    client: TestClient,
    db_connection: Connection,
) -> None:
    created = _post_run(
        client,
        _run_payload(
            candidates=[
                _candidate("https://example.gov/second"),
                _candidate("https://example.gov/first"),
            ]
        ),
    )
    statements: list[str] = []

    def record_statement(*args: object) -> None:
        statements.append(str(args[2]))

    event.listen(db_connection, "before_cursor_execute", record_statement)
    try:
        response = client.get(f"/api/v1/source-discovery-runs/{created['id']}")
    finally:
        event.remove(db_connection, "before_cursor_execute", record_statement)

    assert response.status_code == 200
    assert response.json() == created
    selects = [
        statement
        for statement in statements
        if statement.lstrip().upper().startswith("SELECT")
    ]
    writes = [
        statement
        for statement in statements
        if statement.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))
    ]
    assert len(selects) == 2
    assert "source_discovery_runs" in selects[0]
    assert "source_candidates" in selects[1]
    assert "ORDER BY source_candidates.position" in selects[1]
    assert all("FOR UPDATE" not in statement.upper() for statement in statements)
    assert writes == []


@pytest.mark.parametrize(
    "values",
    [
        {
            "query": "query",
            "adapter_key": "adapter",
            "status": "UNKNOWN",
            "error_message": None,
        },
        {
            "query": "query",
            "adapter_key": "adapter",
            "status": "SUCCEEDED",
            "error_message": "unexpected",
        },
        {
            "query": "query",
            "adapter_key": "adapter",
            "status": "FAILED",
            "error_message": None,
        },
        {
            "query": "   ",
            "adapter_key": "adapter",
            "status": "SUCCEEDED",
            "error_message": None,
        },
        {
            "query": "query",
            "adapter_key": "   ",
            "status": "SUCCEEDED",
            "error_message": None,
        },
    ],
)
def test_postgresql_rejects_invalid_run_state_and_required_text(
    db_connection: Connection,
    values: dict,
) -> None:
    with pytest.raises(IntegrityError), db_connection.begin_nested():
        db_connection.execute(insert(SourceDiscoveryRun).values(**values))


@pytest.mark.parametrize(
    "invalid_values",
    [
        {"position": -1},
        {"location": "   "},
        {"title": "   "},
        {"publisher": "   "},
        {"snippet": "   "},
        {"run_status": "FAILED"},
    ],
)
def test_postgresql_rejects_invalid_candidate_values(
    db_connection: Connection,
    invalid_values: dict,
) -> None:
    run_id = db_connection.execute(
        insert(SourceDiscoveryRun)
        .values(
            query="query",
            adapter_key="adapter",
            status="SUCCEEDED",
            error_message=None,
        )
        .returning(SourceDiscoveryRun.id)
    ).scalar_one()
    values = {
        "source_discovery_run_id": run_id,
        "run_status": "SUCCEEDED",
        "position": 0,
        "location": "https://example.gov/candidate",
        "title": "Title",
        "publisher": "Publisher",
        "snippet": "Snippet",
    }
    values.update(invalid_values)
    with pytest.raises(IntegrityError), db_connection.begin_nested():
        db_connection.execute(insert(SourceCandidate).values(**values))


def test_postgresql_enforces_candidate_uniqueness_references_and_provenance(
    db_connection: Connection,
) -> None:
    succeeded_run_id = db_connection.execute(
        insert(SourceDiscoveryRun)
        .values(
            query="successful query",
            adapter_key="adapter",
            status="SUCCEEDED",
            error_message=None,
        )
        .returning(SourceDiscoveryRun.id)
    ).scalar_one()
    failed_run_id = db_connection.execute(
        insert(SourceDiscoveryRun)
        .values(
            query="failed query",
            adapter_key="adapter",
            status="FAILED",
            error_message="failure",
        )
        .returning(SourceDiscoveryRun.id)
    ).scalar_one()
    candidate_values = {
        "source_discovery_run_id": succeeded_run_id,
        "run_status": "SUCCEEDED",
        "position": 0,
        "location": "https://example.gov/candidate",
    }
    candidate_id = db_connection.execute(
        insert(SourceCandidate).values(**candidate_values).returning(SourceCandidate.id)
    ).scalar_one()

    for invalid_values in (
        {**candidate_values, "location": "https://example.gov/other"},
        {**candidate_values, "position": 1},
        {
            **candidate_values,
            "source_discovery_run_id": failed_run_id,
            "position": 1,
            "location": "https://example.gov/failed",
        },
        {
            **candidate_values,
            "source_discovery_run_id": 999999,
            "position": 1,
            "location": "https://example.gov/missing",
        },
    ):
        with pytest.raises(IntegrityError), db_connection.begin_nested():
            db_connection.execute(insert(SourceCandidate).values(**invalid_values))

    with pytest.raises(IntegrityError), db_connection.begin_nested():
        db_connection.execute(
            delete(SourceDiscoveryRun).where(SourceDiscoveryRun.id == succeeded_run_id)
        )
    assert db_connection.scalar(
        select(SourceCandidate.id).where(SourceCandidate.id == candidate_id)
    ) == candidate_id
