from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import engine, get_db
from app.main import app
from app.models import Exam, PreviousPaper, PreviousQuestion, Source, Topic


@pytest.fixture
def db_connection() -> Generator[Connection, None, None]:
    database_name = engine.url.database or ""
    if not database_name.endswith("_test"):
        pytest.fail("Previous-paper tests require a dedicated *_test database")

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


def _create_exam(client: TestClient) -> int:
    response = client.post(
        "/api/v1/exams",
        json={"code": "ADRE", "name": "Assam Direct Recruitment Examination"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_source(client: TestClient) -> int:
    response = client.post(
        "/api/v1/sources",
        json={
            "title": "Official previous paper",
            "publisher": "Official examination authority",
            "source_type": "previous_paper",
            "authority_tier": 1,
            "location": "https://example.gov/previous-paper",
            "license_status": "UNKNOWN",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_topic(client: TestClient, name: str = "Assam History") -> int:
    response = client.post("/api/v1/topics", json={"name": name})
    assert response.status_code == 201
    return response.json()["id"]


def _create_paper(
    client: TestClient,
    exam_id: int,
    source_id: int,
    year: int = 2024,
    label: str = "Paper I",
) -> dict:
    response = client.post(
        "/api/v1/previous-papers",
        json={
            "exam_id": exam_id,
            "source_id": source_id,
            "year": year,
            "label": label,
        },
    )
    assert response.status_code == 201
    return response.json()


def test_create_previous_paper_and_question_preserves_exact_linkage(
    client: TestClient,
    db_connection: Connection,
) -> None:
    exam_id = _create_exam(client)
    source_id = _create_source(client)
    topic_id = _create_topic(client)

    paper = _create_paper(client, exam_id, source_id)
    response = client.post(
        "/api/v1/previous-questions",
        json={
            "previous_paper_id": paper["id"],
            "topic_id": topic_id,
            "position": 3,
            "question_text": "Who founded the Ahom kingdom?",
            "source_location_reference": "Page 4, Question 4",
        },
    )

    assert paper == {
        "exam_id": exam_id,
        "source_id": source_id,
        "year": 2024,
        "label": "Paper I",
        "id": paper["id"],
        "created_at": paper["created_at"],
    }
    assert response.status_code == 201
    question = response.json()
    assert question == {
        "previous_paper_id": paper["id"],
        "topic_id": topic_id,
        "position": 3,
        "question_text": "Who founded the Ahom kingdom?",
        "source_location_reference": "Page 4, Question 4",
        "id": question["id"],
        "created_at": question["created_at"],
    }
    stored = db_connection.execute(
        select(
            PreviousQuestion.previous_paper_id,
            PreviousQuestion.topic_id,
            PreviousQuestion.position,
            PreviousQuestion.question_text,
            PreviousQuestion.source_location_reference,
        ).where(PreviousQuestion.id == question["id"])
    ).one()
    assert stored == (
        paper["id"],
        topic_id,
        3,
        "Who founded the Ahom kingdom?",
        "Page 4, Question 4",
    )


@pytest.mark.parametrize("missing_resource", ["Exam", "Source"])
def test_create_previous_paper_rejects_missing_reference_without_partial_row(
    client: TestClient,
    db_connection: Connection,
    missing_resource: str,
) -> None:
    exam_id = _create_exam(client)
    source_id = _create_source(client)
    missing_id = 999991 if missing_resource == "Exam" else 999992
    request = {
        "exam_id": exam_id,
        "source_id": source_id,
        "year": 2024,
        "label": f"Missing {missing_resource}",
    }
    request[f"{missing_resource.lower()}_id"] = missing_id

    response = client.post("/api/v1/previous-papers", json=request)

    assert response.status_code == 404
    assert response.json() == {
        "detail": f"{missing_resource} {missing_id} not found"
    }
    assert db_connection.scalar(select(func.count()).select_from(PreviousPaper)) == 0


@pytest.mark.parametrize("missing_resource", ["PreviousPaper", "Topic"])
def test_create_previous_question_rejects_missing_reference_without_partial_row(
    client: TestClient,
    db_connection: Connection,
    missing_resource: str,
) -> None:
    exam_id = _create_exam(client)
    source_id = _create_source(client)
    topic_id = _create_topic(client)
    paper = _create_paper(client, exam_id, source_id)
    missing_id = 999993 if missing_resource == "PreviousPaper" else 999994
    request = {
        "previous_paper_id": paper["id"],
        "topic_id": topic_id,
        "position": 0,
        "question_text": "A sourced question?",
    }
    request[
        "previous_paper_id" if missing_resource == "PreviousPaper" else "topic_id"
    ] = missing_id

    response = client.post("/api/v1/previous-questions", json=request)

    assert response.status_code == 404
    assert response.json() == {
        "detail": f"{missing_resource} {missing_id} not found"
    }
    assert (
        db_connection.scalar(select(func.count()).select_from(PreviousQuestion)) == 0
    )


def test_create_previous_paper_returns_stable_conflict(client: TestClient) -> None:
    exam_id = _create_exam(client)
    source_id = _create_source(client)
    _create_paper(client, exam_id, source_id)

    response = client.post(
        "/api/v1/previous-papers",
        json={
            "exam_id": exam_id,
            "source_id": source_id,
            "year": 2024,
            "label": "Paper I",
        },
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": (
            f"PreviousPaper label 'Paper I' already exists for Exam {exam_id} "
            "in year 2024"
        )
    }


def test_create_previous_question_returns_stable_position_conflict(
    client: TestClient,
) -> None:
    exam_id = _create_exam(client)
    source_id = _create_source(client)
    topic_id = _create_topic(client)
    paper = _create_paper(client, exam_id, source_id)
    request = {
        "previous_paper_id": paper["id"],
        "topic_id": topic_id,
        "position": 0,
        "question_text": "First occurrence",
    }
    assert client.post("/api/v1/previous-questions", json=request).status_code == 201
    request["question_text"] = "Conflicting occurrence"

    response = client.post("/api/v1/previous-questions", json=request)

    assert response.status_code == 409
    assert response.json() == {
        "detail": (
            f"PreviousQuestion position 0 already exists for PreviousPaper {paper['id']}"
        )
    }


@pytest.mark.parametrize(
    ("endpoint", "payload"),
    [
        (
            "/api/v1/previous-papers",
            {"exam_id": 1, "source_id": 1, "year": 0, "label": "Invalid"},
        ),
        (
            "/api/v1/previous-questions",
            {
                "previous_paper_id": 1,
                "topic_id": 1,
                "position": -1,
                "question_text": "Invalid position",
            },
        ),
        (
            "/api/v1/previous-questions",
            {
                "previous_paper_id": 1,
                "topic_id": 1,
                "position": 0,
                "question_text": "   ",
            },
        ),
    ],
)
def test_previous_paper_inputs_return_422(
    client: TestClient,
    endpoint: str,
    payload: dict,
) -> None:
    response = client.post(endpoint, json=payload)

    assert response.status_code == 422


def test_previous_paper_database_constraints_are_enforced(
    client: TestClient,
    db_connection: Connection,
) -> None:
    exam_id = _create_exam(client)
    source_id = _create_source(client)
    topic_id = _create_topic(client)
    paper = _create_paper(client, exam_id, source_id)

    invalid_rows = [
        PreviousPaper.__table__.insert().values(
            exam_id=exam_id,
            source_id=source_id,
            year=0,
            label="Invalid year",
        ),
        PreviousQuestion.__table__.insert().values(
            previous_paper_id=paper["id"],
            topic_id=topic_id,
            position=-1,
            question_text="Invalid position",
        ),
        PreviousQuestion.__table__.insert().values(
            previous_paper_id=paper["id"],
            topic_id=topic_id,
            position=1,
            question_text="   ",
        ),
    ]
    for statement in invalid_rows:
        savepoint = db_connection.begin_nested()
        with pytest.raises(IntegrityError):
            db_connection.execute(statement)
        savepoint.rollback()


@pytest.mark.parametrize("model", [Exam, Source, PreviousPaper, Topic])
def test_previous_question_provenance_restricts_parent_deletion(
    client: TestClient,
    db_connection: Connection,
    model: type[Exam] | type[Source] | type[PreviousPaper] | type[Topic],
) -> None:
    exam_id = _create_exam(client)
    source_id = _create_source(client)
    topic_id = _create_topic(client)
    paper = _create_paper(client, exam_id, source_id)
    question_response = client.post(
        "/api/v1/previous-questions",
        json={
            "previous_paper_id": paper["id"],
            "topic_id": topic_id,
            "position": 0,
            "question_text": "Protected occurrence",
        },
    )
    assert question_response.status_code == 201
    target_id = {
        Exam: exam_id,
        Source: source_id,
        PreviousPaper: paper["id"],
        Topic: topic_id,
    }[model]

    savepoint = db_connection.begin_nested()
    with pytest.raises(IntegrityError):
        db_connection.execute(delete(model).where(model.id == target_id))
    savepoint.rollback()
