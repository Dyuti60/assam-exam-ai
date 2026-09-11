from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, event, func, insert, select, update
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
    assert all(
        candidate["approval_status"] == "DRAFT"
        and candidate["approval_decided_at"] is None
        and candidate["reviewer_note"] is None
        for candidate in created["candidates"]
    )
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


def test_source_candidate_review_transitions_preserve_snapshot_and_target_only(
    client: TestClient,
    db_connection: Connection,
) -> None:
    first_run = _post_run(
        client,
        _run_payload(
            candidates=[
                _candidate("https://example.gov/target"),
                _candidate("https://example.gov/same-run-other"),
            ]
        ),
    )
    second_run = _post_run(
        client,
        _run_payload(candidates=[_candidate("https://example.gov/other-run")]),
    )
    target = first_run["candidates"][0]
    target_id = target["id"]
    immutable_fields = {
        key: target[key]
        for key in (
            "id",
            "source_discovery_run_id",
            "run_status",
            "position",
            "location",
            "title",
            "publisher",
            "snippet",
            "created_at",
        )
    }
    run_rows_before = db_connection.execute(
        select(SourceDiscoveryRun.__table__).order_by(SourceDiscoveryRun.id)
    ).mappings().all()
    other_candidates_before = db_connection.execute(
        select(SourceCandidate.__table__)
        .where(SourceCandidate.id != target_id)
        .order_by(SourceCandidate.id)
    ).mappings().all()

    approved = client.post(
        f"/api/v1/source-candidates/{target_id}/approval",
        json={"approval_status": "APPROVED", "reviewer_note": "accepted lead"},
    )
    assert approved.status_code == 200, approved.text
    approved_body = approved.json()
    assert {key: approved_body[key] for key in immutable_fields} == immutable_fields
    assert approved_body["approval_status"] == "APPROVED"
    assert approved_body["reviewer_note"] == "accepted lead"
    assert datetime.fromisoformat(
        approved_body["approval_decided_at"]
    ).utcoffset() == UTC.utcoffset(None)

    rejected = client.post(
        f"/api/v1/source-candidates/{target_id}/approval",
        json={"approval_status": "REJECTED", "reviewer_note": "not suitable"},
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["approval_status"] == "REJECTED"
    assert rejected.json()["reviewer_note"] == "not suitable"
    assert datetime.fromisoformat(
        rejected.json()["approval_decided_at"]
    ).utcoffset() == UTC.utcoffset(None)

    reset = client.post(
        f"/api/v1/source-candidates/{target_id}/approval",
        json={"approval_status": "DRAFT", "reviewer_note": "ignored"},
    )
    assert reset.status_code == 200, reset.text
    assert reset.json()["approval_status"] == "DRAFT"
    assert reset.json()["approval_decided_at"] is None
    assert reset.json()["reviewer_note"] is None
    assert {key: reset.json()[key] for key in immutable_fields} == immutable_fields

    retrieved = client.get(f"/api/v1/source-discovery-runs/{first_run['id']}")
    assert retrieved.status_code == 200
    assert [candidate["id"] for candidate in retrieved.json()["candidates"]] == [
        candidate["id"] for candidate in first_run["candidates"]
    ]
    assert retrieved.json()["candidates"][0]["approval_status"] == "DRAFT"
    assert retrieved.json()["candidates"][1] == first_run["candidates"][1]
    assert db_connection.execute(
        select(SourceDiscoveryRun.__table__).order_by(SourceDiscoveryRun.id)
    ).mappings().all() == run_rows_before
    assert db_connection.execute(
        select(SourceCandidate.__table__)
        .where(SourceCandidate.id != target_id)
        .order_by(SourceCandidate.id)
    ).mappings().all() == other_candidates_before
    assert second_run["candidates"][0]["id"] not in [
        candidate["id"] for candidate in retrieved.json()["candidates"]
    ]


def test_source_candidate_review_errors_do_not_mutate(
    client: TestClient,
    db_connection: Connection,
) -> None:
    created = _post_run(
        client,
        _run_payload(candidates=[_candidate("https://example.gov/errors")]),
    )
    candidate_id = created["candidates"][0]["id"]
    before = db_connection.execute(
        select(SourceCandidate.__table__).where(SourceCandidate.id == candidate_id)
    ).mappings().one()

    invalid = client.post(
        f"/api/v1/source-candidates/{candidate_id}/approval",
        json={"approval_status": "UNKNOWN"},
    )
    assert invalid.status_code == 422
    missing_status = client.post(
        f"/api/v1/source-candidates/{candidate_id}/approval",
        json={"reviewer_note": "missing decision"},
    )
    assert missing_status.status_code == 422
    missing = client.post(
        "/api/v1/source-candidates/999999/approval",
        json={"approval_status": "APPROVED"},
    )
    assert missing.status_code == 404
    assert missing.json() == {"detail": "SourceCandidate 999999 not found"}
    assert db_connection.execute(
        select(SourceCandidate.__table__).where(SourceCandidate.id == candidate_id)
    ).mappings().one() == before


def test_source_candidate_review_uses_target_only_sql_and_one_commit(
    client: TestClient,
    db_connection: Connection,
) -> None:
    created = _post_run(
        client,
        _run_payload(
            candidates=[
                _candidate("https://example.gov/sql-target"),
                _candidate("https://example.gov/sql-other"),
            ]
        ),
    )
    target_id = created["candidates"][0]["id"]
    other_id = created["candidates"][1]["id"]
    row_counts_before = {
        table.name: db_connection.scalar(select(func.count()).select_from(table))
        for table in SourceCandidate.metadata.sorted_tables
    }
    statements: list[tuple[str, object]] = []
    commits = 0

    def record_statement(
        connection: object,
        cursor: object,
        statement: str,
        parameters: object,
        context: object,
        executemany: object,
    ) -> None:
        statements.append((statement, parameters))

    def record_commit(*args: object) -> None:
        nonlocal commits
        commits += 1

    event.listen(db_connection, "before_cursor_execute", record_statement)
    event.listen(Session, "after_commit", record_commit)
    try:
        response = client.post(
            f"/api/v1/source-candidates/{target_id}/approval",
            json={"approval_status": "APPROVED", "reviewer_note": "target only"},
        )
    finally:
        event.remove(db_connection, "before_cursor_execute", record_statement)
        event.remove(Session, "after_commit", record_commit)

    assert response.status_code == 200, response.text
    operations = [
        (" ".join(statement.split()), parameters)
        for statement, parameters in statements
        if statement.lstrip().upper().startswith(("SELECT", "UPDATE", "INSERT", "DELETE"))
    ]
    assert len(operations) == 3
    assert "FOR UPDATE OF SOURCE_CANDIDATES" in operations[0][0].upper()
    assert operations[1][0].upper().startswith("UPDATE SOURCE_CANDIDATES SET ")
    assert "FOR UPDATE" not in operations[2][0].upper()
    assert all(" JOIN " not in statement.upper() for statement, _ in operations)
    assert all("source_candidates" in statement.lower() for statement, _ in operations)
    for _, parameters in operations:
        values = (
            tuple(parameters.values())
            if isinstance(parameters, dict)
            else tuple(parameters)
        )
        assert target_id in values
        assert other_id not in values
    assert commits == 1
    assert {
        table.name: db_connection.scalar(select(func.count()).select_from(table))
        for table in SourceCandidate.metadata.sorted_tables
    } == row_counts_before


def test_source_candidate_review_rolls_back_after_flushed_update(
    client: TestClient,
    db_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created = _post_run(
        client,
        _run_payload(candidates=[_candidate("https://example.gov/rollback")]),
    )
    candidate_id = created["candidates"][0]["id"]
    candidate_before = db_connection.execute(
        select(SourceCandidate.__table__).where(SourceCandidate.id == candidate_id)
    ).mappings().one()
    run_before = db_connection.execute(
        select(SourceDiscoveryRun.__table__).where(
            SourceDiscoveryRun.id == created["id"]
        )
    ).mappings().one()
    original = KnowledgeRepository.update_source_candidate_approval
    commits = 0
    rollbacks = 0

    def fail_after_flush(
        repository: KnowledgeRepository,
        candidate: SourceCandidate,
        approval_status: str,
        reviewer_note: str | None,
        decided_at: datetime | None,
    ) -> None:
        original(repository, candidate, approval_status, reviewer_note, decided_at)
        repository.session.flush()
        raise RuntimeError("injected failure after candidate review flush")

    def record_commit(*args: object) -> None:
        nonlocal commits
        commits += 1

    def record_rollback(*args: object) -> None:
        nonlocal rollbacks
        rollbacks += 1

    monkeypatch.setattr(
        KnowledgeRepository,
        "update_source_candidate_approval",
        fail_after_flush,
    )
    event.listen(Session, "after_commit", record_commit)
    event.listen(Session, "after_rollback", record_rollback)
    try:
        with pytest.raises(
            RuntimeError,
            match="injected failure after candidate review flush",
        ):
            client.post(
                f"/api/v1/source-candidates/{candidate_id}/approval",
                json={"approval_status": "APPROVED", "reviewer_note": "rollback"},
            )
    finally:
        event.remove(Session, "after_commit", record_commit)
        event.remove(Session, "after_rollback", record_rollback)

    assert commits == 0
    assert rollbacks == 1
    assert db_connection.execute(
        select(SourceCandidate.__table__).where(SourceCandidate.id == candidate_id)
    ).mappings().one() == candidate_before
    assert db_connection.execute(
        select(SourceDiscoveryRun.__table__).where(
            SourceDiscoveryRun.id == created["id"]
        )
    ).mappings().one() == run_before


@pytest.mark.parametrize(
    ("values", "constraint_name"),
    [
        ({"approval_status": "UNKNOWN"}, "ck_source_candidates_approval_status"),
        (
            {"approval_status": "DRAFT", "approval_decided_at": func.now()},
            "ck_source_candidates_approval_lifecycle",
        ),
        (
            {"approval_status": "DRAFT", "reviewer_note": "not allowed"},
            "ck_source_candidates_approval_lifecycle",
        ),
        (
            {"approval_status": "APPROVED", "approval_decided_at": None},
            "ck_source_candidates_approval_lifecycle",
        ),
        (
            {"approval_status": "REJECTED", "approval_decided_at": None},
            "ck_source_candidates_approval_lifecycle",
        ),
    ],
)
def test_source_candidate_review_database_constraints(
    client: TestClient,
    db_connection: Connection,
    values: dict,
    constraint_name: str,
) -> None:
    created = _post_run(
        client,
        _run_payload(candidates=[_candidate(f"https://example.gov/db-{len(str(values))}")]),
    )
    candidate_id = created["candidates"][0]["id"]
    with pytest.raises(IntegrityError) as error, db_connection.begin_nested():
        db_connection.execute(
            update(SourceCandidate)
            .where(SourceCandidate.id == candidate_id)
            .values(**values)
        )
    assert error.value.orig.diag.constraint_name == constraint_name


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
