"""Acquisition allowlist only; never a judgement about casualty evidence.

Changing these hosts allows bounded HTTPS FETCH only. The existing reviewer
independently validates evidence hosts, actual origin attribution, attack
geography, dates, civilian status, counts and deduplication.
"""
from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlsplit

GOOGLE_NEWS_HOST = "news.google.com"

# Frozen to the previously permitted network destinations. No new publisher
# is added without a verified FINAL Google RPC target and a separate decision.
PUBLISHER_TRANSPORT_HOSTS = frozenset({
    "suspilne.media", "armyinform.com.ua", "lb.ua", "npu.gov.ua",
    "vechirniy.kyiv.ua", "unian.ua", "ua.korrespondent.net", "t.me",
})


class CaptureError(Exception):
    """Transport failure, never an assertion that zero people were killed."""

    def __init__(self, reason: str, *, resolved_host: str | None = None,
                 transport_reason: str | None = None,
                 resolved_url_sha256: str | None = None,
                 redirect_count: int | None = None):
        super().__init__(reason)
        self.resolved_host = resolved_host
        self.transport_reason = transport_reason
        self.resolved_url_sha256 = resolved_url_sha256
        self.redirect_count = redirect_count


def diagnostic_host(url: str) -> str | None:
    """Sanitized HTTPS DNS hostname for failure receipts; NEVER for authorization.

    Omit URL paths, queries, credentials, IP literals and internal hostnames.
    The function performs no DNS lookup and no HTTP request.
    """
    if not isinstance(url, str) or not 1 <= len(url) <= 4096:
        return None
    try:
        p = urlsplit(url)
        host = (p.hostname or "").lower().rstrip(".")
        if (p.scheme != "https" or p.username or p.password or
                p.port not in (None, 443)):
            return None
    except ValueError:
        return None
    if not host or len(host) > 253 or "." not in host:
        return None
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
        return None
    labels = host.split(".")
    if any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
           for label in labels):
        return None
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return host
    return None


def safe_url(value: str, allow_google: bool = True) -> str:
    """Exact fixed-host HTTPS policy; validate every redirect and RPC target."""
    if not isinstance(value, str) or not value or len(value) > 4096:
        raise CaptureError("URL_INVALID")
    if any(ord(c) <= 32 or ord(c) == 127 for c in value):
        raise CaptureError("URL_UNSAFE_CHARACTERS")
    try:
        p = urlsplit(value)
        host = (p.hostname or "").lower().rstrip(".")
        port = p.port
    except ValueError as exc:
        raise CaptureError("URL_INVALID") from exc
    if p.scheme != "https" or not host or p.username or p.password or port not in (None, 443):
        raise CaptureError("URL_NOT_HTTPS_OR_NONSTANDARD_PORT")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise CaptureError("URL_IP_ADDRESS_BLOCKED")
    plain_host = host.removeprefix("www.")
    if plain_host not in PUBLISHER_TRANSPORT_HOSTS and not (
            allow_google and host == GOOGLE_NEWS_HOST):
        raise CaptureError("HOST_NOT_ALLOWED")
    if host == GOOGLE_NEWS_HOST and not (
            p.path.startswith("/rss/articles/") or p.path.startswith("/articles/")):
        raise CaptureError("GOOGLE_WRAPPER_PATH_NOT_ALLOWED")
    return value
