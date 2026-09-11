from __future__ import annotations

import http.client
import ipaddress
import re
import socket
import ssl
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser
from xml.etree import ElementTree

from app.core.config import Settings, settings

TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
REDIRECT_STATUSES = {301, 302, 303, 307, 308}
MAX_DISCOVERY_URL_LENGTH = 2_048


class OfficialDiscoveryError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class HttpResponse:
    status_code: int
    content_type: str
    body: bytes
    location: str | None = None


@dataclass(frozen=True)
class DiscoveredCandidate:
    location: str
    title: str | None = None
    publisher: str | None = None
    snippet: str | None = None


@dataclass(frozen=True)
class OfficialDiscoveryResult:
    candidates: list[DiscoveredCandidate]


def canonicalize_site_root(value: str) -> str:
    _validate_url_text(value, ValueError)
    raw = value
    parsed = urlsplit(raw)
    if (
        parsed.scheme.lower() != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in ("", "/")
    ):
        raise ValueError("site_root must be an HTTPS origin")
    try:
        port = parsed.port
    except ValueError as error:
        raise ValueError("site_root has an invalid port") from error
    hostname = parsed.hostname.rstrip(".").lower()
    if port not in (None, 443) or hostname == "localhost":
        raise ValueError("site_root must use the default HTTPS port")
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        pass
    else:
        raise ValueError("site_root must use a hostname")
    if not _valid_hostname(hostname):
        raise ValueError("site_root has an invalid hostname")
    return f"https://{hostname}"


def _valid_hostname(hostname: str) -> bool:
    if len(hostname) > 253 or "." not in hostname:
        return False
    labels = hostname.split(".")
    return all(
        label
        and len(label) <= 63
        and not label.startswith("-")
        and not label.endswith("-")
        and all(character.isalnum() or character == "-" for character in label)
        for label in labels
    )


class PinnedHttpsClient:
    def __init__(
        self,
        config: Settings = settings,
        resolver: Callable[..., list[tuple]] | None = None,
        socket_factory: Callable[..., object] | None = None,
        ssl_context_factory: Callable[[], object] | None = None,
        connection_factory: Callable[..., object] | None = None,
    ) -> None:
        self.config = config
        self.resolver = resolver or socket.getaddrinfo
        self.socket_factory = socket_factory or socket.create_connection
        self.ssl_context_factory = ssl_context_factory or ssl.create_default_context
        self.connection_factory = connection_factory or http.client.HTTPSConnection

    def get(self, url: str, *, max_bytes: int, unavailable_code: str) -> HttpResponse:
        current = url
        for redirect_count in range(self.config.official_discovery_redirect_limit + 1):
            parsed, address = self._validated_target(current)
            raw_socket = None
            tls_socket = None
            connection = None
            response = None
            try:
                raw_socket = self.socket_factory(
                    (address, 443),
                    timeout=self.config.official_discovery_connect_timeout_seconds,
                )
                context = self.ssl_context_factory()
                tls_socket = context.wrap_socket(raw_socket, server_hostname=parsed.hostname)
                tls_socket.settimeout(
                    self.config.official_discovery_read_timeout_seconds
                )
                connection = self.connection_factory(
                    parsed.hostname,
                    443,
                    context=context,
                    timeout=self.config.official_discovery_connect_timeout_seconds,
                )
                connection.sock = tls_socket
                target = urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
                connection.request(
                    "GET",
                    target,
                    headers={
                        "Host": parsed.hostname,
                        "User-Agent": self.config.official_discovery_user_agent,
                        "Accept": "text/plain, application/xml, text/xml",
                        "Connection": "close",
                    },
                )
                response = connection.getresponse()
                location = response.getheader("Location")
                content_type = response.getheader("Content-Type", "")
                body = self._read_bounded(response, max_bytes)
                status = response.status
            except TimeoutError as error:
                raise OfficialDiscoveryError("DISCOVERY_TIMEOUT") from error
            except OfficialDiscoveryError:
                raise
            except (OSError, ssl.SSLError, http.client.HTTPException) as error:
                raise OfficialDiscoveryError(unavailable_code) from error
            finally:
                if response is not None:
                    with suppress(Exception):
                        response.close()
                if connection is not None:
                    with suppress(Exception):
                        connection.close()
                if tls_socket is not None:
                    with suppress(Exception):
                        tls_socket.close()
                if raw_socket is not None:
                    with suppress(Exception):
                        raw_socket.close()

            if status in REDIRECT_STATUSES:
                if not location or redirect_count >= self.config.official_discovery_redirect_limit:
                    raise OfficialDiscoveryError("REDIRECT_POLICY_REJECTED")
                current = urljoin(current, location)
                continue
            return HttpResponse(status, content_type, body, location)
        raise OfficialDiscoveryError("REDIRECT_POLICY_REJECTED")

    def _validated_target(self, url: str):
        _validate_url_text(url, OfficialDiscoveryError)
        parsed = urlsplit(url)
        try:
            port = parsed.port
        except ValueError as error:
            raise OfficialDiscoveryError("REDIRECT_POLICY_REJECTED") from error
        hostname = (parsed.hostname or "").rstrip(".").lower()
        allowed = _allowed_hosts(self.config)
        if (
            parsed.scheme.lower() != "https"
            or not hostname
            or not _valid_hostname(hostname)
            or _is_ip_literal(hostname)
            or hostname == "localhost"
            or parsed.username is not None
            or parsed.password is not None
            or port not in (None, 443)
            or hostname not in allowed
        ):
            raise OfficialDiscoveryError("REDIRECT_POLICY_REJECTED")
        try:
            answers = self.resolver(hostname, 443, type=socket.SOCK_STREAM)
        except OSError as error:
            raise OfficialDiscoveryError("DNS_POLICY_REJECTED") from error
        addresses = sorted({answer[4][0] for answer in answers})
        if not addresses:
            raise OfficialDiscoveryError("DNS_POLICY_REJECTED")
        try:
            parsed_addresses = [ipaddress.ip_address(address) for address in addresses]
        except ValueError as error:
            raise OfficialDiscoveryError("DNS_POLICY_REJECTED") from error
        if any(not address.is_global for address in parsed_addresses):
            raise OfficialDiscoveryError("DNS_POLICY_REJECTED")
        return parsed, addresses[0]

    @staticmethod
    def _read_bounded(response: http.client.HTTPResponse, max_bytes: int) -> bytes:
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = response.read(min(65_536, max_bytes + 1 - total))
            if not chunk:
                return b"".join(chunks)
            chunks.append(chunk)
            total += len(chunk)
            if total > max_bytes:
                raise OfficialDiscoveryError("RESPONSE_TOO_LARGE")


class OfficialSiteDiscoveryAdapter:
    adapter_key = "official-sitemap-v1"

    def __init__(
        self,
        config: Settings = settings,
        client: PinnedHttpsClient | None = None,
    ) -> None:
        self.config = config
        self.client = client or PinnedHttpsClient(config)

    def discover(self, query: str, site_root: str) -> OfficialDiscoveryResult:
        allowed = _allowed_hosts(self.config)
        root_host = urlsplit(site_root).hostname
        if not allowed or root_host not in allowed:
            raise OfficialDiscoveryError("HOST_NOT_ALLOWED")

        robots_url = f"{site_root}/robots.txt"
        robots_response = self.client.get(
            robots_url,
            max_bytes=self.config.official_discovery_robots_max_bytes,
            unavailable_code="ROBOTS_UNAVAILABLE",
        )
        if robots_response.status_code != 200 or not _is_text(robots_response.content_type):
            raise OfficialDiscoveryError("ROBOTS_UNAVAILABLE")
        try:
            robots_text = robots_response.body.decode("utf-8")
        except UnicodeDecodeError as error:
            raise OfficialDiscoveryError("ROBOTS_UNAVAILABLE") from error
        robots = RobotFileParser()
        robots.set_url(robots_url)
        robots.parse(robots_text.splitlines())
        if not robots.can_fetch(self.config.official_discovery_user_agent, robots_url):
            raise OfficialDiscoveryError("ROBOTS_DENIED")

        declared = [
            line.split(":", 1)[1].strip()
            for line in robots_text.splitlines()
            if line.lower().startswith("sitemap:") and line.split(":", 1)[1].strip()
        ]
        sitemap_queue = declared or [f"{site_root}/sitemap.xml"]
        sitemap_queue = [
            _canonicalize_discovered_url(url, allowed, root_host) for url in sitemap_queue
        ]
        seen_documents: set[str] = set()
        candidate_urls: set[str] = set()
        inspected = 0

        while sitemap_queue:
            sitemap_url = sitemap_queue.pop(0)
            if sitemap_url in seen_documents:
                raise OfficialDiscoveryError("DISCOVERY_LIMIT_EXCEEDED")
            seen_documents.add(sitemap_url)
            if len(seen_documents) > self.config.official_discovery_sitemap_document_limit:
                raise OfficialDiscoveryError("DISCOVERY_LIMIT_EXCEEDED")
            if not robots.can_fetch(
                self.config.official_discovery_user_agent,
                sitemap_url,
            ):
                raise OfficialDiscoveryError("ROBOTS_DENIED")
            response = self.client.get(
                sitemap_url,
                max_bytes=self.config.official_discovery_sitemap_max_bytes,
                unavailable_code="SITEMAP_UNAVAILABLE",
            )
            if response.status_code != 200:
                raise OfficialDiscoveryError("SITEMAP_UNAVAILABLE")
            if not _is_xml(response.content_type):
                raise OfficialDiscoveryError("SITEMAP_INVALID")
            locations, is_index = _parse_sitemap(response.body)
            if is_index:
                for location in locations:
                    canonical = _canonicalize_discovered_url(
                        location,
                        allowed,
                        root_host,
                    )
                    if canonical in seen_documents or canonical in sitemap_queue:
                        raise OfficialDiscoveryError("DISCOVERY_LIMIT_EXCEEDED")
                    sitemap_queue.append(canonical)
                if (
                    len(seen_documents) + len(sitemap_queue)
                    > self.config.official_discovery_sitemap_document_limit
                ):
                    raise OfficialDiscoveryError("DISCOVERY_LIMIT_EXCEEDED")
                continue
            for location in locations:
                inspected += 1
                if inspected > self.config.official_discovery_inspected_url_limit:
                    raise OfficialDiscoveryError("DISCOVERY_LIMIT_EXCEEDED")
                canonical = _canonicalize_discovered_url(location, allowed, root_host)
                if robots.can_fetch(
                    self.config.official_discovery_user_agent,
                    canonical,
                ):
                    candidate_urls.add(canonical)

        tokens = set(TOKEN_PATTERN.findall(query.casefold()))
        scored = [
            (sum(token in url.casefold() for token in tokens), url)
            for url in candidate_urls
        ]
        relevant = sorted(
            ((score, url) for score, url in scored if score > 0),
            key=lambda item: (-item[0], item[1]),
        )
        if len(relevant) > self.config.official_discovery_candidate_limit:
            relevant = relevant[: self.config.official_discovery_candidate_limit]
        return OfficialDiscoveryResult(
            candidates=[DiscoveredCandidate(location=url) for _, url in relevant]
        )


def _allowed_hosts(config: Settings) -> set[str]:
    return {
        host.strip().rstrip(".").lower()
        for host in config.official_discovery_allowed_hosts.split(",")
        if host.strip()
    }


def _canonicalize_discovered_url(
    value: str,
    allowed_hosts: set[str],
    root_host: str | None,
) -> str:
    _validate_url_text(value, OfficialDiscoveryError)
    parsed = urlsplit(value)
    try:
        port = parsed.port
    except ValueError as error:
        raise OfficialDiscoveryError("REDIRECT_POLICY_REJECTED") from error
    hostname = (parsed.hostname or "").rstrip(".").lower()
    if (
        parsed.scheme.lower() != "https"
        or not hostname
        or not _valid_hostname(hostname)
        or _is_ip_literal(hostname)
        or hostname == "localhost"
        or parsed.username is not None
        or parsed.password is not None
        or port not in (None, 443)
        or hostname not in allowed_hosts
        or hostname != root_host
    ):
        raise OfficialDiscoveryError("REDIRECT_POLICY_REJECTED")
    query = urlencode(sorted(parse_qsl(parsed.query, keep_blank_values=True)))
    canonical = urlunsplit(("https", hostname, parsed.path or "/", query, ""))
    _validate_url_text(canonical, OfficialDiscoveryError)
    return canonical


def _validate_url_text(
    value: str,
    error_type: type[ValueError | OfficialDiscoveryError],
) -> None:
    if len(value) > MAX_DISCOVERY_URL_LENGTH or any(
        character.isspace()
        or ord(character) < 32
        or 127 <= ord(character) <= 159
        for character in value
    ):
        if error_type is OfficialDiscoveryError:
            raise OfficialDiscoveryError("REDIRECT_POLICY_REJECTED")
        raise ValueError("URL contains whitespace, control characters, or is too long")


def _parse_sitemap(body: bytes) -> tuple[list[str], bool]:
    upper = body.upper()
    if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
        raise OfficialDiscoveryError("SITEMAP_INVALID")
    try:
        root = ElementTree.fromstring(body)
    except (ElementTree.ParseError, ValueError) as error:
        raise OfficialDiscoveryError("SITEMAP_INVALID") from error
    root_name = root.tag.rsplit("}", 1)[-1]
    if root_name not in {"urlset", "sitemapindex"}:
        raise OfficialDiscoveryError("SITEMAP_INVALID")
    locations = [
        (element.text or "").strip()
        for element in root.iter()
        if element.tag.rsplit("}", 1)[-1] == "loc" and (element.text or "").strip()
    ]
    return locations, root_name == "sitemapindex"


def _is_ip_literal(hostname: str) -> bool:
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        return False
    return True


def _is_text(content_type: str) -> bool:
    return content_type.split(";", 1)[0].strip().lower() == "text/plain"


def _is_xml(content_type: str) -> bool:
    media_type = content_type.split(";", 1)[0].strip().lower()
    return media_type in {"application/xml", "text/xml"} or media_type.endswith("+xml")
