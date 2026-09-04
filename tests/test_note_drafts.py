from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import engine, get_db
from app.main import app
from app.models import NoteDraft, NoteDraftClaim


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
