from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

from app.core.config import Settings, settings
from app.schemas.knowledge import SourceFetchStatus, SourceSnapshotContentType
from app.services.official_site_discovery import (
    MAX_DISCOVERY_URL_LENGTH,
    OfficialDiscoveryError,
    PinnedHttpsClient,
    PinnedHttpsErrorCodes,
    PinnedHttpsPolicy,
)

ROBOTS_DIRECTIVE = re.compile(r"^[A-Za-z][A-Za-z-]*$")
SUPPORTED_CONTENT_TYPES = {content_type.value for content_type in SourceSnapshotContentType}


@dataclass(frozen=True)
class SourceFetchResult:
    status: SourceFetchStatus
    requested_url: str
    final_url: str | None
    http_status: int | None
    error_code: str | None
    content_type: str | None = None
    content_bytes: bytes | None = None


class SourceFetchExecutor:
    def __init__(
        self,
        config: Settings = settings,
        client: PinnedHttpsClient | None = None,
    ) -> None:
        self.config = config
        self.allowed_hosts = frozenset(
            host.strip().rstrip(".").lower()
            for host in config.source_fetch_allowed_hosts.split(",")
            if host.strip()
        )
        policy = PinnedHttpsPolicy(
            allowed_hosts=self.allowed_hosts,
            connect_timeout_seconds=config.source_fetch_connect_timeout_seconds,
            read_timeout_seconds=config.source_fetch_read_timeout_seconds,
            redirect_limit=config.source_fetch_redirect_limit,
            user_agent=config.source_fetch_user_agent,
            accept=", ".join(sorted(SUPPORTED_CONTENT_TYPES | {"text/plain"})),
        )
        self.client = client or PinnedHttpsClient(config, policy=policy)

    def fetch(self, requested_url: str) -> SourceFetchResult:
        policy_error = _validate_source_url(requested_url, self.allowed_hosts)
        if policy_error is not None:
            return self._failed(requested_url, policy_error)

        parsed = urlsplit(requested_url)
        hostname = (parsed.hostname or "").rstrip(".").lower()
        robots_url = f"https://{hostname}/robots.txt"
        try:
            robots_response = self.client.get(
                robots_url,
                max_bytes=self.config.source_fetch_robots_max_bytes,
                unavailable_code="FETCH_ROBOTS_UNAVAILABLE",
                error_codes=ROBOTS_ERROR_CODES,
                read_non_success_body=False,
            )
        except OfficialDiscoveryError as error:
            return self._failed(requested_url, error.code)

        if robots_response.status_code != 200:
            return self._failed(requested_url, "FETCH_ROBOTS_UNAVAILABLE")
        if _normalized_media_type(robots_response.content_type) != "text/plain":
            return self._failed(requested_url, "FETCH_ROBOTS_INVALID")
        try:
            robots_text = robots_response.body.decode("utf-8", errors="strict")
            _validate_robots_text(robots_text)
            robots = RobotFileParser()
            robots.set_url(robots_response.final_url or robots_url)
            robots.parse(robots_text.splitlines())
        except (UnicodeDecodeError, ValueError):
            return self._failed(requested_url, "FETCH_ROBOTS_INVALID")
        if not robots.can_fetch(self.config.source_fetch_user_agent, requested_url):
            return self._failed(requested_url, "FETCH_ROBOTS_DENIED")

        try:
            response = self.client.get(
                requested_url,
                max_bytes=self.config.source_fetch_response_max_bytes,
                unavailable_code="FETCH_TRANSPORT",
                error_codes=SOURCE_ERROR_CODES,
                read_non_success_body=False,
            )
        except OfficialDiscoveryError as error:
            return self._failed(requested_url, error.code)

        final_url = response.final_url or requested_url
        if not 200 <= response.status_code <= 299:
            return self._failed(
                requested_url,
                "FETCH_HTTP_STATUS",
                final_url=final_url,
                http_status=response.status_code,
            )
        content_type = _normalized_media_type(response.content_type)
        if content_type not in SUPPORTED_CONTENT_TYPES:
            return self._failed(
                requested_url,
                "FETCH_UNSUPPORTED_CONTENT_TYPE",
                final_url=final_url,
                http_status=response.status_code,
            )
        if not response.body:
            return self._failed(
                requested_url,
                "FETCH_EMPTY_CONTENT",
                final_url=final_url,
                http_status=response.status_code,
            )
        return SourceFetchResult(
            status=SourceFetchStatus.SUCCEEDED,
            requested_url=requested_url,
            final_url=final_url,
            http_status=response.status_code,
            error_code=None,
            content_type=content_type,
            content_bytes=response.body,
        )

    @staticmethod
    def _failed(
        requested_url: str,
        error_code: str,
        *,
        final_url: str | None = None,
        http_status: int | None = None,
    ) -> SourceFetchResult:
        return SourceFetchResult(
            status=SourceFetchStatus.FAILED,
            requested_url=requested_url,
            final_url=final_url,
            http_status=http_status,
            error_code=error_code,
        )


ROBOTS_ERROR_CODES = PinnedHttpsErrorCodes(
    url_policy="FETCH_REDIRECT_POLICY",
    dns_policy="FETCH_DNS_POLICY",
    timeout="FETCH_ROBOTS_TIMEOUT",
    tls="FETCH_TLS",
    connect="FETCH_CONNECT",
    redirect_policy="FETCH_REDIRECT_POLICY",
    response_too_large="FETCH_ROBOTS_TOO_LARGE",
    transport="FETCH_ROBOTS_UNAVAILABLE",
)

SOURCE_ERROR_CODES = PinnedHttpsErrorCodes(
    url_policy="FETCH_REDIRECT_POLICY",
    dns_policy="FETCH_DNS_POLICY",
    timeout="FETCH_TIMEOUT",
    tls="FETCH_TLS",
    connect="FETCH_CONNECT",
    redirect_policy="FETCH_REDIRECT_POLICY",
    response_too_large="FETCH_RESPONSE_TOO_LARGE",
    transport="FETCH_TRANSPORT",
)


def _validate_source_url(url: str, allowed_hosts: frozenset[str]) -> str | None:
    if (
        not url
        or len(url) > MAX_DISCOVERY_URL_LENGTH
        or any(
            character.isspace()
            or ord(character) < 32
            or 127 <= ord(character) <= 159
            for character in url
        )
    ):
        return "FETCH_URL_POLICY"
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError:
        return "FETCH_URL_POLICY"
    hostname = (parsed.hostname or "").rstrip(".").lower()
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        pass
    else:
        return "FETCH_URL_POLICY"
    if (
        parsed.scheme.lower() != "https"
        or not hostname
        or hostname == "localhost"
        or "." not in hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
        or port not in (None, 443)
        or hostname not in allowed_hosts
    ):
        return "FETCH_URL_POLICY"
    return None


def _normalized_media_type(content_type: str) -> str:
    return content_type.split(";", 1)[0].strip().lower()


def _validate_robots_text(text: str) -> None:
    if not text.strip() or any(
        (ord(character) < 32 and character not in "\t\r\n")
        or 127 <= ord(character) <= 159
        for character in text
    ):
        raise ValueError("robots text is invalid")
    directives = []
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        if ":" not in line:
            raise ValueError("robots directive is malformed")
        name, _ = line.split(":", 1)
        if not ROBOTS_DIRECTIVE.fullmatch(name.strip()):
            raise ValueError("robots directive is malformed")
        directives.append(name.strip().lower())
    if "user-agent" not in directives:
        raise ValueError("robots user-agent directive is missing")
