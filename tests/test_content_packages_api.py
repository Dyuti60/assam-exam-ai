from collections.abc import Generator
from datetime import UTC, datetime
from hashlib import sha256

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
    ContentDocument,
    ContentPackage,
    ContentPackageNoteDraft,
    ContentPackageQuestionBankItem,
    ContentVersion,
    Evidence,
    NoteDraft,
    PreviousPaper,
    PreviousQuestion,
    QuestionBankItem,
    QuestionBankOption,
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


def _approve_and_release_package(client: TestClient, package_id: int) -> dict:
    approval = client.post(
        f"/api/v1/content-packages/{package_id}/approval",
        json={"approval_status": "APPROVED", "reviewer_note": "Document review"},
    )
    assert approval.status_code == 200
    release = client.post(
        f"/api/v1/content-packages/{package_id}/release",
        json={"release_status": "RELEASED", "release_note": "Document release"},
    )
    assert release.status_code == 200
    return release.json()


def _create_content_document_fixture(client: TestClient, suffix: str) -> dict:
    foundation = _foundation(client, suffix)
    topic_id = foundation["topic"]["id"]
    version_id = foundation["first_version"]["id"]
    claim_id = _approved_claim(client, topic_id, suffix)
    draft = _create_draft(client, topic_id, version_id)
    _approve_and_release_draft(client, draft["id"])
    package = _create_package(client, version_id)
    _approve_and_release_package(client, package["id"])
    response = client.post(
        f"/api/v1/content-packages/{package['id']}/content-documents"
    )
    assert response.status_code == 201
    return {
        "foundation": foundation,
        "claim_id": claim_id,
        "draft": draft,
        "package": package,
        "document": response.json(),
    }


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


def test_released_content_packages_empty_and_ineligible_states_are_excluded(
    client: TestClient,
) -> None:
    empty = client.get("/api/v1/content-packages/released")
    assert empty.status_code == 200
    assert empty.json() == []

    foundation = _foundation(client, "released-packages-ineligible")
    version_id = foundation["first_version"]["id"]
    topic_id = foundation["topic"]["id"]
    _approved_claim(client, topic_id, "released-packages-ineligible")
    draft = _create_draft(client, topic_id, version_id)
    _approve_and_release_draft(client, draft["id"])

    draft_package = _create_package(client, version_id)
    approved_package = _create_package(client, version_id)
    rejected_package = _create_package(client, version_id)
    withdrawn_package = _create_package(client, version_id)
    assert client.post(
        f"/api/v1/content-packages/{approved_package['id']}/approval",
        json={"approval_status": "APPROVED"},
    ).status_code == 200
    assert client.post(
        f"/api/v1/content-packages/{rejected_package['id']}/approval",
        json={"approval_status": "REJECTED"},
    ).status_code == 200
    assert client.post(
        f"/api/v1/content-packages/{withdrawn_package['id']}/approval",
        json={"approval_status": "APPROVED"},
    ).status_code == 200
    assert client.post(
        f"/api/v1/content-packages/{withdrawn_package['id']}/release",
        json={"release_status": "RELEASED"},
    ).status_code == 200
    assert client.post(
        f"/api/v1/content-packages/{withdrawn_package['id']}/release",
        json={"release_status": "WITHDRAWN"},
    ).status_code == 200

    response = client.get("/api/v1/content-packages/released")
    assert response.status_code == 200
    assert response.json() == []
    assert draft_package["approval_status"] == "DRAFT"


def test_released_content_packages_preserve_order_snapshot_and_are_read_only(
    client: TestClient,
    db_connection: Connection,
) -> None:
    foundation = _foundation(client, "released-packages-snapshot")
    version_id = foundation["first_version"]["id"]
    other_version_id = foundation["second_version"]["id"]
    topic_id = foundation["topic"]["id"]
    first_claim_id = _approved_claim(client, topic_id, "released-packages-first")
    second_claim_id = _approved_claim(client, topic_id, "released-packages-second")
    first_draft = _create_draft(client, topic_id, version_id)
    second_draft = _create_draft(client, topic_id, version_id)
    other_draft = _create_draft(client, topic_id, other_version_id)
    first_item = _create_item(
        client, version_id, [first_claim_id], "released-packages-first"
    )
    second_item = _create_item(
        client, version_id, [second_claim_id], "released-packages-second"
    )
    for draft in (first_draft, second_draft, other_draft):
        _approve_and_release_draft(client, draft["id"])
    for item in (first_item, second_item):
        _approve_and_release_item(client, item["id"])

    ordered_package = _create_package(client, version_id)
    second_package = _create_package(client, version_id)
    note_only_package = _create_package(client, version_id)
    item_only_package = _create_package(client, version_id)
    other_package = _create_package(client, other_version_id)

    db_connection.execute(
        delete(ContentPackageQuestionBankItem).where(
            ContentPackageQuestionBankItem.content_package_id
            == note_only_package["id"]
        )
    )
    db_connection.execute(
        delete(ContentPackageNoteDraft).where(
            ContentPackageNoteDraft.content_package_id == item_only_package["id"]
        )
    )
    for model, id_column, first_id, second_id in (
        (
            ContentPackageNoteDraft,
            ContentPackageNoteDraft.note_draft_id,
            first_draft["id"],
            second_draft["id"],
        ),
        (
            ContentPackageQuestionBankItem,
            ContentPackageQuestionBankItem.question_bank_item_id,
            first_item["id"],
            second_item["id"],
        ),
    ):
        package_filter = model.content_package_id == ordered_package["id"]
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

    released_ids = []
    for package in (
        ordered_package,
        second_package,
        note_only_package,
        item_only_package,
    ):
        approval = client.post(
            f"/api/v1/content-packages/{package['id']}/approval",
            json={"approval_status": "APPROVED", "reviewer_note": "Reviewed"},
        )
        assert approval.status_code == 200
        release = client.post(
            f"/api/v1/content-packages/{package['id']}/release",
            json={"release_status": "RELEASED", "release_note": "Released"},
        )
        assert release.status_code == 200
        released_ids.append(package["id"])
    assert other_package["release_status"] == "UNRELEASED"

    for resource, resource_id in (
        ("note-drafts", first_draft["id"]),
        ("question-bank-items", first_item["id"]),
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
        f"/api/v1/claims/{first_claim_id}/approval",
        json={"approval_status": "REJECTED"},
    ).status_code == 200
    manifest = client.get(f"/api/v1/content-versions/{version_id}/released-assets")
    assert manifest.status_code == 200
    assert [draft["id"] for draft in manifest.json()["note_drafts"]] == [
        second_draft["id"]
    ]
    assert [item["id"] for item in manifest.json()["question_bank_items"]] == [
        second_item["id"]
    ]

    counts_before = _content_snapshot_row_counts(db_connection)
    statements: list[str] = []

    def record_sql(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(db_connection, "before_cursor_execute", record_sql)
    try:
        first_read = client.get("/api/v1/content-packages/released")
        second_read = client.get("/api/v1/content-packages/released")
    finally:
        event.remove(db_connection, "before_cursor_execute", record_sql)
    assert first_read.status_code == 200
    assert first_read.json() == second_read.json()
    returned = first_read.json()
    assert [package["id"] for package in returned] == sorted(released_ids)
    by_id = {package["id"]: package for package in returned}
    assert by_id[ordered_package["id"]]["note_draft_ids"] == [
        second_draft["id"],
        first_draft["id"],
    ]
    assert by_id[ordered_package["id"]]["question_bank_item_ids"] == [
        second_item["id"],
        first_item["id"],
    ]
    assert by_id[note_only_package["id"]]["question_bank_item_ids"] == []
    assert by_id[item_only_package["id"]]["note_draft_ids"] == []
    for package in returned:
        assert package["approval_status"] == "APPROVED"
        assert package["approval_decided_at"] is not None
        assert package["reviewer_note"] == "Reviewed"
        assert package["release_status"] == "RELEASED"
        assert package["released_at"] is not None
        assert package["withdrawn_at"] is None
        assert package["release_note"] == "Released"
    select_statements = [
        statement
        for statement in statements
        if statement.lstrip().upper().startswith("SELECT")
    ]
    assert len(select_statements) == 6
    assert all("FOR UPDATE" not in statement.upper() for statement in statements)
    assert _content_snapshot_row_counts(db_connection) == counts_before

    withdrawal = client.post(
        f"/api/v1/content-packages/{second_package['id']}/release",
        json={"release_status": "WITHDRAWN"},
    )
    assert withdrawal.status_code == 200
    after = client.get("/api/v1/content-packages/released").json()
    assert [package["id"] for package in after] == sorted(
        set(released_ids) - {second_package["id"]}
    )
    assert by_id[ordered_package["id"]] in after


def test_content_document_missing_and_unreleased_package_fail_without_rows(
    client: TestClient,
    db_connection: Connection,
) -> None:
    missing = client.post(
        "/api/v1/content-packages/999999/content-documents"
    )
    assert missing.status_code == 404
    assert missing.json() == {"detail": "ContentPackage 999999 not found"}

    foundation = _foundation(client, "document-ineligible")
    topic_id = foundation["topic"]["id"]
    version_id = foundation["first_version"]["id"]
    _approved_claim(client, topic_id, "document-ineligible")
    draft = _create_draft(client, topic_id, version_id)
    _approve_and_release_draft(client, draft["id"])
    package = _create_package(client, version_id)

    response = client.post(
        f"/api/v1/content-packages/{package['id']}/content-documents"
    )
    assert response.status_code == 409
    assert response.json() == {
        "detail": (
            f"ContentPackage {package['id']} must be released before document creation"
        )
    }
    approved = client.post(
        f"/api/v1/content-packages/{package['id']}/approval",
        json={"approval_status": "APPROVED"},
    )
    assert approved.status_code == 200
    approved_unreleased = client.post(
        f"/api/v1/content-packages/{package['id']}/content-documents"
    )
    assert approved_unreleased.status_code == 409
    assert approved_unreleased.json() == response.json()
    assert client.post(
        f"/api/v1/content-packages/{package['id']}/release",
        json={"release_status": "RELEASED"},
    ).status_code == 200
    assert client.post(
        f"/api/v1/content-packages/{package['id']}/release",
        json={"release_status": "WITHDRAWN"},
    ).status_code == 200
    withdrawn = client.post(
        f"/api/v1/content-packages/{package['id']}/content-documents"
    )
    assert withdrawn.status_code == 409
    assert withdrawn.json() == response.json()
    assert db_connection.scalar(select(func.count()).select_from(ContentDocument)) == 0


def test_content_document_renders_retained_members_and_is_immutable(
    client: TestClient,
    db_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    foundation = _foundation(client, "document-render")
    topic_id = foundation["topic"]["id"]
    version_id = foundation["first_version"]["id"]
    claim_id = _approved_claim(client, topic_id, "document-render")
    draft = _create_draft(client, topic_id, version_id)
    item = _create_item(client, version_id, [claim_id], "document-render")
    _approve_and_release_draft(client, draft["id"])
    _approve_and_release_item(client, item["id"])
    package = _create_package(client, version_id)
    _approve_and_release_package(client, package["id"])

    assert client.post(
        f"/api/v1/note-drafts/{draft['id']}/release",
        json={"release_status": "WITHDRAWN"},
    ).status_code == 200
    assert client.post(
        f"/api/v1/question-bank-items/{item['id']}/release",
        json={"release_status": "WITHDRAWN"},
    ).status_code == 200
    assert client.post(
        f"/api/v1/claims/{claim_id}/approval",
        json={"approval_status": "REJECTED"},
    ).status_code == 200

    statements: list[str] = []

    def record_sql(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(db_connection, "before_cursor_execute", record_sql)
    commit_count = 0
    original_commit = Session.commit

    def count_commit(session):
        nonlocal commit_count
        commit_count += 1
        return original_commit(session)

    monkeypatch.setattr(Session, "commit", count_commit)
    try:
        response = client.post(
            f"/api/v1/content-packages/{package['id']}/content-documents"
        )
    finally:
        event.remove(db_connection, "before_cursor_execute", record_sql)
    assert response.status_code == 201
    assert commit_count == 1
    body = response.json()
    expected_markdown = (
        f"# Content Package {package['id']}\n\n"
        "## Notes\n\n"
        f"# {foundation['topic']['name']}\n\n"
        "- Package grounded fact document-render.\n\n"
        "## Practice Questions\n\n"
        "### Question 1\n\n"
        "Package question document-render?\n\n"
        "A. Option A document-render\n"
        "B. Option B document-render\n\n"
        "**Answer:** B. Option B document-render\n\n"
        "**Explanation:** Package explanation document-render.\n"
    )
    assert body == {
        "id": body["id"],
        "content_package_id": package["id"],
        "content_version_id": version_id,
        "title": f"Content Package {package['id']}",
        "markdown": expected_markdown,
        "sha256": sha256(expected_markdown.encode("utf-8")).hexdigest(),
        "created_at": body["created_at"],
        "approval_status": "DRAFT",
        "approval_decided_at": None,
        "reviewer_note": None,
        "release_status": "UNRELEASED",
        "released_at": None,
        "withdrawn_at": None,
        "release_note": None,
    }
    assert datetime.fromisoformat(body["created_at"]).utcoffset() == UTC.utcoffset(None)
    assert body["markdown"].endswith("\n")
    assert not body["markdown"].endswith("\n\n")
    locking_sql = [statement.upper() for statement in statements if "FOR UPDATE" in statement.upper()]
    assert len(locking_sql) == 1
    assert "CONTENT_PACKAGES" in locking_sql[0]
    assert "NOTE_DRAFTS" not in locking_sql[0]
    assert "QUESTION_BANK_ITEMS" not in locking_sql[0]

    stored = db_connection.execute(
        select(
            ContentDocument.markdown,
            ContentDocument.sha256,
            ContentDocument.content_version_id,
        ).where(ContentDocument.id == body["id"])
    ).one()
    assert stored.markdown == expected_markdown
    assert stored.sha256 == body["sha256"]
    assert stored.content_version_id == version_id

    duplicate = client.post(
        f"/api/v1/content-packages/{package['id']}/content-documents"
    )
    assert duplicate.status_code == 409
    assert duplicate.json() == {
        "detail": f"ContentPackage {package['id']} already has a ContentDocument"
    }
    assert db_connection.scalar(select(func.count()).select_from(ContentDocument)) == 1

    package_withdrawal = client.post(
        f"/api/v1/content-packages/{package['id']}/release",
        json={"release_status": "WITHDRAWN"},
    )
    assert package_withdrawal.status_code == 200
    package_rejection = client.post(
        f"/api/v1/content-packages/{package['id']}/approval",
        json={"approval_status": "REJECTED"},
    )
    assert package_rejection.status_code == 200
    unchanged = db_connection.execute(
        select(ContentDocument.markdown, ContentDocument.sha256).where(
            ContentDocument.id == body["id"]
        )
    ).one()
    assert unchanged.markdown == expected_markdown
    assert unchanged.sha256 == body["sha256"]


def test_content_document_note_only_and_question_only_sections(
    client: TestClient,
) -> None:
    note_foundation = _foundation(client, "document-note-only")
    note_claim = _approved_claim(
        client, note_foundation["topic"]["id"], "document-note-only"
    )
    assert note_claim > 0
    draft = _create_draft(
        client,
        note_foundation["topic"]["id"],
        note_foundation["first_version"]["id"],
    )
    _approve_and_release_draft(client, draft["id"])
    note_package = _create_package(client, note_foundation["first_version"]["id"])
    _approve_and_release_package(client, note_package["id"])
    note_document = client.post(
        f"/api/v1/content-packages/{note_package['id']}/content-documents"
    ).json()
    assert "## Notes" in note_document["markdown"]
    assert "## Practice Questions" not in note_document["markdown"]

    item_foundation = _foundation(client, "document-question-only")
    item_claim = _approved_claim(
        client, item_foundation["topic"]["id"], "document-question-only"
    )
    item = _create_item(
        client,
        item_foundation["first_version"]["id"],
        [item_claim],
        "document-question-only",
    )
    _approve_and_release_item(client, item["id"])
    item_package = _create_package(client, item_foundation["first_version"]["id"])
    _approve_and_release_package(client, item_package["id"])
    item_document = client.post(
        f"/api/v1/content-packages/{item_package['id']}/content-documents"
    ).json()
    assert "## Notes" not in item_document["markdown"]
    assert "## Practice Questions" in item_document["markdown"]


def test_content_document_persistence_failure_rolls_back(
    client: TestClient,
    db_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    foundation = _foundation(client, "document-rollback")
    topic_id = foundation["topic"]["id"]
    version_id = foundation["first_version"]["id"]
    _approved_claim(client, topic_id, "document-rollback")
    draft = _create_draft(client, topic_id, version_id)
    _approve_and_release_draft(client, draft["id"])
    package = _create_package(client, version_id)
    _approve_and_release_package(client, package["id"])

    original = KnowledgeRepository.add_content_document

    def fail_after_add(repository, content_document):
        original(repository, content_document)
        raise RuntimeError("injected content document failure")

    monkeypatch.setattr(
        KnowledgeRepository,
        "add_content_document",
        fail_after_add,
    )
    with pytest.raises(RuntimeError, match="injected content document failure"):
        client.post(
            f"/api/v1/content-packages/{package['id']}/content-documents"
        )
    assert db_connection.scalar(select(func.count()).select_from(ContentDocument)) == 0


def test_content_document_rejects_unresolved_members_and_more_than_26_options(
    client: TestClient,
    db_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    foundation = _foundation(client, "document-integrity")
    topic_id = foundation["topic"]["id"]
    version_id = foundation["first_version"]["id"]
    claim_id = _approved_claim(client, topic_id, "document-integrity")
    item = _create_item(client, version_id, [claim_id], "document-integrity")
    _approve_and_release_item(client, item["id"])
    package = _create_package(client, version_id)
    _approve_and_release_package(client, package["id"])

    original = KnowledgeRepository.get_content_package_question_bank_items
    monkeypatch.setattr(
        KnowledgeRepository,
        "get_content_package_question_bank_items",
        lambda repository, content_package_id: [],
    )
    with pytest.raises(
        RuntimeError,
        match=f"ContentPackage {package['id']} membership could not be resolved",
    ):
        client.post(
            f"/api/v1/content-packages/{package['id']}/content-documents"
        )
    assert db_connection.scalar(select(func.count()).select_from(ContentDocument)) == 0
    monkeypatch.setattr(
        KnowledgeRepository,
        "get_content_package_question_bank_items",
        original,
    )

    db_connection.execute(
        insert(QuestionBankOption),
        [
            {
                "question_bank_item_id": item["id"],
                "position": position,
                "option_text": f"Extra option {position}",
            }
            for position in range(2, 27)
        ],
    )
    with pytest.raises(
        RuntimeError,
        match=f"QuestionBankItem {item['id']} has more than 26 options",
    ):
        client.post(
            f"/api/v1/content-packages/{package['id']}/content-documents"
        )
    assert db_connection.scalar(select(func.count()).select_from(ContentDocument)) == 0


@pytest.mark.parametrize(
    ("values", "constraint_name"),
    [
        ({"title": "   "}, "ck_content_documents_title_non_blank"),
        ({"markdown": "\t"}, "ck_content_documents_markdown_non_blank"),
        ({"sha256": "A" * 64}, "ck_content_documents_sha256_lower_hex"),
        ({"sha256": "a" * 63}, "ck_content_documents_sha256_lower_hex"),
    ],
)
def test_database_rejects_invalid_content_document_values(
    client: TestClient,
    db_connection: Connection,
    values: dict,
    constraint_name: str,
) -> None:
    foundation = _foundation(client, "document-constraint")
    topic_id = foundation["topic"]["id"]
    version_id = foundation["first_version"]["id"]
    _approved_claim(client, topic_id, constraint_name)
    draft = _create_draft(client, topic_id, version_id)
    _approve_and_release_draft(client, draft["id"])
    package = _create_package(client, version_id)
    document_values = {
        "content_package_id": package["id"],
        "content_version_id": version_id,
        "title": "Content Package",
        "markdown": "# Document\n",
        "sha256": "a" * 64,
        **values,
    }
    with pytest.raises(IntegrityError) as error, db_connection.begin_nested():
        db_connection.execute(insert(ContentDocument).values(**document_values))
    assert error.value.orig.diag.constraint_name == constraint_name


def test_database_enforces_content_document_package_identity_and_uniqueness(
    client: TestClient,
    db_connection: Connection,
) -> None:
    foundation = _foundation(client, "document-database")
    topic_id = foundation["topic"]["id"]
    first_version_id = foundation["first_version"]["id"]
    second_version_id = foundation["second_version"]["id"]
    _approved_claim(client, topic_id, "document-database")
    draft = _create_draft(client, topic_id, first_version_id)
    _approve_and_release_draft(client, draft["id"])
    package = _create_package(client, first_version_id)
    valid_values = {
        "content_package_id": package["id"],
        "content_version_id": first_version_id,
        "title": "Content Package",
        "markdown": "# Document\n",
        "sha256": "a" * 64,
    }

    with pytest.raises(IntegrityError) as mismatch, db_connection.begin_nested():
        db_connection.execute(
            insert(ContentDocument).values(
                **{**valid_values, "content_version_id": second_version_id}
            )
        )
    assert (
        mismatch.value.orig.diag.constraint_name
        == "fk_content_documents_package_version"
    )

    document_id = db_connection.execute(
        insert(ContentDocument).values(**valid_values).returning(ContentDocument.id)
    ).scalar_one()
    with pytest.raises(IntegrityError) as duplicate, db_connection.begin_nested():
        db_connection.execute(insert(ContentDocument).values(**valid_values))
    assert (
        duplicate.value.orig.diag.constraint_name
        == "uq_content_documents_content_package_id"
    )
    with pytest.raises(IntegrityError), db_connection.begin_nested():
        db_connection.execute(
            delete(ContentPackage).where(ContentPackage.id == package["id"])
        )
    assert db_connection.get_transaction() is not None
    assert db_connection.scalar(
        select(ContentDocument.id).where(ContentDocument.id == document_id)
    ) == document_id


def test_content_document_retrieval_missing_returns_404_without_mutation(
    client: TestClient,
    db_connection: Connection,
) -> None:
    counts_before = (
        *_content_snapshot_row_counts(db_connection),
        db_connection.scalar(select(func.count()).select_from(ContentDocument)),
    )

    response = client.get("/api/v1/content-documents/999999")

    assert response.status_code == 404
    assert response.json() == {"detail": "ContentDocument 999999 not found"}
    assert (
        *_content_snapshot_row_counts(db_connection),
        db_connection.scalar(select(func.count()).select_from(ContentDocument)),
    ) == counts_before


def test_content_document_retrieval_preserves_stored_snapshot_and_is_read_only(
    client: TestClient,
    db_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    foundation = _foundation(client, "document-retrieval")
    topic_id = foundation["topic"]["id"]
    version_id = foundation["first_version"]["id"]
    claim_id = _approved_claim(client, topic_id, "document-retrieval")
    draft = _create_draft(client, topic_id, version_id)
    item = _create_item(client, version_id, [claim_id], "document-retrieval")
    _approve_and_release_draft(client, draft["id"])
    _approve_and_release_item(client, item["id"])
    package = _create_package(client, version_id)
    _approve_and_release_package(client, package["id"])
    creation = client.post(
        f"/api/v1/content-packages/{package['id']}/content-documents"
    )
    assert creation.status_code == 201
    created = creation.json()
    assert created["markdown"].endswith("\n")
    assert not created["markdown"].endswith("\n\n")
    assert created["sha256"] == sha256(
        created["markdown"].encode("utf-8")
    ).hexdigest()
    assert created["sha256"] == created["sha256"].lower()
    assert len(created["sha256"]) == 64
    assert created["content_package_id"] == package["id"]
    assert created["content_version_id"] == version_id
    assert datetime.fromisoformat(created["created_at"]).utcoffset() == UTC.utcoffset(
        None
    )

    assert client.post(
        f"/api/v1/content-packages/{package['id']}/release",
        json={"release_status": "WITHDRAWN"},
    ).status_code == 200
    assert client.post(
        f"/api/v1/content-packages/{package['id']}/approval",
        json={"approval_status": "REJECTED"},
    ).status_code == 200
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

    counts_before = (
        *_content_snapshot_row_counts(db_connection),
        db_connection.scalar(select(func.count()).select_from(ContentDocument)),
    )
    statements: list[str] = []
    commit_count = 0
    flush_count = 0
    original_commit = Session.commit
    original_flush = Session.flush

    def record_sql(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    def count_commit(session):
        nonlocal commit_count
        commit_count += 1
        return original_commit(session)

    def count_flush(session, objects=None):
        nonlocal flush_count
        flush_count += 1
        return original_flush(session, objects)

    monkeypatch.setattr(Session, "commit", count_commit)
    monkeypatch.setattr(Session, "flush", count_flush)
    event.listen(db_connection, "before_cursor_execute", record_sql)
    try:
        first = client.get(f"/api/v1/content-documents/{created['id']}")
        second = client.get(f"/api/v1/content-documents/{created['id']}")
    finally:
        event.remove(db_connection, "before_cursor_execute", record_sql)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == created
    assert second.json() == created
    assert commit_count == 0
    assert flush_count == 0
    select_statements = [
        statement
        for statement in statements
        if statement.lstrip().upper().startswith("SELECT")
    ]
    assert len(select_statements) == 2
    assert all("CONTENT_DOCUMENTS" in statement.upper() for statement in select_statements)
    assert all("CONTENT_PACKAGES" not in statement.upper() for statement in select_statements)
    assert all("NOTE_DRAFTS" not in statement.upper() for statement in select_statements)
    assert all(
        "QUESTION_BANK_ITEMS" not in statement.upper()
        for statement in select_statements
    )
    assert all(
        not statement.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))
        for statement in statements
    )
    assert all("FOR UPDATE" not in statement.upper() for statement in statements)
    assert (
        *_content_snapshot_row_counts(db_connection),
        db_connection.scalar(select(func.count()).select_from(ContentDocument)),
    ) == counts_before


def test_content_document_review_decisions_lock_only_document_and_preserve_payload(
    client: TestClient,
    db_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    foundation = _foundation(client, "document-review")
    topic_id = foundation["topic"]["id"]
    version_id = foundation["first_version"]["id"]
    _approved_claim(client, topic_id, "document-review")
    draft = _create_draft(client, topic_id, version_id)
    _approve_and_release_draft(client, draft["id"])
    package = _create_package(client, version_id)
    _approve_and_release_package(client, package["id"])
    created = client.post(
        f"/api/v1/content-packages/{package['id']}/content-documents"
    ).json()
    assert created["approval_status"] == "DRAFT"
    assert created["approval_decided_at"] is None
    assert created["reviewer_note"] is None
    immutable = {
        key: created[key]
        for key in (
            "id",
            "content_package_id",
            "content_version_id",
            "title",
            "markdown",
            "sha256",
            "created_at",
        )
    }
    assert client.post(
        f"/api/v1/content-packages/{package['id']}/release",
        json={"release_status": "WITHDRAWN"},
    ).status_code == 200
    assert client.post(
        f"/api/v1/content-packages/{package['id']}/approval",
        json={"approval_status": "REJECTED"},
    ).status_code == 200
    assert client.post(
        f"/api/v1/note-drafts/{draft['id']}/release",
        json={"release_status": "WITHDRAWN"},
    ).status_code == 200
    assert client.post(
        f"/api/v1/note-drafts/{draft['id']}/approval",
        json={"approval_status": "REJECTED"},
    ).status_code == 200
    counts_before = _content_snapshot_row_counts(db_connection)
    statements: list[str] = []
    commit_count = 0
    original_commit = Session.commit

    def record_sql(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    def count_commit(session):
        nonlocal commit_count
        commit_count += 1
        return original_commit(session)

    monkeypatch.setattr(Session, "commit", count_commit)
    event.listen(db_connection, "before_cursor_execute", record_sql)
    try:
        approved_response = client.post(
            f"/api/v1/content-documents/{created['id']}/approval",
            json={"approval_status": "APPROVED", "reviewer_note": "Reviewed"},
        )
    finally:
        event.remove(db_connection, "before_cursor_execute", record_sql)
    assert approved_response.status_code == 200
    approved = approved_response.json()
    assert {key: approved[key] for key in immutable} == immutable
    assert approved["approval_status"] == "APPROVED"
    assert datetime.fromisoformat(
        approved["approval_decided_at"]
    ).utcoffset() == UTC.utcoffset(None)
    assert approved["reviewer_note"] == "Reviewed"
    assert commit_count == 1
    locking = [statement for statement in statements if "FOR UPDATE" in statement.upper()]
    assert len(locking) == 1
    assert "CONTENT_DOCUMENTS" in locking[0].upper()
    assert "CONTENT_PACKAGES" not in locking[0].upper()
    assert "NOTE_DRAFTS" not in locking[0].upper()
    assert "QUESTION_BANK_ITEMS" not in locking[0].upper()

    rejected = client.post(
        f"/api/v1/content-documents/{created['id']}/approval",
        json={"approval_status": "REJECTED"},
    ).json()
    assert {key: rejected[key] for key in immutable} == immutable
    assert rejected["approval_status"] == "REJECTED"
    assert datetime.fromisoformat(
        rejected["approval_decided_at"]
    ).utcoffset() == UTC.utcoffset(None)
    assert rejected["reviewer_note"] is None

    reset = client.post(
        f"/api/v1/content-documents/{created['id']}/approval",
        json={"approval_status": "DRAFT", "reviewer_note": "Must clear"},
    ).json()
    assert {key: reset[key] for key in immutable} == immutable
    assert reset["approval_status"] == "DRAFT"
    assert reset["approval_decided_at"] is None
    assert reset["reviewer_note"] is None
    assert _content_snapshot_row_counts(db_connection) == counts_before
    assert client.get(f"/api/v1/content-documents/{created['id']}").json() == reset


def test_content_document_review_validation_and_missing_do_not_mutate(
    client: TestClient,
    db_connection: Connection,
) -> None:
    counts_before = (
        *_content_snapshot_row_counts(db_connection),
        db_connection.scalar(select(func.count()).select_from(ContentDocument)),
    )
    missing = client.post(
        "/api/v1/content-documents/999999/approval",
        json={"approval_status": "APPROVED"},
    )
    assert missing.status_code == 404
    assert missing.json() == {"detail": "ContentDocument 999999 not found"}
    for payload in ({}, {"approval_status": "INVALID"}, {"approval_status": None}):
        response = client.post(
            "/api/v1/content-documents/999999/approval",
            json=payload,
        )
        assert response.status_code == 422
    assert (
        *_content_snapshot_row_counts(db_connection),
        db_connection.scalar(select(func.count()).select_from(ContentDocument)),
    ) == counts_before


def test_content_document_review_failure_rolls_back(
    client: TestClient,
    db_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    foundation = _foundation(client, "document-review-rollback")
    topic_id = foundation["topic"]["id"]
    version_id = foundation["first_version"]["id"]
    _approved_claim(client, topic_id, "document-review-rollback")
    draft = _create_draft(client, topic_id, version_id)
    _approve_and_release_draft(client, draft["id"])
    package = _create_package(client, version_id)
    _approve_and_release_package(client, package["id"])
    created = client.post(
        f"/api/v1/content-packages/{package['id']}/content-documents"
    ).json()
    original = KnowledgeRepository.update_content_document_approval

    def fail_after_update(repository, document, status, note, decided_at):
        original(repository, document, status, note, decided_at)
        raise RuntimeError("injected content document review failure")

    monkeypatch.setattr(
        KnowledgeRepository,
        "update_content_document_approval",
        fail_after_update,
    )
    with pytest.raises(RuntimeError, match="injected content document review failure"):
        client.post(
            f"/api/v1/content-documents/{created['id']}/approval",
            json={"approval_status": "APPROVED", "reviewer_note": "Rollback"},
        )
    stored = db_connection.execute(
        select(
            ContentDocument.approval_status,
            ContentDocument.approval_decided_at,
            ContentDocument.reviewer_note,
        ).where(ContentDocument.id == created["id"])
    ).one()
    assert stored == ("DRAFT", None, None)


@pytest.mark.parametrize(
    ("values", "constraint_name"),
    [
        ({"approval_status": "INVALID"}, "ck_content_documents_approval_status"),
        (
            {"approval_status": "DRAFT", "approval_decided_at": datetime.now(UTC)},
            "ck_content_documents_approval_lifecycle",
        ),
        (
            {"approval_status": "DRAFT", "reviewer_note": "Invalid"},
            "ck_content_documents_approval_lifecycle",
        ),
        (
            {"approval_status": "APPROVED", "approval_decided_at": None},
            "ck_content_documents_approval_lifecycle",
        ),
        (
            {"approval_status": "REJECTED", "approval_decided_at": None},
            "ck_content_documents_approval_lifecycle",
        ),
    ],
)
def test_database_rejects_invalid_content_document_review_state(
    client: TestClient,
    db_connection: Connection,
    values: dict,
    constraint_name: str,
) -> None:
    foundation = _foundation(client, "document-review-constraint")
    topic_id = foundation["topic"]["id"]
    version_id = foundation["first_version"]["id"]
    _approved_claim(client, topic_id, "document-review-constraint")
    draft = _create_draft(client, topic_id, version_id)
    _approve_and_release_draft(client, draft["id"])
    package = _create_package(client, version_id)
    document_values = {
        "content_package_id": package["id"],
        "content_version_id": version_id,
        "title": "Content Package",
        "markdown": "# Document\n",
        "sha256": "a" * 64,
        "approval_status": "DRAFT",
        **values,
    }
    with pytest.raises(IntegrityError) as error, db_connection.begin_nested():
        db_connection.execute(insert(ContentDocument).values(**document_values))
    assert error.value.orig.diag.constraint_name == constraint_name


def test_content_document_release_lifecycle_locks_only_document_and_preserves_state(
    client: TestClient,
    db_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _create_content_document_fixture(client, "document-release")
    document = fixture["document"]
    package = fixture["package"]
    draft = fixture["draft"]
    claim_id = fixture["claim_id"]
    assert document["release_status"] == "UNRELEASED"
    assert document["released_at"] is None
    assert document["withdrawn_at"] is None
    assert document["release_note"] is None

    immutable = {
        key: document[key]
        for key in (
            "id",
            "content_package_id",
            "content_version_id",
            "title",
            "markdown",
            "sha256",
            "created_at",
        )
    }
    counts_before = (
        *_content_snapshot_row_counts(db_connection),
        db_connection.scalar(select(func.count()).select_from(ContentDocument)),
    )
    before = client.get(f"/api/v1/content-documents/{document['id']}").json()
    for status in ("DRAFT", "REJECTED"):
        if status == "REJECTED":
            decision = client.post(
                f"/api/v1/content-documents/{document['id']}/approval",
                json={"approval_status": "REJECTED", "reviewer_note": "Rejected"},
            )
            assert decision.status_code == 200
            before = decision.json()
        conflict = client.post(
            f"/api/v1/content-documents/{document['id']}/release",
            json={"release_status": "RELEASED"},
        )
        assert conflict.status_code == 409
        assert conflict.json() == {
            "detail": f"ContentDocument {document['id']} must be approved before release"
        }
        assert client.get(
            f"/api/v1/content-documents/{document['id']}"
        ).json() == before

    approval = client.post(
        f"/api/v1/content-documents/{document['id']}/approval",
        json={"approval_status": "APPROVED", "reviewer_note": "Document review"},
    )
    assert approval.status_code == 200
    approved = approval.json()
    assert approved["release_status"] == "UNRELEASED"
    assert approved["released_at"] is None

    assert client.post(
        f"/api/v1/content-packages/{package['id']}/release",
        json={"release_status": "WITHDRAWN"},
    ).status_code == 200
    assert client.post(
        f"/api/v1/content-packages/{package['id']}/approval",
        json={"approval_status": "REJECTED"},
    ).status_code == 200
    assert client.post(
        f"/api/v1/note-drafts/{draft['id']}/release",
        json={"release_status": "WITHDRAWN"},
    ).status_code == 200
    assert client.post(
        f"/api/v1/note-drafts/{draft['id']}/approval",
        json={"approval_status": "REJECTED"},
    ).status_code == 200
    assert client.post(
        f"/api/v1/claims/{claim_id}/approval",
        json={"approval_status": "REJECTED"},
    ).status_code == 200

    statements: list[str] = []
    commit_count = 0
    original_commit = Session.commit

    def record_sql(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    def count_commit(session):
        nonlocal commit_count
        commit_count += 1
        return original_commit(session)

    monkeypatch.setattr(Session, "commit", count_commit)
    event.listen(db_connection, "before_cursor_execute", record_sql)
    try:
        release = client.post(
            f"/api/v1/content-documents/{document['id']}/release",
            json={"release_status": "RELEASED", "release_note": "Release note"},
        )
    finally:
        event.remove(db_connection, "before_cursor_execute", record_sql)
    assert release.status_code == 200
    released = release.json()
    assert commit_count == 1
    assert {key: released[key] for key in immutable} == immutable
    assert released["approval_status"] == "APPROVED"
    assert released["approval_decided_at"] == approved["approval_decided_at"]
    assert released["reviewer_note"] == "Document review"
    assert released["release_status"] == "RELEASED"
    assert datetime.fromisoformat(
        released["released_at"]
    ).utcoffset() == UTC.utcoffset(None)
    assert released["withdrawn_at"] is None
    assert released["release_note"] == "Release note"
    locking = [statement for statement in statements if "FOR UPDATE" in statement.upper()]
    assert len(locking) == 1
    assert "FOR UPDATE OF content_documents" in locking[0]
    assert "content_packages" not in locking[0]
    assert "note_drafts" not in locking[0]
    assert "question_bank_items" not in locking[0]
    select_statements = [
        statement
        for statement in statements
        if statement.lstrip().upper().startswith("SELECT")
    ]
    assert len(select_statements) == 2
    assert all("content_documents" in statement for statement in select_statements)
    assert all("content_packages" not in statement for statement in select_statements)
    assert all("claims" not in statement for statement in select_statements)
    assert all("verifications" not in statement for statement in select_statements)

    reapproved = client.post(
        f"/api/v1/content-documents/{document['id']}/approval",
        json={"approval_status": "APPROVED", "reviewer_note": "Still approved"},
    )
    assert reapproved.status_code == 200
    assert reapproved.json()["release_status"] == "RELEASED"
    assert reapproved.json()["released_at"] == released["released_at"]
    released = reapproved.json()
    blocked_statements: list[str] = []
    statements.clear()
    event.listen(db_connection, "before_cursor_execute", record_sql)
    for approval_status in ("DRAFT", "REJECTED"):
        try:
            blocked = client.post(
                f"/api/v1/content-documents/{document['id']}/approval",
                json={"approval_status": approval_status},
            )
            blocked_statements.extend(statements)
            statements.clear()
        finally:
            if approval_status == "REJECTED":
                event.remove(db_connection, "before_cursor_execute", record_sql)
        assert blocked.status_code == 409
        assert blocked.json() == {
            "detail": f"ContentDocument {document['id']} must be withdrawn before changing approval"
        }
        assert client.get(
            f"/api/v1/content-documents/{document['id']}"
        ).json() == released
    blocked_locks = [
        statement
        for statement in blocked_statements
        if "FOR UPDATE" in statement.upper()
    ]
    assert len(blocked_locks) == 2
    assert all("FOR UPDATE OF content_documents" in statement for statement in blocked_locks)
    assert all("content_packages" not in statement for statement in blocked_locks)

    duplicate = client.post(
        f"/api/v1/content-documents/{document['id']}/release",
        json={"release_status": "RELEASED"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json() == {
        "detail": f"ContentDocument {document['id']} cannot transition from RELEASED to RELEASED"
    }
    commits_before_withdrawal = commit_count
    withdrawal = client.post(
        f"/api/v1/content-documents/{document['id']}/release",
        json={"release_status": "WITHDRAWN", "release_note": "Withdrawal note"},
    )
    assert withdrawal.status_code == 200
    assert commit_count == commits_before_withdrawal + 1
    withdrawn = withdrawal.json()
    assert withdrawn["released_at"] == released["released_at"]
    assert datetime.fromisoformat(
        withdrawn["withdrawn_at"]
    ).utcoffset() == UTC.utcoffset(None)
    assert withdrawn["release_note"] == "Withdrawal note"
    assert {key: withdrawn[key] for key in immutable} == immutable

    after_withdrawal_review = client.post(
        f"/api/v1/content-documents/{document['id']}/approval",
        json={"approval_status": "REJECTED", "reviewer_note": "After withdrawal"},
    )
    assert after_withdrawal_review.status_code == 200
    reviewed = after_withdrawal_review.json()
    assert reviewed["release_status"] == "WITHDRAWN"
    assert reviewed["released_at"] == withdrawn["released_at"]
    assert reviewed["withdrawn_at"] == withdrawn["withdrawn_at"]
    assert reviewed["release_note"] == "Withdrawal note"
    for decision in ("WITHDRAWN", "RELEASED"):
        conflict = client.post(
            f"/api/v1/content-documents/{document['id']}/release",
            json={"release_status": decision},
        )
        assert conflict.status_code == 409
        assert conflict.json() == {
            "detail": f"ContentDocument {document['id']} cannot transition from WITHDRAWN to {decision}"
        }
        assert client.get(
            f"/api/v1/content-documents/{document['id']}"
        ).json() == reviewed
    assert (
        *_content_snapshot_row_counts(db_connection),
        db_connection.scalar(select(func.count()).select_from(ContentDocument)),
    ) == counts_before


def test_content_document_release_validation_and_premature_withdrawal_do_not_mutate(
    client: TestClient,
    db_connection: Connection,
) -> None:
    fixture = _create_content_document_fixture(client, "document-release-validation")
    document = fixture["document"]
    before = client.get(f"/api/v1/content-documents/{document['id']}").json()
    counts_before = (
        *_content_snapshot_row_counts(db_connection),
        db_connection.scalar(select(func.count()).select_from(ContentDocument)),
    )
    missing = client.post(
        "/api/v1/content-documents/999999/release",
        json={"release_status": "RELEASED"},
    )
    assert missing.status_code == 404
    assert missing.json() == {"detail": "ContentDocument 999999 not found"}
    for payload in (
        {},
        {"release_status": "INVALID"},
        {"release_status": "UNRELEASED"},
        {"release_status": None},
    ):
        response = client.post(
            f"/api/v1/content-documents/{document['id']}/release",
            json=payload,
        )
        assert response.status_code == 422
    premature = client.post(
        f"/api/v1/content-documents/{document['id']}/release",
        json={"release_status": "WITHDRAWN"},
    )
    assert premature.status_code == 409
    assert premature.json() == {
        "detail": f"ContentDocument {document['id']} cannot transition from UNRELEASED to WITHDRAWN"
    }
    assert client.get(f"/api/v1/content-documents/{document['id']}").json() == before
    assert (
        *_content_snapshot_row_counts(db_connection),
        db_connection.scalar(select(func.count()).select_from(ContentDocument)),
    ) == counts_before


def test_content_document_release_failure_rolls_back(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _create_content_document_fixture(client, "document-release-rollback")
    document = fixture["document"]
    approval = client.post(
        f"/api/v1/content-documents/{document['id']}/approval",
        json={"approval_status": "APPROVED", "reviewer_note": "Reviewed"},
    )
    assert approval.status_code == 200
    before = approval.json()
    original = KnowledgeRepository.update_content_document_release

    def fail_after_update(repository, content_document, *args):
        original(repository, content_document, *args)
        raise RuntimeError("injected content document release failure")

    monkeypatch.setattr(
        KnowledgeRepository,
        "update_content_document_release",
        fail_after_update,
    )
    with pytest.raises(RuntimeError, match="injected content document release failure"):
        client.post(
            f"/api/v1/content-documents/{document['id']}/release",
            json={"release_status": "RELEASED", "release_note": "Rollback"},
        )
    assert client.get(f"/api/v1/content-documents/{document['id']}").json() == before


@pytest.mark.parametrize(
    ("values", "constraint_name"),
    [
        ({"release_status": "INVALID"}, "ck_content_documents_release_status"),
        (
            {"release_status": "UNRELEASED", "released_at": datetime.now(UTC)},
            "ck_content_documents_release_lifecycle",
        ),
        (
            {"release_status": "UNRELEASED", "withdrawn_at": datetime.now(UTC)},
            "ck_content_documents_release_lifecycle",
        ),
        (
            {"release_status": "UNRELEASED", "release_note": "Invalid"},
            "ck_content_documents_release_lifecycle",
        ),
        (
            {"release_status": "RELEASED", "released_at": None},
            "ck_content_documents_release_lifecycle",
        ),
        (
            {
                "release_status": "WITHDRAWN",
                "released_at": datetime.now(UTC),
                "withdrawn_at": None,
            },
            "ck_content_documents_release_lifecycle",
        ),
    ],
)
def test_database_rejects_invalid_content_document_release_state(
    client: TestClient,
    db_connection: Connection,
    values: dict,
    constraint_name: str,
) -> None:
    foundation = _foundation(client, "document-release-constraint")
    topic_id = foundation["topic"]["id"]
    version_id = foundation["first_version"]["id"]
    _approved_claim(client, topic_id, "document-release-constraint")
    draft = _create_draft(client, topic_id, version_id)
    _approve_and_release_draft(client, draft["id"])
    package = _create_package(client, version_id)
    document_values = {
        "content_package_id": package["id"],
        "content_version_id": version_id,
        "title": "Content Package",
        "markdown": "# Document\n",
        "sha256": "a" * 64,
        "approval_status": "APPROVED",
        "approval_decided_at": datetime.now(UTC),
        **values,
    }
    with pytest.raises(IntegrityError) as error, db_connection.begin_nested():
        db_connection.execute(insert(ContentDocument).values(**document_values))
    assert error.value.orig.diag.constraint_name == constraint_name


def test_database_blocks_review_change_while_content_document_is_released(
    client: TestClient,
    db_connection: Connection,
) -> None:
    fixture = _create_content_document_fixture(client, "document-release-review-lock")
    document = fixture["document"]
    assert client.post(
        f"/api/v1/content-documents/{document['id']}/approval",
        json={"approval_status": "APPROVED"},
    ).status_code == 200
    assert client.post(
        f"/api/v1/content-documents/{document['id']}/release",
        json={"release_status": "RELEASED"},
    ).status_code == 200
    for approval_status in ("DRAFT", "REJECTED"):
        with pytest.raises(IntegrityError) as error, db_connection.begin_nested():
            db_connection.execute(
                update(ContentDocument)
                .where(ContentDocument.id == document["id"])
                .values(
                    approval_status=approval_status,
                    approval_decided_at=(
                        None if approval_status == "DRAFT" else datetime.now(UTC)
                    ),
                    reviewer_note=None,
                )
            )
        assert (
            error.value.orig.diag.constraint_name
            == "ck_content_documents_release_lifecycle"
        )
