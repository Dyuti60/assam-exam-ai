from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import engine, get_db
from app.main import app
from app.models import Exam, Source, SyllabusVersion, SyllabusVersionTopic, Topic


@pytest.fixture
def db_connection() -> Generator[Connection, None, None]:
    database_name = engine.url.database or ""
    if not database_name.endswith("_test"):
        pytest.fail("Syllabus tests require a dedicated *_test database")

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


def _create_exam(client: TestClient, code: str = "ADRE", name: str = "ADRE") -> int:
    response = client.post("/api/v1/exams", json={"code": code, "name": name})
    assert response.status_code == 201
    return response.json()["id"]


def _create_source(client: TestClient) -> int:
    response = client.post(
        "/api/v1/sources",
        json={
            "title": "Official syllabus",
            "publisher": "Official authority",
            "source_type": "notification",
            "authority_tier": 1,
            "location": "https://example.gov/syllabus",
            "license_status": "UNKNOWN",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_topic(client: TestClient, name: str) -> int:
    response = client.post("/api/v1/topics", json={"name": name})
    assert response.status_code == 201
    return response.json()["id"]


def test_create_syllabus_version_persists_topics_in_request_order(
    client: TestClient,
    db_connection: Connection,
) -> None:
    exam_id = _create_exam(client)
    source_id = _create_source(client)
    topic_ids = [_create_topic(client, name) for name in ["History", "Polity"]]

    response = client.post(
        "/api/v1/syllabus-versions",
        json={
            "exam_id": exam_id,
            "source_id": source_id,
            "label": "2026 official syllabus",
            "topic_ids": list(reversed(topic_ids)),
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body == {
        "id": body["id"],
        "exam_id": exam_id,
        "source_id": source_id,
        "label": "2026 official syllabus",
        "created_at": body["created_at"],
        "topic_ids": list(reversed(topic_ids)),
    }
    links = db_connection.execute(
        select(SyllabusVersionTopic.topic_id, SyllabusVersionTopic.position)
        .where(SyllabusVersionTopic.syllabus_version_id == body["id"])
        .order_by(SyllabusVersionTopic.position)
    ).all()
    assert links == [(topic_ids[1], 0), (topic_ids[0], 1)]


@pytest.mark.parametrize(
    ("missing_resource", "missing_id"),
    [("Exam", 999991), ("Source", 999992), ("Topic", 999993)],
)
def test_create_syllabus_version_rejects_missing_reference_without_partial_rows(
    client: TestClient,
    db_connection: Connection,
    missing_resource: str,
    missing_id: int,
) -> None:
    exam_id = _create_exam(client, f"EX-{missing_id}", f"Exam {missing_id}")
    source_id = _create_source(client)
    topic_id = _create_topic(client, f"Topic {missing_id}")
    request = {
        "exam_id": exam_id,
        "source_id": source_id,
        "label": f"Missing {missing_resource}",
        "topic_ids": [topic_id],
    }
    if missing_resource == "Topic":
        request["topic_ids"] = [missing_id]
    else:
        request[f"{missing_resource.lower()}_id"] = missing_id

    response = client.post("/api/v1/syllabus-versions", json=request)

    assert response.status_code == 404
    assert response.json() == {
        "detail": f"{missing_resource} {missing_id} not found"
    }
    assert db_connection.scalar(select(func.count()).select_from(SyllabusVersion)) == 0
    assert (
        db_connection.scalar(select(func.count()).select_from(SyllabusVersionTopic))
        == 0
    )


@pytest.mark.parametrize(
    ("second_request", "detail"),
    [
        (
            {"code": "EXAM-A", "name": "Different name"},
            "Exam code 'EXAM-A' already exists",
        ),
        (
            {"code": "EXAM-B", "name": "Exam A"},
            "Exam name 'Exam A' already exists",
        ),
    ],
)
def test_create_exam_returns_stable_conflict(
    client: TestClient,
    second_request: dict[str, str],
    detail: str,
) -> None:
    _create_exam(client, "EXAM-A", "Exam A")

    response = client.post("/api/v1/exams", json=second_request)

    assert response.status_code == 409
    assert response.json() == {"detail": detail}


def test_create_syllabus_version_returns_stable_label_conflict(
    client: TestClient,
) -> None:
    exam_id = _create_exam(client)
    source_id = _create_source(client)
    topic_id = _create_topic(client, "Geography")
    request = {
        "exam_id": exam_id,
        "source_id": source_id,
        "label": "Version 1",
        "topic_ids": [topic_id],
    }
    assert client.post("/api/v1/syllabus-versions", json=request).status_code == 201

    response = client.post("/api/v1/syllabus-versions", json=request)

    assert response.status_code == 409
    assert response.json() == {
        "detail": f"SyllabusVersion label 'Version 1' already exists for Exam {exam_id}"
    }


@pytest.mark.parametrize("topic_ids", [[], [1, 1], [0]])
def test_create_syllabus_version_rejects_invalid_topic_ids(
    client: TestClient,
    topic_ids: list[int],
) -> None:
    response = client.post(
        "/api/v1/syllabus-versions",
        json={
            "exam_id": 1,
            "source_id": 1,
            "label": "Invalid",
            "topic_ids": topic_ids,
        },
    )

    assert response.status_code == 422


def test_syllabus_topic_database_constraints_are_enforced(
    client: TestClient,
    db_connection: Connection,
) -> None:
    exam_id = _create_exam(client)
    source_id = _create_source(client)
    topic_ids = [_create_topic(client, name) for name in ["Economy", "Science"]]
    response = client.post(
        "/api/v1/syllabus-versions",
        json={
            "exam_id": exam_id,
            "source_id": source_id,
            "label": "Constraints",
            "topic_ids": [topic_ids[0]],
        },
    )
    assert response.status_code == 201
    syllabus_version_id = response.json()["id"]

    for topic_id, position in [
        (topic_ids[1], -1),
        (topic_ids[1], 0),
        (topic_ids[0], 1),
    ]:
        savepoint = db_connection.begin_nested()
        with pytest.raises(IntegrityError):
            db_connection.execute(
                SyllabusVersionTopic.__table__.insert().values(
                    syllabus_version_id=syllabus_version_id,
                    topic_id=topic_id,
                    position=position,
                )
            )
        savepoint.rollback()


@pytest.mark.parametrize("model", [Exam, Source, Topic, SyllabusVersion])
def test_syllabus_references_restrict_parent_deletion(
    client: TestClient,
    db_connection: Connection,
    model: type[Exam] | type[Source] | type[Topic] | type[SyllabusVersion],
) -> None:
    exam_id = _create_exam(client)
    source_id = _create_source(client)
    topic_id = _create_topic(client, "Protected Topic")
    response = client.post(
        "/api/v1/syllabus-versions",
        json={
            "exam_id": exam_id,
            "source_id": source_id,
            "label": "Protected",
            "topic_ids": [topic_id],
        },
    )
    assert response.status_code == 201
    target_id = {
        Exam: exam_id,
        Source: source_id,
        Topic: topic_id,
        SyllabusVersion: response.json()["id"],
    }[model]

    savepoint = db_connection.begin_nested()
    with pytest.raises(IntegrityError):
        db_connection.execute(delete(model).where(model.id == target_id))
    savepoint.rollback()
