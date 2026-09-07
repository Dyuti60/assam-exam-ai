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
    ContentVersion,
    Evidence,
    NoteDraft,
    NoteDraftClaim,
    PreviousPaper,
    PreviousQuestion,
    QuestionBankItem,
    QuestionBankItemClaim,
    QuestionBankOption,
    Source,
    Verification,
)


@pytest.fixture
def db_connection() -> Generator[Connection, None, None]:
    database_name = engine.url.database or ""
    if not database_name.endswith("_test"):
        pytest.fail("ContentVersion manifest tests require a dedicated *_test database")
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


def _foundation(client: TestClient, suffix: str) -> dict[str, dict]:
    exam = _post(
        client,
        "/api/v1/exams",
        {"code": f"CM-{suffix}", "name": f"Content Manifest Exam {suffix}"},
    )
    syllabus_source = _post(
        client,
        "/api/v1/sources",
        {
            "title": f"Content Manifest Syllabus {suffix}",
            "source_type": "official",
            "authority_tier": 1,
            "location": f"https://example.gov/cm-{suffix}",
            "license_status": "UNKNOWN",
        },
    )
    topic = _post(
        client,
        "/api/v1/topics",
        {"name": f"Content Manifest Topic {suffix}"},
    )
    syllabus = _post(
        client,
        "/api/v1/syllabus-versions",
        {
            "exam_id": exam["id"],
            "source_id": syllabus_source["id"],
            "label": "Version 1",
            "topic_ids": [topic["id"]],
        },
    )
    first_version = _post(
        client,
        "/api/v1/content-versions",
        {
            "syllabus_version_id": syllabus["id"],
            "topic_id": topic["id"],
            "version": 1,
        },
    )
    second_version = _post(
        client,
        "/api/v1/content-versions",
        {
            "syllabus_version_id": syllabus["id"],
            "topic_id": topic["id"],
            "version": 2,
        },
    )
    return {
        "exam": exam,
        "syllabus_source": syllabus_source,
        "topic": topic,
        "syllabus": syllabus,
        "first_version": first_version,
        "second_version": second_version,
    }


def _approved_claim(client: TestClient, topic_id: int, suffix: str) -> int:
    claim = _post(
        client,
        "/api/v1/claims",
        {"statement": f"Manifest grounded fact {suffix}.", "topic_id": topic_id},
    )
    response = client.post(
        f"/api/v1/claims/{claim['id']}/approval",
        json={"approval_status": "APPROVED"},
    )
    assert response.status_code == 200
    return claim["id"]


def _create_note_draft(
    client: TestClient,
    topic_id: int,
    content_version_id: int,
) -> dict:
    return _post(
        client,
        f"/api/v1/topics/{topic_id}/note-drafts",
        {"content_version_id": content_version_id},
    )


def _approve_note_draft(client: TestClient, draft_id: int, note: str) -> dict:
    response = client.post(
        f"/api/v1/note-drafts/{draft_id}/approval",
        json={"approval_status": "APPROVED", "reviewer_note": note},
    )
    assert response.status_code == 200
    return response.json()


def _release_note_draft(client: TestClient, draft_id: int, note: str) -> dict:
    response = client.post(
        f"/api/v1/note-drafts/{draft_id}/release",
        json={"release_status": "RELEASED", "release_note": note},
    )
    assert response.status_code == 200
    return response.json()


def _create_question_bank_item(
    client: TestClient,
    content_version_id: int,
    claim_ids: list[int],
    suffix: str,
) -> dict:
    return _post(
        client,
        "/api/v1/question-bank-items",
        {
            "content_version_id": content_version_id,
            "question_text": f"Manifest question {suffix}?",
            "explanation": f"Manifest explanation {suffix}.",
            "difficulty": "MEDIUM",
            "claim_ids": claim_ids,
            "options": [f"Option A {suffix}", f"Option B {suffix}"],
            "correct_option_position": 1,
        },
    )


def _approve_question_bank_item(client: TestClient, item_id: int, note: str) -> dict:
    response = client.post(
        f"/api/v1/question-bank-items/{item_id}/approval",
        json={"approval_status": "APPROVED", "reviewer_note": note},
    )
    assert response.status_code == 200
    return response.json()


def _release_question_bank_item(client: TestClient, item_id: int, note: str) -> dict:
    response = client.post(
        f"/api/v1/question-bank-items/{item_id}/release",
        json={"release_status": "RELEASED", "release_note": note},
    )
    assert response.status_code == 200
    return response.json()


def test_released_assets_manifest_missing_and_empty_content_version(
    client: TestClient,
) -> None:
    missing = client.get("/api/v1/content-versions/999999/released-assets")
    assert missing.status_code == 404
    assert missing.json() == {"detail": "ContentVersion 999999 not found"}

    foundation = _foundation(client, "empty")
    content_version = foundation["first_version"]
    response = client.get(
        f"/api/v1/content-versions/{content_version['id']}/released-assets"
    )

    assert response.status_code == 200
    assert response.json() == {
        "content_version": content_version,
        "note_drafts": [],
        "question_bank_items": [],
    }
    retrieval = client.get(f"/api/v1/content-versions/{content_version['id']}")
    assert retrieval.status_code == 200
    assert retrieval.json() == content_version


def test_released_assets_manifest_excludes_only_ineligible_assets(
    client: TestClient,
) -> None:
    foundation = _foundation(client, "ineligible")
    content_version = foundation["first_version"]
    topic_id = foundation["topic"]["id"]
    claim_id = _approved_claim(client, topic_id, "ineligible")

    approved_unreleased_draft = _create_note_draft(
        client, topic_id, content_version["id"]
    )
    withdrawn_draft = _create_note_draft(client, topic_id, content_version["id"])
    _approve_note_draft(client, approved_unreleased_draft["id"], "Unreleased")
    _approve_note_draft(client, withdrawn_draft["id"], "Withdrawn")
    _release_note_draft(client, withdrawn_draft["id"], "Temporary")
    withdrawn_draft_response = client.post(
        f"/api/v1/note-drafts/{withdrawn_draft['id']}/release",
        json={"release_status": "WITHDRAWN", "release_note": "Withdrawn"},
    )
    assert withdrawn_draft_response.status_code == 200

    approved_unreleased_item = _create_question_bank_item(
        client, content_version["id"], [claim_id], "unreleased"
    )
    withdrawn_item = _create_question_bank_item(
        client, content_version["id"], [claim_id], "withdrawn"
    )
    _approve_question_bank_item(client, approved_unreleased_item["id"], "Unreleased")
    _approve_question_bank_item(client, withdrawn_item["id"], "Withdrawn")
    _release_question_bank_item(client, withdrawn_item["id"], "Temporary")
    withdrawn_item_response = client.post(
        f"/api/v1/question-bank-items/{withdrawn_item['id']}/release",
        json={"release_status": "WITHDRAWN", "release_note": "Withdrawn"},
    )
    assert withdrawn_item_response.status_code == 200

    response = client.get(
        f"/api/v1/content-versions/{content_version['id']}/released-assets"
    )
    assert response.status_code == 200
    assert response.json() == {
        "content_version": content_version,
        "note_drafts": [],
        "question_bank_items": [],
    }

    approved_drafts = client.get("/api/v1/note-drafts/approved").json()
    approved_items = client.get("/api/v1/question-bank-items/approved").json()
    assert {draft["id"] for draft in approved_drafts} == {
        approved_unreleased_draft["id"],
        withdrawn_draft["id"],
    }
    assert {item["id"] for item in approved_items} == {
        approved_unreleased_item["id"],
        withdrawn_item["id"],
    }


def test_released_assets_manifest_filters_orders_preserves_and_does_not_mutate(
    client: TestClient,
    db_connection: Connection,
) -> None:
    foundation = _foundation(client, "complete")
    first_version = foundation["first_version"]
    second_version = foundation["second_version"]
    topic_id = foundation["topic"]["id"]
    first_claim_id = _approved_claim(client, topic_id, "first")
    second_claim_id = _approved_claim(client, topic_id, "second")

    first_draft = _create_note_draft(client, topic_id, first_version["id"])
    second_draft = _create_note_draft(client, topic_id, first_version["id"])
    other_version_draft = _create_note_draft(client, topic_id, second_version["id"])
    first_draft_approval = _approve_note_draft(
        client, first_draft["id"], "First draft review"
    )
    first_draft_release = _release_note_draft(
        client, first_draft["id"], "First draft release"
    )
    _approve_note_draft(client, second_draft["id"], "Second draft review")
    second_draft_release = _release_note_draft(
        client, second_draft["id"], "Second draft release"
    )
    _approve_note_draft(client, other_version_draft["id"], "Other draft review")
    other_version_draft_release = _release_note_draft(
        client, other_version_draft["id"], "Other draft release"
    )

    first_item = _create_question_bank_item(
        client,
        first_version["id"],
        [second_claim_id, first_claim_id],
        "first",
    )
    second_item = _create_question_bank_item(
        client, first_version["id"], [first_claim_id], "second"
    )
    other_version_item = _create_question_bank_item(
        client, second_version["id"], [first_claim_id], "other-version"
    )
    first_item_approval = _approve_question_bank_item(
        client, first_item["id"], "First item review"
    )
    first_item_release = _release_question_bank_item(
        client, first_item["id"], "First item release"
    )
    _approve_question_bank_item(client, second_item["id"], "Second item review")
    second_item_release = _release_question_bank_item(
        client, second_item["id"], "Second item release"
    )
    _approve_question_bank_item(
        client, other_version_item["id"], "Other item review"
    )
    other_version_item_release = _release_question_bank_item(
        client, other_version_item["id"], "Other item release"
    )

    unrelated_draft = _create_note_draft(client, topic_id, first_version["id"])
    unrelated_item = _create_question_bank_item(
        client, first_version["id"], [first_claim_id], "unrelated-state"
    )
    evidence_source = _post(
        client,
        "/api/v1/sources",
        {
            "title": "Manifest verification source",
            "source_type": "official",
            "authority_tier": 1,
            "location": "https://example.gov/manifest-verification",
            "license_status": "UNKNOWN",
        },
    )
    evidence = _post(
        client,
        "/api/v1/evidence",
        {"source_id": evidence_source["id"], "content": "Manifest evidence."},
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
    paper = _post(
        client,
        "/api/v1/previous-papers",
        {
            "exam_id": foundation["exam"]["id"],
            "source_id": foundation["syllabus_source"]["id"],
            "year": 2025,
            "label": "Manifest paper",
        },
    )
    previous_question = _post(
        client,
        "/api/v1/previous-questions",
        {
            "previous_paper_id": paper["id"],
            "topic_id": topic_id,
            "position": 0,
            "question_text": "Historical manifest question?",
        },
    )
    priority = client.get(
        "/api/v1/syllabus-versions/"
        f"{foundation['syllabus']['id']}/topics/{topic_id}/priority"
    )
    assert verification["claim"]["id"] == first_claim_id
    assert previous_question["previous_paper_id"] == paper["id"]
    assert priority.status_code == 200

    claim_reset = client.post(
        f"/api/v1/claims/{second_claim_id}/approval",
        json={"approval_status": "REJECTED"},
    )
    assert claim_reset.status_code == 200

    draft_ids = [first_draft["id"], second_draft["id"], other_version_draft["id"]]
    item_ids = [first_item["id"], second_item["id"], other_version_item["id"]]
    snapshots_before = {
        "drafts": {
            draft_id: client.get(f"/api/v1/note-drafts/{draft_id}").json()
            for draft_id in draft_ids
        },
        "items": {
            item_id: client.get(f"/api/v1/question-bank-items/{item_id}").json()
            for item_id in item_ids
        },
    }
    counts_before = (
        db_connection.scalar(select(func.count()).select_from(ContentVersion)),
        db_connection.scalar(select(func.count()).select_from(NoteDraft)),
        db_connection.scalar(select(func.count()).select_from(NoteDraftClaim)),
        db_connection.scalar(select(func.count()).select_from(QuestionBankItem)),
        db_connection.scalar(select(func.count()).select_from(QuestionBankItemClaim)),
        db_connection.scalar(select(func.count()).select_from(QuestionBankOption)),
        db_connection.scalar(select(func.count()).select_from(Claim)),
        db_connection.scalar(select(func.count()).select_from(Verification)),
        db_connection.scalar(select(func.count()).select_from(Evidence)),
        db_connection.scalar(select(func.count()).select_from(Source)),
        db_connection.scalar(select(func.count()).select_from(PreviousPaper)),
        db_connection.scalar(select(func.count()).select_from(PreviousQuestion)),
    )

    response = client.get(
        f"/api/v1/content-versions/{first_version['id']}/released-assets"
    )

    counts_after = (
        db_connection.scalar(select(func.count()).select_from(ContentVersion)),
        db_connection.scalar(select(func.count()).select_from(NoteDraft)),
        db_connection.scalar(select(func.count()).select_from(NoteDraftClaim)),
        db_connection.scalar(select(func.count()).select_from(QuestionBankItem)),
        db_connection.scalar(select(func.count()).select_from(QuestionBankItemClaim)),
        db_connection.scalar(select(func.count()).select_from(QuestionBankOption)),
        db_connection.scalar(select(func.count()).select_from(Claim)),
        db_connection.scalar(select(func.count()).select_from(Verification)),
        db_connection.scalar(select(func.count()).select_from(Evidence)),
        db_connection.scalar(select(func.count()).select_from(Source)),
        db_connection.scalar(select(func.count()).select_from(PreviousPaper)),
        db_connection.scalar(select(func.count()).select_from(PreviousQuestion)),
    )
    snapshots_after = {
        "drafts": {
            draft_id: client.get(f"/api/v1/note-drafts/{draft_id}").json()
            for draft_id in draft_ids
        },
        "items": {
            item_id: client.get(f"/api/v1/question-bank-items/{item_id}").json()
            for item_id in item_ids
        },
    }

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "content_version": first_version,
        "note_drafts": [first_draft_release, second_draft_release],
        "question_bank_items": [first_item_release, second_item_release],
    }
    assert [draft["id"] for draft in body["note_drafts"]] == sorted(
        [first_draft["id"], second_draft["id"]]
    )
    assert [item["id"] for item in body["question_bank_items"]] == sorted(
        [first_item["id"], second_item["id"]]
    )

    returned_draft = body["note_drafts"][0]
    assert returned_draft["topic_id"] == topic_id
    assert returned_draft["topic_name"] == "Content Manifest Topic complete"
    assert returned_draft["content_version_id"] == first_version["id"]
    assert returned_draft["markdown"] == first_draft["markdown"]
    assert returned_draft["created_at"] == first_draft["created_at"]
    assert returned_draft["claim_ids"] == [first_claim_id, second_claim_id]
    assert returned_draft["approval_status"] == "APPROVED"
    assert returned_draft["approval_decided_at"] == first_draft_approval[
        "approval_decided_at"
    ]
    assert returned_draft["reviewer_note"] == "First draft review"
    assert returned_draft["release_status"] == "RELEASED"
    assert returned_draft["released_at"] == first_draft_release["released_at"]
    assert returned_draft["withdrawn_at"] is None
    assert returned_draft["release_note"] == "First draft release"

    returned_item = body["question_bank_items"][0]
    assert returned_item["content_version_id"] == first_version["id"]
    assert returned_item["question_text"] == "Manifest question first?"
    assert returned_item["explanation"] == "Manifest explanation first."
    assert returned_item["difficulty"] == "MEDIUM"
    assert returned_item["created_at"] == first_item["created_at"]
    assert returned_item["claim_ids"] == [second_claim_id, first_claim_id]
    assert returned_item["options"] == ["Option A first", "Option B first"]
    assert returned_item["correct_option_position"] == 1
    assert returned_item["approval_status"] == "APPROVED"
    assert returned_item["approval_decided_at"] == first_item_approval[
        "approval_decided_at"
    ]
    assert returned_item["reviewer_note"] == "First item review"
    assert returned_item["release_status"] == "RELEASED"
    assert returned_item["released_at"] == first_item_release["released_at"]
    assert returned_item["withdrawn_at"] is None
    assert returned_item["release_note"] == "First item release"

    assert unrelated_draft["id"] not in {d["id"] for d in body["note_drafts"]}
    assert unrelated_item["id"] not in {i["id"] for i in body["question_bank_items"]}
    assert other_version_draft_release["id"] not in {
        draft["id"] for draft in body["note_drafts"]
    }
    assert other_version_item_release["id"] not in {
        item["id"] for item in body["question_bank_items"]
    }
    assert snapshots_after == snapshots_before
    assert counts_after == counts_before

    global_released_drafts = client.get("/api/v1/note-drafts/released").json()
    global_released_items = client.get("/api/v1/question-bank-items/released").json()
    assert {draft["id"] for draft in global_released_drafts} == set(draft_ids)
    assert {item["id"] for item in global_released_items} == set(item_ids)
    assert {draft["id"] for draft in client.get("/api/v1/note-drafts/approved").json()} == set(
        draft_ids
    )
    assert {
        item["id"] for item in client.get("/api/v1/question-bank-items/approved").json()
    } == set(item_ids)
