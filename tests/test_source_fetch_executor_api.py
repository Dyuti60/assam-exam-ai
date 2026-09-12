import base64
from collections.abc import Generator
from hashlib import sha256
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import event, func, select
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from app.core.config import Settings, settings
from app.core.database import engine, get_db
from app.main import app
from app.models import Source, SourceFetchRun, SourceSnapshot
from app.repositories import KnowledgeRepository
from app.schemas.knowledge import SourceFetchStatus
from app.services.official_site_discovery import (
    HttpResponse,
    OfficialDiscoveryError,
    PinnedHttpsClient,
    PinnedHttpsPolicy,
)
from app.services.source_fetch_executor import SourceFetchExecutor, SourceFetchResult


@pytest.fixture
def db_connection() -> Generator[Connection, None, None]:
    database_name = engine.url.database or ""
    if not database_name.endswith("_test"):
        pytest.fail("Source executor tests require a dedicated *_test database")
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


def _create_source(client: TestClient, location: str, title: str = "Source") -> dict:
    response = client.post(
        "/api/v1/sources",
        json={
            "title": title,
            "publisher": "Government publisher",
            "source_type": "OFFICIAL",
            "authority_tier": 1,
            "location": location,
            "license_status": "OFFICIAL_PUBLICATION",
            "content_hash": None,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _counts(connection: Connection) -> tuple[int, int]:
    return (
        connection.scalar(select(func.count()).select_from(SourceFetchRun)),
        connection.scalar(select(func.count()).select_from(SourceSnapshot)),
    )


def _install_responses(
    monkeypatch: pytest.MonkeyPatch,
    responses: dict[str, HttpResponse | OfficialDiscoveryError],
    calls: list[str],
) -> None:
    def fake_get(
        pinned_client: PinnedHttpsClient,
        url: str,
        **kwargs: object,
    ) -> HttpResponse:
        calls.append(url)
        result = responses[url]
        if isinstance(result, OfficialDiscoveryError):
            raise result
        return result

    monkeypatch.setattr(PinnedHttpsClient, "get", fake_get)


@pytest.mark.parametrize(
    ("body", "upstream_type", "stored_type"),
    [
        (b"%PDF-1.4\nexact\n%%EOF", "Application/PDF; version=1.4", "application/pdf"),
        ("অসমীয়া UTF-8".encode(), "TEXT/PLAIN; charset=utf-8", "text/plain"),
    ],
)
def test_fetch_success_persists_exact_t053_snapshot(
    client: TestClient,
    db_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
    body: bytes,
    upstream_type: str,
    stored_type: str,
) -> None:
    location = f"https://example.gov.in/files/{stored_type.replace('/', '-')}?v=1"
    source = _create_source(client, location)
    monkeypatch.setattr(settings, "source_fetch_allowed_hosts", "example.gov.in")
    calls: list[str] = []
    _install_responses(
        monkeypatch,
        {
            "https://example.gov.in/robots.txt": HttpResponse(
                200,
                "text/plain; charset=utf-8",
                b"User-agent: AssamExamAI-SourceFetch/1.0\nAllow: /\n",
                final_url="https://example.gov.in/robots.txt",
            ),
            location: HttpResponse(
                200,
                upstream_type,
                body,
                final_url=location,
            ),
        },
        calls,
    )
    commits = 0

    def record_commit(*args: object) -> None:
        nonlocal commits
        commits += 1

    before_source = db_connection.execute(
        select(Source).where(Source.id == source["id"])
    ).one()

    event.listen(Session, "after_commit", record_commit)
    try:
        response = client.post(f"/api/v1/sources/{source['id']}/fetch")
    finally:
        event.remove(Session, "after_commit", record_commit)

    assert response.status_code == 201, response.text
    assert commits == 1
    result = response.json()
    assert result["source_id"] == source["id"]
    assert result["requested_url"] == location
    assert result["status"] == "SUCCEEDED"
    assert result["final_url"] == location
    assert result["http_status"] == 200
    assert result["error_code"] is None
    snapshot = result["snapshot"]
    assert snapshot["content_type"] == stored_type
    assert base64.b64decode(snapshot["content_base64"]) == body
    assert snapshot["byte_size"] == len(body)
    assert snapshot["sha256"] == sha256(body).hexdigest()
    assert calls == ["https://example.gov.in/robots.txt", location]
    assert _counts(db_connection) == (1, 1)
    assert db_connection.execute(
        select(Source).where(Source.id == source["id"])
    ).one() == before_source


def test_missing_source_returns_404_before_network(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def unexpected_fetch(*args: object, **kwargs: object) -> None:
        nonlocal calls
        calls += 1
        raise AssertionError("network executor must not run")

    monkeypatch.setattr(SourceFetchExecutor, "fetch", unexpected_fetch)
    response = client.post("/api/v1/sources/999999/fetch")
    assert response.status_code == 404
    assert response.json() == {"detail": "Source 999999 not found"}
    assert calls == 0


@pytest.mark.parametrize(
    "location",
    [
        "http://example.gov.in/file",
        "https://user:secret@example.gov.in/file",
        "https://example.gov.in/file#fragment",
        "https://example.gov.in:444/file",
        "https://127.0.0.1/file",
        "https://[::1]/file",
        "https://localhost/file",
        "not-a-url",
        "https://example.gov.in/path with-space",
        "https://example.gov.in/control\x80",
        f"https://example.gov.in/{'x' * 2_030}",
        "https://not-allowed.gov.in/file",
    ],
)
def test_stored_url_policy_failures_persist_without_network(
    client: TestClient,
    db_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
    location: str,
) -> None:
    source = _create_source(client, location)
    monkeypatch.setattr(settings, "source_fetch_allowed_hosts", "example.gov.in")
    calls = 0

    def unexpected_get(*args: object, **kwargs: object) -> None:
        nonlocal calls
        calls += 1
        raise AssertionError("policy rejection must precede network")

    monkeypatch.setattr(PinnedHttpsClient, "get", unexpected_get)
    response = client.post(f"/api/v1/sources/{source['id']}/fetch")
    assert response.status_code == 201
    assert response.json()["status"] == "FAILED"
    assert response.json()["error_code"] == "FETCH_URL_POLICY"
    assert response.json()["snapshot"] is None
    assert calls == 0
    assert _counts(db_connection) == (1, 0)


def test_empty_allowlist_disables_fetch_without_network(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _create_source(client, "https://example.gov.in/file")
    monkeypatch.setattr(settings, "source_fetch_allowed_hosts", "")
    monkeypatch.setattr(
        PinnedHttpsClient,
        "get",
        lambda *args, **kwargs: pytest.fail("network must be disabled"),
    )
    response = client.post(f"/api/v1/sources/{source['id']}/fetch")
    assert response.status_code == 201
    assert response.json()["error_code"] == "FETCH_URL_POLICY"


@pytest.mark.parametrize(
    ("robots", "expected_code", "source_called"),
    [
        (HttpResponse(404, "text/plain", b"", final_url="https://example.gov.in/robots.txt"), "FETCH_ROBOTS_UNAVAILABLE", False),
        (HttpResponse(200, "application/pdf", b"x", final_url="https://example.gov.in/robots.txt"), "FETCH_ROBOTS_INVALID", False),
        (HttpResponse(200, "text/plain", b"not a robots file", final_url="https://example.gov.in/robots.txt"), "FETCH_ROBOTS_INVALID", False),
        (HttpResponse(200, "text/plain", b"\xff", final_url="https://example.gov.in/robots.txt"), "FETCH_ROBOTS_INVALID", False),
        (HttpResponse(200, "text/plain", b"User-agent: *\nDisallow: /private\n", final_url="https://example.gov.in/robots.txt"), "FETCH_ROBOTS_DENIED", False),
        (OfficialDiscoveryError("FETCH_ROBOTS_TIMEOUT"), "FETCH_ROBOTS_TIMEOUT", False),
        (OfficialDiscoveryError("FETCH_ROBOTS_TOO_LARGE"), "FETCH_ROBOTS_TOO_LARGE", False),
    ],
)
def test_current_robots_failures_are_sanitized(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    robots: HttpResponse | OfficialDiscoveryError,
    expected_code: str,
    source_called: bool,
) -> None:
    location = "https://example.gov.in/private/file"
    source = _create_source(client, location)
    monkeypatch.setattr(settings, "source_fetch_allowed_hosts", "example.gov.in")
    calls: list[str] = []
    _install_responses(
        monkeypatch,
        {"https://example.gov.in/robots.txt": robots},
        calls,
    )
    response = client.post(f"/api/v1/sources/{source['id']}/fetch")
    assert response.status_code == 201
    assert response.json()["error_code"] == expected_code
    assert response.json()["snapshot"] is None
    assert calls == ["https://example.gov.in/robots.txt"]
    assert source_called is False


@pytest.mark.parametrize(
    ("source_result", "expected_code", "final_url", "http_status"),
    [
        (HttpResponse(503, "text/plain", b"secret", final_url="https://example.gov.in/file"), "FETCH_HTTP_STATUS", "https://example.gov.in/file", 503),
        (HttpResponse(200, "application/octet-stream", b"secret", final_url="https://example.gov.in/file"), "FETCH_UNSUPPORTED_CONTENT_TYPE", "https://example.gov.in/file", 200),
        (HttpResponse(200, "", b"secret", final_url="https://example.gov.in/file"), "FETCH_UNSUPPORTED_CONTENT_TYPE", "https://example.gov.in/file", 200),
        (HttpResponse(200, "text/plain", b"", final_url="https://example.gov.in/file"), "FETCH_EMPTY_CONTENT", "https://example.gov.in/file", 200),
        (OfficialDiscoveryError("FETCH_RESPONSE_TOO_LARGE"), "FETCH_RESPONSE_TOO_LARGE", None, None),
        (OfficialDiscoveryError("FETCH_TIMEOUT"), "FETCH_TIMEOUT", None, None),
        (OfficialDiscoveryError("FETCH_DNS_POLICY"), "FETCH_DNS_POLICY", None, None),
        (OfficialDiscoveryError("FETCH_TLS"), "FETCH_TLS", None, None),
        (OfficialDiscoveryError("FETCH_CONNECT"), "FETCH_CONNECT", None, None),
        (OfficialDiscoveryError("FETCH_REDIRECT_POLICY"), "FETCH_REDIRECT_POLICY", None, None),
        (OfficialDiscoveryError("FETCH_TRANSPORT"), "FETCH_TRANSPORT", None, None),
    ],
)
def test_source_failures_persist_stable_terminal_results(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    source_result: HttpResponse | OfficialDiscoveryError,
    expected_code: str,
    final_url: str | None,
    http_status: int | None,
) -> None:
    location = "https://example.gov.in/file"
    source = _create_source(client, location)
    monkeypatch.setattr(settings, "source_fetch_allowed_hosts", "example.gov.in")
    calls: list[str] = []
    _install_responses(
        monkeypatch,
        {
            "https://example.gov.in/robots.txt": HttpResponse(
                200,
                "text/plain",
                b"User-agent: *\nAllow: /\n",
                final_url="https://example.gov.in/robots.txt",
            ),
            location: source_result,
        },
        calls,
    )
    response = client.post(f"/api/v1/sources/{source['id']}/fetch")
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "FAILED"
    assert body["error_code"] == expected_code
    assert body["final_url"] == final_url
    assert body["http_status"] == http_status
    assert body["snapshot"] is None
    assert "secret" not in body["error_code"]


def test_network_runs_without_database_transaction_and_commits_once(
    client: TestClient,
    db_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _create_source(client, "https://example.gov.in/file")
    sessions: list[Session] = []
    commits = 0
    statements: list[str] = []

    def record_begin(session: Session, *args: object) -> None:
        sessions.append(session)

    def fake_fetch(executor: SourceFetchExecutor, requested_url: str):
        assert sessions
        assert all(not session.in_transaction() for session in sessions)
        return SourceFetchExecutor._failed(requested_url, "FETCH_TIMEOUT")

    def record_commit(*args: object) -> None:
        nonlocal commits
        commits += 1

    def record_statement(
        connection: Connection,
        cursor: object,
        statement: str,
        parameters: object,
        context: object,
        executemany: bool,
    ) -> None:
        statements.append(statement.upper())

    monkeypatch.setattr(SourceFetchExecutor, "fetch", fake_fetch)
    event.listen(Session, "after_begin", record_begin)
    event.listen(Session, "after_commit", record_commit)
    event.listen(db_connection, "before_cursor_execute", record_statement)
    try:
        response = client.post(f"/api/v1/sources/{source['id']}/fetch")
    finally:
        event.remove(Session, "after_begin", record_begin)
        event.remove(Session, "after_commit", record_commit)
        event.remove(db_connection, "before_cursor_execute", record_statement)
    assert response.status_code == 201
    assert response.json()["error_code"] == "FETCH_TIMEOUT"
    assert commits == 1
    assert statements
    assert all("FOR UPDATE" not in statement for statement in statements)


def test_executor_and_manual_raw_bytes_share_identical_metadata(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    location = "https://example.gov.in/shared"
    source = _create_source(client, location)
    content = b"same exact bytes"
    monkeypatch.setattr(settings, "source_fetch_allowed_hosts", "example.gov.in")
    monkeypatch.setattr(
        SourceFetchExecutor,
        "fetch",
        lambda executor, requested_url: SourceFetchResult(
            status=SourceFetchStatus.SUCCEEDED,
            requested_url=requested_url,
            final_url=requested_url,
            http_status=200,
            error_code=None,
            content_type="text/plain",
            content_bytes=content,
        ),
    )
    executed = client.post(f"/api/v1/sources/{source['id']}/fetch")
    manual = client.post(
        f"/api/v1/sources/{source['id']}/fetch-runs",
        json={
            "status": "SUCCEEDED",
            "requested_url": location,
            "final_url": location,
            "http_status": 200,
            "content_type": "text/plain",
            "content_base64": base64.b64encode(content).decode(),
        },
    )
    assert executed.status_code == manual.status_code == 201
    for field in ("byte_size", "sha256", "content_base64", "content_type"):
        assert executed.json()["snapshot"][field] == manual.json()["snapshot"][field]


def test_repeated_direct_and_promoted_source_attempts_are_independent(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    direct = _create_source(client, "https://example.gov.in/direct")
    candidate = client.post(
        "/api/v1/source-discovery-runs",
        json={
            "query": "source fetch",
            "adapter_key": "manual-test-v1",
            "status": "SUCCEEDED",
            "error_message": None,
            "candidates": [{"location": "https://example.gov.in/promoted"}],
        },
    ).json()["candidates"][0]
    client.post(
        f"/api/v1/source-candidates/{candidate['id']}/approval",
        json={"approval_status": "APPROVED", "reviewer_note": None},
    )
    promoted = client.post(
        f"/api/v1/source-candidates/{candidate['id']}/promote",
        json={
            "title": "Promoted",
            "publisher": "Government",
            "source_type": "OFFICIAL",
            "authority_tier": 1,
            "license_status": "OFFICIAL_PUBLICATION",
        },
    ).json()["source"]
    rejected = client.post(
        f"/api/v1/source-candidates/{candidate['id']}/approval",
        json={"approval_status": "REJECTED", "reviewer_note": "later decision"},
    )
    assert rejected.status_code == 200
    monkeypatch.setattr(
        SourceFetchExecutor,
        "fetch",
        lambda executor, url: SourceFetchResult(
            status=SourceFetchStatus.SUCCEEDED,
            requested_url=url,
            final_url=url,
            http_status=200,
            error_code=None,
            content_type="text/plain",
            content_bytes=b"stored",
        ),
    )
    responses = [
        client.post(f"/api/v1/sources/{source_id}/fetch")
        for source_id in (direct["id"], direct["id"], promoted["id"])
    ]
    assert all(response.status_code == 201 for response in responses)
    assert all(response.json()["status"] == "SUCCEEDED" for response in responses)
    assert len({response.json()["id"] for response in responses}) == 3


def test_post_flush_failure_rolls_back_executor_result(
    client: TestClient,
    db_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _create_source(client, "https://example.gov.in/rollback")
    monkeypatch.setattr(
        SourceFetchExecutor,
        "fetch",
        lambda executor, url: SourceFetchExecutor._failed(url, "FETCH_TIMEOUT"),
    )
    original_add = KnowledgeRepository.add_source_fetch_run
    commits = 0
    rollbacks = 0

    def fail_after_flush(repository: KnowledgeRepository, run: SourceFetchRun):
        original_add(repository, run)
        raise RuntimeError("injected post-flush failure")

    def record_commit(*args: object) -> None:
        nonlocal commits
        commits += 1

    def record_rollback(*args: object) -> None:
        nonlocal rollbacks
        rollbacks += 1

    monkeypatch.setattr(KnowledgeRepository, "add_source_fetch_run", fail_after_flush)
    event.listen(Session, "after_commit", record_commit)
    event.listen(Session, "after_rollback", record_rollback)
    try:
        with pytest.raises(RuntimeError, match="injected post-flush failure"):
            client.post(f"/api/v1/sources/{source['id']}/fetch")
    finally:
        event.remove(Session, "after_commit", record_commit)
        event.remove(Session, "after_rollback", record_rollback)
    assert commits == 0
    assert rollbacks == 2  # one transaction break before I/O, one failed persistence
    assert _counts(db_connection) == (0, 0)


def test_source_identity_race_cannot_persist_mismatched_provenance(
    client: TestClient,
    db_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _create_source(client, "https://example.gov.in/race")
    original_get = KnowledgeRepository.get_source
    calls = 0

    def disappear_on_revalidation(repository: KnowledgeRepository, source_id: int):
        nonlocal calls
        calls += 1
        return original_get(repository, source_id) if calls == 1 else None

    monkeypatch.setattr(KnowledgeRepository, "get_source", disappear_on_revalidation)
    monkeypatch.setattr(
        SourceFetchExecutor,
        "fetch",
        lambda executor, url: SourceFetchExecutor._failed(url, "FETCH_TIMEOUT"),
    )
    response = client.post(f"/api/v1/sources/{source['id']}/fetch")
    assert response.status_code == 404
    assert _counts(db_connection) == (0, 0)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_fetch_allowed_hosts", "localhost"),
        ("source_fetch_allowed_hosts", "127.0.0.1"),
        ("source_fetch_connect_timeout_seconds", 0),
        ("source_fetch_read_timeout_seconds", 0),
        ("source_fetch_robots_max_bytes", 0),
        ("source_fetch_response_max_bytes", 0),
        ("source_fetch_redirect_limit", -1),
        ("source_fetch_user_agent", ""),
        ("source_fetch_user_agent", "agent\r\nInjected: yes"),
    ],
)
def test_source_fetch_configuration_fails_fast(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            database_url="postgresql+psycopg://test/test",
            **{field: value},
        )


def test_source_fetch_response_limit_cannot_exceed_snapshot_limit() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            database_url="postgresql+psycopg://test/test",
            source_snapshot_max_bytes=10,
            source_fetch_response_max_bytes=11,
        )


@pytest.mark.parametrize(
    "answers",
    [
        [(None, None, None, None, ("127.0.0.1", 443))],
        [(None, None, None, None, ("::1", 443, 0, 0))],
        [
            (None, None, None, None, ("93.184.216.34", 443)),
            (None, None, None, None, ("10.0.0.1", 443)),
        ],
        [],
    ],
)
def test_source_policy_rejects_unsafe_mixed_and_empty_dns(answers: list[tuple]) -> None:
    policy = PinnedHttpsPolicy(
        allowed_hosts=frozenset({"example.gov.in"}),
        connect_timeout_seconds=1,
        read_timeout_seconds=1,
        redirect_limit=1,
        user_agent="test-agent",
        accept="text/plain",
    )
    pinned = PinnedHttpsClient(
        resolver=lambda *args, **kwargs: answers,
        policy=policy,
    )
    with pytest.raises(OfficialDiscoveryError, match="DNS_POLICY_REJECTED"):
        pinned._validated_target("https://example.gov.in/file")


def test_pinned_source_policy_retains_hostname_tls_and_validated_ip() -> None:
    connected: list[tuple[str, int]] = []
    server_names: list[str] = []

    class Socket:
        def settimeout(self, timeout: float) -> None:
            pass

        def close(self) -> None:
            pass

    def socket_factory(address: tuple[str, int], **kwargs: object) -> Socket:
        connected.append(address)
        return Socket()

    def ssl_factory():
        def wrap_socket(raw_socket: Socket, *, server_hostname: str) -> Socket:
            server_names.append(server_hostname)
            return Socket()

        return SimpleNamespace(wrap_socket=wrap_socket)

    class Response:
        status = 200

        def getheader(self, name: str, default: str | None = None):
            return "text/plain" if name == "Content-Type" else default

        def read(self, size: int) -> bytes:
            return b""

        def close(self) -> None:
            pass

    class Connection:
        sock = None

        def request(self, *args: object, **kwargs: object) -> None:
            pass

        def getresponse(self) -> Response:
            return Response()

        def close(self) -> None:
            pass

    policy = PinnedHttpsPolicy(
        allowed_hosts=frozenset({"example.gov.in"}),
        connect_timeout_seconds=1,
        read_timeout_seconds=1,
        redirect_limit=0,
        user_agent="test-agent",
        accept="text/plain",
    )
    pinned = PinnedHttpsClient(
        resolver=lambda *args, **kwargs: [
            (None, None, None, None, ("93.184.216.34", 443))
        ],
        socket_factory=socket_factory,
        ssl_context_factory=ssl_factory,
        connection_factory=lambda *args, **kwargs: Connection(),
        policy=policy,
    )
    pinned.get("https://example.gov.in/file", max_bytes=10, unavailable_code="X")
    assert connected == [("93.184.216.34", 443)]
    assert server_names == ["example.gov.in"]
