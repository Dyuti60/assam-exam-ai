from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import engine, get_db
from app.main import app
from app.models import ContentVersion, SyllabusVersionTopic


@pytest.fixture
def db_connection() -> Generator[Connection, None, None]:
    database_name = engine.url.database or ""
    if not database_name.endswith("_test"):
        pytest.fail("ContentVersion tests require a dedicated *_test database")
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


def _post(client: TestClient, path: str, payload: dict) -> dict:
    response = client.post(path, json=payload)
    assert response.status_code == 201
    return response.json()


def _mapping(
    client: TestClient,
    suffix: str = "A",
    topic_id: int | None = None,
) -> tuple[int, int]:
    exam = _post(
        client,
        "/api/v1/exams",
        {"code": f"EX-{suffix}", "name": f"Exam {suffix}"},
    )
    source = _post(
        client,
        "/api/v1/sources",
        {
            "title": f"Syllabus {suffix}",
            "source_type": "official",
            "authority_tier": 1,
            "location": f"https://example.gov/syllabus-{suffix}",
            "license_status": "UNKNOWN",
        },
    )
    if topic_id is None:
        topic_id = _post(client, "/api/v1/topics", {"name": f"Topic {suffix}"})[
            "id"
        ]
    syllabus = _post(
        client,
        "/api/v1/syllabus-versions",
        {
            "exam_id": exam["id"],
            "source_id": source["id"],
            "label": "Version 1",
            "topic_ids": [topic_id],
        },
    )
    return syllabus["id"], topic_id


def _create_content_version(
    client: TestClient,
    syllabus_version_id: int,
    topic_id: int,
    version: int,
) -> dict:
    return _post(
        client,
        "/api/v1/content-versions",
        {
            "syllabus_version_id": syllabus_version_id,
            "topic_id": topic_id,
            "version": version,
        },
    )


def test_create_and_retrieve_content_version_identity(client: TestClient) -> None:
    syllabus_version_id, topic_id = _mapping(client)

    created = _create_content_version(client, syllabus_version_id, topic_id, 1)
    response = client.get(f"/api/v1/content-versions/{created['id']}")

    assert created == {
        "syllabus_version_id": syllabus_version_id,
        "topic_id": topic_id,
        "version": 1,
        "id": created["id"],
        "created_at": created["created_at"],
    }
    assert response.status_code == 200
    assert response.json() == created


def test_explicit_versions_one_and_two_can_share_mapping(client: TestClient) -> None:
    syllabus_version_id, topic_id = _mapping(client)

    first = _create_content_version(client, syllabus_version_id, topic_id, 1)
    second = _create_content_version(client, syllabus_version_id, topic_id, 2)

    assert [first["version"], second["version"]] == [1, 2]
    assert first["id"] != second["id"]


def test_version_one_can_exist_under_different_syllabus_versions(
    client: TestClient,
) -> None:
    first_syllabus_id, topic_id = _mapping(client, "A")
    second_syllabus_id, second_topic_id = _mapping(client, "B", topic_id)

    first = _create_content_version(client, first_syllabus_id, topic_id, 1)
    second = _create_content_version(client, second_syllabus_id, topic_id, 1)

    assert first["version"] == second["version"] == 1
    assert first["topic_id"] == second["topic_id"] == second_topic_id == topic_id
    assert first["syllabus_version_id"] != second["syllabus_version_id"]
    assert first["id"] != second["id"]


@pytest.mark.parametrize(
    ("field", "missing_id", "resource"),
    [
        ("syllabus_version_id", 999991, "SyllabusVersion"),
        ("topic_id", 999992, "Topic"),
    ],
)
def test_create_content_version_returns_404_for_missing_reference(
    client: TestClient,
    db_connection: Connection,
    field: str,
    missing_id: int,
    resource: str,
) -> None:
    syllabus_version_id, topic_id = _mapping(client)
    payload = {
        "syllabus_version_id": syllabus_version_id,
        "topic_id": topic_id,
        "version": 1,
    }
    payload[field] = missing_id

    response = client.post("/api/v1/content-versions", json=payload)

    assert response.status_code == 404
    assert response.json() == {"detail": f"{resource} {missing_id} not found"}
    assert db_connection.scalar(select(func.count()).select_from(ContentVersion)) == 0


def test_get_content_version_returns_404_for_missing_identity(
    client: TestClient,
) -> None:
    response = client.get("/api/v1/content-versions/999993")

    assert response.status_code == 404
    assert response.json() == {"detail": "ContentVersion 999993 not found"}


def test_topic_outside_syllabus_returns_stable_conflict_without_partial_row(
    client: TestClient,
    db_connection: Connection,
) -> None:
    syllabus_version_id, _ = _mapping(client)
    outside_topic = _post(client, "/api/v1/topics", {"name": "Outside Topic"})

    response = client.post(
        "/api/v1/content-versions",
        json={
            "syllabus_version_id": syllabus_version_id,
            "topic_id": outside_topic["id"],
            "version": 1,
        },
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": (
            f"Topic {outside_topic['id']} is not mapped to "
            f"SyllabusVersion {syllabus_version_id}"
        )
    }
    assert db_connection.scalar(select(func.count()).select_from(ContentVersion)) == 0


@pytest.mark.parametrize("version", [0, -1])
def test_non_positive_content_version_returns_422(
    client: TestClient,
    version: int,
) -> None:
    response = client.post(
        "/api/v1/content-versions",
        json={"syllabus_version_id": 1, "topic_id": 1, "version": version},
    )

    assert response.status_code == 422


def test_duplicate_content_version_returns_stable_conflict(
    client: TestClient,
) -> None:
    syllabus_version_id, topic_id = _mapping(client)
    _create_content_version(client, syllabus_version_id, topic_id, 1)

    response = client.post(
        "/api/v1/content-versions",
        json={
            "syllabus_version_id": syllabus_version_id,
            "topic_id": topic_id,
            "version": 1,
        },
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": (
            f"ContentVersion 1 already exists for SyllabusVersion "
            f"{syllabus_version_id} and Topic {topic_id}"
        )
    }


def test_content_version_database_constraints(
    client: TestClient,
    db_connection: Connection,
) -> None:
    syllabus_version_id, topic_id = _mapping(client)
    _create_content_version(client, syllabus_version_id, topic_id, 1)
    outside_topic = _post(client, "/api/v1/topics", {"name": "Unmapped Topic"})
    invalid_rows = [
        ContentVersion.__table__.insert().values(
            syllabus_version_id=syllabus_version_id,
            topic_id=topic_id,
            version=1,
        ),
        ContentVersion.__table__.insert().values(
            syllabus_version_id=syllabus_version_id,
            topic_id=topic_id,
            version=0,
        ),
        ContentVersion.__table__.insert().values(
            syllabus_version_id=syllabus_version_id,
            topic_id=outside_topic["id"],
            version=1,
        ),
    ]

    for statement in invalid_rows:
        savepoint = db_connection.begin_nested()
        with pytest.raises(IntegrityError):
            db_connection.execute(statement)
        savepoint.rollback()


def test_content_version_restricts_syllabus_topic_mapping_deletion(
    client: TestClient,
    db_connection: Connection,
) -> None:
    syllabus_version_id, topic_id = _mapping(client)
    _create_content_version(client, syllabus_version_id, topic_id, 1)

    savepoint = db_connection.begin_nested()
    with pytest.raises(IntegrityError):
        db_connection.execute(
            delete(SyllabusVersionTopic).where(
                SyllabusVersionTopic.syllabus_version_id == syllabus_version_id,
                SyllabusVersionTopic.topic_id == topic_id,
            )
        )
    savepoint.rollback()
