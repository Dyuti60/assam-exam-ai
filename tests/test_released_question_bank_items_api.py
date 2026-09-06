from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from app.core.database import engine, get_db
from app.main import app
from app.models import (
    Claim,
    NoteDraft,
    QuestionBankItem,
    QuestionBankItemClaim,
    QuestionBankOption,
    Verification,
)


@pytest.fixture
def db_connection() -> Generator[Connection, None, None]:
    database_name = engine.url.database or ""
    if not database_name.endswith("_test"):
        pytest.fail("QuestionBankItem tests require a dedicated *_test database")
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


def _foundation(client: TestClient, suffix: str) -> tuple[int, int]:
    exam = _post(
        client,
        "/api/v1/exams",
        {"code": f"QR-{suffix}", "name": f"Released Question Exam {suffix}"},
    )
    source = _post(
        client,
        "/api/v1/sources",
        {
            "title": f"Released Question Syllabus {suffix}",
            "source_type": "official",
            "authority_tier": 1,
            "location": f"https://example.gov/qr-{suffix}",
            "license_status": "UNKNOWN",
        },
    )
    topic = _post(client, "/api/v1/topics", {"name": f"Released Topic {suffix}"})
    syllabus = _post(
        client,
        "/api/v1/syllabus-versions",
        {
            "exam_id": exam["id"],
            "source_id": source["id"],
            "label": "Version 1",
            "topic_ids": [topic["id"]],
        },
    )
    content_version = _post(
        client,
        "/api/v1/content-versions",
        {
            "syllabus_version_id": syllabus["id"],
            "topic_id": topic["id"],
            "version": 1,
        },
    )
    return content_version["id"], topic["id"]


def _claim(client: TestClient, topic_id: int, suffix: str) -> int:
    claim = _post(
        client,
        "/api/v1/claims",
        {"statement": f"Released grounded fact {suffix}", "topic_id": topic_id},
    )
    approval = client.post(
        f"/api/v1/claims/{claim['id']}/approval",
        json={"approval_status": "APPROVED"},
    )
    assert approval.status_code == 200
    return claim["id"]


def _item_payload(content_version_id: int, claim_ids: list[int]) -> dict:
    return {
        "content_version_id": content_version_id,
        "question_text": "Which released statement is supported?",
        "explanation": "The stored approved Claims provide the grounding.",
        "difficulty": "MEDIUM",
        "claim_ids": claim_ids,
        "options": ["First option", "Second option"],
        "correct_option_position": 1,
    }


def test_get_released_items_returns_empty_for_empty_and_ineligible_sets(
    client: TestClient,
) -> None:
    empty = client.get("/api/v1/question-bank-items/released")
    assert empty.status_code == 200
    assert empty.json() == []

    content_version_id, topic_id = _foundation(client, "empty")
    claim_id = _claim(client, topic_id, "empty")
    item = _post(
        client,
        "/api/v1/question-bank-items",
        _item_payload(content_version_id, [claim_id]),
    )
    approved = client.post(
        f"/api/v1/question-bank-items/{item['id']}/approval",
        json={"approval_status": "APPROVED"},
    )
    released = client.post(
        f"/api/v1/question-bank-items/{item['id']}/release",
        json={"release_status": "RELEASED"},
    )
    withdrawn = client.post(
        f"/api/v1/question-bank-items/{item['id']}/release",
        json={"release_status": "WITHDRAWN"},
    )
    assert approved.status_code == 200
    assert released.status_code == 200
    assert withdrawn.status_code == 200

    no_current_release = client.get("/api/v1/question-bank-items/released")
    assert no_current_release.status_code == 200
    assert no_current_release.json() == []


def test_get_released_items_filters_orders_and_preserves_stored_snapshots(
    client: TestClient,
    db_connection: Connection,
) -> None:
    content_version_id, topic_id = _foundation(client, "list")
    first_claim_id = _claim(client, topic_id, "list-first")
    second_claim_id = _claim(client, topic_id, "list-second")

    first = _post(
        client,
        "/api/v1/question-bank-items",
        {
            **_item_payload(content_version_id, [second_claim_id, first_claim_id]),
            "question_text": "First released candidate",
            "options": ["Released A", "Released B", "Released C"],
            "correct_option_position": 2,
        },
    )
    approved_unreleased = _post(
        client,
        "/api/v1/question-bank-items",
        _item_payload(content_version_id, [first_claim_id]),
    )
    withdrawn_item = _post(
        client,
        "/api/v1/question-bank-items",
        _item_payload(content_version_id, [first_claim_id]),
    )
    second = _post(
        client,
        "/api/v1/question-bank-items",
        _item_payload(content_version_id, [first_claim_id]),
    )
    externally_supported = _post(
        client,
        "/api/v1/question-bank-items",
        _item_payload(content_version_id, [first_claim_id]),
    )

    first_approved = client.post(
        f"/api/v1/question-bank-items/{first['id']}/approval",
        json={"approval_status": "APPROVED", "reviewer_note": "First review"},
    )
    first_released = client.post(
        f"/api/v1/question-bank-items/{first['id']}/release",
        json={"release_status": "RELEASED", "release_note": "First release"},
    )
    unreleased_approved = client.post(
        f"/api/v1/question-bank-items/{approved_unreleased['id']}/approval",
        json={"approval_status": "APPROVED"},
    )
    withdrawn_approved = client.post(
        f"/api/v1/question-bank-items/{withdrawn_item['id']}/approval",
        json={"approval_status": "APPROVED"},
    )
    withdrawn_released = client.post(
        f"/api/v1/question-bank-items/{withdrawn_item['id']}/release",
        json={"release_status": "RELEASED"},
    )
    withdrawn = client.post(
        f"/api/v1/question-bank-items/{withdrawn_item['id']}/release",
        json={"release_status": "WITHDRAWN"},
    )
    second_approved = client.post(
        f"/api/v1/question-bank-items/{second['id']}/approval",
        json={"approval_status": "APPROVED", "reviewer_note": "Second review"},
    )
    second_released = client.post(
        f"/api/v1/question-bank-items/{second['id']}/release",
        json={"release_status": "RELEASED", "release_note": "Second release"},
    )
    for decision in (
        first_approved,
        first_released,
        unreleased_approved,
        withdrawn_approved,
        withdrawn_released,
        withdrawn,
        second_approved,
        second_released,
    ):
        assert decision.status_code == 200

    source = _post(
        client,
        "/api/v1/sources",
        {
            "title": "Released-list verification source",
            "source_type": "official",
            "authority_tier": 1,
            "location": "https://example.gov/released-list-verification",
            "license_status": "UNKNOWN",
        },
    )
    evidence = _post(
        client,
        "/api/v1/evidence",
        {"source_id": source["id"], "content": "Stored verification evidence"},
    )
    verification = _post(
        client,
        "/api/v1/verifications",
        {
            "claim_id": first_claim_id,
            "verdict": "SUPPORTED",
            "confidence": 0.9,
            "evidence": [
                {
                    "evidence_id": evidence["id"],
                    "evidence_role": "SUPPORTS",
                    "position": 0,
                }
            ],
        },
    )
    note_draft = _post(
        client,
        f"/api/v1/topics/{topic_id}/note-drafts",
        {"content_version_id": content_version_id},
    )
    note_approved = client.post(
        f"/api/v1/note-drafts/{note_draft['id']}/approval",
        json={"approval_status": "APPROVED"},
    )
    claim_reset = client.post(
        f"/api/v1/claims/{second_claim_id}/approval",
        json={"approval_status": "DRAFT"},
    )
    assert verification["claim"]["id"] == first_claim_id
    assert note_approved.status_code == 200
    assert claim_reset.status_code == 200

    counts_before = (
        db_connection.scalar(select(func.count()).select_from(QuestionBankItem)),
        db_connection.scalar(select(func.count()).select_from(QuestionBankItemClaim)),
        db_connection.scalar(select(func.count()).select_from(QuestionBankOption)),
        db_connection.scalar(select(func.count()).select_from(Claim)),
        db_connection.scalar(select(func.count()).select_from(NoteDraft)),
        db_connection.scalar(select(func.count()).select_from(Verification)),
    )
    response = client.get("/api/v1/question-bank-items/released")
    counts_after = (
        db_connection.scalar(select(func.count()).select_from(QuestionBankItem)),
        db_connection.scalar(select(func.count()).select_from(QuestionBankItemClaim)),
        db_connection.scalar(select(func.count()).select_from(QuestionBankOption)),
        db_connection.scalar(select(func.count()).select_from(Claim)),
        db_connection.scalar(select(func.count()).select_from(NoteDraft)),
        db_connection.scalar(select(func.count()).select_from(Verification)),
    )

    assert response.status_code == 200
    assert response.json() == [first_released.json(), second_released.json()]
    assert [item["id"] for item in response.json()] == sorted(
        [first["id"], second["id"]]
    )
    assert response.json()[0]["claim_ids"] == [second_claim_id, first_claim_id]
    assert response.json()[0]["options"] == [
        "Released A",
        "Released B",
        "Released C",
    ]
    assert response.json()[0]["correct_option_position"] == 2
    assert response.json()[0]["approval_status"] == "APPROVED"
    assert response.json()[0]["approval_decided_at"] is not None
    assert response.json()[0]["reviewer_note"] == "First review"
    assert response.json()[0]["release_status"] == "RELEASED"
    assert response.json()[0]["released_at"] is not None
    assert response.json()[0]["withdrawn_at"] is None
    assert response.json()[0]["release_note"] == "First release"
    returned_ids = {item["id"] for item in response.json()}
    assert approved_unreleased["id"] not in returned_ids
    assert withdrawn_item["id"] not in returned_ids
    assert externally_supported["id"] not in returned_ids

    approved_response = client.get("/api/v1/question-bank-items/approved")
    approved_ids = {item["id"] for item in approved_response.json()}
    assert approved_response.status_code == 200
    assert approved_unreleased["id"] in approved_ids
    assert withdrawn_item["id"] in approved_ids
    assert first["id"] in approved_ids
    assert second["id"] in approved_ids
    assert counts_after == counts_before
