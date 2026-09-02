from collections.abc import Generator

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import engine
from app.models import Claim, Evidence, Source, Verification, VerificationEvidence


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    database_name = engine.url.database or ""
    if not database_name.endswith("_test"):
        pytest.fail("Verification evidence tests require a dedicated *_test database")

    with engine.connect() as connection:
        transaction = connection.begin()
        session = Session(bind=connection, expire_on_commit=False)
        try:
            yield session
        finally:
            session.close()
            if transaction.is_active:
                transaction.rollback()


def _persist_foundation(db_session: Session) -> tuple[Verification, list[Evidence]]:
    source = Source(
        title="Test source",
        source_type="official_notification",
        authority_tier=1,
        location="https://example.test/source",
        license_status="TEST_ONLY",
    )
    claim = Claim(statement="A test claim")
    db_session.add_all([source, claim])
    db_session.flush()

    evidence = [
        Evidence(source_id=source.id, content="First evidence"),
        Evidence(source_id=source.id, content="Second evidence"),
    ]
    verification = Verification(
        claim_id=claim.id,
        verdict="SUPPORTED",
        confidence=0.9,
        reasoning="Test verification",
    )
    db_session.add_all([*evidence, verification])
    db_session.flush()
    return verification, evidence


def test_verification_retains_ordered_evidence(db_session: Session) -> None:
    verification, evidence = _persist_foundation(db_session)
    db_session.add_all(
        [
            VerificationEvidence(
                verification=verification,
                evidence=evidence[1],
                evidence_role="CONTEXT",
                position=1,
            ),
            VerificationEvidence(
                verification=verification,
                evidence=evidence[0],
                evidence_role="SUPPORTS",
                position=0,
            ),
        ]
    )
    db_session.flush()
    db_session.expire(verification, ["evidence_links"])

    assert [link.position for link in verification.evidence_links] == [0, 1]
    assert [link.evidence_role for link in verification.evidence_links] == [
        "SUPPORTS",
        "CONTEXT",
    ]
    assert [item.content for item in verification.used_evidence] == [
        "First evidence",
        "Second evidence",
    ]


@pytest.mark.parametrize(
    ("evidence_role", "position"),
    [("INVALID", 0), ("SUPPORTS", -1)],
)
def test_verification_evidence_rejects_invalid_values(
    db_session: Session,
    evidence_role: str,
    position: int,
) -> None:
    verification, evidence = _persist_foundation(db_session)
    db_session.add(
        VerificationEvidence(
            verification=verification,
            evidence=evidence[0],
            evidence_role=evidence_role,
            position=position,
        )
    )

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_used_evidence_cannot_be_deleted(db_session: Session) -> None:
    verification, evidence = _persist_foundation(db_session)
    link = VerificationEvidence(
        verification=verification,
        evidence=evidence[0],
        evidence_role="SUPPORTS",
        position=0,
    )
    db_session.add(link)
    db_session.flush()
    link_key = (verification.id, evidence[0].id)

    savepoint = db_session.begin_nested()
    db_session.delete(evidence[0])
    with pytest.raises(IntegrityError):
        db_session.flush()
    savepoint.rollback()
    db_session.expire_all()

    retained_link = db_session.get(
        VerificationEvidence,
        link_key,
    )
    assert retained_link is not None
    assert retained_link.evidence_role == "SUPPORTS"
    assert retained_link.position == 0


def test_verification_evidence_rejects_duplicate_position(
    db_session: Session,
) -> None:
    verification, evidence = _persist_foundation(db_session)
    db_session.add_all(
        [
            VerificationEvidence(
                verification=verification,
                evidence=evidence[0],
                evidence_role="SUPPORTS",
                position=0,
            ),
            VerificationEvidence(
                verification=verification,
                evidence=evidence[1],
                evidence_role="CONTEXT",
                position=0,
            ),
        ]
    )

    with pytest.raises(IntegrityError):
        db_session.flush()
