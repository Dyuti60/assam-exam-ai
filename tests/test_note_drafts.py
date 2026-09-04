from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import engine, get_db
from app.main import app
from app.models import Claim, NoteDraft, NoteDraftClaim


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

    response = client.post(f"/api/v1/topics/{topic_id}/note-drafts")

    assert response.status_code == 201
    body = response.json()
    assert body == {
        "id": body["id"],
        "topic_id": topic_id,
        "topic_name": "Stored Draft Topic",
        "created_at": body["created_at"],
        "claim_ids": [claim_ids[0], claim_ids[3]],
        "markdown": "# Stored Draft Topic\n\n- First stored fact.\n- Second stored fact.",
        "approval_status": "DRAFT",
        "approval_decided_at": None,
        "reviewer_note": None,
    }
    stored_draft = db_connection.execute(
        select(NoteDraft.id, NoteDraft.topic_id, NoteDraft.markdown).where(
            NoteDraft.id == body["id"]
        )
    ).one()
    assert stored_draft.topic_id == topic_id
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
    claim_ids = [
        _create_claim(client, topic_id, statement, "APPROVED")
        for statement in ["First snapshot fact.", "Second snapshot fact."]
    ]
    create_response = client.post(f"/api/v1/topics/{topic_id}/note-drafts")
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
    claim_ids = [
        _create_claim(client, topic_id, statement, "APPROVED")
        for statement in ["First approved snapshot.", "Second approved snapshot."]
    ]
    draft_ids = []
    for status in ["APPROVED", "DRAFT", "REJECTED", "APPROVED"]:
        create_response = client.post(f"/api/v1/topics/{topic_id}/note-drafts")
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
    claim_id = _create_claim(
        client,
        topic_id,
        f"Fact for {approval_status.lower()} draft.",
        "APPROVED",
    )
    create_response = client.post(f"/api/v1/topics/{topic_id}/note-drafts")
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
    assert decided_draft["approval_status"] == approval_status
    assert decided_draft["approval_decided_at"] is not None
    assert decided_draft["reviewer_note"] == (
        f"Human draft decision: {approval_status}"
    )
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
    _create_claim(client, topic_id, "Fact for reset.", "APPROVED")
    create_response = client.post(f"/api/v1/topics/{topic_id}/note-drafts")
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
    _create_claim(client, topic_id, "Constraint approval fact.", "APPROVED")
    create_response = client.post(f"/api/v1/topics/{topic_id}/note-drafts")
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
    response = client.post("/api/v1/topics/999999/note-drafts")

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
    _create_claim(client, topic_id, "Still awaiting approval.", "DRAFT")
    _create_claim(client, topic_id, "Explicitly rejected.", "REJECTED")

    response = client.post(f"/api/v1/topics/{topic_id}/note-drafts")

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
    claim_id = _create_claim(client, topic_id, "Constraint fact.", "APPROVED")
    other_claim_id = _create_claim(client, topic_id, "Other constraint fact.", "DRAFT")
    draft_response = client.post(f"/api/v1/topics/{topic_id}/note-drafts")
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
