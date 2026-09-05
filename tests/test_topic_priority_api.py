from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from app.core.database import engine, get_db
from app.main import app
from app.models import PreviousPaper, PreviousQuestion, SyllabusVersion, Topic


@pytest.fixture
def db_connection() -> Generator[Connection, None, None]:
    database_name = engine.url.database or ""
    if not database_name.endswith("_test"):
        pytest.fail("Topic-priority tests require a dedicated *_test database")
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


def _setup(
    client: TestClient,
    *,
    covered: bool = True,
    suffix: str = "A",
) -> tuple[int, int, int, int]:
    exam = _post(client, "/api/v1/exams", {"code": f"EX-{suffix}", "name": f"Exam {suffix}"})
    source = _post(
        client,
        "/api/v1/sources",
        {
            "title": f"Source {suffix}",
            "source_type": "official",
            "authority_tier": 1,
            "location": f"https://example.gov/{suffix}",
            "license_status": "UNKNOWN",
        },
    )
    topic = _post(client, "/api/v1/topics", {"name": f"Topic {suffix}"})
    syllabus_topic = topic
    if not covered:
        syllabus_topic = _post(
            client,
            "/api/v1/topics",
            {"name": f"Different Topic {suffix}"},
        )
    syllabus = _post(
        client,
        "/api/v1/syllabus-versions",
        {
            "exam_id": exam["id"],
            "source_id": source["id"],
            "label": "Version 1",
            "topic_ids": [syllabus_topic["id"]],
        },
    )
    return exam["id"], source["id"], topic["id"], syllabus["id"]


def _paper(client: TestClient, exam_id: int, source_id: int, year: int, label: str) -> int:
    return _post(
        client,
        "/api/v1/previous-papers",
        {"exam_id": exam_id, "source_id": source_id, "year": year, "label": label},
    )["id"]


def _question(client: TestClient, paper_id: int, topic_id: int, position: int) -> None:
    _post(
        client,
        "/api/v1/previous-questions",
        {
            "previous_paper_id": paper_id,
            "topic_id": topic_id,
            "position": position,
            "question_text": f"Question {paper_id}-{position}",
        },
    )


def _priority(client: TestClient, syllabus_id: int, topic_id: int):
    return client.get(
        f"/api/v1/syllabus-versions/{syllabus_id}/topics/{topic_id}/priority"
    )


def test_priority_medium_with_no_previous_paper_data_exact_response(
    client: TestClient,
) -> None:
    exam_id, _, topic_id, syllabus_id = _setup(client)

    response = _priority(client, syllabus_id, topic_id)

    assert response.status_code == 200
    assert response.json() == {
        "syllabus_version_id": syllabus_id,
        "exam_id": exam_id,
        "topic_id": topic_id,
        "syllabus_covered": True,
        "exam_paper_count": 0,
        "matched_question_count": 0,
        "matched_paper_count": 0,
        "matched_years": [],
        "priority_band": "MEDIUM",
        "rule_version": "topic-priority-v1",
        "reason_codes": ["DIRECT_SYLLABUS_COVERAGE", "NO_PREVIOUS_PAPER_DATA"],
    }


def test_priority_medium_distinguishes_papers_with_no_match(client: TestClient) -> None:
    exam_id, source_id, topic_id, syllabus_id = _setup(client)
    _paper(client, exam_id, source_id, 2024, "Paper I")

    response = _priority(client, syllabus_id, topic_id)

    assert response.json()["priority_band"] == "MEDIUM"
    assert response.json()["exam_paper_count"] == 1
    assert response.json()["reason_codes"] == [
        "DIRECT_SYLLABUS_COVERAGE",
        "NO_RECORDED_PREVIOUS_OCCURRENCE",
    ]


def test_priority_medium_counts_multiple_questions_in_one_paper_once(
    client: TestClient,
) -> None:
    exam_id, source_id, topic_id, syllabus_id = _setup(client)
    paper_id = _paper(client, exam_id, source_id, 2023, "Paper I")
    _question(client, paper_id, topic_id, 0)
    _question(client, paper_id, topic_id, 1)

    body = _priority(client, syllabus_id, topic_id).json()

    assert body["priority_band"] == "MEDIUM"
    assert body["matched_question_count"] == 2
    assert body["matched_paper_count"] == 1
    assert body["matched_years"] == [2023]
    assert body["reason_codes"] == [
        "DIRECT_SYLLABUS_COVERAGE",
        "APPEARED_IN_PREVIOUS_PAPER",
    ]


def test_priority_high_uses_distinct_exam_papers_and_sorted_unique_years(
    client: TestClient,
) -> None:
    exam_id, source_id, topic_id, syllabus_id = _setup(client)
    for year, label in [(2024, "Paper II"), (2022, "Paper I"), (2022, "Paper II")]:
        paper_id = _paper(client, exam_id, source_id, year, label)
        _question(client, paper_id, topic_id, 0)
    other_exam_id, other_source_id, _, _ = _setup(client, suffix="B")
    other_paper_id = _paper(client, other_exam_id, other_source_id, 2025, "Paper I")
    _question(client, other_paper_id, topic_id, 0)

    body = _priority(client, syllabus_id, topic_id).json()

    assert body["priority_band"] == "HIGH"
    assert body["exam_paper_count"] == 3
    assert body["matched_question_count"] == 3
    assert body["matched_paper_count"] == 3
    assert body["matched_years"] == [2022, 2024]
    assert body["reason_codes"] == [
        "DIRECT_SYLLABUS_COVERAGE",
        "REPEATED_IN_PREVIOUS_PAPERS",
    ]


def test_priority_low_when_topic_is_absent_from_selected_syllabus(
    client: TestClient,
) -> None:
    exam_id, source_id, topic_id, syllabus_id = _setup(client, covered=False)
    for year in [2023, 2024]:
        paper_id = _paper(client, exam_id, source_id, year, f"Paper {year}")
        _question(client, paper_id, topic_id, 0)

    body = _priority(client, syllabus_id, topic_id).json()

    assert body["priority_band"] == "LOW"
    assert body["syllabus_covered"] is False
    assert body["matched_paper_count"] == 2
    assert body["reason_codes"] == [
        "NOT_IN_SELECTED_SYLLABUS_VERSION",
        "REPEATED_IN_PREVIOUS_PAPERS",
    ]


@pytest.mark.parametrize(
    ("missing", "detail"),
    [("syllabus", "SyllabusVersion 999991 not found"), ("topic", "Topic 999992 not found")],
)
def test_priority_returns_established_404_for_missing_resources(
    client: TestClient,
    missing: str,
    detail: str,
) -> None:
    _, _, topic_id, syllabus_id = _setup(client)
    if missing == "syllabus":
        syllabus_id = 999991
    else:
        topic_id = 999992

    response = _priority(client, syllabus_id, topic_id)

    assert response.status_code == 404
    assert response.json() == {"detail": detail}


def test_priority_is_read_only(client: TestClient, db_connection: Connection) -> None:
    _, _, topic_id, syllabus_id = _setup(client)
    before = {
        "syllabus": db_connection.scalar(select(func.count()).select_from(SyllabusVersion)),
        "topics": db_connection.scalar(select(func.count()).select_from(Topic)),
        "papers": db_connection.scalar(select(func.count()).select_from(PreviousPaper)),
        "questions": db_connection.scalar(select(func.count()).select_from(PreviousQuestion)),
    }

    assert _priority(client, syllabus_id, topic_id).status_code == 200

    after = {
        "syllabus": db_connection.scalar(select(func.count()).select_from(SyllabusVersion)),
        "topics": db_connection.scalar(select(func.count()).select_from(Topic)),
        "papers": db_connection.scalar(select(func.count()).select_from(PreviousPaper)),
        "questions": db_connection.scalar(select(func.count()).select_from(PreviousQuestion)),
    }
    assert after == before
