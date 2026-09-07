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
    NoteDraftClaim,
    QuestionBankItem,
    Verification,
)


@pytest.fixture
def db_connection() -> Generator[Connection, None, None]:
    database_name = engine.url.database or ""
    if not database_name.endswith("_test"):
        pytest.fail("Released NoteDraft tests require a dedicated *_test database")
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


def _foundation(client: TestClient, suffix: str) -> tuple[int, int, int]:
    exam = _post(
        client,
        "/api/v1/exams",
        {"code": f"NR-{suffix}", "name": f"Released Note Exam {suffix}"},
    )
    source = _post(
        client,
        "/api/v1/sources",
        {
            "title": f"Released Note Syllabus {suffix}",
            "source_type": "official",
            "authority_tier": 1,
            "location": f"https://example.gov/nr-{suffix}",
            "license_status": "UNKNOWN",
        },
    )
    topic = _post(client, "/api/v1/topics", {"name": f"Released Note Topic {suffix}"})
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
    return content_version["id"], topic["id"], syllabus["id"]


def _approved_claim(client: TestClient, topic_id: int, suffix: str) -> int:
    claim = _post(
        client,
        "/api/v1/claims",
        {"statement": f"Released note fact {suffix}.", "topic_id": topic_id},
    )
    approval = client.post(
        f"/api/v1/claims/{claim['id']}/approval",
        json={"approval_status": "APPROVED"},
    )
    assert approval.status_code == 200
    return claim["id"]


def _create_draft(
    client: TestClient,
    topic_id: int,
    content_version_id: int,
) -> dict:
    return _post(
        client,
        f"/api/v1/topics/{topic_id}/note-drafts",
        {"content_version_id": content_version_id},
    )


def _approve_draft(client: TestClient, draft_id: int, note: str | None = None) -> dict:
    response = client.post(
        f"/api/v1/note-drafts/{draft_id}/approval",
        json={"approval_status": "APPROVED", "reviewer_note": note},
    )
    assert response.status_code == 200
    return response.json()


def _release_draft(client: TestClient, draft_id: int, note: str | None = None) -> dict:
    response = client.post(
        f"/api/v1/note-drafts/{draft_id}/release",
        json={"release_status": "RELEASED", "release_note": note},
    )
    assert response.status_code == 200
    return response.json()


def test_get_released_note_drafts_returns_empty_for_empty_and_ineligible_sets(
    client: TestClient,
) -> None:
    empty = client.get("/api/v1/note-drafts/released")
    assert empty.status_code == 200
    assert empty.json() == []

    content_version_id, topic_id, _ = _foundation(client, "empty")
    _approved_claim(client, topic_id, "empty")
    draft_unreleased = _create_draft(client, topic_id, content_version_id)
    approved_unreleased = _create_draft(client, topic_id, content_version_id)
    withdrawn = _create_draft(client, topic_id, content_version_id)
    _approve_draft(client, approved_unreleased["id"])
    _approve_draft(client, withdrawn["id"])
    _release_draft(client, withdrawn["id"])
    withdrawal = client.post(
        f"/api/v1/note-drafts/{withdrawn['id']}/release",
        json={"release_status": "WITHDRAWN"},
    )
    assert withdrawal.status_code == 200
    assert draft_unreleased["approval_status"] == "DRAFT"

    no_current_release = client.get("/api/v1/note-drafts/released")
    assert no_current_release.status_code == 200
    assert no_current_release.json() == []


def test_get_released_note_drafts_filters_orders_and_preserves_snapshots(
    client: TestClient,
    db_connection: Connection,
) -> None:
    content_version_id, topic_id, syllabus_version_id = _foundation(client, "list")
    first_claim_id = _approved_claim(client, topic_id, "first")
    second_claim_id = _approved_claim(client, topic_id, "second")

    first = _create_draft(client, topic_id, content_version_id)
    draft_unreleased = _create_draft(client, topic_id, content_version_id)
    approved_unreleased = _create_draft(client, topic_id, content_version_id)
    withdrawn = _create_draft(client, topic_id, content_version_id)
    second = _create_draft(client, topic_id, content_version_id)

    first_approved = _approve_draft(client, first["id"], "First review")
    first_released = _release_draft(client, first["id"], "First release")
    _approve_draft(client, approved_unreleased["id"], "Unreleased review")
    _approve_draft(client, withdrawn["id"], "Withdrawn review")
    _release_draft(client, withdrawn["id"], "Temporary release")
    withdrawn_response = client.post(
        f"/api/v1/note-drafts/{withdrawn['id']}/release",
        json={"release_status": "WITHDRAWN", "release_note": "Withdrawn"},
    )
    assert withdrawn_response.status_code == 200
    second_approved = _approve_draft(client, second["id"], "Second review")

    source = _post(
        client,
        "/api/v1/sources",
        {
            "title": "Released-note verification source",
            "source_type": "official",
            "authority_tier": 1,
            "location": "https://example.gov/released-note-verification",
            "license_status": "UNKNOWN",
        },
    )
    evidence = _post(
        client,
        "/api/v1/evidence",
        {"source_id": source["id"], "content": "Stored verification evidence."},
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
    question = _post(
        client,
        "/api/v1/question-bank-items",
        {
            "content_version_id": content_version_id,
            "question_text": "Which stored fact grounds this released note?",
            "explanation": "The ordered Claims provide the grounding.",
            "difficulty": "EASY",
            "claim_ids": [first_claim_id],
            "options": ["The stored fact", "An unrelated fact"],
            "correct_option_position": 0,
        },
    )
    question_approval = client.post(
        f"/api/v1/question-bank-items/{question['id']}/approval",
        json={"approval_status": "APPROVED"},
    )
    question_release = client.post(
        f"/api/v1/question-bank-items/{question['id']}/release",
        json={"release_status": "RELEASED"},
    )
    priority = client.get(
        f"/api/v1/syllabus-versions/{syllabus_version_id}/topics/{topic_id}/priority"
    )
    assert verification["claim"]["id"] == first_claim_id
    assert question_approval.status_code == 200
    assert question_release.status_code == 200
    assert priority.status_code == 200

    claim_reset = client.post(
        f"/api/v1/claims/{second_claim_id}/approval",
        json={"approval_status": "REJECTED"},
    )
    assert claim_reset.status_code == 200
    second_released = _release_draft(client, second["id"], "Second release")

    draft_ids = [
        first["id"],
        draft_unreleased["id"],
        approved_unreleased["id"],
        withdrawn["id"],
        second["id"],
    ]
    snapshots_before = {
        draft_id: client.get(f"/api/v1/note-drafts/{draft_id}").json()
        for draft_id in draft_ids
    }
    counts_before = (
        db_connection.scalar(select(func.count()).select_from(NoteDraft)),
        db_connection.scalar(select(func.count()).select_from(NoteDraftClaim)),
        db_connection.scalar(select(func.count()).select_from(Claim)),
        db_connection.scalar(select(func.count()).select_from(Verification)),
        db_connection.scalar(select(func.count()).select_from(QuestionBankItem)),
    )

    response = client.get("/api/v1/note-drafts/released")

    counts_after = (
        db_connection.scalar(select(func.count()).select_from(NoteDraft)),
        db_connection.scalar(select(func.count()).select_from(NoteDraftClaim)),
        db_connection.scalar(select(func.count()).select_from(Claim)),
        db_connection.scalar(select(func.count()).select_from(Verification)),
        db_connection.scalar(select(func.count()).select_from(QuestionBankItem)),
    )
    snapshots_after = {
        draft_id: client.get(f"/api/v1/note-drafts/{draft_id}").json()
        for draft_id in draft_ids
    }

    assert response.status_code == 200
    assert response.json() == [first_released, second_released]
    assert [draft["id"] for draft in response.json()] == sorted(
        [first["id"], second["id"]]
    )
    assert response.json()[0]["topic_id"] == topic_id
    assert response.json()[0]["topic_name"] == "Released Note Topic list"
    assert response.json()[0]["content_version_id"] == content_version_id
    assert response.json()[0]["created_at"] == first["created_at"]
    assert response.json()[0]["claim_ids"] == [first_claim_id, second_claim_id]
    assert response.json()[0]["markdown"] == first["markdown"]
    assert response.json()[0]["approval_status"] == "APPROVED"
    assert response.json()[0]["approval_decided_at"] == first_approved[
        "approval_decided_at"
    ]
    assert response.json()[0]["reviewer_note"] == "First review"
    assert response.json()[0]["release_status"] == "RELEASED"
    assert response.json()[0]["released_at"] == first_released["released_at"]
    assert response.json()[0]["withdrawn_at"] is None
    assert response.json()[0]["release_note"] == "First release"
    returned_ids = {draft["id"] for draft in response.json()}
    assert draft_unreleased["id"] not in returned_ids
    assert approved_unreleased["id"] not in returned_ids
    assert withdrawn["id"] not in returned_ids
    assert snapshots_after == snapshots_before
    assert counts_after == counts_before

    approved_response = client.get("/api/v1/note-drafts/approved")
    approved_ids = {draft["id"] for draft in approved_response.json()}
    assert approved_response.status_code == 200
    assert first["id"] in approved_ids
    assert approved_unreleased["id"] in approved_ids
    assert withdrawn["id"] in approved_ids
    assert second["id"] in approved_ids
    assert draft_unreleased["id"] not in approved_ids
    assert second_approved["content_version_id"] == content_version_id
