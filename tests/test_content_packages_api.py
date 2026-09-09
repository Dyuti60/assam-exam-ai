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
from app.models import (
    Claim,
    ContentPackage,
    ContentPackageNoteDraft,
    ContentPackageQuestionBankItem,
    ContentVersion,
    Evidence,
    NoteDraft,
    PreviousPaper,
    PreviousQuestion,
    QuestionBankItem,
    Verification,
)
from app.repositories import KnowledgeRepository


@pytest.fixture
def db_connection() -> Generator[Connection, None, None]:
    database_name = engine.url.database or ""
    if not database_name.endswith("_test"):
        pytest.fail("ContentPackage tests require a dedicated *_test database")
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
        {"code": f"CP-{suffix}", "name": f"Content Package Exam {suffix}"},
    )
    source = _post(
        client,
        "/api/v1/sources",
        {
            "title": f"Content Package Syllabus {suffix}",
            "source_type": "official",
            "authority_tier": 1,
            "location": f"https://example.gov/cp-{suffix}",
            "license_status": "UNKNOWN",
        },
    )
    topic = _post(
        client,
        "/api/v1/topics",
        {"name": f"Content Package Topic {suffix}"},
    )
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
        "source": source,
        "topic": topic,
        "syllabus": syllabus,
        "first_version": first_version,
        "second_version": second_version,
    }


def _approved_claim(client: TestClient, topic_id: int, suffix: str) -> int:
    claim = _post(
        client,
        "/api/v1/claims",
        {"statement": f"Package grounded fact {suffix}.", "topic_id": topic_id},
    )
    response = client.post(
        f"/api/v1/claims/{claim['id']}/approval",
        json={"approval_status": "APPROVED"},
    )
    assert response.status_code == 200
    return claim["id"]


def _create_draft(client: TestClient, topic_id: int, version_id: int) -> dict:
    return _post(
        client,
        f"/api/v1/topics/{topic_id}/note-drafts",
        {"content_version_id": version_id},
    )


def _approve_and_release_draft(client: TestClient, draft_id: int) -> dict:
    approval = client.post(
        f"/api/v1/note-drafts/{draft_id}/approval",
        json={"approval_status": "APPROVED", "reviewer_note": "Package review"},
    )
    assert approval.status_code == 200
    release = client.post(
        f"/api/v1/note-drafts/{draft_id}/release",
        json={"release_status": "RELEASED", "release_note": "Package release"},
    )
    assert release.status_code == 200
    return release.json()


def _create_item(
    client: TestClient,
    version_id: int,
    claim_ids: list[int],
    suffix: str,
) -> dict:
    return _post(
        client,
        "/api/v1/question-bank-items",
        {
            "content_version_id": version_id,
            "question_text": f"Package question {suffix}?",
            "explanation": f"Package explanation {suffix}.",
            "difficulty": "MEDIUM",
            "claim_ids": claim_ids,
            "options": [f"Option A {suffix}", f"Option B {suffix}"],
            "correct_option_position": 1,
        },
    )


def _approve_and_release_item(client: TestClient, item_id: int) -> dict:
    approval = client.post(
        f"/api/v1/question-bank-items/{item_id}/approval",
        json={"approval_status": "APPROVED", "reviewer_note": "Package review"},
    )
    assert approval.status_code == 200
    release = client.post(
        f"/api/v1/question-bank-items/{item_id}/release",
        json={"release_status": "RELEASED", "release_note": "Package release"},
    )
    assert release.status_code == 200
    return release.json()


def _create_package(client: TestClient, version_id: int) -> dict:
    response = client.post(
        f"/api/v1/content-versions/{version_id}/content-packages"
    )
    assert response.status_code == 201
    return response.json()


def _row_counts(connection: Connection) -> tuple[int, int, int]:
    return (
        connection.scalar(select(func.count()).select_from(ContentPackage)),
        connection.scalar(
            select(func.count()).select_from(ContentPackageNoteDraft)
        ),
        connection.scalar(
            select(func.count()).select_from(ContentPackageQuestionBankItem)
        ),
    )


def _content_snapshot_row_counts(connection: Connection) -> tuple[int, ...]:
    return tuple(
        connection.scalar(select(func.count()).select_from(model))
        for model in (
            ContentPackage,
            ContentPackageNoteDraft,
            ContentPackageQuestionBankItem,
            NoteDraft,
            QuestionBankItem,
            Claim,
            Evidence,
            Verification,
            PreviousPaper,
            PreviousQuestion,
        )
    )


def test_missing_and_empty_content_version_create_no_package(
    client: TestClient,
    db_connection: Connection,
) -> None:
    missing = client.post("/api/v1/content-versions/999999/content-packages")
    assert missing.status_code == 404
    assert missing.json() == {"detail": "ContentVersion 999999 not found"}
    assert _row_counts(db_connection) == (0, 0, 0)

    foundation = _foundation(client, "empty")
    version_id = foundation["first_version"]["id"]
    empty = client.post(f"/api/v1/content-versions/{version_id}/content-packages")
    assert empty.status_code == 409
    assert empty.json() == {
        "detail": f"ContentVersion {version_id} has no released assets to package"
    }
    assert _row_counts(db_connection) == (0, 0, 0)


def test_only_unreleased_and_withdrawn_assets_create_no_package(
    client: TestClient,
    db_connection: Connection,
) -> None:
    foundation = _foundation(client, "ineligible")
    version_id = foundation["first_version"]["id"]
    topic_id = foundation["topic"]["id"]
    claim_id = _approved_claim(client, topic_id, "ineligible")
    unreleased_draft = _create_draft(client, topic_id, version_id)
    withdrawn_draft = _create_draft(client, topic_id, version_id)
    unreleased_item = _create_item(client, version_id, [claim_id], "unreleased")
    withdrawn_item = _create_item(client, version_id, [claim_id], "withdrawn")

    for resource, resource_id in (
        ("note-drafts", unreleased_draft["id"]),
        ("note-drafts", withdrawn_draft["id"]),
        ("question-bank-items", unreleased_item["id"]),
        ("question-bank-items", withdrawn_item["id"]),
    ):
        approval = client.post(
            f"/api/v1/{resource}/{resource_id}/approval",
            json={"approval_status": "APPROVED"},
        )
        assert approval.status_code == 200
    _approve_and_release_draft(client, withdrawn_draft["id"])
    _approve_and_release_item(client, withdrawn_item["id"])
    for resource, resource_id in (
        ("note-drafts", withdrawn_draft["id"]),
        ("question-bank-items", withdrawn_item["id"]),
    ):
        withdrawal = client.post(
            f"/api/v1/{resource}/{resource_id}/release",
            json={"release_status": "WITHDRAWN"},
        )
        assert withdrawal.status_code == 200

    response = client.post(
        f"/api/v1/content-versions/{version_id}/content-packages"
    )
    assert response.status_code == 409
    assert response.json() == {
        "detail": f"ContentVersion {version_id} has no released assets to package"
    }
    assert _row_counts(db_connection) == (0, 0, 0)


def test_package_can_capture_only_note_drafts(client: TestClient) -> None:
    foundation = _foundation(client, "notes-only")
    version_id = foundation["first_version"]["id"]
    topic_id = foundation["topic"]["id"]
    _approved_claim(client, topic_id, "notes-only")
    draft = _create_draft(client, topic_id, version_id)
    _approve_and_release_draft(client, draft["id"])

    package = _create_package(client, version_id)

    assert package["content_version_id"] == version_id
    assert package["note_draft_ids"] == [draft["id"]]
    assert package["question_bank_item_ids"] == []
    assert (
        datetime.fromisoformat(package["created_at"]).utcoffset()
        == UTC.utcoffset(None)
    )


def test_package_can_capture_only_question_bank_items(client: TestClient) -> None:
    foundation = _foundation(client, "items-only")
    version_id = foundation["first_version"]["id"]
    topic_id = foundation["topic"]["id"]
    claim_id = _approved_claim(client, topic_id, "items-only")
    item = _create_item(client, version_id, [claim_id], "items-only")
    _approve_and_release_item(client, item["id"])

    package = _create_package(client, version_id)

    assert package["content_version_id"] == version_id
    assert package["note_draft_ids"] == []
    assert package["question_bank_item_ids"] == [item["id"]]


def test_package_filters_orders_persists_exact_membership_and_counts(
    client: TestClient,
    db_connection: Connection,
) -> None:
    foundation = _foundation(client, "complete")
    first_version_id = foundation["first_version"]["id"]
    second_version_id = foundation["second_version"]["id"]
    topic_id = foundation["topic"]["id"]
    first_claim_id = _approved_claim(client, topic_id, "first")
    second_claim_id = _approved_claim(client, topic_id, "second")

    first_draft = _create_draft(client, topic_id, first_version_id)
    unreleased_draft = _create_draft(client, topic_id, first_version_id)
    second_draft = _create_draft(client, topic_id, first_version_id)
    other_version_draft = _create_draft(client, topic_id, second_version_id)
    _approve_and_release_draft(client, first_draft["id"])
    approval = client.post(
        f"/api/v1/note-drafts/{unreleased_draft['id']}/approval",
        json={"approval_status": "APPROVED"},
    )
    assert approval.status_code == 200
    _approve_and_release_draft(client, second_draft["id"])
    _approve_and_release_draft(client, other_version_draft["id"])

    first_item = _create_item(
        client, first_version_id, [second_claim_id, first_claim_id], "first"
    )
    unreleased_item = _create_item(
        client, first_version_id, [first_claim_id], "unreleased"
    )
    second_item = _create_item(client, first_version_id, [first_claim_id], "second")
    other_version_item = _create_item(
        client, second_version_id, [first_claim_id], "other-version"
    )
    _approve_and_release_item(client, first_item["id"])
    approval = client.post(
        f"/api/v1/question-bank-items/{unreleased_item['id']}/approval",
        json={"approval_status": "APPROVED"},
    )
    assert approval.status_code == 200
    _approve_and_release_item(client, second_item["id"])
    _approve_and_release_item(client, other_version_item["id"])

    other_package = _create_package(client, second_version_id)
    assert other_package["note_draft_ids"] == [other_version_draft["id"]]
    assert other_package["question_bank_item_ids"] == [other_version_item["id"]]

    source = _post(
        client,
        "/api/v1/sources",
        {
            "title": "Package verification source",
            "source_type": "official",
            "authority_tier": 1,
            "location": "https://example.gov/package-verification",
            "license_status": "UNKNOWN",
        },
    )
    evidence = _post(
        client,
        "/api/v1/evidence",
        {"source_id": source["id"], "content": "Package evidence."},
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
            "source_id": foundation["source"]["id"],
            "year": 2025,
            "label": "Package paper",
        },
    )
    previous_question = _post(
        client,
        "/api/v1/previous-questions",
        {
            "previous_paper_id": paper["id"],
            "topic_id": topic_id,
            "position": 0,
            "question_text": "Historical package question?",
        },
    )
    priority = client.get(
        "/api/v1/syllabus-versions/"
        f"{foundation['syllabus']['id']}/topics/{topic_id}/priority"
    )
    assert verification["claim"]["id"] == first_claim_id
    assert previous_question["previous_paper_id"] == paper["id"]
    assert priority.status_code == 200

    claim_change = client.post(
        f"/api/v1/claims/{second_claim_id}/approval",
        json={"approval_status": "REJECTED"},
    )
    assert claim_change.status_code == 200
    counts_before = _row_counts(db_connection)

    package = _create_package(client, first_version_id)

    assert package["content_version_id"] == first_version_id
    assert package["note_draft_ids"] == [first_draft["id"], second_draft["id"]]
    assert package["question_bank_item_ids"] == [first_item["id"], second_item["id"]]
    assert unreleased_draft["id"] not in package["note_draft_ids"]
    assert other_version_draft["id"] not in package["note_draft_ids"]
    assert unreleased_item["id"] not in package["question_bank_item_ids"]
    assert other_version_item["id"] not in package["question_bank_item_ids"]
    assert _row_counts(db_connection) == (
        counts_before[0] + 1,
        counts_before[1] + 2,
        counts_before[2] + 2,
    )

    package_row = db_connection.execute(
        select(ContentPackage.content_version_id, ContentPackage.created_at).where(
            ContentPackage.id == package["id"]
        )
    ).one()
    note_links = db_connection.execute(
        select(
            ContentPackageNoteDraft.note_draft_id,
            ContentPackageNoteDraft.position,
        )
        .where(ContentPackageNoteDraft.content_package_id == package["id"])
        .order_by(ContentPackageNoteDraft.position)
    ).all()
    item_links = db_connection.execute(
        select(
            ContentPackageQuestionBankItem.question_bank_item_id,
            ContentPackageQuestionBankItem.position,
        )
        .where(ContentPackageQuestionBankItem.content_package_id == package["id"])
        .order_by(ContentPackageQuestionBankItem.position)
    ).all()
    assert package_row.content_version_id == first_version_id
    assert package_row.created_at == datetime.fromisoformat(package["created_at"])
    assert [(link.note_draft_id, link.position) for link in note_links] == [
        (first_draft["id"], 0),
        (second_draft["id"], 1),
    ]
    assert [(link.question_bank_item_id, link.position) for link in item_links] == [
        (first_item["id"], 0),
        (second_item["id"], 1),
    ]


def test_withdrawal_changes_manifest_but_not_package_membership(
    client: TestClient,
    db_connection: Connection,
) -> None:
    foundation = _foundation(client, "snapshot")
    version_id = foundation["first_version"]["id"]
    topic_id = foundation["topic"]["id"]
    claim_id = _approved_claim(client, topic_id, "snapshot")
    draft = _create_draft(client, topic_id, version_id)
    item = _create_item(client, version_id, [claim_id], "snapshot")
    _approve_and_release_draft(client, draft["id"])
    _approve_and_release_item(client, item["id"])
    package = _create_package(client, version_id)

    for resource, resource_id in (
        ("note-drafts", draft["id"]),
        ("question-bank-items", item["id"]),
    ):
        response = client.post(
            f"/api/v1/{resource}/{resource_id}/release",
            json={"release_status": "WITHDRAWN"},
        )
        assert response.status_code == 200

    manifest = client.get(
        f"/api/v1/content-versions/{version_id}/released-assets"
    )
    assert manifest.status_code == 200
    assert manifest.json()["note_drafts"] == []
    assert manifest.json()["question_bank_items"] == []
    note_ids = db_connection.scalars(
        select(ContentPackageNoteDraft.note_draft_id).where(
            ContentPackageNoteDraft.content_package_id == package["id"]
        )
    ).all()
    item_ids = db_connection.scalars(
        select(ContentPackageQuestionBankItem.question_bank_item_id).where(
            ContentPackageQuestionBankItem.content_package_id == package["id"]
        )
    ).all()
    assert note_ids == [draft["id"]]
    assert item_ids == [item["id"]]


def test_persistence_failure_rolls_back_package_and_links(
    client: TestClient,
    db_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    foundation = _foundation(client, "rollback")
    version_id = foundation["first_version"]["id"]
    topic_id = foundation["topic"]["id"]
    _approved_claim(client, topic_id, "rollback")
    first = _create_draft(client, topic_id, version_id)
    second = _create_draft(client, topic_id, version_id)
    _approve_and_release_draft(client, first["id"])
    _approve_and_release_draft(client, second["id"])
    original = KnowledgeRepository.add_content_package

    def fail_after_flush(
        repository: KnowledgeRepository,
        content_package: ContentPackage,
    ) -> ContentPackage:
        original(repository, content_package)
        content_package.note_draft_links[1].position = 0
        repository.session.flush()
        return content_package

    monkeypatch.setattr(KnowledgeRepository, "add_content_package", fail_after_flush)
    with pytest.raises(IntegrityError):
        client.post(f"/api/v1/content-versions/{version_id}/content-packages")

    assert _row_counts(db_connection) == (0, 0, 0)


def _assert_integrity_error(connection: Connection, statement) -> None:
    savepoint = connection.begin_nested()
    with pytest.raises(IntegrityError):
        connection.execute(statement)
    savepoint.rollback()


def test_database_rejects_invalid_note_draft_memberships(
    client: TestClient,
    db_connection: Connection,
) -> None:
    foundation = _foundation(client, "note-constraints")
    first_version_id = foundation["first_version"]["id"]
    second_version_id = foundation["second_version"]["id"]
    topic_id = foundation["topic"]["id"]
    _approved_claim(client, topic_id, "note-constraints")
    released = _create_draft(client, topic_id, first_version_id)
    spare = _create_draft(client, topic_id, first_version_id)
    other_version = _create_draft(client, topic_id, second_version_id)
    _approve_and_release_draft(client, released["id"])
    package = _create_package(client, first_version_id)

    _assert_integrity_error(
        db_connection,
        insert(ContentPackageNoteDraft).values(
            content_package_id=package["id"],
            content_version_id=first_version_id,
            note_draft_id=other_version["id"],
            position=1,
        ),
    )
    _assert_integrity_error(
        db_connection,
        insert(ContentPackageNoteDraft).values(
            content_package_id=package["id"],
            content_version_id=first_version_id,
            note_draft_id=released["id"],
            position=1,
        ),
    )
    _assert_integrity_error(
        db_connection,
        insert(ContentPackageNoteDraft).values(
            content_package_id=package["id"],
            content_version_id=first_version_id,
            note_draft_id=spare["id"],
            position=0,
        ),
    )
    _assert_integrity_error(
        db_connection,
        insert(ContentPackageNoteDraft).values(
            content_package_id=package["id"],
            content_version_id=first_version_id,
            note_draft_id=spare["id"],
            position=-1,
        ),
    )


def test_database_rejects_invalid_question_item_memberships(
    client: TestClient,
    db_connection: Connection,
) -> None:
    foundation = _foundation(client, "item-constraints")
    first_version_id = foundation["first_version"]["id"]
    second_version_id = foundation["second_version"]["id"]
    topic_id = foundation["topic"]["id"]
    claim_id = _approved_claim(client, topic_id, "item-constraints")
    released = _create_item(client, first_version_id, [claim_id], "released")
    spare = _create_item(client, first_version_id, [claim_id], "spare")
    other_version = _create_item(client, second_version_id, [claim_id], "other")
    _approve_and_release_item(client, released["id"])
    package = _create_package(client, first_version_id)

    _assert_integrity_error(
        db_connection,
        insert(ContentPackageQuestionBankItem).values(
            content_package_id=package["id"],
            content_version_id=first_version_id,
            question_bank_item_id=other_version["id"],
            position=1,
        ),
    )
    _assert_integrity_error(
        db_connection,
        insert(ContentPackageQuestionBankItem).values(
            content_package_id=package["id"],
            content_version_id=first_version_id,
            question_bank_item_id=released["id"],
            position=1,
        ),
    )
    _assert_integrity_error(
        db_connection,
        insert(ContentPackageQuestionBankItem).values(
            content_package_id=package["id"],
            content_version_id=first_version_id,
            question_bank_item_id=spare["id"],
            position=0,
        ),
    )
    _assert_integrity_error(
        db_connection,
        insert(ContentPackageQuestionBankItem).values(
            content_package_id=package["id"],
            content_version_id=first_version_id,
            question_bank_item_id=spare["id"],
            position=-1,
        ),
    )


def test_package_membership_restricts_referenced_deletions(
    client: TestClient,
    db_connection: Connection,
) -> None:
    foundation = _foundation(client, "deletion")
    version_id = foundation["first_version"]["id"]
    topic_id = foundation["topic"]["id"]
    claim_id = _approved_claim(client, topic_id, "deletion")
    draft = _create_draft(client, topic_id, version_id)
    item = _create_item(client, version_id, [claim_id], "deletion")
    _approve_and_release_draft(client, draft["id"])
    _approve_and_release_item(client, item["id"])
    package = _create_package(client, version_id)

    for statement in (
        delete(NoteDraft).where(NoteDraft.id == draft["id"]),
        delete(QuestionBankItem).where(QuestionBankItem.id == item["id"]),
    ):
        _assert_integrity_error(db_connection, statement)
    _assert_integrity_error(
        db_connection,
        delete(ContentVersion).where(ContentVersion.id == version_id),
    )

    db_connection.execute(
        delete(ContentPackage).where(ContentPackage.id == package["id"])
    )
    assert _row_counts(db_connection) == (0, 0, 0)


def test_get_content_package_missing_is_stable_and_read_only(
    client: TestClient,
    db_connection: Connection,
) -> None:
    counts_before = _row_counts(db_connection)

    response = client.get("/api/v1/content-packages/999999")

    assert response.status_code == 404
    assert response.json() == {"detail": "ContentPackage 999999 not found"}
    assert _row_counts(db_connection) == counts_before


def test_get_content_package_preserves_single_type_empty_lists(
    client: TestClient,
) -> None:
    note_foundation = _foundation(client, "retrieve-notes")
    note_version_id = note_foundation["first_version"]["id"]
    note_topic_id = note_foundation["topic"]["id"]
    _approved_claim(client, note_topic_id, "retrieve-notes")
    draft = _create_draft(client, note_topic_id, note_version_id)
    _approve_and_release_draft(client, draft["id"])
    note_package = _create_package(client, note_version_id)

    item_foundation = _foundation(client, "retrieve-items")
    item_version_id = item_foundation["first_version"]["id"]
    item_topic_id = item_foundation["topic"]["id"]
    claim_id = _approved_claim(client, item_topic_id, "retrieve-items")
    item = _create_item(client, item_version_id, [claim_id], "retrieve-items")
    _approve_and_release_item(client, item["id"])
    item_package = _create_package(client, item_version_id)

    note_response = client.get(
        f"/api/v1/content-packages/{note_package['id']}"
    )
    item_response = client.get(
        f"/api/v1/content-packages/{item_package['id']}"
    )

    assert note_response.status_code == 200
    assert note_response.json() == note_package
    assert note_response.json()["note_draft_ids"] == [draft["id"]]
    assert note_response.json()["question_bank_item_ids"] == []
    assert item_response.status_code == 200
    assert item_response.json() == item_package
    assert item_response.json()["note_draft_ids"] == []
    assert item_response.json()["question_bank_item_ids"] == [item["id"]]


def test_get_content_package_uses_stored_positions_and_retains_snapshot(
    client: TestClient,
    db_connection: Connection,
) -> None:
    foundation = _foundation(client, "retrieve-snapshot")
    version_id = foundation["first_version"]["id"]
    other_version_id = foundation["second_version"]["id"]
    topic_id = foundation["topic"]["id"]
    first_claim_id = _approved_claim(client, topic_id, "retrieve-first")
    second_claim_id = _approved_claim(client, topic_id, "retrieve-second")

    first_draft = _create_draft(client, topic_id, version_id)
    second_draft = _create_draft(client, topic_id, version_id)
    other_draft = _create_draft(client, topic_id, other_version_id)
    for draft in (first_draft, second_draft, other_draft):
        _approve_and_release_draft(client, draft["id"])

    first_item = _create_item(
        client,
        version_id,
        [second_claim_id, first_claim_id],
        "retrieve-first",
    )
    second_item = _create_item(
        client,
        version_id,
        [first_claim_id],
        "retrieve-second",
    )
    other_item = _create_item(
        client,
        other_version_id,
        [first_claim_id],
        "retrieve-other",
    )
    for item in (first_item, second_item, other_item):
        _approve_and_release_item(client, item["id"])

    package = _create_package(client, version_id)
    other_package = _create_package(client, other_version_id)

    for model, first_id, second_id, id_column in (
        (
            ContentPackageNoteDraft,
            first_draft["id"],
            second_draft["id"],
            ContentPackageNoteDraft.note_draft_id,
        ),
        (
            ContentPackageQuestionBankItem,
            first_item["id"],
            second_item["id"],
            ContentPackageQuestionBankItem.question_bank_item_id,
        ),
    ):
        package_filter = model.content_package_id == package["id"]
        db_connection.execute(
            update(model)
            .where(package_filter, id_column == first_id)
            .values(position=2)
        )
        db_connection.execute(
            update(model)
            .where(package_filter, id_column == second_id)
            .values(position=0)
        )
        db_connection.execute(
            update(model)
            .where(package_filter, id_column == first_id)
            .values(position=1)
        )

    for resource, resource_id in (
        ("note-drafts", first_draft["id"]),
        ("note-drafts", second_draft["id"]),
        ("question-bank-items", first_item["id"]),
        ("question-bank-items", second_item["id"]),
    ):
        withdrawal = client.post(
            f"/api/v1/{resource}/{resource_id}/release",
            json={"release_status": "WITHDRAWN", "release_note": "Retained"},
        )
        assert withdrawal.status_code == 200

    draft_review = client.post(
        f"/api/v1/note-drafts/{first_draft['id']}/approval",
        json={"approval_status": "REJECTED", "reviewer_note": "After withdrawal"},
    )
    item_review = client.post(
        f"/api/v1/question-bank-items/{first_item['id']}/approval",
        json={"approval_status": "REJECTED", "reviewer_note": "After withdrawal"},
    )
    claim_review = client.post(
        f"/api/v1/claims/{second_claim_id}/approval",
        json={"approval_status": "REJECTED"},
    )
    assert draft_review.status_code == 200
    assert item_review.status_code == 200
    assert claim_review.status_code == 200

    source = _post(
        client,
        "/api/v1/sources",
        {
            "title": "Retrieval unrelated evidence",
            "source_type": "official",
            "authority_tier": 1,
            "location": "https://example.gov/retrieval-evidence",
            "license_status": "UNKNOWN",
        },
    )
    evidence = _post(
        client,
        "/api/v1/evidence",
        {"source_id": source["id"], "content": "Unrelated evidence."},
    )
    verification = _post(
        client,
        "/api/v1/verifications",
        {
            "claim_id": first_claim_id,
            "verdict": "SUPPORTED",
            "confidence": 0.8,
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
            "source_id": foundation["source"]["id"],
            "year": 2024,
            "label": "Retrieval paper",
        },
    )
    previous_question = _post(
        client,
        "/api/v1/previous-questions",
        {
            "previous_paper_id": paper["id"],
            "topic_id": topic_id,
            "position": 0,
            "question_text": "Unrelated historical question?",
        },
    )
    priority = client.get(
        "/api/v1/syllabus-versions/"
        f"{foundation['syllabus']['id']}/topics/{topic_id}/priority"
    )
    assert verification["claim"]["id"] == first_claim_id
    assert previous_question["previous_paper_id"] == paper["id"]
    assert priority.status_code == 200
    assert other_package["content_version_id"] == other_version_id

    manifest = client.get(f"/api/v1/content-versions/{version_id}/released-assets")
    assert manifest.status_code == 200
    assert manifest.json()["note_drafts"] == []
    assert manifest.json()["question_bank_items"] == []
    released_drafts = client.get("/api/v1/note-drafts/released")
    released_items = client.get("/api/v1/question-bank-items/released")
    assert released_drafts.status_code == 200
    assert [draft["id"] for draft in released_drafts.json()] == [other_draft["id"]]
    assert released_items.status_code == 200
    assert [item["id"] for item in released_items.json()] == [other_item["id"]]

    counts_before = _row_counts(db_connection)
    package_row_before = db_connection.execute(
        select(ContentPackage).where(ContentPackage.id == package["id"])
    ).first()
    selected_statements: list[str] = []

    def record_selects(
        connection,
        cursor,
        statement: str,
        parameters,
        context,
        executemany,
    ) -> None:
        if statement.lstrip().upper().startswith("SELECT"):
            selected_statements.append(statement)

    event.listen(db_connection, "before_cursor_execute", record_selects)
    try:
        first_response = client.get(f"/api/v1/content-packages/{package['id']}")
        second_response = client.get(f"/api/v1/content-packages/{package['id']}")
    finally:
        event.remove(db_connection, "before_cursor_execute", record_selects)

    expected = {
        "id": package["id"],
        "content_version_id": version_id,
        "created_at": package["created_at"],
        "note_draft_ids": [second_draft["id"], first_draft["id"]],
        "question_bank_item_ids": [second_item["id"], first_item["id"]],
        "approval_status": "DRAFT",
        "approval_decided_at": None,
        "reviewer_note": None,
        "release_status": "UNRELEASED",
        "released_at": None,
        "withdrawn_at": None,
        "release_note": None,
    }
    assert package_row_before.id == expected["id"]
    assert package_row_before.content_version_id == expected["content_version_id"]
    assert package_row_before.created_at == datetime.fromisoformat(
        expected["created_at"]
    )
    assert first_response.status_code == 200
    assert first_response.json() == expected
    assert second_response.status_code == 200
    assert second_response.json() == expected
    assert len(selected_statements) == 6
    assert all("FOR UPDATE" not in statement.upper() for statement in selected_statements)
    assert _row_counts(db_connection) == counts_before
    assert db_connection.execute(
        select(ContentPackage).where(ContentPackage.id == package["id"])
    ).first() == package_row_before


def test_get_content_package_content_missing_is_stable_and_read_only(
    client: TestClient,
    db_connection: Connection,
) -> None:
    counts_before = _content_snapshot_row_counts(db_connection)

    response = client.get("/api/v1/content-packages/999999/content")

    assert response.status_code == 404
    assert response.json() == {"detail": "ContentPackage 999999 not found"}
    assert _content_snapshot_row_counts(db_connection) == counts_before


def test_get_content_package_content_preserves_single_type_packages(
    client: TestClient,
) -> None:
    note_foundation = _foundation(client, "content-notes")
    note_version_id = note_foundation["first_version"]["id"]
    note_topic_id = note_foundation["topic"]["id"]
    _approved_claim(client, note_topic_id, "content-notes")
    draft = _create_draft(client, note_topic_id, note_version_id)
    released_draft = _approve_and_release_draft(client, draft["id"])
    note_package = _create_package(client, note_version_id)

    item_foundation = _foundation(client, "content-items")
    item_version_id = item_foundation["first_version"]["id"]
    item_topic_id = item_foundation["topic"]["id"]
    claim_id = _approved_claim(client, item_topic_id, "content-items")
    item = _create_item(client, item_version_id, [claim_id], "content-items")
    released_item = _approve_and_release_item(client, item["id"])
    item_package = _create_package(client, item_version_id)

    note_response = client.get(
        f"/api/v1/content-packages/{note_package['id']}/content"
    )
    item_response = client.get(
        f"/api/v1/content-packages/{item_package['id']}/content"
    )

    assert note_response.status_code == 200
    assert note_response.json() == {
        "content_package": note_package,
        "note_drafts": [released_draft],
        "question_bank_items": [],
    }
    assert item_response.status_code == 200
    assert item_response.json() == {
        "content_package": item_package,
        "note_drafts": [],
        "question_bank_items": [released_item],
    }


def test_get_content_package_content_expands_only_retained_ordered_members(
    client: TestClient,
    db_connection: Connection,
) -> None:
    foundation = _foundation(client, "content-snapshot")
    version_id = foundation["first_version"]["id"]
    other_version_id = foundation["second_version"]["id"]
    topic_id = foundation["topic"]["id"]
    first_claim_id = _approved_claim(client, topic_id, "content-snapshot-first")
    second_claim_id = _approved_claim(client, topic_id, "content-snapshot-second")

    first_draft = _create_draft(client, topic_id, version_id)
    second_draft = _create_draft(client, topic_id, version_id)
    for draft in (first_draft, second_draft):
        _approve_and_release_draft(client, draft["id"])

    first_item = _create_item(
        client,
        version_id,
        [second_claim_id, first_claim_id],
        "content-snapshot-first",
    )
    second_item = _create_item(
        client,
        version_id,
        [first_claim_id],
        "content-snapshot-second",
    )
    for item in (first_item, second_item):
        _approve_and_release_item(client, item["id"])

    package = _create_package(client, version_id)
    for model, first_id, second_id, id_column in (
        (
            ContentPackageNoteDraft,
            first_draft["id"],
            second_draft["id"],
            ContentPackageNoteDraft.note_draft_id,
        ),
        (
            ContentPackageQuestionBankItem,
            first_item["id"],
            second_item["id"],
            ContentPackageQuestionBankItem.question_bank_item_id,
        ),
    ):
        package_filter = model.content_package_id == package["id"]
        db_connection.execute(
            update(model)
            .where(package_filter, id_column == first_id)
            .values(position=2)
        )
        db_connection.execute(
            update(model)
            .where(package_filter, id_column == second_id)
            .values(position=0)
        )
        db_connection.execute(
            update(model)
            .where(package_filter, id_column == first_id)
            .values(position=1)
        )

    nonmember_draft = _create_draft(client, topic_id, version_id)
    _approve_and_release_draft(client, nonmember_draft["id"])
    nonmember_item = _create_item(
        client,
        version_id,
        [first_claim_id],
        "content-nonmember",
    )
    _approve_and_release_item(client, nonmember_item["id"])

    other_draft = _create_draft(client, topic_id, other_version_id)
    _approve_and_release_draft(client, other_draft["id"])
    other_item = _create_item(
        client,
        other_version_id,
        [first_claim_id],
        "content-other-version",
    )
    _approve_and_release_item(client, other_item["id"])
    other_package = _create_package(client, other_version_id)

    for resource, resource_id in (
        ("note-drafts", first_draft["id"]),
        ("note-drafts", second_draft["id"]),
        ("question-bank-items", first_item["id"]),
        ("question-bank-items", second_item["id"]),
    ):
        withdrawal = client.post(
            f"/api/v1/{resource}/{resource_id}/release",
            json={"release_status": "WITHDRAWN", "release_note": "Retained"},
        )
        assert withdrawal.status_code == 200

    same_version_other_package = _create_package(client, version_id)
    assert same_version_other_package["note_draft_ids"] == [nonmember_draft["id"]]
    assert same_version_other_package["question_bank_item_ids"] == [
        nonmember_item["id"]
    ]

    draft_review = client.post(
        f"/api/v1/note-drafts/{first_draft['id']}/approval",
        json={"approval_status": "REJECTED", "reviewer_note": "Retained"},
    )
    item_review = client.post(
        f"/api/v1/question-bank-items/{first_item['id']}/approval",
        json={"approval_status": "DRAFT"},
    )
    claim_review = client.post(
        f"/api/v1/claims/{second_claim_id}/approval",
        json={"approval_status": "REJECTED"},
    )
    assert draft_review.status_code == 200
    assert item_review.status_code == 200
    assert claim_review.status_code == 200

    source = _post(
        client,
        "/api/v1/sources",
        {
            "title": "Expanded package evidence",
            "source_type": "official",
            "authority_tier": 1,
            "location": "https://example.gov/expanded-package",
            "license_status": "UNKNOWN",
        },
    )
    evidence = _post(
        client,
        "/api/v1/evidence",
        {"source_id": source["id"], "content": "Expanded package evidence."},
    )
    verification = _post(
        client,
        "/api/v1/verifications",
        {
            "claim_id": first_claim_id,
            "verdict": "SUPPORTED",
            "confidence": 0.8,
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
            "source_id": foundation["source"]["id"],
            "year": 2023,
            "label": "Expanded package paper",
        },
    )
    previous_question = _post(
        client,
        "/api/v1/previous-questions",
        {
            "previous_paper_id": paper["id"],
            "topic_id": topic_id,
            "position": 0,
            "question_text": "Expanded package history?",
        },
    )
    priority = client.get(
        "/api/v1/syllabus-versions/"
        f"{foundation['syllabus']['id']}/topics/{topic_id}/priority"
    )
    assert verification["claim"]["id"] == first_claim_id
    assert previous_question["previous_paper_id"] == paper["id"]
    assert priority.status_code == 200
    assert other_package["content_version_id"] == other_version_id

    manifest = client.get(f"/api/v1/content-versions/{version_id}/released-assets")
    released_drafts = client.get("/api/v1/note-drafts/released")
    released_items = client.get("/api/v1/question-bank-items/released")
    assert manifest.status_code == 200
    assert [draft["id"] for draft in manifest.json()["note_drafts"]] == [
        nonmember_draft["id"]
    ]
    assert [item["id"] for item in manifest.json()["question_bank_items"]] == [
        nonmember_item["id"]
    ]
    assert released_drafts.status_code == 200
    assert {draft["id"] for draft in released_drafts.json()} == {
        nonmember_draft["id"],
        other_draft["id"],
    }
    assert released_items.status_code == 200
    assert {item["id"] for item in released_items.json()} == {
        nonmember_item["id"],
        other_item["id"],
    }

    package_response = client.get(f"/api/v1/content-packages/{package['id']}")
    expected_drafts = [
        client.get(f"/api/v1/note-drafts/{draft_id}").json()
        for draft_id in (second_draft["id"], first_draft["id"])
    ]
    expected_items = [
        client.get(f"/api/v1/question-bank-items/{item_id}").json()
        for item_id in (second_item["id"], first_item["id"])
    ]
    counts_before = _content_snapshot_row_counts(db_connection)
    selected_statements: list[str] = []

    def record_selects(
        connection,
        cursor,
        statement: str,
        parameters,
        context,
        executemany,
    ) -> None:
        if statement.lstrip().upper().startswith("SELECT"):
            selected_statements.append(statement)

    event.listen(db_connection, "before_cursor_execute", record_selects)
    try:
        first_response = client.get(
            f"/api/v1/content-packages/{package['id']}/content"
        )
        second_response = client.get(
            f"/api/v1/content-packages/{package['id']}/content"
        )
    finally:
        event.remove(db_connection, "before_cursor_execute", record_selects)

    expected = {
        "content_package": package_response.json(),
        "note_drafts": expected_drafts,
        "question_bank_items": expected_items,
    }
    assert package_response.status_code == 200
    assert expected["content_package"]["note_draft_ids"] == [
        draft["id"] for draft in expected_drafts
    ]
    assert expected["content_package"]["question_bank_item_ids"] == [
        item["id"] for item in expected_items
    ]
    assert expected_drafts[0]["content_version_id"] == version_id
    assert expected_drafts[0]["topic_id"] == topic_id
    assert expected_drafts[0]["topic_name"] == foundation["topic"]["name"]
    assert expected_drafts[0]["markdown"] == second_draft["markdown"]
    assert expected_drafts[0]["claim_ids"] == [first_claim_id, second_claim_id]
    assert expected_drafts[0]["created_at"] == second_draft["created_at"]
    assert expected_drafts[0]["approval_status"] == "APPROVED"
    assert expected_drafts[0]["approval_decided_at"] is not None
    assert expected_drafts[0]["reviewer_note"] == "Package review"
    assert expected_drafts[0]["release_status"] == "WITHDRAWN"
    assert expected_drafts[0]["released_at"] is not None
    assert expected_drafts[0]["withdrawn_at"] is not None
    assert expected_drafts[0]["release_note"] == "Retained"
    assert expected_items[1]["content_version_id"] == version_id
    assert expected_items[1]["question_text"] == first_item["question_text"]
    assert expected_items[1]["explanation"] == first_item["explanation"]
    assert expected_items[1]["difficulty"] == first_item["difficulty"]
    assert expected_items[1]["claim_ids"] == [second_claim_id, first_claim_id]
    assert expected_items[1]["options"] == first_item["options"]
    assert (
        expected_items[1]["correct_option_position"]
        == first_item["correct_option_position"]
    )
    assert expected_items[1]["created_at"] == first_item["created_at"]
    assert expected_items[1]["approval_status"] == "DRAFT"
    assert expected_items[1]["release_status"] == "WITHDRAWN"
    assert expected_items[1]["release_note"] == "Retained"
    assert expected_items[0]["approval_status"] == "APPROVED"
    assert expected_items[0]["approval_decided_at"] is not None
    assert expected_items[0]["reviewer_note"] == "Package review"
    assert expected_items[0]["released_at"] is not None
    assert expected_items[0]["withdrawn_at"] is not None
    assert first_response.status_code == 200
    assert first_response.json() == expected
    assert second_response.status_code == 200
    assert second_response.json() == expected
    assert len(selected_statements) == 16
    assert all("FOR UPDATE" not in statement.upper() for statement in selected_statements)
    assert _content_snapshot_row_counts(db_connection) == counts_before


def test_get_content_package_content_rejects_unresolved_membership(
    client: TestClient,
    db_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    foundation = _foundation(client, "content-integrity")
    version_id = foundation["first_version"]["id"]
    topic_id = foundation["topic"]["id"]
    _approved_claim(client, topic_id, "content-integrity")
    draft = _create_draft(client, topic_id, version_id)
    _approve_and_release_draft(client, draft["id"])
    package = _create_package(client, version_id)
    counts_before = _content_snapshot_row_counts(db_connection)

    monkeypatch.setattr(
        KnowledgeRepository,
        "get_content_package_note_drafts",
        lambda repository, content_package_id: [],
    )

    with pytest.raises(
        RuntimeError,
        match=f"ContentPackage {package['id']} membership could not be resolved",
    ):
        client.get(f"/api/v1/content-packages/{package['id']}/content")

    assert _content_snapshot_row_counts(db_connection) == counts_before


def test_content_package_review_defaults_are_exposed_on_all_boundaries(
    client: TestClient,
) -> None:
    foundation = _foundation(client, "package-review-defaults")
    version_id = foundation["first_version"]["id"]
    topic_id = foundation["topic"]["id"]
    claim_id = _approved_claim(client, topic_id, "package-review-defaults")
    draft = _create_draft(client, topic_id, version_id)
    item = _create_item(client, version_id, [claim_id], "package-review-defaults")
    _approve_and_release_draft(client, draft["id"])
    _approve_and_release_item(client, item["id"])

    package = _create_package(client, version_id)
    retrieved = client.get(f"/api/v1/content-packages/{package['id']}")
    expanded = client.get(f"/api/v1/content-packages/{package['id']}/content")

    assert package["approval_status"] == "DRAFT"
    assert package["approval_decided_at"] is None
    assert package["reviewer_note"] is None
    assert retrieved.status_code == 200
    assert retrieved.json() == package
    assert expanded.status_code == 200
    assert expanded.json()["content_package"] == package


def test_content_package_review_missing_and_invalid_requests_do_not_mutate(
    client: TestClient,
    db_connection: Connection,
) -> None:
    counts_before = _content_snapshot_row_counts(db_connection)

    missing = client.post(
        "/api/v1/content-packages/999999/approval",
        json={"approval_status": "APPROVED", "reviewer_note": "Missing"},
    )
    assert missing.status_code == 404
    assert missing.json() == {"detail": "ContentPackage 999999 not found"}

    for payload in (
        {},
        {"approval_status": "INVALID"},
        {"approval_status": "UNRELEASED"},
        {"approval_status": 1},
        {"approval_status": None},
    ):
        response = client.post(
            "/api/v1/content-packages/999999/approval",
            json=payload,
        )
        assert response.status_code == 422

    assert _content_snapshot_row_counts(db_connection) == counts_before


def test_content_package_review_records_resets_locks_and_preserves_membership(
    client: TestClient,
    db_connection: Connection,
) -> None:
    foundation = _foundation(client, "package-review-lifecycle")
    version_id = foundation["first_version"]["id"]
    other_version_id = foundation["second_version"]["id"]
    topic_id = foundation["topic"]["id"]
    first_claim_id = _approved_claim(client, topic_id, "package-review-first")
    second_claim_id = _approved_claim(client, topic_id, "package-review-second")
    draft = _create_draft(client, topic_id, version_id)
    item = _create_item(
        client,
        version_id,
        [second_claim_id, first_claim_id],
        "package-review",
    )
    _approve_and_release_draft(client, draft["id"])
    _approve_and_release_item(client, item["id"])
    package = _create_package(client, version_id)

    other_draft = _create_draft(client, topic_id, other_version_id)
    _approve_and_release_draft(client, other_draft["id"])
    other_package = _create_package(client, other_version_id)

    source = _post(
        client,
        "/api/v1/sources",
        {
            "title": "Package review verification",
            "source_type": "official",
            "authority_tier": 1,
            "location": "https://example.gov/package-review",
            "license_status": "UNKNOWN",
        },
    )
    evidence = _post(
        client,
        "/api/v1/evidence",
        {"source_id": source["id"], "content": "Package review evidence."},
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
    claim_change = client.post(
        f"/api/v1/claims/{second_claim_id}/approval",
        json={"approval_status": "REJECTED"},
    )
    for resource, resource_id in (
        ("note-drafts", draft["id"]),
        ("question-bank-items", item["id"]),
    ):
        withdrawal = client.post(
            f"/api/v1/{resource}/{resource_id}/release",
            json={"release_status": "WITHDRAWN", "release_note": "Review test"},
        )
        assert withdrawal.status_code == 200
        member_review = client.post(
            f"/api/v1/{resource}/{resource_id}/approval",
            json={"approval_status": "REJECTED"},
        )
        assert member_review.status_code == 200
    assert verification["claim"]["id"] == first_claim_id
    assert claim_change.status_code == 200
    assert other_package["approval_status"] == "DRAFT"

    immutable_fields = {
        key: package[key]
        for key in (
            "id",
            "content_version_id",
            "created_at",
            "note_draft_ids",
            "question_bank_item_ids",
        )
    }
    note_links_before = db_connection.execute(
        select(
            ContentPackageNoteDraft.note_draft_id,
            ContentPackageNoteDraft.position,
        )
        .where(ContentPackageNoteDraft.content_package_id == package["id"])
        .order_by(ContentPackageNoteDraft.position)
    ).all()
    item_links_before = db_connection.execute(
        select(
            ContentPackageQuestionBankItem.question_bank_item_id,
            ContentPackageQuestionBankItem.position,
        )
        .where(ContentPackageQuestionBankItem.content_package_id == package["id"])
        .order_by(ContentPackageQuestionBankItem.position)
    ).all()
    counts_before = _content_snapshot_row_counts(db_connection)
    approval_statements: list[str] = []

    def record_approval_sql(
        connection,
        cursor,
        statement: str,
        parameters,
        context,
        executemany,
    ) -> None:
        approval_statements.append(statement)

    event.listen(db_connection, "before_cursor_execute", record_approval_sql)
    try:
        approved = client.post(
            f"/api/v1/content-packages/{package['id']}/approval",
            json={
                "approval_status": "APPROVED",
                "reviewer_note": "Package approved",
            },
        )
    finally:
        event.remove(db_connection, "before_cursor_execute", record_approval_sql)

    assert approved.status_code == 200
    approved_body = approved.json()
    assert {key: approved_body[key] for key in immutable_fields} == immutable_fields
    assert approved_body["approval_status"] == "APPROVED"
    assert approved_body["reviewer_note"] == "Package approved"
    assert (
        datetime.fromisoformat(approved_body["approval_decided_at"]).utcoffset()
        == UTC.utcoffset(None)
    )
    package_locks = [
        statement
        for statement in approval_statements
        if "FROM content_packages" in statement and "FOR UPDATE" in statement.upper()
    ]
    assert len(package_locks) == 1
    assert "FOR UPDATE OF content_packages" in package_locks[0]
    assert all(
        not (
            "FOR UPDATE" in statement.upper()
            and (
                "content_package_note_drafts" in statement
                or "content_package_question_bank_items" in statement
                or "note_drafts" in statement
                or "question_bank_items" in statement
            )
        )
        for statement in approval_statements
    )

    rejected = client.post(
        f"/api/v1/content-packages/{package['id']}/approval",
        json={"approval_status": "REJECTED", "reviewer_note": None},
    )
    assert rejected.status_code == 200
    assert rejected.json()["approval_status"] == "REJECTED"
    assert rejected.json()["reviewer_note"] is None
    assert (
        datetime.fromisoformat(
            rejected.json()["approval_decided_at"]
        ).utcoffset()
        == UTC.utcoffset(None)
    )

    reset = client.post(
        f"/api/v1/content-packages/{package['id']}/approval",
        json={"approval_status": "DRAFT", "reviewer_note": "Discarded"},
    )
    assert reset.status_code == 200
    assert reset.json() == package
    assert reset.json()["approval_decided_at"] is None
    assert reset.json()["reviewer_note"] is None

    read_statements: list[str] = []

    def record_read_sql(
        connection,
        cursor,
        statement: str,
        parameters,
        context,
        executemany,
    ) -> None:
        read_statements.append(statement)

    event.listen(db_connection, "before_cursor_execute", record_read_sql)
    try:
        retrieved = client.get(f"/api/v1/content-packages/{package['id']}")
        expanded = client.get(
            f"/api/v1/content-packages/{package['id']}/content"
        )
    finally:
        event.remove(db_connection, "before_cursor_execute", record_read_sql)

    assert retrieved.status_code == 200
    assert retrieved.json() == package
    assert expanded.status_code == 200
    assert expanded.json()["content_package"] == package
    assert all("FOR UPDATE" not in statement.upper() for statement in read_statements)
    assert _content_snapshot_row_counts(db_connection) == counts_before
    assert db_connection.execute(
        select(
            ContentPackageNoteDraft.note_draft_id,
            ContentPackageNoteDraft.position,
        )
        .where(ContentPackageNoteDraft.content_package_id == package["id"])
        .order_by(ContentPackageNoteDraft.position)
    ).all() == note_links_before
    assert db_connection.execute(
        select(
            ContentPackageQuestionBankItem.question_bank_item_id,
            ContentPackageQuestionBankItem.position,
        )
        .where(ContentPackageQuestionBankItem.content_package_id == package["id"])
        .order_by(ContentPackageQuestionBankItem.position)
    ).all() == item_links_before
    assert client.get(f"/api/v1/content-packages/{other_package['id']}").json() == (
        other_package
    )


def test_content_package_review_persistence_failure_rolls_back(
    client: TestClient,
    db_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    foundation = _foundation(client, "package-review-rollback")
    version_id = foundation["first_version"]["id"]
    topic_id = foundation["topic"]["id"]
    _approved_claim(client, topic_id, "package-review-rollback")
    draft = _create_draft(client, topic_id, version_id)
    _approve_and_release_draft(client, draft["id"])
    package = _create_package(client, version_id)
    counts_before = _content_snapshot_row_counts(db_connection)
    original = KnowledgeRepository.update_content_package_approval

    def fail_after_update(
        repository: KnowledgeRepository,
        content_package: ContentPackage,
        approval_status: str,
        reviewer_note: str | None,
        decided_at: datetime | None,
    ) -> None:
        original(
            repository,
            content_package,
            approval_status,
            reviewer_note,
            decided_at,
        )
        raise RuntimeError("injected package approval failure")

    monkeypatch.setattr(
        KnowledgeRepository,
        "update_content_package_approval",
        fail_after_update,
    )
    with pytest.raises(RuntimeError, match="injected package approval failure"):
        client.post(
            f"/api/v1/content-packages/{package['id']}/approval",
            json={"approval_status": "APPROVED", "reviewer_note": "Rollback"},
        )

    assert client.get(f"/api/v1/content-packages/{package['id']}").json() == package
    assert _content_snapshot_row_counts(db_connection) == counts_before


def test_database_rejects_invalid_content_package_review_states(
    client: TestClient,
    db_connection: Connection,
) -> None:
    foundation = _foundation(client, "package-review-constraints")
    version_id = foundation["first_version"]["id"]
    topic_id = foundation["topic"]["id"]
    _approved_claim(client, topic_id, "package-review-constraints")
    draft = _create_draft(client, topic_id, version_id)
    _approve_and_release_draft(client, draft["id"])
    package = _create_package(client, version_id)
    decided_at = datetime.now(UTC)

    for values in (
        {"approval_status": "INVALID"},
        {"approval_status": "DRAFT", "approval_decided_at": decided_at},
        {"approval_status": "DRAFT", "reviewer_note": "Invalid"},
        {"approval_status": "APPROVED", "approval_decided_at": None},
        {"approval_status": "REJECTED", "approval_decided_at": None},
    ):
        _assert_integrity_error(
            db_connection,
            update(ContentPackage)
            .where(ContentPackage.id == package["id"])
            .values(**values),
        )

    assert client.get(f"/api/v1/content-packages/{package['id']}").json() == package


def test_content_package_release_defaults_and_validation_are_non_mutating(
    client: TestClient,
    db_connection: Connection,
) -> None:
    foundation = _foundation(client, "package-release-defaults")
    version_id = foundation["first_version"]["id"]
    topic_id = foundation["topic"]["id"]
    _approved_claim(client, topic_id, "package-release-defaults")
    draft = _create_draft(client, topic_id, version_id)
    _approve_and_release_draft(client, draft["id"])
    package = _create_package(client, version_id)

    assert package["release_status"] == "UNRELEASED"
    assert package["released_at"] is None
    assert package["withdrawn_at"] is None
    assert package["release_note"] is None
    assert client.get(f"/api/v1/content-packages/{package['id']}").json() == package
    expanded = client.get(f"/api/v1/content-packages/{package['id']}/content")
    assert expanded.json()["content_package"] == package

    counts_before = _content_snapshot_row_counts(db_connection)
    missing = client.post(
        "/api/v1/content-packages/999999/release",
        json={"release_status": "RELEASED"},
    )
    assert missing.status_code == 404
    assert missing.json() == {"detail": "ContentPackage 999999 not found"}
    for payload in ({}, {"release_status": "UNRELEASED"}, {"release_status": "BAD"}):
        response = client.post(
            f"/api/v1/content-packages/{package['id']}/release", json=payload
        )
        assert response.status_code == 422
    assert _content_snapshot_row_counts(db_connection) == counts_before
    assert client.get(f"/api/v1/content-packages/{package['id']}").json() == package


def test_content_package_release_lifecycle_locks_and_preserves_snapshot(
    client: TestClient,
    db_connection: Connection,
) -> None:
    foundation = _foundation(client, "package-release-lifecycle")
    version_id = foundation["first_version"]["id"]
    topic_id = foundation["topic"]["id"]
    claim_id = _approved_claim(client, topic_id, "package-release-lifecycle")
    draft = _create_draft(client, topic_id, version_id)
    item = _create_item(client, version_id, [claim_id], "package-release-lifecycle")
    _approve_and_release_draft(client, draft["id"])
    _approve_and_release_item(client, item["id"])
    package = _create_package(client, version_id)
    immutable = {
        key: package[key]
        for key in (
            "id",
            "content_version_id",
            "created_at",
            "note_draft_ids",
            "question_bank_item_ids",
        )
    }
    counts_before = _content_snapshot_row_counts(db_connection)

    draft_conflict = client.post(
        f"/api/v1/content-packages/{package['id']}/release",
        json={"release_status": "RELEASED"},
    )
    assert draft_conflict.status_code == 409
    assert draft_conflict.json() == {
        "detail": f"ContentPackage {package['id']} must be approved before release"
    }
    unreleased_withdrawal = client.post(
        f"/api/v1/content-packages/{package['id']}/release",
        json={"release_status": "WITHDRAWN"},
    )
    assert unreleased_withdrawal.status_code == 409
    assert unreleased_withdrawal.json() == {
        "detail": f"ContentPackage {package['id']} cannot transition from UNRELEASED to WITHDRAWN"
    }
    rejected_package = client.post(
        f"/api/v1/content-packages/{package['id']}/approval",
        json={"approval_status": "REJECTED"},
    )
    assert rejected_package.status_code == 200
    rejected_conflict = client.post(
        f"/api/v1/content-packages/{package['id']}/release",
        json={"release_status": "RELEASED"},
    )
    assert rejected_conflict.status_code == 409
    assert rejected_conflict.json() == {
        "detail": f"ContentPackage {package['id']} must be approved before release"
    }
    approved = client.post(
        f"/api/v1/content-packages/{package['id']}/approval",
        json={"approval_status": "APPROVED", "reviewer_note": "Reviewed"},
    ).json()
    assert approved["release_status"] == "UNRELEASED"
    for resource, resource_id in (
        ("note-drafts", draft["id"]),
        ("question-bank-items", item["id"]),
    ):
        assert client.post(
            f"/api/v1/{resource}/{resource_id}/release",
            json={"release_status": "WITHDRAWN"},
        ).status_code == 200
        assert client.post(
            f"/api/v1/{resource}/{resource_id}/approval",
            json={"approval_status": "REJECTED"},
        ).status_code == 200
    assert client.post(
        f"/api/v1/claims/{claim_id}/approval",
        json={"approval_status": "REJECTED"},
    ).status_code == 200

    statements: list[str] = []

    def record_sql(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(db_connection, "before_cursor_execute", record_sql)
    try:
        release = client.post(
            f"/api/v1/content-packages/{package['id']}/release",
            json={"release_status": "RELEASED", "release_note": "Ship package"},
        )
    finally:
        event.remove(db_connection, "before_cursor_execute", record_sql)
    assert release.status_code == 200
    released = release.json()
    assert {key: released[key] for key in immutable} == immutable
    assert released["approval_status"] == "APPROVED"
    assert released["release_status"] == "RELEASED"
    assert released["release_note"] == "Ship package"
    assert datetime.fromisoformat(released["released_at"]).utcoffset() == UTC.utcoffset(
        None
    )
    assert released["withdrawn_at"] is None
    package_locks = [
        statement
        for statement in statements
        if "FROM content_packages" in statement and "FOR UPDATE" in statement.upper()
    ]
    assert len(package_locks) == 1
    assert "FOR UPDATE OF content_packages" in package_locks[0]
    assert all(
        "FOR UPDATE" not in statement.upper()
        or (
            "note_drafts" not in statement
            and "question_bank_items" not in statement
            and "content_package_note_drafts" not in statement
            and "content_package_question_bank_items" not in statement
        )
        for statement in statements
    )

    for approval_status in ("DRAFT", "REJECTED"):
        blocked = client.post(
            f"/api/v1/content-packages/{package['id']}/approval",
            json={"approval_status": approval_status},
        )
        assert blocked.status_code == 409
        assert blocked.json() == {
            "detail": f"ContentPackage {package['id']} must be withdrawn before changing approval"
        }
        assert client.get(f"/api/v1/content-packages/{package['id']}").json() == released

    duplicate = client.post(
        f"/api/v1/content-packages/{package['id']}/release",
        json={"release_status": "RELEASED"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json() == {
        "detail": f"ContentPackage {package['id']} cannot transition from RELEASED to RELEASED"
    }
    withdrawal = client.post(
        f"/api/v1/content-packages/{package['id']}/release",
        json={"release_status": "WITHDRAWN", "release_note": "Withdraw package"},
    )
    assert withdrawal.status_code == 200
    withdrawn = withdrawal.json()
    assert withdrawn["released_at"] == released["released_at"]
    assert datetime.fromisoformat(withdrawn["withdrawn_at"]).utcoffset() == UTC.utcoffset(
        None
    )
    assert withdrawn["release_note"] == "Withdraw package"
    assert {key: withdrawn[key] for key in immutable} == immutable

    rejected = client.post(
        f"/api/v1/content-packages/{package['id']}/approval",
        json={"approval_status": "REJECTED", "reviewer_note": "After withdrawal"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["release_status"] == "WITHDRAWN"
    assert rejected.json()["released_at"] == withdrawn["released_at"]
    assert rejected.json()["withdrawn_at"] == withdrawn["withdrawn_at"]
    assert rejected.json()["release_note"] == "Withdraw package"
    for decision in ("WITHDRAWN", "RELEASED"):
        conflict = client.post(
            f"/api/v1/content-packages/{package['id']}/release",
            json={"release_status": decision},
        )
        assert conflict.status_code == 409
        assert conflict.json() == {
            "detail": f"ContentPackage {package['id']} cannot transition from WITHDRAWN to {decision}"
        }
    assert _content_snapshot_row_counts(db_connection) == counts_before


def test_empty_approved_content_package_cannot_release(
    client: TestClient,
    db_connection: Connection,
) -> None:
    foundation = _foundation(client, "package-release-empty")
    version_id = foundation["first_version"]["id"]
    package_id = db_connection.scalar(
        insert(ContentPackage)
        .values(
            content_version_id=version_id,
            approval_status="APPROVED",
            approval_decided_at=datetime.now(UTC),
        )
        .returning(ContentPackage.id)
    )
    before = client.get(f"/api/v1/content-packages/{package_id}").json()
    response = client.post(
        f"/api/v1/content-packages/{package_id}/release",
        json={"release_status": "RELEASED"},
    )
    assert response.status_code == 409
    assert response.json() == {
        "detail": f"ContentPackage {package_id} has no retained members to release"
    }
    assert client.get(f"/api/v1/content-packages/{package_id}").json() == before


def test_content_package_release_failure_rolls_back(
    client: TestClient,
    db_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    foundation = _foundation(client, "package-release-rollback")
    version_id = foundation["first_version"]["id"]
    topic_id = foundation["topic"]["id"]
    _approved_claim(client, topic_id, "package-release-rollback")
    draft = _create_draft(client, topic_id, version_id)
    _approve_and_release_draft(client, draft["id"])
    package = _create_package(client, version_id)
    client.post(
        f"/api/v1/content-packages/{package['id']}/approval",
        json={"approval_status": "APPROVED"},
    )
    before = client.get(f"/api/v1/content-packages/{package['id']}").json()
    original = KnowledgeRepository.update_content_package_release

    def fail_after_update(repository, content_package, *args):
        original(repository, content_package, *args)
        raise RuntimeError("injected package release failure")

    monkeypatch.setattr(
        KnowledgeRepository, "update_content_package_release", fail_after_update
    )
    with pytest.raises(RuntimeError, match="injected package release failure"):
        client.post(
            f"/api/v1/content-packages/{package['id']}/release",
            json={"release_status": "RELEASED"},
        )
    assert client.get(f"/api/v1/content-packages/{package['id']}").json() == before


def test_database_rejects_invalid_content_package_release_states(
    client: TestClient,
    db_connection: Connection,
) -> None:
    foundation = _foundation(client, "package-release-constraints")
    version_id = foundation["first_version"]["id"]
    topic_id = foundation["topic"]["id"]
    _approved_claim(client, topic_id, "package-release-constraints")
    draft = _create_draft(client, topic_id, version_id)
    _approve_and_release_draft(client, draft["id"])
    package = _create_package(client, version_id)
    now = datetime.now(UTC)
    for values in (
        {"release_status": "INVALID"},
        {"release_status": "UNRELEASED", "released_at": now},
        {"release_status": "UNRELEASED", "withdrawn_at": now},
        {"release_status": "UNRELEASED", "release_note": "Invalid"},
        {"release_status": "RELEASED", "released_at": None},
        {"release_status": "RELEASED", "released_at": now},
        {
            "release_status": "RELEASED",
            "released_at": now,
            "withdrawn_at": now,
            "approval_status": "APPROVED",
            "approval_decided_at": now,
        },
        {"release_status": "WITHDRAWN", "released_at": None, "withdrawn_at": now},
        {"release_status": "WITHDRAWN", "released_at": now, "withdrawn_at": None},
    ):
        _assert_integrity_error(
            db_connection,
            update(ContentPackage)
            .where(ContentPackage.id == package["id"])
            .values(**values),
        )
    assert client.get(f"/api/v1/content-packages/{package['id']}").json() == package
