import http.client
import ssl
from collections.abc import Generator
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
from app.models import SourceCandidate, SourceDiscoveryRun
from app.repositories.knowledge import KnowledgeRepository
from app.services.official_site_discovery import (
    HttpResponse,
    OfficialDiscoveryError,
    PinnedHttpsClient,
    canonicalize_site_root,
)


@pytest.fixture
def db_connection() -> Generator[Connection, None, None]:
    database_name = engine.url.database or ""
    if not database_name.endswith("_test"):
        pytest.fail("Official discovery tests require a dedicated *_test database")
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


def _counts(connection: Connection) -> tuple[int, int]:
    return (
        connection.scalar(select(func.count()).select_from(SourceDiscoveryRun)),
        connection.scalar(select(func.count()).select_from(SourceCandidate)),
    )


def _response(status: int, content_type: str, body: str) -> HttpResponse:
    return HttpResponse(status, content_type, body.encode())


def _install_responses(
    monkeypatch: pytest.MonkeyPatch,
    responses: dict[str, HttpResponse | OfficialDiscoveryError],
    requests: list[str],
) -> None:
    def fake_get(
        client: PinnedHttpsClient,
        url: str,
        *,
        max_bytes: int,
        unavailable_code: str,
    ) -> HttpResponse:
        requests.append(url)
        result = responses[url]
        if isinstance(result, OfficialDiscoveryError):
            raise result
        return result

    monkeypatch.setattr(PinnedHttpsClient, "get", fake_get)


class _FakeSocket:
    def __init__(self) -> None:
        self.closed = False
        self.timeout: float | None = None

    def settimeout(self, timeout: float) -> None:
        self.timeout = timeout

    def close(self) -> None:
        self.closed = True


class _FakeResponse:
    def __init__(
        self,
        body: bytes = b"ok",
        *,
        status: int = 200,
        location: str | None = None,
        read_error: Exception | None = None,
    ) -> None:
        self.status = status
        self.body = body
        self.location = location
        self.read_error = read_error
        self.offset = 0
        self.closed = False

    def getheader(self, name: str, default: str | None = None) -> str | None:
        if name == "Location":
            return self.location
        if name == "Content-Type":
            return "application/xml"
        return default

    def read(self, size: int) -> bytes:
        if self.read_error is not None:
            raise self.read_error
        chunk = self.body[self.offset : self.offset + size]
        self.offset += len(chunk)
        return chunk

    def close(self) -> None:
        self.closed = True


class _FakeConnection:
    def __init__(
        self,
        response: _FakeResponse,
        *,
        request_error: Exception | None = None,
        response_error: Exception | None = None,
    ) -> None:
        self.response = response
        self.request_error = request_error
        self.response_error = response_error
        self.sock: _FakeSocket | None = None
        self.closed = False
        self.requests: list[tuple[str, str]] = []

    def request(self, method: str, target: str, **kwargs: object) -> None:
        self.requests.append((method, target))
        if self.request_error is not None:
            raise self.request_error

    def getresponse(self) -> _FakeResponse:
        if self.response_error is not None:
            raise self.response_error
        return self.response

    def close(self) -> None:
        self.closed = True
        if self.sock is not None:
            self.sock.close()


class _FakeTransport:
    def __init__(
        self,
        responses: list[_FakeResponse],
        *,
        tls_error: Exception | None = None,
        request_error: Exception | None = None,
        response_error: Exception | None = None,
    ) -> None:
        self.responses = responses
        self.tls_error = tls_error
        self.request_error = request_error
        self.response_error = response_error
        self.raw_sockets: list[_FakeSocket] = []
        self.tls_sockets: list[_FakeSocket] = []
        self.connections: list[_FakeConnection] = []
        self.resolved_hosts: list[str] = []

    def resolve(self, hostname: str, *args: object, **kwargs: object) -> list[tuple]:
        self.resolved_hosts.append(hostname)
        return [(None, None, None, None, ("93.184.216.34", 443))]

    def create_socket(self, *args: object, **kwargs: object) -> _FakeSocket:
        raw_socket = _FakeSocket()
        self.raw_sockets.append(raw_socket)
        return raw_socket

    def create_context(self) -> SimpleNamespace:
        def wrap_socket(
            raw_socket: _FakeSocket,
            *,
            server_hostname: str,
        ) -> _FakeSocket:
            if self.tls_error is not None:
                raise self.tls_error
            tls_socket = _FakeSocket()
            self.tls_sockets.append(tls_socket)
            return tls_socket

        return SimpleNamespace(wrap_socket=wrap_socket)

    def create_connection(self, *args: object, **kwargs: object) -> _FakeConnection:
        connection = _FakeConnection(
            self.responses[len(self.connections)],
            request_error=self.request_error,
            response_error=self.response_error,
        )
        self.connections.append(connection)
        return connection


def _transport_client(
    transport: _FakeTransport,
    *,
    allowed_hosts: str = "example.gov.in",
    redirect_limit: int = 3,
) -> PinnedHttpsClient:
    config = SimpleNamespace(
        official_discovery_allowed_hosts=allowed_hosts,
        official_discovery_connect_timeout_seconds=1.0,
        official_discovery_read_timeout_seconds=2.0,
        official_discovery_redirect_limit=redirect_limit,
        official_discovery_user_agent="test-agent",
    )
    return PinnedHttpsClient(
        config,
        resolver=transport.resolve,
        socket_factory=transport.create_socket,
        ssl_context_factory=transport.create_context,
        connection_factory=transport.create_connection,
    )


def test_official_discovery_persists_deterministic_order_and_fixed_adapter(
    client: TestClient,
    db_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "official_discovery_allowed_hosts", "example.gov.in")
    requests: list[str] = []
    _install_responses(
        monkeypatch,
        {
            "https://example.gov.in/robots.txt": _response(
                200,
                "text/plain; charset=utf-8",
                "User-agent: *\nDisallow: /private\nAllow: /\n"
                "Sitemap: https://EXAMPLE.gov.in/site-index.xml\n",
            ),
            "https://example.gov.in/site-index.xml": _response(
                200,
                "application/xml",
                "<sitemapindex><sitemap><loc>https://example.gov.in/a.xml</loc>"
                "</sitemap></sitemapindex>",
            ),
            "https://example.gov.in/a.xml": _response(
                200,
                "application/xml",
                "<urlset>"
                "<url><loc>https://example.gov.in/assam/history-syllabus#part</loc></url>"
                "<url><loc>https://example.gov.in/syllabus?b=2&amp;a=1</loc></url>"
                "<url><loc>https://example.gov.in/private/assam-history</loc></url>"
                "<url><loc>https://EXAMPLE.GOV.IN/assam/history-syllabus</loc></url>"
                "<url><loc>https://example.gov.in/unrelated</loc></url>"
                "</urlset>",
            ),
        },
        requests,
    )
    commits = 0

    def record_commit(*args: object) -> None:
        nonlocal commits
        commits += 1

    event.listen(Session, "after_commit", record_commit)
    try:
        response = client.post(
            "/api/v1/source-discovery-runs/official-site",
            json={
                "query": "  Assam history syllabus  ",
                "site_root": "https://EXAMPLE.GOV.IN/",
            },
        )
    finally:
        event.remove(Session, "after_commit", record_commit)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["query"] == "Assam history syllabus"
    assert body["adapter_key"] == "official-sitemap-v1"
    assert body["status"] == "SUCCEEDED"
    assert body["error_message"] is None
    assert [candidate["position"] for candidate in body["candidates"]] == [0, 1]
    assert [candidate["location"] for candidate in body["candidates"]] == [
        "https://example.gov.in/assam/history-syllabus",
        "https://example.gov.in/syllabus?a=1&b=2",
    ]
    assert all(
        candidate[field] is None
        for candidate in body["candidates"]
        for field in ("title", "publisher", "snippet")
    )
    assert requests == [
        "https://example.gov.in/robots.txt",
        "https://example.gov.in/site-index.xml",
        "https://example.gov.in/a.xml",
    ]
    assert commits == 1
    assert _counts(db_connection) == (1, 2)


def test_fallback_sitemap_and_zero_relevant_results_succeed(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "official_discovery_allowed_hosts", "example.gov.in")
    requests: list[str] = []
    _install_responses(
        monkeypatch,
        {
            "https://example.gov.in/robots.txt": _response(
                200, "text/plain", "User-agent: *\nAllow: /\n"
            ),
            "https://example.gov.in/sitemap.xml": _response(
                200,
                "text/xml",
                "<urlset><url><loc>https://example.gov.in/geography</loc></url></urlset>",
            ),
        },
        requests,
    )
    response = client.post(
        "/api/v1/source-discovery-runs/official-site",
        json={"query": "history", "site_root": "https://example.gov.in"},
    )
    assert response.status_code == 201
    assert response.json()["status"] == "SUCCEEDED"
    assert response.json()["candidates"] == []
    assert requests[-1] == "https://example.gov.in/sitemap.xml"


@pytest.mark.parametrize(
    "site_root",
    [
        "http://example.gov.in",
        "https://user:password@example.gov.in",
        "https://example.gov.in:444",
        "https://example.gov.in/path",
        "https://example.gov.in?query=1",
        "https://example.gov.in#fragment",
        "https://127.0.0.1",
        "https://[::1]",
        "https://localhost",
        "not-a-url",
    ],
)
def test_invalid_site_roots_return_422_before_network_or_persistence(
    client: TestClient,
    db_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
    site_root: str,
) -> None:
    calls = 0

    def unexpected_get(*args: object, **kwargs: object) -> HttpResponse:
        nonlocal calls
        calls += 1
        raise AssertionError("network must not be called")

    monkeypatch.setattr(PinnedHttpsClient, "get", unexpected_get)
    before = _counts(db_connection)
    response = client.post(
        "/api/v1/source-discovery-runs/official-site",
        json={"query": "Assam", "site_root": site_root},
    )
    assert response.status_code == 422
    assert calls == 0
    assert _counts(db_connection) == before


@pytest.mark.parametrize("query", ["", "   ", "x" * 501])
def test_invalid_query_returns_422_without_persistence(
    client: TestClient,
    db_connection: Connection,
    query: str,
) -> None:
    before = _counts(db_connection)
    response = client.post(
        "/api/v1/source-discovery-runs/official-site",
        json={"query": query, "site_root": "https://example.gov.in"},
    )
    assert response.status_code == 422
    assert _counts(db_connection) == before


@pytest.mark.parametrize(
    ("responses", "expected_code"),
    [
        ({}, "HOST_NOT_ALLOWED"),
        (
            {
                "https://example.gov.in/robots.txt": OfficialDiscoveryError(
                    "DISCOVERY_TIMEOUT"
                )
            },
            "DISCOVERY_TIMEOUT",
        ),
        (
            {
                "https://example.gov.in/robots.txt": _response(
                    404, "text/plain", "upstream body must not be stored"
                )
            },
            "ROBOTS_UNAVAILABLE",
        ),
        (
            {
                "https://example.gov.in/robots.txt": _response(
                    200, "text/plain", "User-agent: *\nDisallow: /\n"
                )
            },
            "ROBOTS_DENIED",
        ),
    ],
)
def test_controlled_failures_persist_sanitized_terminal_runs(
    client: TestClient,
    db_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
    responses: dict[str, HttpResponse | OfficialDiscoveryError],
    expected_code: str,
) -> None:
    monkeypatch.setattr(
        settings,
        "official_discovery_allowed_hosts",
        "" if expected_code == "HOST_NOT_ALLOWED" else "example.gov.in",
    )
    requests: list[str] = []
    _install_responses(monkeypatch, responses, requests)
    commits = 0

    def record_commit(*args: object) -> None:
        nonlocal commits
        commits += 1

    event.listen(Session, "after_commit", record_commit)
    try:
        response = client.post(
            "/api/v1/source-discovery-runs/official-site",
            json={"query": "Assam", "site_root": "https://example.gov.in"},
        )
    finally:
        event.remove(Session, "after_commit", record_commit)
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "FAILED"
    assert body["error_message"] == expected_code
    assert body["candidates"] == []
    assert "upstream" not in body["error_message"]
    assert commits == 1
    assert _counts(db_connection) == (1, 0)


def test_network_completes_before_database_transaction_begins(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "official_discovery_allowed_hosts", "example.gov.in")
    order: list[str] = []

    def fake_get(
        client: PinnedHttpsClient,
        url: str,
        *,
        max_bytes: int,
        unavailable_code: str,
    ) -> HttpResponse:
        order.append(f"network:{url}")
        if url.endswith("robots.txt"):
            return _response(200, "text/plain", "User-agent: *\nAllow: /\n")
        return _response(200, "application/xml", "<urlset/>")

    def record_begin(*args: object) -> None:
        order.append("database:begin")

    monkeypatch.setattr(PinnedHttpsClient, "get", fake_get)
    event.listen(Session, "after_begin", record_begin)
    try:
        response = client.post(
            "/api/v1/source-discovery-runs/official-site",
            json={"query": "Assam", "site_root": "https://example.gov.in"},
        )
    finally:
        event.remove(Session, "after_begin", record_begin)

    assert response.status_code == 201
    assert order[:2] == [
        "network:https://example.gov.in/robots.txt",
        "network:https://example.gov.in/sitemap.xml",
    ]
    assert order[2:]
    assert all(step == "database:begin" for step in order[2:])


def test_persistence_failure_rolls_back_after_flush(
    client: TestClient,
    db_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "official_discovery_allowed_hosts", "example.gov.in")
    requests: list[str] = []
    _install_responses(
        monkeypatch,
        {
            "https://example.gov.in/robots.txt": _response(
                200, "text/plain", "User-agent: *\nAllow: /\n"
            ),
            "https://example.gov.in/sitemap.xml": _response(
                200,
                "application/xml",
                "<urlset><url><loc>https://example.gov.in/assam</loc></url></urlset>",
            ),
        },
        requests,
    )
    original_add = KnowledgeRepository.add_source_discovery_run
    commits = 0
    rollbacks = 0

    def fail_after_flush(
        repository: KnowledgeRepository,
        source_discovery_run: SourceDiscoveryRun,
    ) -> SourceDiscoveryRun:
        original_add(repository, source_discovery_run)
        raise RuntimeError("injected persistence failure")

    def record_commit(*args: object) -> None:
        nonlocal commits
        commits += 1

    def record_rollback(*args: object) -> None:
        nonlocal rollbacks
        rollbacks += 1

    monkeypatch.setattr(
        KnowledgeRepository,
        "add_source_discovery_run",
        fail_after_flush,
    )
    event.listen(Session, "after_commit", record_commit)
    event.listen(Session, "after_rollback", record_rollback)
    try:
        with pytest.raises(RuntimeError, match="injected persistence failure"):
            client.post(
                "/api/v1/source-discovery-runs/official-site",
                json={"query": "Assam", "site_root": "https://example.gov.in"},
            )
    finally:
        event.remove(Session, "after_commit", record_commit)
        event.remove(Session, "after_rollback", record_rollback)

    assert commits == 0
    assert rollbacks == 1
    assert _counts(db_connection) == (0, 0)


@pytest.mark.parametrize(
    ("content_type", "xml", "expected_code"),
    [
        ("text/html", "<urlset/>", "SITEMAP_INVALID"),
        ("application/xml", "not xml secret body", "SITEMAP_INVALID"),
        (
            "application/xml",
            "<!DOCTYPE x [<!ENTITY secret SYSTEM 'file:///etc/passwd'>]><urlset/>",
            "SITEMAP_INVALID",
        ),
    ],
)
def test_invalid_sitemaps_are_sanitized_failed_runs(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    content_type: str,
    xml: str,
    expected_code: str,
) -> None:
    monkeypatch.setattr(settings, "official_discovery_allowed_hosts", "example.gov.in")
    requests: list[str] = []
    _install_responses(
        monkeypatch,
        {
            "https://example.gov.in/robots.txt": _response(
                200, "text/plain", "User-agent: *\nAllow: /\n"
            ),
            "https://example.gov.in/sitemap.xml": _response(200, content_type, xml),
        },
        requests,
    )
    response = client.post(
        "/api/v1/source-discovery-runs/official-site",
        json={"query": "Assam", "site_root": "https://example.gov.in"},
    )
    assert response.status_code == 201
    assert response.json()["error_message"] == expected_code
    assert "secret" not in response.json()["error_message"]


def test_sitemap_cycle_and_limits_fail_without_candidates(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "official_discovery_allowed_hosts", "example.gov.in")
    requests: list[str] = []
    _install_responses(
        monkeypatch,
        {
            "https://example.gov.in/robots.txt": _response(
                200, "text/plain", "User-agent: *\nAllow: /\n"
            ),
            "https://example.gov.in/sitemap.xml": _response(
                200,
                "application/xml",
                "<sitemapindex><sitemap><loc>https://example.gov.in/sitemap.xml</loc>"
                "</sitemap></sitemapindex>",
            ),
        },
        requests,
    )
    response = client.post(
        "/api/v1/source-discovery-runs/official-site",
        json={"query": "Assam", "site_root": "https://example.gov.in"},
    )
    assert response.status_code == 201
    assert response.json()["error_message"] == "DISCOVERY_LIMIT_EXCEEDED"
    assert response.json()["candidates"] == []


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
def test_dns_policy_rejects_unsafe_mixed_and_empty_answers(answers: list[tuple]) -> None:
    config = SimpleNamespace(
        official_discovery_allowed_hosts="example.gov.in",
        official_discovery_redirect_limit=3,
    )
    client = PinnedHttpsClient(config, resolver=lambda *args, **kwargs: answers)
    with pytest.raises(OfficialDiscoveryError, match="DNS_POLICY_REJECTED"):
        client._validated_target("https://example.gov.in/sitemap.xml")


def test_discovered_cross_host_and_redirect_policy_are_rejected() -> None:
    assert canonicalize_site_root("HTTPS://Example.GOV.IN/") == "https://example.gov.in"
    config = SimpleNamespace(
        official_discovery_allowed_hosts="example.gov.in",
        official_discovery_redirect_limit=3,
    )
    client = PinnedHttpsClient(
        config,
        resolver=lambda *args, **kwargs: [
            (None, None, None, None, ("93.184.216.34", 443))
        ],
    )
    with pytest.raises(OfficialDiscoveryError, match="REDIRECT_POLICY_REJECTED"):
        client._validated_target("https://evil.example/sitemap.xml")


@pytest.mark.parametrize(
    ("value", "field"),
    [
        (0, "official_discovery_connect_timeout_seconds"),
        (-1, "official_discovery_read_timeout_seconds"),
        (0, "official_discovery_robots_max_bytes"),
        (-1, "official_discovery_sitemap_max_bytes"),
        (0, "official_discovery_sitemap_document_limit"),
        (-1, "official_discovery_inspected_url_limit"),
        (0, "official_discovery_candidate_limit"),
        (-1, "official_discovery_redirect_limit"),
    ],
)
def test_security_limits_fail_fast(value: int, field: str) -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            database_url="postgresql+psycopg://test/test",
            **{field: value},
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("official_discovery_allowed_hosts", "localhost"),
        ("official_discovery_allowed_hosts", "127.0.0.1"),
        ("official_discovery_allowed_hosts", "example.gov.in,,other.gov.in"),
        ("official_discovery_allowed_hosts", "bad host.gov.in"),
        ("official_discovery_user_agent", ""),
        ("official_discovery_user_agent", "agent\r\nInjected: value"),
        ("official_discovery_user_agent", "x" * 201),
    ],
)
def test_allowlist_and_user_agent_fail_fast(field: str, value: str) -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            database_url="postgresql+psycopg://test/test",
            **{field: value},
        )


@pytest.mark.parametrize(
    "site_root",
    [
        " https://example.gov.in",
        "https://example.gov.in/path with-space",
        "https://example.gov.in/line\nbreak",
        "https://example.gov.in/control\x80character",
        f"https://example.gov.in/{'x' * 2_026}",
    ],
)
def test_site_root_rejects_whitespace_controls_and_excessive_length(
    site_root: str,
) -> None:
    with pytest.raises(ValueError):
        canonicalize_site_root(site_root)


def test_pinned_client_success_reads_bound_and_closes_connection() -> None:
    transport = _FakeTransport([_FakeResponse(b"abcd")])
    client = _transport_client(transport)

    response = client.get(
        "https://example.gov.in/sitemap.xml",
        max_bytes=4,
        unavailable_code="SITEMAP_UNAVAILABLE",
    )

    assert response.body == b"abcd"
    assert transport.responses[0].closed is True
    assert transport.raw_sockets[0].closed is True
    assert transport.connections[0].closed is True
    assert transport.tls_sockets[0].closed is True
    assert transport.connections[0].requests == [("GET", "/sitemap.xml")]


@pytest.mark.parametrize(
    ("transport", "expected_code", "closed_collection"),
    [
        (
            _FakeTransport([_FakeResponse()], tls_error=ssl.SSLError("TLS failed")),
            "SITEMAP_UNAVAILABLE",
            "raw_sockets",
        ),
        (
            _FakeTransport([_FakeResponse()], request_error=OSError("request failed")),
            "SITEMAP_UNAVAILABLE",
            "connections",
        ),
        (
            _FakeTransport(
                [_FakeResponse()],
                response_error=http.client.BadStatusLine("bad response"),
            ),
            "SITEMAP_UNAVAILABLE",
            "connections",
        ),
        (
            _FakeTransport([_FakeResponse(read_error=TimeoutError("timed out"))]),
            "DISCOVERY_TIMEOUT",
            "connections",
        ),
        (
            _FakeTransport([_FakeResponse(b"12345")]),
            "RESPONSE_TOO_LARGE",
            "connections",
        ),
    ],
)
def test_pinned_client_closes_transport_on_every_failure(
    transport: _FakeTransport,
    expected_code: str,
    closed_collection: str,
) -> None:
    client = _transport_client(transport)

    with pytest.raises(OfficialDiscoveryError, match=expected_code):
        client.get(
            "https://example.gov.in/sitemap.xml",
            max_bytes=4,
            unavailable_code="SITEMAP_UNAVAILABLE",
        )

    resources = getattr(transport, closed_collection)
    assert resources
    assert all(resource.closed for resource in resources)
    assert all(raw_socket.closed for raw_socket in transport.raw_sockets)
    assert all(tls_socket.closed for tls_socket in transport.tls_sockets)
    assert all(connection.closed for connection in transport.connections)
    if expected_code in {"DISCOVERY_TIMEOUT", "RESPONSE_TOO_LARGE"}:
        assert transport.responses[0].closed is True


def test_pinned_client_revalidates_and_closes_every_redirect_hop() -> None:
    transport = _FakeTransport(
        [
            _FakeResponse(
                status=302,
                location="https://other.gov.in/next.xml",
            ),
            _FakeResponse(b"done"),
        ]
    )
    client = _transport_client(
        transport,
        allowed_hosts="example.gov.in,other.gov.in",
    )

    response = client.get(
        "https://example.gov.in/start.xml",
        max_bytes=10,
        unavailable_code="SITEMAP_UNAVAILABLE",
    )

    assert response.body == b"done"
    assert transport.resolved_hosts == ["example.gov.in", "other.gov.in"]
    assert [connection.closed for connection in transport.connections] == [True, True]


def test_pinned_client_enforces_redirect_limit_and_closes_every_hop() -> None:
    transport = _FakeTransport(
        [
            _FakeResponse(status=302, location="/second.xml"),
            _FakeResponse(status=302, location="/third.xml"),
        ]
    )
    client = _transport_client(transport, redirect_limit=1)

    with pytest.raises(OfficialDiscoveryError, match="REDIRECT_POLICY_REJECTED"):
        client.get(
            "https://example.gov.in/first.xml",
            max_bytes=10,
            unavailable_code="SITEMAP_UNAVAILABLE",
        )

    assert transport.resolved_hosts == ["example.gov.in", "example.gov.in"]
    assert [connection.closed for connection in transport.connections] == [True, True]


@pytest.mark.parametrize(
    "candidate_location",
    [
        "https://example.gov.in/bad url",
        f"https://example.gov.in/{'x' * 2_026}",
    ],
)
def test_discovered_urls_reject_unsafe_text_before_request_or_persistence(
    client: TestClient,
    db_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
    candidate_location: str,
) -> None:
    monkeypatch.setattr(settings, "official_discovery_allowed_hosts", "example.gov.in")
    requests: list[str] = []
    _install_responses(
        monkeypatch,
        {
            "https://example.gov.in/robots.txt": _response(
                200, "text/plain", "User-agent: *\nAllow: /\n"
            ),
            "https://example.gov.in/sitemap.xml": _response(
                200,
                "application/xml",
                f"<urlset><url><loc>{candidate_location}</loc></url></urlset>",
            ),
        },
        requests,
    )

    response = client.post(
        "/api/v1/source-discovery-runs/official-site",
        json={"query": "Assam", "site_root": "https://example.gov.in"},
    )

    assert response.status_code == 201
    assert response.json()["error_message"] == "REDIRECT_POLICY_REJECTED"
    assert requests == [
        "https://example.gov.in/robots.txt",
        "https://example.gov.in/sitemap.xml",
    ]
    assert _counts(db_connection) == (1, 0)


@pytest.mark.parametrize(
    "sitemap_location",
    [
        "https://example.gov.in/bad sitemap.xml",
        f"https://example.gov.in/{'x' * 2_026}",
    ],
)
def test_unsafe_sitemap_urls_are_rejected_before_request(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    sitemap_location: str,
) -> None:
    monkeypatch.setattr(settings, "official_discovery_allowed_hosts", "example.gov.in")
    requests: list[str] = []
    _install_responses(
        monkeypatch,
        {
            "https://example.gov.in/robots.txt": _response(
                200,
                "text/plain",
                f"User-agent: *\nAllow: /\nSitemap: {sitemap_location}\n",
            ),
        },
        requests,
    )

    response = client.post(
        "/api/v1/source-discovery-runs/official-site",
        json={"query": "Assam", "site_root": "https://example.gov.in"},
    )

    assert response.status_code == 201
    assert response.json()["error_message"] == "REDIRECT_POLICY_REJECTED"
    assert requests == ["https://example.gov.in/robots.txt"]


def test_configured_document_and_inspected_url_limits_are_enforced(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "official_discovery_allowed_hosts", "example.gov.in")
    monkeypatch.setattr(settings, "official_discovery_sitemap_document_limit", 1)
    monkeypatch.setattr(settings, "official_discovery_inspected_url_limit", 1)
    requests: list[str] = []
    _install_responses(
        monkeypatch,
        {
            "https://example.gov.in/robots.txt": _response(
                200, "text/plain", "User-agent: *\nAllow: /\n"
            ),
            "https://example.gov.in/sitemap.xml": _response(
                200,
                "application/xml",
                "<sitemapindex><sitemap><loc>https://example.gov.in/a.xml</loc>"
                "</sitemap></sitemapindex>",
            ),
        },
        requests,
    )

    document_response = client.post(
        "/api/v1/source-discovery-runs/official-site",
        json={"query": "Assam", "site_root": "https://example.gov.in"},
    )
    assert document_response.json()["error_message"] == "DISCOVERY_LIMIT_EXCEEDED"

    monkeypatch.setattr(settings, "official_discovery_sitemap_document_limit", 2)
    _install_responses(
        monkeypatch,
        {
            "https://example.gov.in/robots.txt": _response(
                200, "text/plain", "User-agent: *\nAllow: /\n"
            ),
            "https://example.gov.in/sitemap.xml": _response(
                200,
                "application/xml",
                "<urlset><url><loc>https://example.gov.in/assam-one</loc></url>"
                "<url><loc>https://example.gov.in/assam-two</loc></url></urlset>",
            ),
        },
        requests,
    )
    inspected_response = client.post(
        "/api/v1/source-discovery-runs/official-site",
        json={"query": "Assam", "site_root": "https://example.gov.in"},
    )
    assert inspected_response.json()["error_message"] == "DISCOVERY_LIMIT_EXCEEDED"


def test_configured_candidate_limit_is_enforced(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "official_discovery_allowed_hosts", "example.gov.in")
    monkeypatch.setattr(settings, "official_discovery_candidate_limit", 1)
    requests: list[str] = []
    _install_responses(
        monkeypatch,
        {
            "https://example.gov.in/robots.txt": _response(
                200, "text/plain", "User-agent: *\nAllow: /\n"
            ),
            "https://example.gov.in/sitemap.xml": _response(
                200,
                "application/xml",
                "<urlset><url><loc>https://example.gov.in/assam-one</loc></url>"
                "<url><loc>https://example.gov.in/assam-two</loc></url></urlset>",
            ),
        },
        requests,
    )

    response = client.post(
        "/api/v1/source-discovery-runs/official-site",
        json={"query": "Assam", "site_root": "https://example.gov.in"},
    )

    assert response.status_code == 201
    assert [candidate["location"] for candidate in response.json()["candidates"]] == [
        "https://example.gov.in/assam-one"
    ]


def test_repeated_requests_create_independent_runs(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "official_discovery_allowed_hosts", "example.gov.in")
    requests: list[str] = []
    responses = {
        "https://example.gov.in/robots.txt": _response(
            200, "text/plain", "User-agent: *\nAllow: /\n"
        ),
        "https://example.gov.in/sitemap.xml": _response(
            200,
            "application/xml",
            "<urlset><url><loc>https://example.gov.in/assam</loc></url></urlset>",
        ),
    }
    _install_responses(monkeypatch, responses, requests)
    payload = {"query": "Assam", "site_root": "https://example.gov.in"}
    first = client.post("/api/v1/source-discovery-runs/official-site", json=payload)
    second = client.post("/api/v1/source-discovery-runs/official-site", json=payload)
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] != second.json()["id"]
    assert first.json()["candidates"][0]["id"] != second.json()["candidates"][0]["id"]
