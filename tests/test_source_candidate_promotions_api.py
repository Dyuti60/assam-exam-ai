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
from app.models import (
    Source,
    SourceCandidate,
    SourceCandidatePromotion,
    SourceDiscoveryRun,
)
from app.repositories import KnowledgeRepository


@pytest.fixture
def db_connection() -> Generator[Connection, None, None]:
    database_name = engine.url.database or ""
    if not database_name.endswith("_test"):
        pytest.fail("Source candidate promotion tests require a dedicated *_test database")
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


def _candidate_payload(location: str) -> dict:
    return {
        "location": location,
        "title": "Discovery title must not become Source metadata",
        "publisher": "Discovery publisher",
        "snippet": "Discovery snippet must not become Source content",
    }


def _create_candidate(client: TestClient, location: str) -> dict:
    response = client.post(
        "/api/v1/source-discovery-runs",
        json={
            "query": f"discover {location}",
            "adapter_key": "manual-test-v1",
            "status": "SUCCEEDED",
            "error_message": None,
            "candidates": [_candidate_payload(location)],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["candidates"][0]


def _approve_candidate(
    client: TestClient,
    candidate_id: int,
    note: str = "eligible for curated intake",
) -> dict:
    response = client.post(
        f"/api/v1/source-candidates/{candidate_id}/approval",
        json={"approval_status": "APPROVED", "reviewer_note": note},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _promotion_payload() -> dict:
    return {
        "title": "  Curated Assam Government Source  ",
        "publisher": "  Government of Assam  ",
        "source_type": "  OFFICIAL  ",
        "authority_tier": 1,
        "license_status": "  OFFICIAL_PUBLICATION  ",
    }


def _promote(client: TestClient, candidate_id: int, payload: dict | None = None):
    return client.post(
        f"/api/v1/source-candidates/{candidate_id}/promote",
        json=payload or _promotion_payload(),
    )


def _counts(connection: Connection) -> tuple[int, int]:
    return (
        connection.scalar(select(func.count()).select_from(Source)),
        connection.scalar(
            select(func.count()).select_from(SourceCandidatePromotion)
        ),
    )


def test_approved_candidate_creates_exact_source_and_promotion_snapshot(
    client: TestClient,
    db_connection: Connection,
) -> None:
    candidate = _create_candidate(client, "https://example.gov/exact-stored-location")
    approved = _approve_candidate(client, candidate["id"], "review snapshot")
    counts_before = _counts(db_connection)

    response = _promote(client, candidate["id"])

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["source_candidate_id"] == candidate["id"]
    assert body["source_id"] == body["source"]["id"]
    assert body["location"] == candidate["location"]
    assert body["candidate_approval_status"] == "APPROVED"
    assert body["candidate_approval_decided_at"] == approved["approval_decided_at"]
    assert body["candidate_reviewer_note"] == "review snapshot"
    assert datetime.fromisoformat(body["created_at"]).utcoffset() == UTC.utcoffset(None)
    assert body["source"] == {
        "title": "Curated Assam Government Source",
        "publisher": "Government of Assam",
        "source_type": "OFFICIAL",
        "authority_tier": 1,
        "location": candidate["location"],
        "license_status": "OFFICIAL_PUBLICATION",
        "content_hash": None,
        "id": body["source_id"],
        "created_at": body["source"]["created_at"],
    }
    assert _counts(db_connection) == (counts_before[0] + 1, counts_before[1] + 1)

    stored = db_connection.execute(
        select(SourceCandidatePromotion.__table__).where(
            SourceCandidatePromotion.id == body["id"]
        )
    ).mappings().one()
    assert stored["source_candidate_id"] == candidate["id"]
    assert stored["source_id"] == body["source_id"]
    assert stored["location"] == candidate["location"]
    assert stored["candidate_approval_status"] == "APPROVED"
    assert stored["candidate_approval_decided_at"] == datetime.fromisoformat(
        approved["approval_decided_at"]
    )
    assert stored["candidate_reviewer_note"] == "review snapshot"


@pytest.mark.parametrize("approval_status", ["DRAFT", "REJECTED"])
def test_unapproved_candidates_return_exact_conflict_without_persistence(
    client: TestClient,
    db_connection: Connection,
    approval_status: str,
) -> None:
    candidate = _create_candidate(
        client,
        f"https://example.gov/{approval_status.lower()}-candidate",
    )
    if approval_status == "REJECTED":
        response = client.post(
            f"/api/v1/source-candidates/{candidate['id']}/approval",
            json={"approval_status": "REJECTED", "reviewer_note": "not eligible"},
        )
        assert response.status_code == 200
    counts_before = _counts(db_connection)

    response = _promote(client, candidate["id"])

    assert response.status_code == 409
    assert response.json() == {
        "detail": (
            f"SourceCandidate {candidate['id']} must be approved before promotion"
        )
    }
    assert _counts(db_connection) == counts_before


def test_missing_candidate_returns_exact_404_without_persistence(
    client: TestClient,
    db_connection: Connection,
) -> None:
    counts_before = _counts(db_connection)
    response = _promote(client, 999999)
    assert response.status_code == 404
    assert response.json() == {"detail": "SourceCandidate 999999 not found"}
    assert _counts(db_connection) == counts_before


@pytest.mark.parametrize(
    "missing_field",
    ["title", "source_type", "authority_tier", "license_status"],
)
def test_missing_required_metadata_returns_422_without_persistence(
    client: TestClient,
    db_connection: Connection,
    missing_field: str,
) -> None:
    candidate = _create_candidate(
        client,
        f"https://example.gov/missing-{missing_field}",
    )
    _approve_candidate(client, candidate["id"])
    payload = _promotion_payload()
    payload.pop(missing_field)
    counts_before = _counts(db_connection)

    response = _promote(client, candidate["id"], payload)

    assert response.status_code == 422
    assert _counts(db_connection) == counts_before


@pytest.mark.parametrize(
    "change",
    [
        {"title": " "},
        {"title": "x" * 501},
        {"publisher": " "},
        {"publisher": "x" * 256},
        {"source_type": " "},
        {"source_type": "x" * 101},
        {"authority_tier": 0},
        {"authority_tier": 5},
        {"license_status": " "},
        {"license_status": "x" * 101},
        {"location": "https://attacker.invalid"},
        {"content_hash": "client-controlled"},
        {"source_id": 42},
        {"approval_status": "APPROVED"},
    ],
)
def test_invalid_or_forbidden_metadata_returns_422_without_persistence(
    client: TestClient,
    db_connection: Connection,
    change: dict,
) -> None:
    candidate = _create_candidate(
        client,
        f"https://example.gov/invalid-{next(iter(change))}-{len(str(change))}",
    )
    _approve_candidate(client, candidate["id"])
    payload = _promotion_payload()
    payload.update(change)
    counts_before = _counts(db_connection)

    response = _promote(client, candidate["id"], payload)

    assert response.status_code == 422
    assert _counts(db_connection) == counts_before


def test_duplicate_promotion_conflict_preserves_original_and_approved_collection(
    client: TestClient,
    db_connection: Connection,
) -> None:
    candidate = _create_candidate(client, "https://example.gov/one-promotion")
    _approve_candidate(client, candidate["id"])
    first = _promote(client, candidate["id"])
    assert first.status_code == 201
    original_source = db_connection.execute(
        select(Source.__table__).where(Source.id == first.json()["source_id"])
    ).mappings().one()
    original_promotion = db_connection.execute(
        select(SourceCandidatePromotion.__table__).where(
            SourceCandidatePromotion.id == first.json()["id"]
        )
    ).mappings().one()
    counts_before = _counts(db_connection)

    duplicate = _promote(client, candidate["id"])

    assert duplicate.status_code == 409
    assert duplicate.json() == {
        "detail": f"SourceCandidate {candidate['id']} already has a Source"
    }
    assert _counts(db_connection) == counts_before
    assert db_connection.execute(
        select(Source.__table__).where(Source.id == first.json()["source_id"])
    ).mappings().one() == original_source
    assert db_connection.execute(
        select(SourceCandidatePromotion.__table__).where(
            SourceCandidatePromotion.id == first.json()["id"]
        )
    ).mappings().one() == original_promotion
    approved_ids = {
        item["id"]
        for item in client.get("/api/v1/source-candidates/approved").json()
    }
    assert candidate["id"] in approved_ids


def test_later_candidate_review_changes_do_not_change_source_or_snapshot(
    client: TestClient,
    db_connection: Connection,
) -> None:
    candidate = _create_candidate(client, "https://example.gov/review-independent")
    _approve_candidate(client, candidate["id"], "authorizing decision")
    promoted = _promote(client, candidate["id"])
    assert promoted.status_code == 201
    source_before = db_connection.execute(
        select(Source.__table__).where(Source.id == promoted.json()["source_id"])
    ).mappings().one()
    promotion_before = db_connection.execute(
        select(SourceCandidatePromotion.__table__).where(
            SourceCandidatePromotion.id == promoted.json()["id"]
        )
    ).mappings().one()

    for status in ("DRAFT", "REJECTED", "APPROVED"):
        response = client.post(
            f"/api/v1/source-candidates/{candidate['id']}/approval",
            json={"approval_status": status, "reviewer_note": f"later {status}"},
        )
        assert response.status_code == 200

    assert db_connection.execute(
        select(Source.__table__).where(Source.id == promoted.json()["source_id"])
    ).mappings().one() == source_before
    assert db_connection.execute(
        select(SourceCandidatePromotion.__table__).where(
            SourceCandidatePromotion.id == promoted.json()["id"]
        )
    ).mappings().one() == promotion_before


def test_promotion_locks_only_target_and_commits_once(
    client: TestClient,
    db_connection: Connection,
) -> None:
    target = _create_candidate(client, "https://example.gov/lock-target")
    other = _create_candidate(client, "https://example.gov/lock-other")
    _approve_candidate(client, target["id"])
    other_before = db_connection.execute(
        select(SourceCandidate.__table__).where(SourceCandidate.id == other["id"])
    ).mappings().one()
    run_rows_before = db_connection.execute(
        select(SourceDiscoveryRun.__table__).order_by(SourceDiscoveryRun.id)
    ).mappings().all()
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
        response = _promote(client, target["id"])
    finally:
        event.remove(db_connection, "before_cursor_execute", record_statement)
        event.remove(Session, "after_commit", record_commit)

    assert response.status_code == 201, response.text
    operations = [
        (" ".join(sql.split()).upper(), parameters)
        for sql, parameters in statements
        if sql.lstrip().upper().startswith(("SELECT", "INSERT", "UPDATE", "DELETE"))
    ]
    locks = [(sql, params) for sql, params in operations if "FOR UPDATE" in sql]
    assert len(locks) == 1
    lock_sql, lock_parameters = locks[0]
    assert "FROM SOURCE_CANDIDATES" in lock_sql
    assert "SOURCE_CANDIDATES.ID =" in lock_sql
    assert "FOR UPDATE OF SOURCE_CANDIDATES" in lock_sql
    assert target["id"] in tuple(lock_parameters.values())
    assert other["id"] not in tuple(lock_parameters.values())
    assert all("SOURCE_DISCOVERY_RUNS" not in sql for sql, _ in operations)
    assert not any(sql.startswith(("UPDATE", "DELETE")) for sql, _ in operations)
    assert commits == 1
    assert db_connection.execute(
        select(SourceCandidate.__table__).where(SourceCandidate.id == other["id"])
    ).mappings().one() == other_before
    assert db_connection.execute(
        select(SourceDiscoveryRun.__table__).order_by(SourceDiscoveryRun.id)
    ).mappings().all() == run_rows_before


def test_post_flush_failure_rolls_back_source_and_promotion(
    client: TestClient,
    db_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = _create_candidate(client, "https://example.gov/rollback-promotion")
    candidate_before = _approve_candidate(client, candidate["id"])
    counts_before = _counts(db_connection)
    original_add = KnowledgeRepository.add_source_candidate_promotion
    commits = 0
    rollbacks = 0

    def fail_after_flush(
        repository: KnowledgeRepository,
        promotion: SourceCandidatePromotion,
    ) -> SourceCandidatePromotion:
        original_add(repository, promotion)
        raise RuntimeError("injected failure after promotion flush")

    def record_commit(*args: object) -> None:
        nonlocal commits
        commits += 1

    def record_rollback(*args: object) -> None:
        nonlocal rollbacks
        rollbacks += 1

    monkeypatch.setattr(
        KnowledgeRepository,
        "add_source_candidate_promotion",
        fail_after_flush,
    )
    event.listen(Session, "after_commit", record_commit)
    event.listen(Session, "after_rollback", record_rollback)
    try:
        with pytest.raises(RuntimeError, match="injected failure"):
            _promote(client, candidate["id"])
    finally:
        event.remove(Session, "after_commit", record_commit)
        event.remove(Session, "after_rollback", record_rollback)

    assert commits == 0
    assert rollbacks == 1
    assert _counts(db_connection) == counts_before
    stored_candidate = db_connection.execute(
        select(SourceCandidate.__table__).where(
            SourceCandidate.id == candidate["id"]
        )
    ).mappings().one()
    assert stored_candidate["approval_status"] == candidate_before["approval_status"]
    assert stored_candidate["approval_decided_at"] == datetime.fromisoformat(
        candidate_before["approval_decided_at"]
    )
    assert stored_candidate["reviewer_note"] == candidate_before["reviewer_note"]


def test_unrelated_integrity_failure_is_rolled_back_and_reraised(
    client: TestClient,
    db_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = _create_candidate(client, "https://example.gov/unrelated-integrity")
    _approve_candidate(client, candidate["id"])
    counts_before = _counts(db_connection)
    rollbacks = 0

    def fail_with_unrelated_integrity(
        repository: KnowledgeRepository,
        promotion: SourceCandidatePromotion,
    ) -> SourceCandidatePromotion:
        raise IntegrityError("injected", {}, RuntimeError("unrelated integrity"))

    def record_rollback(*args: object) -> None:
        nonlocal rollbacks
        rollbacks += 1

    monkeypatch.setattr(
        KnowledgeRepository,
        "add_source_candidate_promotion",
        fail_with_unrelated_integrity,
    )
    event.listen(Session, "after_rollback", record_rollback)
    try:
        with pytest.raises(IntegrityError):
            _promote(client, candidate["id"])
    finally:
        event.remove(Session, "after_rollback", record_rollback)

    assert rollbacks == 1
    assert _counts(db_connection) == counts_before


def test_named_candidate_uniqueness_is_concurrency_authority(
    client: TestClient,
    db_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = _create_candidate(client, "https://example.gov/concurrency-authority")
    _approve_candidate(client, candidate["id"])
    first = _promote(client, candidate["id"])
    assert first.status_code == 201
    counts_before = _counts(db_connection)
    monkeypatch.setattr(
        KnowledgeRepository,
        "get_source_candidate_promotion_by_candidate_id",
        lambda repository, source_candidate_id: None,
    )

    duplicate = _promote(client, candidate["id"])

    assert duplicate.status_code == 409
    assert duplicate.json() == {
        "detail": f"SourceCandidate {candidate['id']} already has a Source"
    }
    assert _counts(db_connection) == counts_before


def test_direct_source_creation_remains_independent(
    client: TestClient,
    db_connection: Connection,
) -> None:
    response = client.post(
        "/api/v1/sources",
        json={
            "title": "Direct curated source",
            "publisher": None,
            "source_type": "OFFICIAL",
            "authority_tier": 1,
            "location": "https://example.gov/direct-source",
            "license_status": "OFFICIAL_PUBLICATION",
            "content_hash": None,
        },
    )
    assert response.status_code == 201
    assert db_connection.scalar(
        select(func.count()).select_from(SourceCandidatePromotion)
    ) == 0


def test_postgresql_enforces_promotion_constraints_and_restricted_deletion(
    client: TestClient,
    db_connection: Connection,
) -> None:
    first = _create_candidate(client, "https://example.gov/constraint-first")
    second = _create_candidate(client, "https://example.gov/constraint-second")
    third = _create_candidate(client, "https://example.gov/constraint-first")
    first_approved = _approve_candidate(client, first["id"], "first")
    second_approved = _approve_candidate(client, second["id"], "second")
    third_approved = _approve_candidate(client, third["id"], "third")
    promoted = _promote(client, first["id"])
    assert promoted.status_code == 201
    source_id = promoted.json()["source_id"]

    second_source = db_connection.execute(
        insert(Source.__table__)
        .values(
            title="Second",
            publisher=None,
            source_type="OFFICIAL",
            authority_tier=1,
            location=second["location"],
            license_status="TEST_ONLY",
            content_hash=None,
        )
        .returning(Source.id)
    ).scalar_one()
    alternate_first_source = db_connection.execute(
        insert(Source.__table__)
        .values(
            title="Alternate first",
            publisher=None,
            source_type="OFFICIAL",
            authority_tier=1,
            location=first["location"],
            license_status="TEST_ONLY",
            content_hash=None,
        )
        .returning(Source.id)
    ).scalar_one()

    invalid_rows = [
        (
            {
                "source_candidate_id": first["id"],
                "source_id": alternate_first_source,
                "location": first["location"],
                "candidate_approval_status": "APPROVED",
                "candidate_approval_decided_at": first_approved[
                    "approval_decided_at"
                ],
            },
            "uq_source_candidate_promotions_source_candidate_id",
        ),
        (
            {
                "source_candidate_id": third["id"],
                "source_id": source_id,
                "location": third["location"],
                "candidate_approval_status": "APPROVED",
                "candidate_approval_decided_at": third_approved[
                    "approval_decided_at"
                ],
            },
            "uq_source_candidate_promotions_source_id",
        ),
        (
            {
                "source_candidate_id": second["id"],
                "source_id": alternate_first_source,
                "location": first["location"],
                "candidate_approval_status": "APPROVED",
                "candidate_approval_decided_at": second_approved[
                    "approval_decided_at"
                ],
            },
            "fk_source_candidate_promotions_candidate_location",
        ),
        (
            {
                "source_candidate_id": second["id"],
                "source_id": alternate_first_source,
                "location": second["location"],
                "candidate_approval_status": "APPROVED",
                "candidate_approval_decided_at": second_approved[
                    "approval_decided_at"
                ],
            },
            "fk_source_candidate_promotions_source_location",
        ),
        (
            {
                "source_candidate_id": second["id"],
                "source_id": second_source,
                "location": " ",
                "candidate_approval_status": "APPROVED",
                "candidate_approval_decided_at": second_approved[
                    "approval_decided_at"
                ],
            },
            "ck_source_candidate_promotions_location_non_blank",
        ),
        (
            {
                "source_candidate_id": second["id"],
                "source_id": second_source,
                "location": second["location"],
                "candidate_approval_status": "REJECTED",
                "candidate_approval_decided_at": second_approved[
                    "approval_decided_at"
                ],
            },
            "ck_source_candidate_promotions_approval_status",
        ),
        (
            {
                "source_candidate_id": second["id"],
                "source_id": second_source,
                "location": second["location"],
                "candidate_approval_status": "APPROVED",
                "candidate_approval_decided_at": None,
            },
            None,
        ),
    ]
    for values, constraint_name in invalid_rows:
        with pytest.raises(IntegrityError) as error, db_connection.begin_nested():
            db_connection.execute(
                insert(SourceCandidatePromotion.__table__).values(**values)
            )
        assert error.value.orig.diag.constraint_name == constraint_name

    with pytest.raises(IntegrityError), db_connection.begin_nested():
        db_connection.execute(
            delete(SourceCandidate).where(SourceCandidate.id == first["id"])
        )
    with pytest.raises(IntegrityError), db_connection.begin_nested():
        db_connection.execute(delete(Source).where(Source.id == source_id))
