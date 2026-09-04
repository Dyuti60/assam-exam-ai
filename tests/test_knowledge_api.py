from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from app.core.database import engine, get_db
from app.main import app
from app.models import Claim, Verification, VerificationEvidence, claim_evidence
from app.repositories import KnowledgeRepository


@pytest.fixture
def db_connection() -> Generator[Connection, None, None]:
    database_name = engine.url.database or ""
    if not database_name.endswith("_test"):
        pytest.fail("Knowledge API tests require a dedicated *_test database")

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


def test_complete_knowledge_api_flow(client: TestClient) -> None:
    source_response = client.post(
        "/api/v1/sources",
        json={
            "title": "Official test notification",
            "publisher": "Test Department",
            "source_type": "official_notification",
            "authority_tier": 1,
            "location": "https://example.test/notification",
            "license_status": "TEST_ONLY",
        },
    )
    assert source_response.status_code == 201
    source_id = source_response.json()["id"]

    evidence_ids = []
    for content, location_reference in [
        ("Primary supporting evidence", "page 1"),
        ("Additional context", "page 2"),
    ]:
        response = client.post(
            "/api/v1/evidence",
            json={
                "source_id": source_id,
                "content": content,
                "location_reference": location_reference,
            },
        )
        assert response.status_code == 201
        evidence_ids.append(response.json()["id"])

    claim_response = client.post(
        "/api/v1/claims",
        json={
            "statement": "A test claim supported by official evidence",
            "subject": "test claim",
            "predicate": "is supported by",
            "object_value": "official evidence",
        },
    )
    assert claim_response.status_code == 201
    claim_id = claim_response.json()["id"]

    verification_response = client.post(
        "/api/v1/verifications",
        json={
            "claim_id": claim_id,
            "verdict": "SUPPORTED",
            "confidence": 0.95,
            "reasoning": "Both evidence records were inspected.",
            "evidence": [
                {
                    "evidence_id": evidence_ids[1],
                    "evidence_role": "CONTEXT",
                    "position": 1,
                },
                {
                    "evidence_id": evidence_ids[0],
                    "evidence_role": "SUPPORTS",
                    "position": 0,
                },
            ],
        },
    )
    assert verification_response.status_code == 201
    created_verification = verification_response.json()
    verification_id = created_verification["id"]
    assert created_verification["claim"]["verification_status"] == "SUPPORTED"
    assert created_verification["claim"]["confidence"] == 0.95
    assert created_verification["claim"]["last_verified_at"] == (
        created_verification["created_at"]
    )

    claim_summary_response = client.get(f"/api/v1/claims/{claim_id}")
    assert claim_summary_response.status_code == 200
    claim_summary = claim_summary_response.json()
    assert claim_summary["statement"] == (
        "A test claim supported by official evidence"
    )
    assert claim_summary["verification_status"] == "SUPPORTED"
    assert claim_summary["confidence"] == 0.95
    assert claim_summary["last_verified_at"] == created_verification["created_at"]

    response = client.get(f"/api/v1/verifications/{verification_id}")
    assert response.status_code == 200
    result = response.json()
    assert result["claim"]["id"] == claim_id
    assert result["claim"]["statement"] == (
        "A test claim supported by official evidence"
    )
    assert result["claim"]["verification_status"] == "SUPPORTED"
    assert result["claim"]["confidence"] == 0.95
    assert result["claim"]["last_verified_at"] == result["created_at"]
    assert [item["evidence_id"] for item in result["evidence"]] == evidence_ids
    assert [item["evidence_role"] for item in result["evidence"]] == [
        "SUPPORTS",
        "CONTEXT",
    ]
    assert [item["position"] for item in result["evidence"]] == [0, 1]


def test_create_evidence_returns_404_for_missing_source(client: TestClient) -> None:
    response = client.post(
        "/api/v1/evidence",
        json={
            "source_id": 999999,
            "content": "Evidence without a source",
        },
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Source 999999 not found"}


def test_get_evidence_returns_created_evidence(client: TestClient) -> None:
    source_response = client.post(
        "/api/v1/sources",
        json={
            "title": "Evidence retrieval source",
            "source_type": "official_notification",
            "authority_tier": 1,
            "location": "https://example.test/evidence-retrieval",
            "license_status": "TEST_ONLY",
        },
    )
    assert source_response.status_code == 201
    evidence_response = client.post(
        "/api/v1/evidence",
        json={
            "source_id": source_response.json()["id"],
            "content": "Evidence content to retrieve",
            "location_reference": "page 7",
        },
    )
    assert evidence_response.status_code == 201
    created_evidence = evidence_response.json()

    response = client.get(f"/api/v1/evidence/{created_evidence['id']}")

    assert response.status_code == 200
    assert response.json() == created_evidence


def test_get_evidence_returns_404_for_missing_evidence(client: TestClient) -> None:
    response = client.get("/api/v1/evidence/999999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Evidence 999999 not found"}


def test_get_claim_returns_404_for_missing_claim(client: TestClient) -> None:
    response = client.get("/api/v1/claims/999999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Claim 999999 not found"}


def test_link_claim_evidence_is_idempotent_and_retrievable(
    client: TestClient,
    db_connection: Connection,
) -> None:
    source_response = client.post(
        "/api/v1/sources",
        json={
            "title": "Relevant evidence source",
            "source_type": "official_notification",
            "authority_tier": 1,
            "location": "https://example.test/relevant-evidence",
            "license_status": "TEST_ONLY",
        },
    )
    assert source_response.status_code == 201
    source_id = source_response.json()["id"]

    evidence_ids = []
    for content in ["Earlier evidence", "Later evidence"]:
        evidence_response = client.post(
            "/api/v1/evidence",
            json={"source_id": source_id, "content": content},
        )
        assert evidence_response.status_code == 201
        evidence_ids.append(evidence_response.json()["id"])

    claim_response = client.post(
        "/api/v1/claims",
        json={"statement": "A claim with relevant evidence"},
    )
    assert claim_response.status_code == 201
    claim_id = claim_response.json()["id"]

    for evidence_id in [evidence_ids[1], evidence_ids[0], evidence_ids[1]]:
        link_response = client.post(
            f"/api/v1/claims/{claim_id}/evidence/{evidence_id}"
        )
        assert link_response.status_code == 200

    association_count = db_connection.scalar(
        select(func.count())
        .select_from(claim_evidence)
        .where(claim_evidence.c.claim_id == claim_id)
    )
    assert association_count == 2

    response = client.get(f"/api/v1/claims/{claim_id}")
    assert response.status_code == 200
    assert response.json()["relevant_evidence_ids"] == evidence_ids


def test_link_claim_evidence_returns_404_for_missing_evidence(
    client: TestClient,
) -> None:
    claim_response = client.post(
        "/api/v1/claims",
        json={"statement": "A claim with missing relevant evidence"},
    )
    assert claim_response.status_code == 201
    claim_id = claim_response.json()["id"]

    response = client.post(f"/api/v1/claims/{claim_id}/evidence/999999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Evidence 999999 not found"}


def test_repository_duplicate_claim_evidence_insert_is_conflict_safe(
    client: TestClient,
    db_connection: Connection,
) -> None:
    source_response = client.post(
        "/api/v1/sources",
        json={
            "title": "Conflict-safe link source",
            "source_type": "official_notification",
            "authority_tier": 1,
            "location": "https://example.test/conflict-safe-link",
            "license_status": "TEST_ONLY",
        },
    )
    assert source_response.status_code == 201
    evidence_response = client.post(
        "/api/v1/evidence",
        json={
            "source_id": source_response.json()["id"],
            "content": "Conflict-safe relevant evidence",
        },
    )
    assert evidence_response.status_code == 201
    claim_response = client.post(
        "/api/v1/claims",
        json={"statement": "A claim for conflict-safe linking"},
    )
    assert claim_response.status_code == 201

    claim_id = claim_response.json()["id"]
    evidence_id = evidence_response.json()["id"]
    with Session(
        bind=db_connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    ) as session:
        repository = KnowledgeRepository(session)
        repository.link_claim_evidence(claim_id, evidence_id)
        repository.link_claim_evidence(claim_id, evidence_id)
        session.commit()

    association_count = db_connection.scalar(
        select(func.count())
        .select_from(claim_evidence)
        .where(
            claim_evidence.c.claim_id == claim_id,
            claim_evidence.c.evidence_id == evidence_id,
        )
    )
    assert association_count == 1


def test_create_verification_rejects_invalid_evidence_role(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/v1/verifications",
        json={
            "claim_id": 1,
            "verdict": "SUPPORTED",
            "confidence": 0.9,
            "evidence": [
                {
                    "evidence_id": 1,
                    "evidence_role": "INVALID",
                    "position": 0,
                }
            ],
        },
    )

    assert response.status_code == 422


def test_create_verification_returns_404_without_partial_record(
    client: TestClient,
    db_connection: Connection,
) -> None:
    claim_response = client.post(
        "/api/v1/claims",
        json={"statement": "A claim with missing evidence"},
    )
    assert claim_response.status_code == 201

    verification_count_before = db_connection.scalar(
        select(func.count()).select_from(Verification)
    )
    link_count_before = db_connection.scalar(
        select(func.count()).select_from(VerificationEvidence)
    )

    claim_id = claim_response.json()["id"]
    response = client.post(
        "/api/v1/verifications",
        json={
            "claim_id": claim_id,
            "verdict": "UNVERIFIED",
            "confidence": 0.0,
            "evidence": [
                {
                    "evidence_id": 999999,
                    "evidence_role": "CONTEXT",
                    "position": 0,
                }
            ],
        },
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Evidence 999999 not found"}
    assert db_connection.scalar(select(func.count()).select_from(Verification)) == (
        verification_count_before
    )
    assert db_connection.scalar(
        select(func.count()).select_from(VerificationEvidence)
    ) == link_count_before
    claim_summary = db_connection.execute(
        select(
            Claim.verification_status,
            Claim.confidence,
            Claim.last_verified_at,
        ).where(Claim.id == claim_id)
    ).one()
    assert claim_summary.verification_status == "UNVERIFIED"
    assert claim_summary.confidence is None
    assert claim_summary.last_verified_at is None
