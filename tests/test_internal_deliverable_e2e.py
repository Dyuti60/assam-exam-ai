from collections.abc import Generator
from hashlib import sha256

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from app.core.database import engine, get_db
from app.main import app


@pytest.fixture
def db_connection() -> Generator[Connection, None, None]:
    database_name = engine.url.database or ""
    if not database_name.endswith("_test"):
        pytest.fail("Internal deliverable tests require a dedicated *_test database")
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


def _post_json(
    client: TestClient,
    path: str,
    payload: dict | None = None,
    *,
    expected_status: int = 201,
) -> dict:
    response = client.post(path, json=payload) if payload is not None else client.post(path)
    assert response.status_code == expected_status, response.text
    return response.json()


def test_complete_internal_deliverable_workflow(client: TestClient) -> None:
    source = _post_json(
        client,
        "/api/v1/sources",
        {
            "title": "Assam Government authoritative smoke source",
            "publisher": "Government of Assam",
            "source_type": "official",
            "authority_tier": 1,
            "location": "https://example.gov/assam/smoke-source",
            "license_status": "TEST_ONLY",
            "content_hash": sha256(b"authoritative smoke source").hexdigest(),
        },
    )
    exam = _post_json(
        client,
        "/api/v1/exams",
        {"code": "E2E-SMOKE", "name": "Internal Deliverable Smoke Exam"},
    )
    topic = _post_json(
        client,
        "/api/v1/topics",
        {"name": "Internal Deliverable Smoke Topic"},
    )
    syllabus = _post_json(
        client,
        "/api/v1/syllabus-versions",
        {
            "exam_id": exam["id"],
            "source_id": source["id"],
            "label": "Authoritative smoke syllabus",
            "topic_ids": [topic["id"]],
        },
    )
    assert syllabus["exam_id"] == exam["id"]
    assert syllabus["source_id"] == source["id"]
    assert syllabus["topic_ids"] == [topic["id"]]

    content_version = _post_json(
        client,
        "/api/v1/content-versions",
        {
            "syllabus_version_id": syllabus["id"],
            "topic_id": topic["id"],
            "version": 1,
        },
    )
    assert content_version["syllabus_version_id"] == syllabus["id"]
    assert content_version["topic_id"] == topic["id"]

    evidence = _post_json(
        client,
        "/api/v1/evidence",
        {
            "source_id": source["id"],
            "content": "The authoritative source supports the smoke-test fact.",
            "location_reference": "section 1",
        },
    )
    claim = _post_json(
        client,
        "/api/v1/claims",
        {
            "statement": "The smoke-test fact is supported by authoritative evidence.",
            "subject": "The smoke-test fact",
            "predicate": "is supported by",
            "object_value": "authoritative evidence",
            "topic_id": topic["id"],
        },
    )
    assert claim["verification_status"] == "UNVERIFIED"
    assert claim["approval_status"] == "DRAFT"

    linked_claim = _post_json(
        client,
        f"/api/v1/claims/{claim['id']}/evidence/{evidence['id']}",
        expected_status=200,
    )
    assert linked_claim["id"] == claim["id"]
    assert linked_claim["relevant_evidence_ids"] == [evidence["id"]]

    verification = _post_json(
        client,
        "/api/v1/verifications",
        {
            "claim_id": claim["id"],
            "verdict": "SUPPORTED",
            "confidence": 0.98,
            "reasoning": "The exact authoritative Evidence record supports the Claim.",
            "evidence": [
                {
                    "evidence_id": evidence["id"],
                    "evidence_role": "SUPPORTS",
                    "position": 0,
                }
            ],
        },
    )
    assert verification["claim"]["id"] == claim["id"]
    assert verification["claim"]["verification_status"] == "SUPPORTED"
    assert verification["claim"]["confidence"] == 0.98
    assert verification["claim"]["last_verified_at"] == verification["created_at"]
    assert verification["claim"]["approval_status"] == "DRAFT"
    assert [item["evidence_id"] for item in verification["evidence"]] == [
        evidence["id"]
    ]

    approved_claim = _post_json(
        client,
        f"/api/v1/claims/{claim['id']}/approval",
        {"approval_status": "APPROVED", "reviewer_note": "Human-approved fact"},
        expected_status=200,
    )
    assert approved_claim["verification_status"] == "SUPPORTED"
    assert approved_claim["approval_status"] == "APPROVED"
    assert approved_claim["approval_decided_at"] is not None

    note_draft = _post_json(
        client,
        f"/api/v1/topics/{topic['id']}/note-drafts",
        {"content_version_id": content_version["id"]},
    )
    assert note_draft["topic_id"] == topic["id"]
    assert note_draft["topic_name"] == topic["name"]
    assert note_draft["content_version_id"] == content_version["id"]
    assert note_draft["claim_ids"] == [claim["id"]]
    assert approved_claim["statement"] in note_draft["markdown"]
    assert note_draft["approval_status"] == "DRAFT"
    assert note_draft["release_status"] == "UNRELEASED"

    question = _post_json(
        client,
        "/api/v1/question-bank-items",
        {
            "content_version_id": content_version["id"],
            "question_text": "What supports the smoke-test fact?",
            "explanation": "The authoritative Evidence record supports the Claim.",
            "difficulty": "MEDIUM",
            "claim_ids": [claim["id"]],
            "options": ["Authoritative evidence", "An unsupported assertion"],
            "correct_option_position": 0,
        },
    )
    assert question["content_version_id"] == content_version["id"]
    assert question["claim_ids"] == [claim["id"]]
    assert question["options"] == [
        "Authoritative evidence",
        "An unsupported assertion",
    ]
    assert question["correct_option_position"] == 0
    assert question["approval_status"] == "DRAFT"
    assert question["release_status"] == "UNRELEASED"
    assert "previous_paper_id" not in question

    approved_note = _post_json(
        client,
        f"/api/v1/note-drafts/{note_draft['id']}/approval",
        {"approval_status": "APPROVED", "reviewer_note": "Human-reviewed note"},
        expected_status=200,
    )
    assert approved_note["release_status"] == "UNRELEASED"
    released_note = _post_json(
        client,
        f"/api/v1/note-drafts/{note_draft['id']}/release",
        {"release_status": "RELEASED", "release_note": "Canonical note release"},
        expected_status=200,
    )
    approved_question = _post_json(
        client,
        f"/api/v1/question-bank-items/{question['id']}/approval",
        {
            "approval_status": "APPROVED",
            "reviewer_note": "Human-reviewed practice question",
        },
        expected_status=200,
    )
    assert approved_question["release_status"] == "UNRELEASED"
    released_question = _post_json(
        client,
        f"/api/v1/question-bank-items/{question['id']}/release",
        {
            "release_status": "RELEASED",
            "release_note": "Canonical practice-question release",
        },
        expected_status=200,
    )

    manifest_response = client.get(
        f"/api/v1/content-versions/{content_version['id']}/released-assets"
    )
    assert manifest_response.status_code == 200
    manifest = manifest_response.json()
    assert manifest == {
        "content_version": content_version,
        "note_drafts": [released_note],
        "question_bank_items": [released_question],
    }
    assert manifest["note_drafts"][0]["claim_ids"] == [claim["id"]]
    assert manifest["question_bank_items"][0]["claim_ids"] == [claim["id"]]

    content_package = _post_json(
        client,
        f"/api/v1/content-versions/{content_version['id']}/content-packages",
    )
    assert content_package["content_version_id"] == content_version["id"]
    assert content_package["note_draft_ids"] == [note_draft["id"]]
    assert content_package["question_bank_item_ids"] == [question["id"]]
    assert content_package["approval_status"] == "DRAFT"
    assert content_package["release_status"] == "UNRELEASED"

    package_response = client.get(
        f"/api/v1/content-packages/{content_package['id']}"
    )
    assert package_response.status_code == 200
    assert package_response.json() == content_package
    expanded_response = client.get(
        f"/api/v1/content-packages/{content_package['id']}/content"
    )
    assert expanded_response.status_code == 200
    assert expanded_response.json() == {
        "content_package": content_package,
        "note_drafts": [released_note],
        "question_bank_items": [released_question],
    }

    approved_package = _post_json(
        client,
        f"/api/v1/content-packages/{content_package['id']}/approval",
        {"approval_status": "APPROVED", "reviewer_note": "Human-reviewed package"},
        expected_status=200,
    )
    assert approved_package["release_status"] == "UNRELEASED"
    released_package = _post_json(
        client,
        f"/api/v1/content-packages/{content_package['id']}/release",
        {"release_status": "RELEASED", "release_note": "Package release"},
        expected_status=200,
    )

    document = _post_json(
        client,
        f"/api/v1/content-packages/{content_package['id']}/content-documents",
    )
    expected_markdown = (
        f"# Content Package {content_package['id']}\n\n"
        "## Notes\n\n"
        f"{note_draft['markdown']}\n\n"
        "## Practice Questions\n\n"
        "### Question 1\n\n"
        f"{question['question_text']}\n\n"
        f"A. {question['options'][0]}\n"
        f"B. {question['options'][1]}\n\n"
        f"**Answer:** A. {question['options'][0]}\n\n"
        f"**Explanation:** {question['explanation']}\n"
    )
    assert document["content_package_id"] == content_package["id"]
    assert document["content_version_id"] == content_version["id"]
    assert document["title"] == f"Content Package {content_package['id']}"
    assert document["markdown"] == expected_markdown
    assert "## Notes" in document["markdown"]
    assert note_draft["markdown"] in document["markdown"]
    assert "## Practice Questions" in document["markdown"]
    assert question["question_text"] in document["markdown"]
    assert document["sha256"] == sha256(expected_markdown.encode("utf-8")).hexdigest()
    assert document["approval_status"] == "DRAFT"
    assert document["release_status"] == "UNRELEASED"
    document_response = client.get(f"/api/v1/content-documents/{document['id']}")
    assert document_response.status_code == 200
    assert document_response.json() == document

    approved_document = _post_json(
        client,
        f"/api/v1/content-documents/{document['id']}/approval",
        {"approval_status": "APPROVED", "reviewer_note": "Human-reviewed document"},
        expected_status=200,
    )
    assert approved_document["release_status"] == "UNRELEASED"
    released_document = _post_json(
        client,
        f"/api/v1/content-documents/{document['id']}/release",
        {"release_status": "RELEASED", "release_note": "Document release"},
        expected_status=200,
    )
    released_documents_response = client.get("/api/v1/content-documents/released")
    assert released_documents_response.status_code == 200
    assert released_documents_response.json() == [released_document]

    artifact = _post_json(
        client,
        f"/api/v1/content-documents/{document['id']}/pdf-artifacts",
    )
    assert artifact["content_document_id"] == document["id"]
    assert artifact["content_package_id"] == content_package["id"]
    assert artifact["content_version_id"] == content_version["id"]
    assert artifact["filename"] == f"content-document-{document['id']}.pdf"
    assert artifact["media_type"] == "application/pdf"
    assert artifact["byte_size"] > 0
    assert len(artifact["sha256"]) == 64
    assert artifact["sha256"] == artifact["sha256"].lower()
    assert "pdf_bytes" not in artifact
    assert artifact["approval_status"] == "DRAFT"
    assert artifact["release_status"] == "UNRELEASED"

    internal_download = client.get(f"/api/v1/pdf-artifacts/{artifact['id']}/download")
    assert internal_download.status_code == 200
    assert len(internal_download.content) == artifact["byte_size"]
    assert sha256(internal_download.content).hexdigest() == artifact["sha256"]
    assert internal_download.content.startswith(b"%PDF-1.4")

    approved_artifact = _post_json(
        client,
        f"/api/v1/pdf-artifacts/{artifact['id']}/approval",
        {"approval_status": "APPROVED", "reviewer_note": "Human-reviewed PDF"},
        expected_status=200,
    )
    assert approved_artifact["release_status"] == "UNRELEASED"
    released_artifact = _post_json(
        client,
        f"/api/v1/pdf-artifacts/{artifact['id']}/release",
        {"release_status": "RELEASED", "release_note": "PDF artifact release"},
        expected_status=200,
    )
    released_artifacts_response = client.get("/api/v1/pdf-artifacts/released")
    assert released_artifacts_response.status_code == 200
    assert released_artifacts_response.json() == [released_artifact]
    assert "pdf_bytes" not in released_artifacts_response.json()[0]

    released_download = client.get(
        f"/api/v1/pdf-artifacts/released/{artifact['id']}/download"
    )
    assert released_download.status_code == 200
    assert released_download.content == internal_download.content
    assert released_download.headers["content-type"] == artifact["media_type"]
    assert released_download.headers["content-length"] == str(artifact["byte_size"])
    assert released_download.headers["content-disposition"] == (
        f'attachment; filename="{artifact["filename"]}"'
    )
    assert len(released_download.content) == artifact["byte_size"]
    assert sha256(released_download.content).hexdigest() == artifact["sha256"]
    assert released_package["id"] == content_package["id"]
