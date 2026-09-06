from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select, update
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import engine, get_db
from app.main import app
from app.models import (
    Claim,
    ContentVersion,
    QuestionBankItem,
    QuestionBankItemClaim,
    QuestionBankOption,
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


def _foundation(client: TestClient, suffix: str = "A") -> tuple[int, int]:
    exam = _post(
        client,
        "/api/v1/exams",
        {"code": f"QB-{suffix}", "name": f"Question Bank Exam {suffix}"},
    )
    source = _post(
        client,
        "/api/v1/sources",
        {
            "title": f"Question Bank Syllabus {suffix}",
            "source_type": "official",
            "authority_tier": 1,
            "location": f"https://example.gov/qb-{suffix}",
            "license_status": "UNKNOWN",
        },
    )
    topic = _post(client, "/api/v1/topics", {"name": f"QB Topic {suffix}"})
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


def _claim(
    client: TestClient,
    topic_id: int,
    suffix: str,
    approval_status: str = "APPROVED",
) -> int:
    claim = _post(
        client,
        "/api/v1/claims",
        {"statement": f"Grounded fact {suffix}", "topic_id": topic_id},
    )
    if approval_status != "DRAFT":
        response = client.post(
            f"/api/v1/claims/{claim['id']}/approval",
            json={"approval_status": approval_status},
        )
        assert response.status_code == 200
    return claim["id"]


def _item_payload(content_version_id: int, claim_ids: list[int]) -> dict:
    return {
        "content_version_id": content_version_id,
        "question_text": "Which statement is supported?",
        "explanation": "The approved Claims provide the grounding.",
        "difficulty": "MEDIUM",
        "claim_ids": claim_ids,
        "options": ["First option", "Second option"],
        "correct_option_position": 1,
    }


def test_create_and_retrieve_item_preserves_ordered_claim_provenance(
    client: TestClient,
) -> None:
    content_version_id, topic_id = _foundation(client)
    first_claim_id = _claim(client, topic_id, "first")
    second_claim_id = _claim(client, topic_id, "second")
    payload = _item_payload(
        content_version_id,
        [second_claim_id, first_claim_id],
    )

    created = _post(client, "/api/v1/question-bank-items", payload)
    retrieved = client.get(f"/api/v1/question-bank-items/{created['id']}")

    assert created == {
        **payload,
        "id": created["id"],
        "created_at": created["created_at"],
        "approval_status": "DRAFT",
        "approval_decided_at": None,
        "reviewer_note": None,
    }
    assert retrieved.status_code == 200
    assert retrieved.json() == created


def test_missing_content_version_returns_404_without_partial_rows(
    client: TestClient,
    db_connection: Connection,
) -> None:
    response = client.post(
        "/api/v1/question-bank-items",
        json=_item_payload(999991, [1]),
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "ContentVersion 999991 not found"}
    assert db_connection.scalar(select(func.count()).select_from(QuestionBankItem)) == 0


def test_missing_claim_returns_404_atomically(
    client: TestClient,
    db_connection: Connection,
) -> None:
    content_version_id, topic_id = _foundation(client)
    claim_id = _claim(client, topic_id, "existing")

    response = client.post(
        "/api/v1/question-bank-items",
        json=_item_payload(content_version_id, [claim_id, 999992]),
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Claim 999992 not found"}
    assert db_connection.scalar(select(func.count()).select_from(QuestionBankItem)) == 0
    assert (
        db_connection.scalar(
            select(func.count()).select_from(QuestionBankItemClaim)
        )
        == 0
    )
    assert (
        db_connection.scalar(select(func.count()).select_from(QuestionBankOption))
        == 0
    )


def test_get_missing_item_returns_established_404(client: TestClient) -> None:
    response = client.get("/api/v1/question-bank-items/999993")

    assert response.status_code == 404
    assert response.json() == {"detail": "QuestionBankItem 999993 not found"}


@pytest.mark.parametrize("approval_status", ["DRAFT", "REJECTED"])
def test_unapproved_claim_returns_stable_conflict(
    client: TestClient,
    db_connection: Connection,
    approval_status: str,
) -> None:
    content_version_id, topic_id = _foundation(client, approval_status)
    claim_id = _claim(client, topic_id, approval_status, approval_status)

    response = client.post(
        "/api/v1/question-bank-items",
        json=_item_payload(content_version_id, [claim_id]),
    )

    assert response.status_code == 409
    assert response.json() == {"detail": f"Claim {claim_id} is not approved"}
    assert db_connection.scalar(select(func.count()).select_from(QuestionBankItem)) == 0


def test_wrong_topic_claim_returns_stable_conflict(
    client: TestClient,
    db_connection: Connection,
) -> None:
    content_version_id, content_topic_id = _foundation(client, "main")
    _, other_topic_id = _foundation(client, "other")
    claim_id = _claim(client, other_topic_id, "wrong-topic")

    response = client.post(
        "/api/v1/question-bank-items",
        json=_item_payload(content_version_id, [claim_id]),
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": (
            f"Claim {claim_id} does not match ContentVersion "
            f"Topic {content_topic_id}"
        )
    }
    assert db_connection.scalar(select(func.count()).select_from(QuestionBankItem)) == 0


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("claim_ids", []),
        ("claim_ids", [1, 1]),
        ("claim_ids", [0]),
        ("claim_ids", [-1]),
        ("question_text", "   "),
        ("explanation", "\t"),
        ("difficulty", "EXPERT"),
        ("options", []),
        ("options", ["Only one"]),
        ("options", ["Valid", "  "]),
        ("correct_option_position", -1),
        ("correct_option_position", 2),
    ],
)
def test_invalid_item_input_returns_422(
    client: TestClient,
    field: str,
    value: object,
) -> None:
    payload = _item_payload(1, [1])
    payload[field] = value

    response = client.post("/api/v1/question-bank-items", json=payload)

    assert response.status_code == 422


def test_missing_correct_option_position_returns_422(client: TestClient) -> None:
    payload = _item_payload(1, [1])
    payload.pop("correct_option_position")

    response = client.post("/api/v1/question-bank-items", json=payload)

    assert response.status_code == 422


def test_database_constraints_reject_invalid_item_and_link_rows(
    client: TestClient,
    db_connection: Connection,
) -> None:
    content_version_id, topic_id = _foundation(client)
    first_claim_id = _claim(client, topic_id, "constraint-one")
    second_claim_id = _claim(client, topic_id, "constraint-two")
    item = _post(
        client,
        "/api/v1/question-bank-items",
        _item_payload(content_version_id, [first_claim_id]),
    )
    invalid_statements = [
        QuestionBankItem.__table__.insert().values(
            content_version_id=content_version_id,
            question_text=" ",
            explanation="valid",
            difficulty="EASY",
        ),
        QuestionBankItem.__table__.insert().values(
            content_version_id=content_version_id,
            question_text="valid",
            explanation="\t",
            difficulty="EASY",
        ),
        QuestionBankItem.__table__.insert().values(
            content_version_id=content_version_id,
            question_text="valid",
            explanation="valid",
            difficulty="EXPERT",
        ),
        QuestionBankItemClaim.__table__.insert().values(
            question_bank_item_id=item["id"],
            claim_id=second_claim_id,
            position=-1,
        ),
        QuestionBankItemClaim.__table__.insert().values(
            question_bank_item_id=item["id"],
            claim_id=second_claim_id,
            position=0,
        ),
        QuestionBankItemClaim.__table__.insert().values(
            question_bank_item_id=item["id"],
            claim_id=first_claim_id,
            position=1,
        ),
    ]

    for statement in invalid_statements:
        savepoint = db_connection.begin_nested()
        with pytest.raises(IntegrityError):
            db_connection.execute(statement)
        savepoint.rollback()


def test_item_provenance_restricts_content_version_and_claim_deletion(
    client: TestClient,
    db_connection: Connection,
) -> None:
    content_version_id, topic_id = _foundation(client)
    claim_id = _claim(client, topic_id, "protected")
    _post(
        client,
        "/api/v1/question-bank-items",
        _item_payload(content_version_id, [claim_id]),
    )

    for statement in [
        delete(ContentVersion).where(ContentVersion.id == content_version_id),
        delete(Claim).where(Claim.id == claim_id),
    ]:
        savepoint = db_connection.begin_nested()
        with pytest.raises(IntegrityError):
            db_connection.execute(statement)
        savepoint.rollback()


def test_retrieval_is_stored_snapshot_after_claim_approval_changes(
    client: TestClient,
) -> None:
    content_version_id, topic_id = _foundation(client)
    claim_id = _claim(client, topic_id, "snapshot")
    created = _post(
        client,
        "/api/v1/question-bank-items",
        _item_payload(content_version_id, [claim_id]),
    )

    reset = client.post(
        f"/api/v1/claims/{claim_id}/approval",
        json={"approval_status": "DRAFT", "reviewer_note": "ignored"},
    )
    retrieved = client.get(f"/api/v1/question-bank-items/{created['id']}")

    assert reset.status_code == 200
    assert reset.json()["approval_status"] == "DRAFT"
    assert retrieved.status_code == 200
    assert retrieved.json() == created


def test_option_database_constraints_and_same_item_answer_integrity(
    client: TestClient,
    db_connection: Connection,
) -> None:
    content_version_id, topic_id = _foundation(client)
    claim_id = _claim(client, topic_id, "option-constraints")
    first = _post(
        client,
        "/api/v1/question-bank-items",
        _item_payload(content_version_id, [claim_id]),
    )
    second = _post(
        client,
        "/api/v1/question-bank-items",
        {
            **_item_payload(content_version_id, [claim_id]),
            "question_text": "A second candidate?",
        },
    )
    first_options = db_connection.execute(
        select(QuestionBankOption.id, QuestionBankOption.position).where(
            QuestionBankOption.question_bank_item_id == first["id"]
        )
    ).all()
    second_option_id = db_connection.scalar(
        select(QuestionBankOption.id).where(
            QuestionBankOption.question_bank_item_id == second["id"],
            QuestionBankOption.position == 0,
        )
    )
    assert second_option_id is not None
    invalid_statements = [
        QuestionBankOption.__table__.insert().values(
            question_bank_item_id=first["id"],
            position=-1,
            option_text="Valid",
        ),
        QuestionBankOption.__table__.insert().values(
            question_bank_item_id=first["id"],
            position=0,
            option_text="Duplicate position",
        ),
        QuestionBankOption.__table__.insert().values(
            question_bank_item_id=first["id"],
            position=2,
            option_text="\t",
        ),
        update(QuestionBankItem)
        .where(QuestionBankItem.id == first["id"])
        .values(correct_option_id=second_option_id),
        delete(QuestionBankOption).where(
            QuestionBankOption.id
            == next(
                option.id
                for option in first_options
                if option.position == first["correct_option_position"]
            )
        ),
    ]

    for statement in invalid_statements:
        savepoint = db_connection.begin_nested()
        with pytest.raises(IntegrityError):
            db_connection.execute(statement)
        savepoint.rollback()


def test_deleting_item_cascades_only_its_dependent_rows(
    client: TestClient,
    db_connection: Connection,
) -> None:
    content_version_id, topic_id = _foundation(client)
    claim_id = _claim(client, topic_id, "cascade")
    item = _post(
        client,
        "/api/v1/question-bank-items",
        _item_payload(content_version_id, [claim_id]),
    )

    db_connection.execute(
        delete(QuestionBankItem).where(QuestionBankItem.id == item["id"])
    )

    assert db_connection.scalar(
        select(func.count()).select_from(QuestionBankOption)
    ) == 0
    assert db_connection.scalar(
        select(func.count()).select_from(QuestionBankItemClaim)
    ) == 0
    assert db_connection.scalar(select(func.count()).select_from(Claim)) == 1
    assert (
        db_connection.scalar(select(func.count()).select_from(ContentVersion)) == 1
    )


def test_legacy_item_without_options_remains_retrievable(
    client: TestClient,
    db_connection: Connection,
) -> None:
    content_version_id, _ = _foundation(client)
    legacy_id = db_connection.scalar(
        QuestionBankItem.__table__.insert()
        .values(
            content_version_id=content_version_id,
            question_text="Legacy candidate",
            explanation="Created before complete MCQ options.",
            difficulty="EASY",
        )
        .returning(QuestionBankItem.id)
    )
    assert legacy_id is not None

    response = client.get(f"/api/v1/question-bank-items/{legacy_id}")

    assert response.status_code == 200
    assert response.json()["options"] == []
    assert response.json()["correct_option_position"] is None
    assert response.json()["approval_status"] == "DRAFT"
    assert response.json()["approval_decided_at"] is None
    assert response.json()["reviewer_note"] is None


@pytest.mark.parametrize("approval_status", ["APPROVED", "REJECTED"])
def test_record_item_decision_preserves_complete_stored_snapshot(
    client: TestClient,
    db_connection: Connection,
    approval_status: str,
) -> None:
    content_version_id, topic_id = _foundation(client, approval_status)
    claim_id = _claim(client, topic_id, approval_status)
    created = _post(
        client,
        "/api/v1/question-bank-items",
        _item_payload(content_version_id, [claim_id]),
    )

    response = client.post(
        f"/api/v1/question-bank-items/{created['id']}/approval",
        json={
            "approval_status": approval_status,
            "reviewer_note": f"Human decision: {approval_status}",
        },
    )

    assert response.status_code == 200
    decided = response.json()
    assert decided["approval_status"] == approval_status
    assert decided["approval_decided_at"] is not None
    assert decided["reviewer_note"] == f"Human decision: {approval_status}"
    for field in (
        "content_version_id",
        "question_text",
        "explanation",
        "difficulty",
        "claim_ids",
        "options",
        "correct_option_position",
        "created_at",
    ):
        assert decided[field] == created[field]
    assert db_connection.scalar(select(Claim.approval_status).where(Claim.id == claim_id)) == "APPROVED"


def test_returning_item_to_draft_clears_decision_metadata(
    client: TestClient,
) -> None:
    content_version_id, topic_id = _foundation(client, "reset")
    claim_id = _claim(client, topic_id, "reset")
    item = _post(
        client,
        "/api/v1/question-bank-items",
        _item_payload(content_version_id, [claim_id]),
    )
    approved = client.post(
        f"/api/v1/question-bank-items/{item['id']}/approval",
        json={"approval_status": "APPROVED", "reviewer_note": "Approved"},
    )
    assert approved.status_code == 200

    response = client.post(
        f"/api/v1/question-bank-items/{item['id']}/approval",
        json={"approval_status": "DRAFT", "reviewer_note": "discarded"},
    )

    assert response.status_code == 200
    assert response.json()["approval_status"] == "DRAFT"
    assert response.json()["approval_decided_at"] is None
    assert response.json()["reviewer_note"] is None


def test_item_approval_returns_404_and_invalid_status_returns_422(
    client: TestClient,
) -> None:
    missing = client.post(
        "/api/v1/question-bank-items/999999/approval",
        json={"approval_status": "APPROVED"},
    )
    invalid = client.post(
        "/api/v1/question-bank-items/1/approval",
        json={"approval_status": "INVALID"},
    )

    assert missing.status_code == 404
    assert missing.json() == {"detail": "QuestionBankItem 999999 not found"}
    assert invalid.status_code == 422


def test_complete_item_can_be_approved_after_claim_returns_to_draft(
    client: TestClient,
) -> None:
    content_version_id, topic_id = _foundation(client, "claim-reset")
    claim_id = _claim(client, topic_id, "claim-reset")
    created = _post(
        client,
        "/api/v1/question-bank-items",
        _item_payload(content_version_id, [claim_id]),
    )
    claim_reset = client.post(
        f"/api/v1/claims/{claim_id}/approval",
        json={"approval_status": "DRAFT"},
    )

    approved = client.post(
        f"/api/v1/question-bank-items/{created['id']}/approval",
        json={"approval_status": "APPROVED"},
    )

    assert claim_reset.status_code == 200
    assert approved.status_code == 200
    assert approved.json()["approval_status"] == "APPROVED"
    assert approved.json()["claim_ids"] == created["claim_ids"]
    assert approved.json()["options"] == created["options"]
    assert approved.json()["correct_option_position"] == created["correct_option_position"]


def test_incomplete_legacy_item_cannot_be_approved_and_is_unchanged(
    client: TestClient,
    db_connection: Connection,
) -> None:
    content_version_id, _ = _foundation(client, "legacy-approval")
    legacy_id = db_connection.scalar(
        QuestionBankItem.__table__.insert()
        .values(
            content_version_id=content_version_id,
            question_text="Incomplete legacy candidate",
            explanation="It has no stored options.",
            difficulty="EASY",
        )
        .returning(QuestionBankItem.id)
    )
    assert legacy_id is not None

    response = client.post(
        f"/api/v1/question-bank-items/{legacy_id}/approval",
        json={"approval_status": "APPROVED", "reviewer_note": "Must not persist"},
    )
    retrieved = client.get(f"/api/v1/question-bank-items/{legacy_id}")

    assert response.status_code == 409
    assert response.json() == {
        "detail": (
            f"QuestionBankItem {legacy_id} is incomplete and cannot be approved"
        )
    }
    assert retrieved.status_code == 200
    assert retrieved.json()["approval_status"] == "DRAFT"
    assert retrieved.json()["approval_decided_at"] is None
    assert retrieved.json()["reviewer_note"] is None
    assert retrieved.json()["options"] == []
    assert retrieved.json()["correct_option_position"] is None


def test_incomplete_legacy_item_can_be_rejected(
    client: TestClient,
    db_connection: Connection,
) -> None:
    content_version_id, _ = _foundation(client, "legacy-rejection")
    legacy_id = db_connection.scalar(
        QuestionBankItem.__table__.insert()
        .values(
            content_version_id=content_version_id,
            question_text="Rejectable legacy candidate",
            explanation="Incomplete candidates may be rejected.",
            difficulty="EASY",
        )
        .returning(QuestionBankItem.id)
    )
    assert legacy_id is not None

    response = client.post(
        f"/api/v1/question-bank-items/{legacy_id}/approval",
        json={"approval_status": "REJECTED", "reviewer_note": "Incomplete"},
    )

    assert response.status_code == 200
    assert response.json()["approval_status"] == "REJECTED"
    assert response.json()["approval_decided_at"] is not None
    assert response.json()["reviewer_note"] == "Incomplete"


def test_database_rejects_invalid_item_approval_status(
    client: TestClient,
    db_connection: Connection,
) -> None:
    content_version_id, topic_id = _foundation(client, "approval-constraint")
    claim_id = _claim(client, topic_id, "approval-constraint")
    item = _post(
        client,
        "/api/v1/question-bank-items",
        _item_payload(content_version_id, [claim_id]),
    )

    savepoint = db_connection.begin_nested()
    with pytest.raises(IntegrityError):
        db_connection.execute(
            update(QuestionBankItem)
            .where(QuestionBankItem.id == item["id"])
            .values(approval_status="INVALID")
        )
    savepoint.rollback()
