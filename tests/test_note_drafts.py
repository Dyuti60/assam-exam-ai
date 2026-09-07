from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select, update
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import engine, get_db
from app.main import app
from app.models import Claim, ContentVersion, NoteDraft, NoteDraftClaim


@pytest.fixture
def db_connection() -> Generator[Connection, None, None]:
    database_name = engine.url.database or ""
    if not database_name.endswith("_test"):
        pytest.fail("Note draft tests require a dedicated *_test database")

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


def _create_topic(client: TestClient, name: str) -> int:
    response = client.post("/api/v1/topics", json={"name": name})
    assert response.status_code == 201
    return response.json()["id"]


def _create_content_version(
    client: TestClient,
    topic_id: int,
    suffix: str,
) -> int:
    exam_response = client.post(
        "/api/v1/exams",
        json={"code": f"ND-{suffix}", "name": f"Note Draft Exam {suffix}"},
    )
    assert exam_response.status_code == 201
    source_response = client.post(
        "/api/v1/sources",
        json={
            "title": f"Note Draft Syllabus {suffix}",
            "source_type": "official",
            "authority_tier": 1,
            "location": f"https://example.gov/note-draft-{suffix}",
            "license_status": "UNKNOWN",
        },
    )
    assert source_response.status_code == 201
    syllabus_response = client.post(
        "/api/v1/syllabus-versions",
        json={
            "exam_id": exam_response.json()["id"],
            "source_id": source_response.json()["id"],
            "label": "Version 1",
            "topic_ids": [topic_id],
        },
    )
    assert syllabus_response.status_code == 201
    content_version_response = client.post(
        "/api/v1/content-versions",
        json={
            "syllabus_version_id": syllabus_response.json()["id"],
            "topic_id": topic_id,
            "version": 1,
        },
    )
    assert content_version_response.status_code == 201
    return content_version_response.json()["id"]


def _create_claim(
    client: TestClient,
    topic_id: int,
    statement: str,
    approval_status: str,
) -> int:
    response = client.post(
        "/api/v1/claims",
        json={"topic_id": topic_id, "statement": statement},
    )
    assert response.status_code == 201
    claim_id = response.json()["id"]
    if approval_status != "DRAFT":
        approval_response = client.post(
            f"/api/v1/claims/{claim_id}/approval",
            json={"approval_status": approval_status},
        )
        assert approval_response.status_code == 200
    return claim_id


def test_create_note_draft_persists_exact_ordered_provenance(
    client: TestClient,
    db_connection: Connection,
) -> None:
    topic_id = _create_topic(client, "Stored Draft Topic")
    content_version_id = _create_content_version(client, topic_id, "stored")
    other_topic_id = _create_topic(client, "Other Draft Topic")
    claim_specs = [
        (topic_id, "APPROVED", "First stored fact."),
        (topic_id, "DRAFT", "Draft fact must be excluded."),
        (other_topic_id, "APPROVED", "Wrong-topic fact must be excluded."),
        (topic_id, "APPROVED", "Second stored fact."),
        (topic_id, "REJECTED", "Rejected fact must be excluded."),
    ]
    claim_ids = [
        _create_claim(client, selected_topic_id, statement, status)
        for selected_topic_id, status, statement in claim_specs
    ]

    response = client.post(
        f"/api/v1/topics/{topic_id}/note-drafts",
        json={"content_version_id": content_version_id},
    )

    assert response.status_code == 201
    body = response.json()
    assert body == {
        "id": body["id"],
        "topic_id": topic_id,
        "content_version_id": content_version_id,
        "topic_name": "Stored Draft Topic",
        "created_at": body["created_at"],
        "claim_ids": [claim_ids[0], claim_ids[3]],
        "markdown": "# Stored Draft Topic\n\n- First stored fact.\n- Second stored fact.",
        "approval_status": "DRAFT",
        "approval_decided_at": None,
        "reviewer_note": None,
        "release_status": "UNRELEASED",
        "released_at": None,
        "withdrawn_at": None,
        "release_note": None,
    }
    stored_draft = db_connection.execute(
        select(
            NoteDraft.id,
            NoteDraft.topic_id,
            NoteDraft.content_version_id,
            NoteDraft.markdown,
        ).where(
            NoteDraft.id == body["id"]
        )
    ).one()
    assert stored_draft.topic_id == topic_id
    assert stored_draft.content_version_id == content_version_id
    assert stored_draft.markdown == body["markdown"]
    stored_links = db_connection.execute(
        select(NoteDraftClaim.claim_id, NoteDraftClaim.position)
        .where(NoteDraftClaim.note_draft_id == body["id"])
        .order_by(NoteDraftClaim.position)
    ).all()
    assert stored_links == [(claim_ids[0], 0), (claim_ids[3], 1)]


def test_get_note_draft_returns_stored_snapshot_after_claim_state_changes(
    client: TestClient,
) -> None:
    topic_id = _create_topic(client, "Retrieved Draft Topic")
    content_version_id = _create_content_version(client, topic_id, "retrieved")
    claim_ids = [
        _create_claim(client, topic_id, statement, "APPROVED")
        for statement in ["First snapshot fact.", "Second snapshot fact."]
    ]
    create_response = client.post(
        f"/api/v1/topics/{topic_id}/note-drafts",
        json={"content_version_id": content_version_id},
    )
    assert create_response.status_code == 201
    stored_response = create_response.json()

    response = client.get(f"/api/v1/note-drafts/{stored_response['id']}")

    assert response.status_code == 200
    assert response.json() == stored_response
    assert response.json()["claim_ids"] == claim_ids
    assert response.json()["markdown"] == (
        "# Retrieved Draft Topic\n\n"
        "- First snapshot fact.\n"
        "- Second snapshot fact."
    )

    rejection_response = client.post(
        f"/api/v1/claims/{claim_ids[0]}/approval",
        json={"approval_status": "REJECTED"},
    )
    assert rejection_response.status_code == 200

    unchanged_response = client.get(
        f"/api/v1/note-drafts/{stored_response['id']}"
    )
    assert unchanged_response.status_code == 200
    assert unchanged_response.json() == stored_response


def test_get_note_draft_returns_404_for_missing_draft(client: TestClient) -> None:
    response = client.get("/api/v1/note-drafts/999999")

    assert response.status_code == 404
    assert response.json() == {"detail": "NoteDraft 999999 not found"}


def test_get_approved_note_drafts_returns_empty_list(client: TestClient) -> None:
    response = client.get("/api/v1/note-drafts/approved")

    assert response.status_code == 200
    assert response.json() == []


def test_get_approved_note_drafts_filters_orders_and_preserves_snapshots(
    client: TestClient,
) -> None:
    topic_id = _create_topic(client, "Approved Drafts Topic")
    content_version_id = _create_content_version(client, topic_id, "approved-list")
    claim_ids = [
        _create_claim(client, topic_id, statement, "APPROVED")
        for statement in ["First approved snapshot.", "Second approved snapshot."]
    ]
    draft_ids = []
    for status in ["APPROVED", "DRAFT", "REJECTED", "APPROVED"]:
        create_response = client.post(
            f"/api/v1/topics/{topic_id}/note-drafts",
            json={"content_version_id": content_version_id},
        )
        assert create_response.status_code == 201
        draft_id = create_response.json()["id"]
        draft_ids.append(draft_id)
        if status != "DRAFT":
            approval_response = client.post(
                f"/api/v1/note-drafts/{draft_id}/approval",
                json={"approval_status": status},
            )
            assert approval_response.status_code == 200

    rejection_response = client.post(
        f"/api/v1/claims/{claim_ids[0]}/approval",
        json={"approval_status": "REJECTED"},
    )
    assert rejection_response.status_code == 200

    response = client.get("/api/v1/note-drafts/approved")

    assert response.status_code == 200
    body = response.json()
    assert [draft["id"] for draft in body] == [draft_ids[0], draft_ids[3]]
    assert all(
        draft["content_version_id"] == content_version_id for draft in body
    )
    assert all(draft["approval_status"] == "APPROVED" for draft in body)
    assert all(draft["claim_ids"] == claim_ids for draft in body)
    assert all(
        draft["markdown"]
        == (
            "# Approved Drafts Topic\n\n"
            "- First approved snapshot.\n"
            "- Second approved snapshot."
        )
        for draft in body
    )


@pytest.mark.parametrize("approval_status", ["APPROVED", "REJECTED"])
def test_record_note_draft_approval_preserves_snapshot_and_claim_state(
    client: TestClient,
    db_connection: Connection,
    approval_status: str,
) -> None:
    topic_id = _create_topic(client, f"Draft {approval_status} Topic")
    content_version_id = _create_content_version(
        client,
        topic_id,
        f"approval-{approval_status.lower()}",
    )
    claim_id = _create_claim(
        client,
        topic_id,
        f"Fact for {approval_status.lower()} draft.",
        "APPROVED",
    )
    create_response = client.post(
        f"/api/v1/topics/{topic_id}/note-drafts",
        json={"content_version_id": content_version_id},
    )
    assert create_response.status_code == 201
    draft_before = create_response.json()
    claim_before = db_connection.execute(
        select(
            Claim.approval_status,
            Claim.approval_decided_at,
            Claim.reviewer_note,
            Claim.verification_status,
            Claim.confidence,
            Claim.last_verified_at,
        ).where(Claim.id == claim_id)
    ).one()

    response = client.post(
        f"/api/v1/note-drafts/{draft_before['id']}/approval",
        json={
            "approval_status": approval_status,
            "reviewer_note": f"Human draft decision: {approval_status}",
        },
    )

    assert response.status_code == 200
    decided_draft = response.json()
    assert decided_draft["content_version_id"] == content_version_id
    assert decided_draft["approval_status"] == approval_status
    assert decided_draft["approval_decided_at"] is not None
    assert decided_draft["reviewer_note"] == (
        f"Human draft decision: {approval_status}"
    )
    assert decided_draft["release_status"] == "UNRELEASED"
    assert decided_draft["released_at"] is None
    assert decided_draft["withdrawn_at"] is None
    assert decided_draft["release_note"] is None
    assert decided_draft["markdown"] == draft_before["markdown"]
    assert decided_draft["claim_ids"] == draft_before["claim_ids"]
    claim_after = db_connection.execute(
        select(
            Claim.approval_status,
            Claim.approval_decided_at,
            Claim.reviewer_note,
            Claim.verification_status,
            Claim.confidence,
            Claim.last_verified_at,
        ).where(Claim.id == claim_id)
    ).one()
    assert claim_after == claim_before


def test_returning_note_draft_approval_to_draft_clears_decision(
    client: TestClient,
) -> None:
    topic_id = _create_topic(client, "Draft Reset Topic")
    content_version_id = _create_content_version(client, topic_id, "reset")
    _create_claim(client, topic_id, "Fact for reset.", "APPROVED")
    create_response = client.post(
        f"/api/v1/topics/{topic_id}/note-drafts",
        json={"content_version_id": content_version_id},
    )
    assert create_response.status_code == 201
    draft_id = create_response.json()["id"]
    approved_response = client.post(
        f"/api/v1/note-drafts/{draft_id}/approval",
        json={"approval_status": "APPROVED", "reviewer_note": "Approved"},
    )
    assert approved_response.status_code == 200
    assert approved_response.json()["approval_decided_at"] is not None

    response = client.post(
        f"/api/v1/note-drafts/{draft_id}/approval",
        json={
            "approval_status": "DRAFT",
            "reviewer_note": "This note must be discarded",
        },
    )

    assert response.status_code == 200
    assert response.json()["approval_status"] == "DRAFT"
    assert response.json()["approval_decided_at"] is None
    assert response.json()["reviewer_note"] is None


def test_record_note_draft_approval_returns_404_for_missing_draft(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/v1/note-drafts/999999/approval",
        json={"approval_status": "APPROVED"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "NoteDraft 999999 not found"}


def test_record_note_draft_approval_rejects_invalid_status(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/v1/note-drafts/1/approval",
        json={"approval_status": "INVALID"},
    )

    assert response.status_code == 422


def test_database_rejects_invalid_note_draft_approval_status(
    client: TestClient,
    db_connection: Connection,
) -> None:
    topic_id = _create_topic(client, "Draft Approval Constraint Topic")
    content_version_id = _create_content_version(
        client,
        topic_id,
        "approval-constraint",
    )
    _create_claim(client, topic_id, "Constraint approval fact.", "APPROVED")
    create_response = client.post(
        f"/api/v1/topics/{topic_id}/note-drafts",
        json={"content_version_id": content_version_id},
    )
    assert create_response.status_code == 201

    savepoint = db_connection.begin_nested()
    with pytest.raises(IntegrityError):
        db_connection.execute(
            update(NoteDraft)
            .where(NoteDraft.id == create_response.json()["id"])
            .values(approval_status="INVALID")
        )
    savepoint.rollback()


def test_create_note_draft_returns_404_without_persistence(
    client: TestClient,
    db_connection: Connection,
) -> None:
    response = client.post(
        "/api/v1/topics/999999/note-drafts",
        json={"content_version_id": 999999},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Topic 999999 not found"}
    assert db_connection.scalar(select(func.count()).select_from(NoteDraft)) == 0
    assert (
        db_connection.scalar(select(func.count()).select_from(NoteDraftClaim)) == 0
    )


def test_create_note_draft_returns_409_without_approved_claims_atomically(
    client: TestClient,
    db_connection: Connection,
) -> None:
    topic_id = _create_topic(client, "No Approved Draft Topic")
    content_version_id = _create_content_version(client, topic_id, "no-approved")
    _create_claim(client, topic_id, "Still awaiting approval.", "DRAFT")
    _create_claim(client, topic_id, "Explicitly rejected.", "REJECTED")

    response = client.post(
        f"/api/v1/topics/{topic_id}/note-drafts",
        json={"content_version_id": content_version_id},
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": f"Topic {topic_id} has no approved Claims"
    }
    assert db_connection.scalar(select(func.count()).select_from(NoteDraft)) == 0
    assert (
        db_connection.scalar(select(func.count()).select_from(NoteDraftClaim)) == 0
    )


def test_note_draft_claim_constraints_are_enforced(
    client: TestClient,
    db_connection: Connection,
) -> None:
    topic_id = _create_topic(client, "Draft Constraint Topic")
    content_version_id = _create_content_version(client, topic_id, "constraint")
    claim_id = _create_claim(client, topic_id, "Constraint fact.", "APPROVED")
    other_claim_id = _create_claim(client, topic_id, "Other constraint fact.", "DRAFT")
    draft_response = client.post(
        f"/api/v1/topics/{topic_id}/note-drafts",
        json={"content_version_id": content_version_id},
    )
    assert draft_response.status_code == 201

    savepoint = db_connection.begin_nested()
    with pytest.raises(IntegrityError):
        db_connection.execute(
            NoteDraftClaim.__table__.insert().values(
                note_draft_id=draft_response.json()["id"],
                claim_id=other_claim_id,
                position=-1,
            )
        )
    savepoint.rollback()

    duplicate_position = db_connection.begin_nested()
    with pytest.raises(IntegrityError):
        db_connection.execute(
            NoteDraftClaim.__table__.insert().values(
                note_draft_id=draft_response.json()["id"],
                claim_id=other_claim_id,
                position=0,
            )
        )
    duplicate_position.rollback()

    duplicate_claim = db_connection.begin_nested()
    with pytest.raises(IntegrityError):
        db_connection.execute(
            NoteDraftClaim.__table__.insert().values(
                note_draft_id=draft_response.json()["id"],
                claim_id=claim_id,
                position=1,
            )
        )
    duplicate_claim.rollback()


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"content_version_id": 0},
        {"content_version_id": -1},
        {"content_version_id": "not-an-integer"},
        {"content_version_id": 1.5},
    ],
)
def test_create_note_draft_rejects_invalid_content_version_input_without_rows(
    client: TestClient,
    db_connection: Connection,
    payload: dict,
) -> None:
    topic_id = _create_topic(client, f"Invalid ContentVersion {payload}")

    response = client.post(
        f"/api/v1/topics/{topic_id}/note-drafts",
        json=payload,
    )

    assert response.status_code == 422
    assert db_connection.scalar(select(func.count()).select_from(NoteDraft)) == 0
    assert (
        db_connection.scalar(select(func.count()).select_from(NoteDraftClaim)) == 0
    )


def test_create_note_draft_validates_content_version_reference_and_topic_order(
    client: TestClient,
    db_connection: Connection,
) -> None:
    topic_id = _create_topic(client, "ContentVersion Validation Topic")
    other_topic_id = _create_topic(client, "Other ContentVersion Topic")
    other_content_version_id = _create_content_version(
        client,
        other_topic_id,
        "mismatch",
    )
    _create_claim(client, topic_id, "Approved validation fact.", "APPROVED")

    missing_topic = client.post(
        "/api/v1/topics/999999/note-drafts",
        json={"content_version_id": other_content_version_id},
    )
    missing_content_version = client.post(
        f"/api/v1/topics/{topic_id}/note-drafts",
        json={"content_version_id": 999999},
    )
    mismatched = client.post(
        f"/api/v1/topics/{topic_id}/note-drafts",
        json={"content_version_id": other_content_version_id},
    )

    assert missing_topic.status_code == 404
    assert missing_topic.json() == {"detail": "Topic 999999 not found"}
    assert missing_content_version.status_code == 404
    assert missing_content_version.json() == {
        "detail": "ContentVersion 999999 not found"
    }
    assert mismatched.status_code == 409
    assert mismatched.json() == {
        "detail": (
            f"ContentVersion {other_content_version_id} "
            f"does not belong to Topic {topic_id}"
        )
    }
    assert db_connection.scalar(select(func.count()).select_from(NoteDraft)) == 0
    assert (
        db_connection.scalar(select(func.count()).select_from(NoteDraftClaim)) == 0
    )


def test_database_enforces_same_topic_ownership_and_restricts_content_deletion(
    client: TestClient,
    db_connection: Connection,
) -> None:
    topic_id = _create_topic(client, "Owned Draft Topic")
    other_topic_id = _create_topic(client, "Mismatched Draft Topic")
    content_version_id = _create_content_version(client, topic_id, "owned")
    claim_id = _create_claim(client, topic_id, "Owned draft fact.", "APPROVED")

    mismatch_savepoint = db_connection.begin_nested()
    with pytest.raises(IntegrityError):
        db_connection.execute(
            NoteDraft.__table__.insert().values(
                topic_id=other_topic_id,
                content_version_id=content_version_id,
                markdown="# Invalid ownership",
            )
        )
    mismatch_savepoint.rollback()

    created = client.post(
        f"/api/v1/topics/{topic_id}/note-drafts",
        json={"content_version_id": content_version_id},
    )
    assert created.status_code == 201
    assert created.json()["content_version_id"] == content_version_id
    assert created.json()["claim_ids"] == [claim_id]

    deletion_savepoint = db_connection.begin_nested()
    with pytest.raises(IntegrityError):
        db_connection.execute(
            delete(ContentVersion).where(ContentVersion.id == content_version_id)
        )
    deletion_savepoint.rollback()

    retrieved = client.get(f"/api/v1/note-drafts/{created.json()['id']}")
    assert retrieved.status_code == 200
    assert retrieved.json() == created.json()


def test_legacy_null_content_version_draft_remains_retrievable_and_reviewable(
    client: TestClient,
    db_connection: Connection,
) -> None:
    topic_id = _create_topic(client, "Legacy Draft Topic")
    claim_id = _create_claim(client, topic_id, "Legacy stored fact.", "APPROVED")
    decided_at = datetime.now(UTC)
    legacy_id = db_connection.scalar(
        NoteDraft.__table__.insert()
        .values(
            topic_id=topic_id,
            content_version_id=None,
            markdown="# Legacy Draft Topic\n\n- Legacy stored fact.",
            approval_status="APPROVED",
            approval_decided_at=decided_at,
            reviewer_note="Legacy approval",
        )
        .returning(NoteDraft.id)
    )
    assert legacy_id is not None
    db_connection.execute(
        NoteDraftClaim.__table__.insert().values(
            note_draft_id=legacy_id,
            claim_id=claim_id,
            position=0,
        )
    )

    retrieved = client.get(f"/api/v1/note-drafts/{legacy_id}")
    approved = client.get("/api/v1/note-drafts/approved")

    assert retrieved.status_code == 200
    assert retrieved.json()["content_version_id"] is None
    assert retrieved.json()["claim_ids"] == [claim_id]
    assert retrieved.json()["reviewer_note"] == "Legacy approval"
    assert [draft["id"] for draft in approved.json()] == [legacy_id]
    assert approved.json()[0]["content_version_id"] is None

    rejected = client.post(
        f"/api/v1/note-drafts/{legacy_id}/approval",
        json={"approval_status": "REJECTED", "reviewer_note": "Legacy rejected"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["content_version_id"] is None
    assert rejected.json()["approval_status"] == "REJECTED"
    assert rejected.json()["reviewer_note"] == "Legacy rejected"


def test_approved_version_owned_note_draft_can_be_released_without_re_evaluation(
    client: TestClient,
    db_connection: Connection,
) -> None:
    topic_id = _create_topic(client, "Released Draft Topic")
    content_version_id = _create_content_version(client, topic_id, "released")
    claim_id = _create_claim(
        client,
        topic_id,
        "Released draft snapshot fact.",
        "APPROVED",
    )
    created = client.post(
        f"/api/v1/topics/{topic_id}/note-drafts",
        json={"content_version_id": content_version_id},
    )
    assert created.status_code == 201
    approved = client.post(
        f"/api/v1/note-drafts/{created.json()['id']}/approval",
        json={"approval_status": "APPROVED", "reviewer_note": "Reviewed"},
    )
    assert approved.status_code == 200
    approved_snapshot = approved.json()

    claim_rejection = client.post(
        f"/api/v1/claims/{claim_id}/approval",
        json={"approval_status": "REJECTED"},
    )
    assert claim_rejection.status_code == 200
    unrelated_draft = db_connection.scalar(
        NoteDraft.__table__.insert()
        .values(
            topic_id=topic_id,
            content_version_id=None,
            markdown="# Unrelated",
            approval_status="APPROVED",
            approval_decided_at=datetime.now(UTC),
        )
        .returning(NoteDraft.id)
    )
    assert unrelated_draft is not None

    released = client.post(
        f"/api/v1/note-drafts/{created.json()['id']}/release",
        json={"release_status": "RELEASED", "release_note": "Internal release"},
    )

    assert released.status_code == 200
    released_body = released.json()
    assert released_body["release_status"] == "RELEASED"
    assert released_body["released_at"] is not None
    assert datetime.fromisoformat(
        released_body["released_at"]
    ).utcoffset() == UTC.utcoffset(None)
    assert released_body["withdrawn_at"] is None
    assert released_body["release_note"] == "Internal release"
    for field in (
        "topic_id",
        "content_version_id",
        "topic_name",
        "created_at",
        "claim_ids",
        "markdown",
        "approval_status",
        "approval_decided_at",
        "reviewer_note",
    ):
        assert released_body[field] == approved_snapshot[field]


@pytest.mark.parametrize("approval_status", ["DRAFT", "REJECTED"])
def test_unapproved_note_draft_cannot_be_released_without_mutation(
    client: TestClient,
    approval_status: str,
) -> None:
    topic_id = _create_topic(client, f"Unapproved Release {approval_status}")
    content_version_id = _create_content_version(
        client,
        topic_id,
        f"unapproved-{approval_status.lower()}",
    )
    _create_claim(client, topic_id, "Approved source fact.", "APPROVED")
    created = client.post(
        f"/api/v1/topics/{topic_id}/note-drafts",
        json={"content_version_id": content_version_id},
    )
    assert created.status_code == 201
    if approval_status == "REJECTED":
        decision = client.post(
            f"/api/v1/note-drafts/{created.json()['id']}/approval",
            json={"approval_status": "REJECTED", "reviewer_note": "Rejected"},
        )
        assert decision.status_code == 200
    before = client.get(f"/api/v1/note-drafts/{created.json()['id']}").json()

    response = client.post(
        f"/api/v1/note-drafts/{created.json()['id']}/release",
        json={"release_status": "RELEASED"},
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": f"NoteDraft {created.json()['id']} must be approved before release"
    }
    after = client.get(f"/api/v1/note-drafts/{created.json()['id']}").json()
    assert after == before


def test_approved_legacy_note_draft_cannot_be_released_without_mutation(
    client: TestClient,
    db_connection: Connection,
) -> None:
    topic_id = _create_topic(client, "Legacy Release Topic")
    legacy_id = db_connection.scalar(
        NoteDraft.__table__.insert()
        .values(
            topic_id=topic_id,
            content_version_id=None,
            markdown="# Legacy Release Topic",
            approval_status="APPROVED",
            approval_decided_at=datetime.now(UTC),
        )
        .returning(NoteDraft.id)
    )
    assert legacy_id is not None
    before = client.get(f"/api/v1/note-drafts/{legacy_id}").json()

    response = client.post(
        f"/api/v1/note-drafts/{legacy_id}/release",
        json={"release_status": "RELEASED"},
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": f"NoteDraft {legacy_id} must have a ContentVersion before release"
    }
    assert client.get(f"/api/v1/note-drafts/{legacy_id}").json() == before


def test_note_draft_release_transition_rules_and_withdrawal_snapshot(
    client: TestClient,
) -> None:
    topic_id = _create_topic(client, "Withdrawal Topic")
    content_version_id = _create_content_version(client, topic_id, "withdrawal")
    _create_claim(client, topic_id, "Withdrawal snapshot fact.", "APPROVED")
    created = client.post(
        f"/api/v1/topics/{topic_id}/note-drafts",
        json={"content_version_id": content_version_id},
    )
    draft_id = created.json()["id"]
    approved = client.post(
        f"/api/v1/note-drafts/{draft_id}/approval",
        json={"approval_status": "APPROVED", "reviewer_note": "Approved"},
    )
    assert approved.status_code == 200

    premature_withdrawal = client.post(
        f"/api/v1/note-drafts/{draft_id}/release",
        json={"release_status": "WITHDRAWN"},
    )
    assert premature_withdrawal.status_code == 409
    assert premature_withdrawal.json() == {
        "detail": (
            f"NoteDraft {draft_id} cannot transition from UNRELEASED to WITHDRAWN"
        )
    }
    assert client.get(f"/api/v1/note-drafts/{draft_id}").json() == approved.json()

    released = client.post(
        f"/api/v1/note-drafts/{draft_id}/release",
        json={"release_status": "RELEASED", "release_note": "Release note"},
    )
    assert released.status_code == 200
    released_snapshot = released.json()

    duplicate_release = client.post(
        f"/api/v1/note-drafts/{draft_id}/release",
        json={"release_status": "RELEASED"},
    )
    assert duplicate_release.status_code == 409
    assert duplicate_release.json() == {
        "detail": f"NoteDraft {draft_id} cannot transition from RELEASED to RELEASED"
    }
    assert client.get(f"/api/v1/note-drafts/{draft_id}").json() == released_snapshot

    withdrawn = client.post(
        f"/api/v1/note-drafts/{draft_id}/release",
        json={"release_status": "WITHDRAWN", "release_note": "Withdrawn note"},
    )
    assert withdrawn.status_code == 200
    withdrawn_snapshot = withdrawn.json()
    assert withdrawn_snapshot["release_status"] == "WITHDRAWN"
    assert withdrawn_snapshot["released_at"] == released_snapshot["released_at"]
    assert withdrawn_snapshot["withdrawn_at"] is not None
    assert datetime.fromisoformat(
        withdrawn_snapshot["withdrawn_at"]
    ).utcoffset() == UTC.utcoffset(None)
    assert withdrawn_snapshot["release_note"] == "Withdrawn note"

    for requested_status in ("WITHDRAWN", "RELEASED"):
        conflict = client.post(
            f"/api/v1/note-drafts/{draft_id}/release",
            json={"release_status": requested_status},
        )
        assert conflict.status_code == 409
        assert conflict.json() == {
            "detail": (
                f"NoteDraft {draft_id} cannot transition "
                f"from WITHDRAWN to {requested_status}"
            )
        }
        assert client.get(f"/api/v1/note-drafts/{draft_id}").json() == (
            withdrawn_snapshot
        )


def test_released_note_draft_blocks_review_change_until_withdrawn(
    client: TestClient,
) -> None:
    topic_id = _create_topic(client, "Release Review Lock Topic")
    content_version_id = _create_content_version(client, topic_id, "review-lock")
    _create_claim(client, topic_id, "Release lock fact.", "APPROVED")
    created = client.post(
        f"/api/v1/topics/{topic_id}/note-drafts",
        json={"content_version_id": content_version_id},
    )
    draft_id = created.json()["id"]
    approved = client.post(
        f"/api/v1/note-drafts/{draft_id}/approval",
        json={"approval_status": "APPROVED", "reviewer_note": "Review retained"},
    )
    assert approved.status_code == 200
    released = client.post(
        f"/api/v1/note-drafts/{draft_id}/release",
        json={"release_status": "RELEASED", "release_note": "Release retained"},
    )
    assert released.status_code == 200

    for approval_status in ("DRAFT", "REJECTED"):
        conflict = client.post(
            f"/api/v1/note-drafts/{draft_id}/approval",
            json={"approval_status": approval_status},
        )
        assert conflict.status_code == 409
        assert conflict.json() == {
            "detail": (
                f"NoteDraft {draft_id} must be withdrawn before changing approval"
            )
        }
        assert client.get(f"/api/v1/note-drafts/{draft_id}").json() == released.json()

    withdrawn = client.post(
        f"/api/v1/note-drafts/{draft_id}/release",
        json={"release_status": "WITHDRAWN", "release_note": "Withdraw first"},
    )
    assert withdrawn.status_code == 200
    rejected = client.post(
        f"/api/v1/note-drafts/{draft_id}/approval",
        json={"approval_status": "REJECTED", "reviewer_note": "Post-withdrawal"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["approval_status"] == "REJECTED"
    assert rejected.json()["release_status"] == "WITHDRAWN"
    assert rejected.json()["released_at"] == withdrawn.json()["released_at"]
    assert rejected.json()["withdrawn_at"] == withdrawn.json()["withdrawn_at"]
    assert rejected.json()["release_note"] == "Withdraw first"


def test_note_draft_release_missing_and_invalid_requests(client: TestClient) -> None:
    missing = client.post(
        "/api/v1/note-drafts/999999/release",
        json={"release_status": "RELEASED"},
    )
    assert missing.status_code == 404
    assert missing.json() == {"detail": "NoteDraft 999999 not found"}

    for payload in ({}, {"release_status": "UNRELEASED"}, {"release_status": "INVALID"}):
        response = client.post("/api/v1/note-drafts/1/release", json=payload)
        assert response.status_code == 422


def test_approved_note_draft_collection_remains_approval_only_with_release_metadata(
    client: TestClient,
) -> None:
    topic_id = _create_topic(client, "Approval Boundary Release Topic")
    content_version_id = _create_content_version(client, topic_id, "approval-boundary")
    _create_claim(client, topic_id, "Approval boundary fact.", "APPROVED")
    draft_ids = []
    for _ in range(3):
        created = client.post(
            f"/api/v1/topics/{topic_id}/note-drafts",
            json={"content_version_id": content_version_id},
        )
        draft_ids.append(created.json()["id"])
        approved = client.post(
            f"/api/v1/note-drafts/{created.json()['id']}/approval",
            json={"approval_status": "APPROVED"},
        )
        assert approved.status_code == 200

    released = client.post(
        f"/api/v1/note-drafts/{draft_ids[1]}/release",
        json={"release_status": "RELEASED"},
    )
    assert released.status_code == 200
    released_then_withdrawn = client.post(
        f"/api/v1/note-drafts/{draft_ids[2]}/release",
        json={"release_status": "RELEASED"},
    )
    assert released_then_withdrawn.status_code == 200
    withdrawn = client.post(
        f"/api/v1/note-drafts/{draft_ids[2]}/release",
        json={"release_status": "WITHDRAWN"},
    )
    assert withdrawn.status_code == 200

    response = client.get("/api/v1/note-drafts/approved")

    assert response.status_code == 200
    assert [draft["id"] for draft in response.json()] == draft_ids
    assert [draft["release_status"] for draft in response.json()] == [
        "UNRELEASED",
        "RELEASED",
        "WITHDRAWN",
    ]
    assert response.json()[1]["released_at"] == released.json()["released_at"]
    assert response.json()[2]["withdrawn_at"] == withdrawn.json()["withdrawn_at"]


def test_other_state_cannot_substitute_for_target_note_draft_approval(
    client: TestClient,
) -> None:
    topic_id = _create_topic(client, "Independent Draft Release Topic")
    content_version_id = _create_content_version(client, topic_id, "independence")
    claim_id = _create_claim(
        client,
        topic_id,
        "Independently approved fact.",
        "APPROVED",
    )
    target = client.post(
        f"/api/v1/topics/{topic_id}/note-drafts",
        json={"content_version_id": content_version_id},
    )
    assert target.status_code == 201
    target_snapshot = target.json()

    source = client.post(
        "/api/v1/sources",
        json={
            "title": "Independent release evidence",
            "source_type": "official",
            "authority_tier": 1,
            "location": "https://example.gov/independent-release",
            "license_status": "UNKNOWN",
        },
    )
    assert source.status_code == 201
    evidence = client.post(
        "/api/v1/evidence",
        json={"source_id": source.json()["id"], "content": "Supporting evidence."},
    )
    assert evidence.status_code == 201
    verification = client.post(
        "/api/v1/verifications",
        json={
            "claim_id": claim_id,
            "verdict": "SUPPORTED",
            "confidence": 1.0,
            "evidence": [
                {
                    "evidence_id": evidence.json()["id"],
                    "evidence_role": "SUPPORTS",
                    "position": 0,
                }
            ],
        },
    )
    assert verification.status_code == 201

    question = client.post(
        "/api/v1/question-bank-items",
        json={
            "content_version_id": content_version_id,
            "question_text": "Which fact is independently supported?",
            "explanation": "The stored Claim provides the answer.",
            "difficulty": "EASY",
            "claim_ids": [claim_id],
            "options": ["The stored fact", "An unrelated fact"],
            "correct_option_position": 0,
        },
    )
    assert question.status_code == 201
    question_approval = client.post(
        f"/api/v1/question-bank-items/{question.json()['id']}/approval",
        json={"approval_status": "APPROVED"},
    )
    assert question_approval.status_code == 200
    question_release = client.post(
        f"/api/v1/question-bank-items/{question.json()['id']}/release",
        json={"release_status": "RELEASED"},
    )
    assert question_release.status_code == 200

    other_draft = client.post(
        f"/api/v1/topics/{topic_id}/note-drafts",
        json={"content_version_id": content_version_id},
    )
    assert other_draft.status_code == 201
    other_approval = client.post(
        f"/api/v1/note-drafts/{other_draft.json()['id']}/approval",
        json={"approval_status": "APPROVED"},
    )
    assert other_approval.status_code == 200
    other_release = client.post(
        f"/api/v1/note-drafts/{other_draft.json()['id']}/release",
        json={"release_status": "RELEASED"},
    )
    assert other_release.status_code == 200

    response = client.post(
        f"/api/v1/note-drafts/{target.json()['id']}/release",
        json={"release_status": "RELEASED"},
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": f"NoteDraft {target.json()['id']} must be approved before release"
    }
    assert client.get(f"/api/v1/note-drafts/{target.json()['id']}").json() == (
        target_snapshot
    )


@pytest.mark.parametrize(
    "invalid_values",
    [
        {"release_status": "INVALID"},
        {"release_status": "UNRELEASED", "release_note": "not allowed"},
        {"release_status": "UNRELEASED", "released_at": datetime.now(UTC)},
        {"release_status": "RELEASED"},
        {
            "release_status": "RELEASED",
            "released_at": datetime.now(UTC),
            "approval_status": "DRAFT",
        },
        {
            "release_status": "RELEASED",
            "released_at": datetime.now(UTC),
            "withdrawn_at": datetime.now(UTC),
        },
        {
            "release_status": "WITHDRAWN",
            "released_at": datetime.now(UTC),
        },
        {
            "release_status": "WITHDRAWN",
            "withdrawn_at": datetime.now(UTC),
        },
    ],
)
def test_database_rejects_invalid_note_draft_release_states(
    client: TestClient,
    db_connection: Connection,
    invalid_values: dict,
) -> None:
    topic_id = _create_topic(client, f"Release Constraint {invalid_values}")
    content_version_id = _create_content_version(
        client,
        topic_id,
        f"release-constraint-{len(str(invalid_values))}",
    )
    _create_claim(client, topic_id, "Release constraint fact.", "APPROVED")
    created = client.post(
        f"/api/v1/topics/{topic_id}/note-drafts",
        json={"content_version_id": content_version_id},
    )
    assert created.status_code == 201
    draft_id = created.json()["id"]

    savepoint = db_connection.begin_nested()
    with pytest.raises(IntegrityError):
        db_connection.execute(
            update(NoteDraft).where(NoteDraft.id == draft_id).values(**invalid_values)
        )
    savepoint.rollback()
    assert client.get(f"/api/v1/note-drafts/{draft_id}").json() == created.json()


@pytest.mark.parametrize("release_status", ["RELEASED", "WITHDRAWN"])
def test_database_rejects_released_state_without_content_version(
    client: TestClient,
    db_connection: Connection,
    release_status: str,
) -> None:
    topic_id = _create_topic(client, f"No Owner {release_status}")
    values = {
        "topic_id": topic_id,
        "content_version_id": None,
        "markdown": "# Ownerless",
        "approval_status": "APPROVED",
        "approval_decided_at": datetime.now(UTC),
        "release_status": release_status,
        "released_at": datetime.now(UTC),
    }
    if release_status == "WITHDRAWN":
        values["withdrawn_at"] = datetime.now(UTC)

    savepoint = db_connection.begin_nested()
    with pytest.raises(IntegrityError):
        db_connection.execute(NoteDraft.__table__.insert().values(**values))
    savepoint.rollback()
