from collections.abc import Generator
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import engine, get_db
from app.main import app
from app.models import SourceCandidate, SourceDiscoveryRun
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
    response = client.post(
        "/api/v1/source-discovery-runs/official-site",
        json={"query": "Assam", "site_root": "https://example.gov.in"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "FAILED"
    assert body["error_message"] == expected_code
    assert body["candidates"] == []
    assert "upstream" not in body["error_message"]
    assert _counts(db_connection) == (1, 0)


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
    assert canonicalize_site_root(" HTTPS://Example.GOV.IN/ ") == (
        "https://example.gov.in"
    )
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
