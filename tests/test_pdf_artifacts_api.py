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
    NoteDraft,
    PdfArtifact,
    QuestionBankItem,
)
from app.repositories import KnowledgeRepository
from app.services.pdf_renderer import (
    UnsupportedPdfCharacterError,
    render_content_document_pdf,
)


@pytest.fixture
def db_connection() -> Generator[Connection, None, None]:
    database_name = engine.url.database or ""
    if not database_name.endswith("_test"):
        pytest.fail("PdfArtifact tests require a dedicated *_test database")
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


def _post(client: TestClient, path: str, payload: dict | None = None) -> dict:
    response = client.post(path, json=payload) if payload is not None else client.post(path)
    assert response.status_code in (200, 201), response.text
    return response.json()


def _released_document(client: TestClient, suffix: str) -> dict:
    exam = _post(
        client,
        "/api/v1/exams",
        {"code": f"PDF-{suffix}", "name": f"PDF Exam {suffix}"},
    )
    source = _post(
        client,
        "/api/v1/sources",
        {
            "title": f"PDF Source {suffix}",
            "source_type": "official",
            "authority_tier": 1,
            "location": f"https://example.gov/pdf-{suffix}",
            "license_status": "UNKNOWN",
        },
    )
    topic = _post(client, "/api/v1/topics", {"name": f"PDF Topic {suffix}"})
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
    version = _post(
        client,
        "/api/v1/content-versions",
        {
            "syllabus_version_id": syllabus["id"],
            "topic_id": topic["id"],
            "version": 1,
        },
    )
    claim = _post(
        client,
        "/api/v1/claims",
        {
            "statement": f"Representative notes fact {suffix}.",
            "topic_id": topic["id"],
        },
    )
    _post(
        client,
        f"/api/v1/claims/{claim['id']}/approval",
        {"approval_status": "APPROVED"},
    )
    draft = _post(
        client,
        f"/api/v1/topics/{topic['id']}/note-drafts",
        {"content_version_id": version["id"]},
    )
    _post(
        client,
        f"/api/v1/note-drafts/{draft['id']}/approval",
        {"approval_status": "APPROVED"},
    )
    _post(
        client,
        f"/api/v1/note-drafts/{draft['id']}/release",
        {"release_status": "RELEASED"},
    )
    item = _post(
        client,
        "/api/v1/question-bank-items",
        {
            "content_version_id": version["id"],
            "question_text": f"Representative practice question {suffix}?",
            "explanation": f"Representative explanation {suffix}.",
            "difficulty": "MEDIUM",
            "claim_ids": [claim["id"]],
            "options": [f"First option {suffix}", f"Correct option {suffix}"],
            "correct_option_position": 1,
        },
    )
    _post(
        client,
        f"/api/v1/question-bank-items/{item['id']}/approval",
        {"approval_status": "APPROVED"},
    )
    _post(
        client,
        f"/api/v1/question-bank-items/{item['id']}/release",
        {"release_status": "RELEASED"},
    )
    package = _post(
        client,
        f"/api/v1/content-versions/{version['id']}/content-packages",
    )
    _post(
        client,
        f"/api/v1/content-packages/{package['id']}/approval",
        {"approval_status": "APPROVED"},
    )
    _post(
        client,
        f"/api/v1/content-packages/{package['id']}/release",
        {"release_status": "RELEASED"},
    )
    document = _post(
        client,
        f"/api/v1/content-packages/{package['id']}/content-documents",
    )
    _post(
        client,
        f"/api/v1/content-documents/{document['id']}/approval",
        {"approval_status": "APPROVED", "reviewer_note": "PDF review"},
    )
    document = _post(
        client,
        f"/api/v1/content-documents/{document['id']}/release",
        {"release_status": "RELEASED", "release_note": "PDF release"},
    )
    return {
        "claim": claim,
        "draft": draft,
        "item": item,
        "package": package,
        "document": document,
        "version": version,
    }


def _artifact_count(connection: Connection) -> int:
    return connection.scalar(select(func.count()).select_from(PdfArtifact))


def _create_artifact(client: TestClient, suffix: str) -> tuple[dict, dict]:
    fixture = _released_document(client, suffix)
    response = client.post(
        f"/api/v1/content-documents/{fixture['document']['id']}/pdf-artifacts"
    )
    assert response.status_code == 201, response.text
    return fixture, response.json()


def _related_snapshot(connection: Connection, fixture: dict) -> tuple[object, ...]:
    return (
        connection.execute(
            select(ContentPackage.__table__).where(
                ContentPackage.id == fixture["package"]["id"]
            )
        ).mappings().one(),
        connection.execute(
            select(NoteDraft.__table__).where(NoteDraft.id == fixture["draft"]["id"])
        ).mappings().one(),
        connection.execute(
            select(QuestionBankItem.__table__).where(
                QuestionBankItem.id == fixture["item"]["id"]
            )
        ).mappings().one(),
        connection.execute(
            select(Claim.__table__).where(Claim.id == fixture["claim"]["id"])
        ).mappings().one(),
        tuple(
            connection.execute(
                select(ContentPackageNoteDraft.__table__).where(
                    ContentPackageNoteDraft.content_package_id
                    == fixture["package"]["id"]
                )
            ).mappings()
        ),
        tuple(
            connection.execute(
                select(ContentPackageQuestionBankItem.__table__).where(
                    ContentPackageQuestionBankItem.content_package_id
                    == fixture["package"]["id"]
                )
            ).mappings()
        ),
    )


def test_create_pdf_artifact_persists_deterministic_readable_bytes_and_ownership(
    client: TestClient,
    db_connection: Connection,
) -> None:
    fixture = _released_document(client, "success")
    document = fixture["document"]
    before_document = db_connection.execute(
        select(ContentDocument.__table__).where(ContentDocument.id == document["id"])
    ).mappings().one()
    before_related = _related_snapshot(db_connection, fixture)
    statements: list[str] = []
    commits = 0
    rollbacks = 0

    def record_statement(*args: object) -> None:
        statements.append(str(args[2]))

    def record_commit(*args: object) -> None:
        nonlocal commits
        commits += 1

    def record_rollback(*args: object) -> None:
        nonlocal rollbacks
        rollbacks += 1

    event.listen(db_connection, "before_cursor_execute", record_statement)
    event.listen(Session, "after_commit", record_commit)
    event.listen(Session, "after_rollback", record_rollback)
    try:
        response = client.post(
            f"/api/v1/content-documents/{document['id']}/pdf-artifacts"
        )
    finally:
        event.remove(db_connection, "before_cursor_execute", record_statement)
        event.remove(Session, "after_commit", record_commit)
        event.remove(Session, "after_rollback", record_rollback)

    assert response.status_code == 201
    body = response.json()
    artifact = db_connection.execute(
        select(PdfArtifact.__table__).where(PdfArtifact.id == body["id"])
    ).mappings().one()
    pdf_bytes = bytes(artifact["pdf_bytes"])
    assert body == {
        "id": artifact["id"],
        "content_document_id": document["id"],
        "content_package_id": document["content_package_id"],
        "content_version_id": document["content_version_id"],
        "filename": f"content-document-{document['id']}.pdf",
        "media_type": "application/pdf",
        "byte_size": len(pdf_bytes),
        "sha256": sha256(pdf_bytes).hexdigest(),
        "created_at": body["created_at"],
        "approval_status": "DRAFT",
        "approval_decided_at": None,
        "reviewer_note": None,
    }
    assert datetime.fromisoformat(body["created_at"]) == artifact["created_at"]
    assert pdf_bytes.startswith(b"%PDF-1.4")
    assert pdf_bytes.rstrip().endswith(b"%%EOF")
    assert artifact["byte_size"] > 0
    assert artifact["sha256"] == sha256(pdf_bytes).hexdigest()
    readable_fragments = [
        b"Content Package",
        b"Notes",
        b"Representative notes fact success.",
        b"Practice Questions",
        b"Representative practice question success?",
        b"A. First option success",
        b"B. Correct option success",
        b"Answer: B. Correct option success",
        b"Explanation: Representative explanation success.",
    ]
    positions = [pdf_bytes.index(fragment) for fragment in readable_fragments]
    assert positions == sorted(positions)
    assert pdf_bytes == render_content_document_pdf(
        document["title"], document["markdown"]
    )
    assert before_document == db_connection.execute(
        select(ContentDocument.__table__).where(ContentDocument.id == document["id"])
    ).mappings().one()
    assert _related_snapshot(db_connection, fixture) == before_related
    locking = [statement for statement in statements if "FOR UPDATE" in statement.upper()]
    assert len(locking) == 1
    assert "FOR UPDATE OF content_documents" in locking[0]
    assert all("content_packages" not in statement for statement in locking)
    assert commits == 1
    assert rollbacks == 0


def test_renderer_is_byte_deterministic_and_rejects_unsupported_unicode() -> None:
    title = "Stable title"
    markdown = "# Stable title\n\n## Notes\n\n- Stable fact.\n"
    assert render_content_document_pdf(title, markdown) == render_content_document_pdf(
        title, markdown
    )
    with pytest.raises(UnsupportedPdfCharacterError, match="Windows-1252"):
        render_content_document_pdf("Unsupported \u6f22", markdown)


def test_missing_unreleased_and_withdrawn_documents_fail_before_rendering(
    client: TestClient,
    db_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_render(*args: object) -> bytes:
        raise AssertionError("renderer must not run")

    monkeypatch.setattr(
        "app.services.knowledge.render_content_document_pdf",
        unexpected_render,
    )
    missing = client.post("/api/v1/content-documents/999999/pdf-artifacts")
    assert missing.status_code == 404
    assert missing.json() == {"detail": "ContentDocument 999999 not found"}

    fixture = _released_document(client, "eligibility")
    document_id = fixture["document"]["id"]
    db_connection.execute(
        update(ContentDocument)
        .where(ContentDocument.id == document_id)
        .values(
            release_status="UNRELEASED",
            released_at=None,
            release_note=None,
        )
    )
    unreleased = client.post(
        f"/api/v1/content-documents/{document_id}/pdf-artifacts"
    )
    assert unreleased.status_code == 409
    assert unreleased.json() == {
        "detail": f"ContentDocument {document_id} must be released before PDF creation"
    }
    db_connection.execute(
        update(ContentDocument)
        .where(ContentDocument.id == document_id)
        .values(
            release_status="WITHDRAWN",
            released_at=fixture["document"]["released_at"],
            withdrawn_at=func.now(),
            release_note="withdrawn",
        )
    )
    withdrawn = client.post(
        f"/api/v1/content-documents/{document_id}/pdf-artifacts"
    )
    assert withdrawn.status_code == 409
    assert withdrawn.json() == unreleased.json()
    assert _artifact_count(db_connection) == 0


def test_duplicate_pdf_artifact_is_stable_and_does_not_replace_bytes(
    client: TestClient,
    db_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _released_document(client, "duplicate")
    document_id = fixture["document"]["id"]
    first = client.post(f"/api/v1/content-documents/{document_id}/pdf-artifacts")
    assert first.status_code == 201
    stored_before = db_connection.execute(
        select(PdfArtifact.__table__).where(
            PdfArtifact.content_document_id == document_id
        )
    ).mappings().one()
    monkeypatch.setattr(
        "app.services.knowledge.render_content_document_pdf",
        lambda *args: (_ for _ in ()).throw(AssertionError("must not regenerate")),
    )
    duplicate = client.post(
        f"/api/v1/content-documents/{document_id}/pdf-artifacts"
    )
    assert duplicate.status_code == 409
    assert duplicate.json() == {
        "detail": f"ContentDocument {document_id} already has a PdfArtifact"
    }
    assert _artifact_count(db_connection) == 1
    assert stored_before == db_connection.execute(
        select(PdfArtifact.__table__).where(
            PdfArtifact.content_document_id == document_id
        )
    ).mappings().one()


class _ConstraintDiagnostic:
    def __init__(self, constraint_name: str) -> None:
        self.constraint_name = constraint_name


class _ConstraintOrigin(Exception):
    def __init__(self, constraint_name: str) -> None:
        self.diag = _ConstraintDiagnostic(constraint_name)


@pytest.mark.parametrize(
    ("constraint_name", "expected_status"),
    [
        ("uq_pdf_artifacts_content_document_id", 409),
        ("ck_pdf_artifacts_byte_size_positive", 500),
    ],
)
def test_only_named_duplicate_race_is_translated_and_failures_roll_back(
    client: TestClient,
    db_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
    constraint_name: str,
    expected_status: int,
) -> None:
    fixture = _released_document(client, f"race-{expected_status}")
    document_id = fixture["document"]["id"]

    def fail_add(*args: object) -> None:
        raise IntegrityError(
            "INSERT",
            {},
            _ConstraintOrigin(constraint_name),
        )

    monkeypatch.setattr(KnowledgeRepository, "add_pdf_artifact", fail_add)
    if expected_status == 409:
        response = client.post(
            f"/api/v1/content-documents/{document_id}/pdf-artifacts"
        )
        assert response.status_code == expected_status
        assert response.json() == {
            "detail": f"ContentDocument {document_id} already has a PdfArtifact"
        }
    else:
        with pytest.raises(IntegrityError):
            client.post(f"/api/v1/content-documents/{document_id}/pdf-artifacts")
    assert _artifact_count(db_connection) == 0


def test_renderer_failure_leaves_no_artifact(
    client: TestClient,
    db_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _released_document(client, "renderer-failure")
    document_id = fixture["document"]["id"]
    rollbacks = 0

    def record_rollback(*args: object) -> None:
        nonlocal rollbacks
        rollbacks += 1

    monkeypatch.setattr(
        "app.services.knowledge.render_content_document_pdf",
        lambda *args: (_ for _ in ()).throw(UnsupportedPdfCharacterError("unsupported")),
    )
    event.listen(Session, "after_rollback", record_rollback)
    try:
        with pytest.raises(UnsupportedPdfCharacterError, match="unsupported"):
            client.post(f"/api/v1/content-documents/{document_id}/pdf-artifacts")
    finally:
        event.remove(Session, "after_rollback", record_rollback)
    assert _artifact_count(db_connection) == 0
    assert rollbacks == 1


@pytest.mark.parametrize(
    ("values", "constraint_name"),
    [
        ({"filename": "   "}, "ck_pdf_artifacts_filename_pdf"),
        ({"filename": "artifact.txt"}, "ck_pdf_artifacts_filename_pdf"),
        ({"media_type": "text/plain"}, "ck_pdf_artifacts_media_type"),
        (
            {"byte_size": 0, "pdf_bytes": b""},
            "ck_pdf_artifacts_byte_size_positive",
        ),
        ({"byte_size": 2}, "ck_pdf_artifacts_byte_size_matches"),
        ({"sha256": "A" * 64}, "ck_pdf_artifacts_sha256_lower_hex"),
        ({"sha256": "a" * 63}, "ck_pdf_artifacts_sha256_lower_hex"),
    ],
)
def test_pdf_artifact_database_checks(
    client: TestClient,
    db_connection: Connection,
    values: dict,
    constraint_name: str,
) -> None:
    fixture = _released_document(client, f"constraint-{constraint_name}")
    document = fixture["document"]
    valid = {
        "content_document_id": document["id"],
        "content_package_id": document["content_package_id"],
        "content_version_id": document["content_version_id"],
        "filename": "artifact.pdf",
        "media_type": "application/pdf",
        "pdf_bytes": b"x",
        "byte_size": 1,
        "sha256": "a" * 64,
    }
    with pytest.raises(IntegrityError) as error, db_connection.begin_nested():
        db_connection.execute(insert(PdfArtifact).values(**(valid | values)))
    assert error.value.orig.diag.constraint_name == constraint_name


def test_pdf_artifact_database_ownership_uniqueness_and_delete_restriction(
    client: TestClient,
    db_connection: Connection,
) -> None:
    first = _released_document(client, "ownership-first")["document"]
    second = _released_document(client, "ownership-second")["document"]
    values = {
        "content_document_id": first["id"],
        "content_package_id": first["content_package_id"],
        "content_version_id": first["content_version_id"],
        "filename": "artifact.pdf",
        "media_type": "application/pdf",
        "pdf_bytes": b"x",
        "byte_size": 1,
        "sha256": "a" * 64,
    }
    with pytest.raises(IntegrityError) as mismatch, db_connection.begin_nested():
        db_connection.execute(
            insert(PdfArtifact).values(
                **(values | {"content_package_id": second["content_package_id"]})
            )
        )
    assert (
        mismatch.value.orig.diag.constraint_name
        == "fk_pdf_artifacts_document_package_version"
    )

    db_connection.execute(insert(PdfArtifact).values(**values))
    with pytest.raises(IntegrityError) as duplicate, db_connection.begin_nested():
        db_connection.execute(insert(PdfArtifact).values(**values))
    assert (
        duplicate.value.orig.diag.constraint_name
        == "uq_pdf_artifacts_content_document_id"
    )
    with pytest.raises(IntegrityError), db_connection.begin_nested():
        db_connection.execute(
            delete(ContentDocument).where(ContentDocument.id == first["id"])
        )


def test_pdf_uses_stored_document_after_related_state_changes(
    client: TestClient,
    db_connection: Connection,
) -> None:
    fixture = _released_document(client, "stored-input")
    document = fixture["document"]
    db_connection.execute(
        update(Claim)
        .where(Claim.id == fixture["claim"]["id"])
        .values(approval_status="REJECTED", approval_decided_at=func.now())
    )
    db_connection.execute(
        update(ContentPackage)
        .where(ContentPackage.id == fixture["package"]["id"])
        .values(
            release_status="WITHDRAWN",
            withdrawn_at=func.now(),
            release_note="withdrawn later",
        )
    )
    db_connection.execute(
        update(QuestionBankItem)
        .where(QuestionBankItem.id == fixture["item"]["id"])
        .values(
            release_status="WITHDRAWN",
            withdrawn_at=func.now(),
            release_note="withdrawn later",
        )
    )
    response = client.post(
        f"/api/v1/content-documents/{document['id']}/pdf-artifacts"
    )
    assert response.status_code == 201
    artifact = db_connection.execute(
        select(PdfArtifact.__table__).where(
            PdfArtifact.content_document_id == document["id"]
        )
    ).mappings().one()
    assert bytes(artifact["pdf_bytes"]) == render_content_document_pdf(
        document["title"], document["markdown"]
    )
    assert db_connection.scalar(
        select(func.count()).select_from(ContentPackageNoteDraft)
    ) == 1
    assert db_connection.scalar(
        select(func.count()).select_from(ContentPackageQuestionBankItem)
    ) == 1


def test_pdf_artifact_metadata_and_download_return_exact_stored_values(
    client: TestClient,
    db_connection: Connection,
) -> None:
    _, created = _create_artifact(client, "read")
    stored = db_connection.execute(
        select(PdfArtifact.__table__).where(PdfArtifact.id == created["id"])
    ).mappings().one()
    expected_metadata = {
        "id": stored["id"],
        "content_document_id": stored["content_document_id"],
        "content_package_id": stored["content_package_id"],
        "content_version_id": stored["content_version_id"],
        "filename": stored["filename"],
        "media_type": stored["media_type"],
        "byte_size": stored["byte_size"],
        "sha256": stored["sha256"],
        "created_at": created["created_at"],
        "approval_status": "DRAFT",
        "approval_decided_at": None,
        "reviewer_note": None,
    }

    metadata = client.get(f"/api/v1/pdf-artifacts/{stored['id']}")
    assert metadata.status_code == 200
    assert metadata.json() == expected_metadata
    assert "pdf_bytes" not in metadata.json()
    assert datetime.fromisoformat(metadata.json()["created_at"]) == stored["created_at"]

    download = client.get(f"/api/v1/pdf-artifacts/{stored['id']}/download")
    assert download.status_code == 200
    assert download.content == bytes(stored["pdf_bytes"])
    assert download.headers["content-type"] == stored["media_type"]
    assert download.headers["content-length"] == str(stored["byte_size"])
    assert download.headers["content-disposition"] == (
        f'attachment; filename="{stored["filename"]}"'
    )


@pytest.mark.parametrize("suffix", ["", "/download"])
def test_missing_pdf_artifact_reads_return_stable_404(
    client: TestClient,
    suffix: str,
) -> None:
    response = client.get(f"/api/v1/pdf-artifacts/999999{suffix}")
    assert response.status_code == 404
    assert response.json() == {"detail": "PdfArtifact 999999 not found"}


def test_pdf_artifact_reads_are_stable_pdf_only_queries_without_writes(
    client: TestClient,
    db_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture, created = _create_artifact(client, "stored-read")
    artifact_before = db_connection.execute(
        select(PdfArtifact.__table__).where(PdfArtifact.id == created["id"])
    ).mappings().one()
    related_before = _related_snapshot(db_connection, fixture)

    withdrawal = client.post(
        f"/api/v1/content-documents/{fixture['document']['id']}/release",
        json={"release_status": "WITHDRAWN", "release_note": "withdrawn later"},
    )
    assert withdrawal.status_code == 200
    db_connection.execute(
        update(ContentPackage)
        .where(ContentPackage.id == fixture["package"]["id"])
        .values(
            release_status="WITHDRAWN",
            withdrawn_at=func.now(),
            release_note="package changed later",
        )
    )
    db_connection.execute(
        update(Claim)
        .where(Claim.id == fixture["claim"]["id"])
        .values(
            approval_status="REJECTED",
            approval_decided_at=func.now(),
            verification_status="CONTRADICTED",
        )
    )
    db_connection.execute(
        update(NoteDraft)
        .where(NoteDraft.id == fixture["draft"]["id"])
        .values(
            release_status="WITHDRAWN",
            withdrawn_at=func.now(),
            release_note="member changed later",
        )
    )
    db_connection.execute(
        update(QuestionBankItem)
        .where(QuestionBankItem.id == fixture["item"]["id"])
        .values(
            release_status="WITHDRAWN",
            withdrawn_at=func.now(),
            release_note="member changed later",
        )
    )
    state_after_changes = _related_snapshot(db_connection, fixture)
    artifact_count = _artifact_count(db_connection)

    def unexpected_call(*args: object, **kwargs: object) -> object:
        raise AssertionError("artifact reads must not render or hash")

    monkeypatch.setattr(
        "app.services.knowledge.render_content_document_pdf",
        unexpected_call,
    )
    monkeypatch.setattr("app.services.knowledge.sha256", unexpected_call)
    statements: list[str] = []
    flushes = 0
    commits = 0

    def record_statement(*args: object) -> None:
        statements.append(str(args[2]))

    def record_flush(*args: object) -> None:
        nonlocal flushes
        flushes += 1

    def record_commit(*args: object) -> None:
        nonlocal commits
        commits += 1

    event.listen(db_connection, "before_cursor_execute", record_statement)
    event.listen(Session, "after_flush", record_flush)
    event.listen(Session, "after_commit", record_commit)
    try:
        metadata = client.get(f"/api/v1/pdf-artifacts/{created['id']}")
        download = client.get(
            f"/api/v1/pdf-artifacts/{created['id']}/download"
        )
    finally:
        event.remove(db_connection, "before_cursor_execute", record_statement)
        event.remove(Session, "after_flush", record_flush)
        event.remove(Session, "after_commit", record_commit)

    assert metadata.status_code == 200
    assert metadata.json() == created
    assert download.status_code == 200
    assert download.content == bytes(artifact_before["pdf_bytes"])
    selects = [
        statement
        for statement in statements
        if statement.lstrip().upper().startswith("SELECT")
    ]
    assert len(selects) == 2
    assert all("FROM pdf_artifacts" in statement for statement in selects)
    assert all(" JOIN " not in statement.upper() for statement in selects)
    assert all("FOR UPDATE" not in statement.upper() for statement in selects)
    assert flushes == 0
    assert commits == 0
    assert _artifact_count(db_connection) == artifact_count
    assert artifact_before == db_connection.execute(
        select(PdfArtifact.__table__).where(PdfArtifact.id == created["id"])
    ).mappings().one()
    assert _related_snapshot(db_connection, fixture) == state_after_changes
    assert related_before != state_after_changes


@pytest.mark.parametrize(
    ("approval_status", "reviewer_note"),
    [("APPROVED", "Artifact approved"), ("REJECTED", None)],
)
def test_pdf_artifact_review_records_utc_decision_and_only_review_fields(
    client: TestClient,
    db_connection: Connection,
    approval_status: str,
    reviewer_note: str | None,
) -> None:
    fixture, created = _create_artifact(client, f"review-{approval_status.lower()}")
    before = db_connection.execute(
        select(PdfArtifact.__table__).where(PdfArtifact.id == created["id"])
    ).mappings().one()
    related_before = _related_snapshot(db_connection, fixture)
    statements: list[str] = []
    commits = 0

    def record_statement(*args: object) -> None:
        statements.append(str(args[2]))

    def record_commit(*args: object) -> None:
        nonlocal commits
        commits += 1

    event.listen(db_connection, "before_cursor_execute", record_statement)
    event.listen(Session, "after_commit", record_commit)
    try:
        response = client.post(
            f"/api/v1/pdf-artifacts/{created['id']}/approval",
            json={
                "approval_status": approval_status,
                "reviewer_note": reviewer_note,
            },
        )
    finally:
        event.remove(db_connection, "before_cursor_execute", record_statement)
        event.remove(Session, "after_commit", record_commit)

    assert response.status_code == 200
    body = response.json()
    assert body["approval_status"] == approval_status
    assert body["reviewer_note"] == reviewer_note
    decided_at = datetime.fromisoformat(body["approval_decided_at"])
    assert decided_at.utcoffset() == UTC.utcoffset(None)
    after = db_connection.execute(
        select(PdfArtifact.__table__).where(PdfArtifact.id == created["id"])
    ).mappings().one()
    immutable_fields = {
        "id",
        "content_document_id",
        "content_package_id",
        "content_version_id",
        "filename",
        "media_type",
        "pdf_bytes",
        "byte_size",
        "sha256",
        "created_at",
    }
    assert {key: before[key] for key in immutable_fields} == {
        key: after[key] for key in immutable_fields
    }
    assert _related_snapshot(db_connection, fixture) == related_before
    locking = [statement for statement in statements if "FOR UPDATE" in statement.upper()]
    assert len(locking) == 1
    assert "FOR UPDATE OF pdf_artifacts" in locking[0]
    assert all("content_documents" not in statement for statement in locking)
    assert commits == 1


def test_pdf_artifact_review_reset_and_repeated_decisions_are_fresh(
    client: TestClient,
    db_connection: Connection,
) -> None:
    _, created = _create_artifact(client, "review-transitions")
    artifact_id = created["id"]
    approved = client.post(
        f"/api/v1/pdf-artifacts/{artifact_id}/approval",
        json={"approval_status": "APPROVED", "reviewer_note": "first"},
    ).json()
    assert datetime.fromisoformat(approved["approval_decided_at"]).utcoffset() == (
        UTC.utcoffset(None)
    )
    first_seed = datetime(2000, 1, 1, tzinfo=UTC)
    db_connection.execute(
        update(PdfArtifact)
        .where(PdfArtifact.id == artifact_id)
        .values(approval_decided_at=first_seed)
    )
    rejected_response = client.post(
        f"/api/v1/pdf-artifacts/{artifact_id}/approval",
        json={"approval_status": "REJECTED", "reviewer_note": "second"},
    )
    assert rejected_response.status_code == 200
    rejected = rejected_response.json()
    assert rejected["approval_status"] == "REJECTED"
    assert rejected["reviewer_note"] == "second"
    assert datetime.fromisoformat(rejected["approval_decided_at"]) > first_seed
    second_seed = datetime(2001, 1, 1, tzinfo=UTC)
    db_connection.execute(
        update(PdfArtifact)
        .where(PdfArtifact.id == artifact_id)
        .values(approval_decided_at=second_seed)
    )
    repeated = client.post(
        f"/api/v1/pdf-artifacts/{artifact_id}/approval",
        json={"approval_status": "REJECTED", "reviewer_note": "third"},
    ).json()
    assert datetime.fromisoformat(repeated["approval_decided_at"]) > second_seed
    reset = client.post(
        f"/api/v1/pdf-artifacts/{artifact_id}/approval",
        json={"approval_status": "DRAFT", "reviewer_note": "ignored"},
    )
    assert reset.status_code == 200
    assert reset.json()["approval_status"] == "DRAFT"
    assert reset.json()["approval_decided_at"] is None
    assert reset.json()["reviewer_note"] is None
    stored = db_connection.execute(
        select(PdfArtifact.__table__).where(PdfArtifact.id == artifact_id)
    ).mappings().one()
    assert stored["approval_status"] == "DRAFT"
    assert stored["approval_decided_at"] is None
    assert stored["reviewer_note"] is None


def test_pdf_artifact_review_missing_invalid_and_failure_are_atomic(
    client: TestClient,
    db_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    missing = client.post(
        "/api/v1/pdf-artifacts/999999/approval",
        json={"approval_status": "APPROVED"},
    )
    assert missing.status_code == 404
    assert missing.json() == {"detail": "PdfArtifact 999999 not found"}
    invalid = client.post(
        "/api/v1/pdf-artifacts/999999/approval",
        json={"approval_status": "PUBLISHED"},
    )
    assert invalid.status_code == 422

    _, created = _create_artifact(client, "review-failure")
    before = db_connection.execute(
        select(PdfArtifact.__table__).where(PdfArtifact.id == created["id"])
    ).mappings().one()

    def fail_update(*args: object) -> None:
        raise RuntimeError("injected review failure")

    monkeypatch.setattr(
        KnowledgeRepository,
        "update_pdf_artifact_approval",
        fail_update,
    )
    with pytest.raises(RuntimeError, match="injected review failure"):
        client.post(
            f"/api/v1/pdf-artifacts/{created['id']}/approval",
            json={"approval_status": "APPROVED"},
        )
    assert before == db_connection.execute(
        select(PdfArtifact.__table__).where(PdfArtifact.id == created["id"])
    ).mappings().one()


def test_pdf_artifact_download_is_unchanged_by_review_state(
    client: TestClient,
) -> None:
    _, created = _create_artifact(client, "review-download")
    artifact_id = created["id"]
    draft_download = client.get(f"/api/v1/pdf-artifacts/{artifact_id}/download")
    for status_value in ("APPROVED", "REJECTED"):
        decision = client.post(
            f"/api/v1/pdf-artifacts/{artifact_id}/approval",
            json={"approval_status": status_value},
        )
        assert decision.status_code == 200
        metadata = client.get(f"/api/v1/pdf-artifacts/{artifact_id}")
        assert metadata.json()["approval_status"] == status_value
        assert "pdf_bytes" not in metadata.json()
        download = client.get(f"/api/v1/pdf-artifacts/{artifact_id}/download")
        assert download.content == draft_download.content
        assert download.headers["content-type"] == draft_download.headers["content-type"]
        assert download.headers["content-length"] == draft_download.headers[
            "content-length"
        ]
        assert download.headers["content-disposition"] == draft_download.headers[
            "content-disposition"
        ]


@pytest.mark.parametrize(
    ("values", "constraint_name"),
    [
        ({"approval_status": "UNKNOWN"}, "ck_pdf_artifacts_approval_status"),
        (
            {"approval_status": "DRAFT", "approval_decided_at": func.now()},
            "ck_pdf_artifacts_approval_lifecycle",
        ),
        (
            {"approval_status": "DRAFT", "reviewer_note": "not allowed"},
            "ck_pdf_artifacts_approval_lifecycle",
        ),
        (
            {"approval_status": "APPROVED", "approval_decided_at": None},
            "ck_pdf_artifacts_approval_lifecycle",
        ),
        (
            {"approval_status": "REJECTED", "approval_decided_at": None},
            "ck_pdf_artifacts_approval_lifecycle",
        ),
    ],
)
def test_pdf_artifact_review_database_constraints(
    client: TestClient,
    db_connection: Connection,
    values: dict,
    constraint_name: str,
) -> None:
    _, created = _create_artifact(client, f"review-db-{len(str(values))}")
    with pytest.raises(IntegrityError) as error, db_connection.begin_nested():
        db_connection.execute(
            update(PdfArtifact).where(PdfArtifact.id == created["id"]).values(**values)
        )
    assert error.value.orig.diag.constraint_name == constraint_name
