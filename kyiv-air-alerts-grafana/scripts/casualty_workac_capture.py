#!/usr/bin/env python3
"""Work AC: bounded publisher capture into existing Work X/AA shadow cards.

No source HTTP unless explicitly called with enabled=True. Never stores HTML,
creates incident identity, promotes reviews, or modifies confirmed statistics.
Work J's article/main HTML extraction strategy is reused; Work AA supplies
the existing complete-sentence evidence selector and Work X the review index.
"""
from __future__ import annotations

import hashlib
import http.client
import ipaddress
import queue as thread_queue
import re
import socket
import ssl
import threading
import time
import zlib
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from urllib.parse import urlsplit

import casualty_workaa_context as context
import casualty_workx_evidence as evidence

# Original Work J research allowlist, with only exact approved hosts/known www
# alias. This is a TECHNICAL allowlist, NOT a grant to fetch these sources.
ALLOWED_HOSTS = frozenset({
    "suspilne.media", "zprz.city", "ukrinform.ua", "www.ukrinform.ua",
    "mig.com.ua", "zabor.zp.ua", "shelter.in.ua", "radiosvoboda.org",
    "interfax.com.ua", "1news.zp.ua", "spravzhne.media", "zp.npu.gov.ua",
})
MAX_ARTICLE_GETS = 10
MAX_BYTES = 2 * 1024 * 1024
CONNECT_TIMEOUT = 8
TOTAL_TIMEOUT = 20
UTC = timezone.utc


class CaptureBlocked(ValueError):
    pass


def timestamp(t: datetime) -> str:
    return t.astimezone(UTC).isoformat().replace("+00:00", "Z")


def parse_time(value):
    try:
        t = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return t.astimezone(UTC) if t.tzinfo else None
    except (ValueError, TypeError, AttributeError):
        return None


def allowed_article_url(url: str) -> str:
    """Reject Google proxy links, secrets, internal hosts and URL ambiguity."""
    if not isinstance(url, str) or len(url) > 2048 or re.search(r"[\x00-\x20\x7f\\]", url):
        raise CaptureBlocked("UNSAFE_URL")
    try:
        p = urlsplit(url)
        host = (p.hostname or "").lower()
        if (p.scheme != "https" or host not in ALLOWED_HOSTS or
                p.username is not None or p.password is not None or
                p.port not in (None, 443) or p.fragment):
            raise CaptureBlocked("NOT_EXACT_HTTPS_ALLOWLIST")
        if ipaddress.ip_address(host).is_global is False:
            raise CaptureBlocked("NONPUBLIC_IP")
    except ValueError as exc:
        # A ValueError from ipaddress for a DNS name is expected; one from
        # urlsplit/port is not.
        if "p" not in locals() or not (p.hostname and p.scheme == "https"):
            raise CaptureBlocked("MALFORMED_URL") from exc
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            raise CaptureBlocked("IP_LITERAL_NOT_ALLOWED") from exc
    if not host or host not in ALLOWED_HOSTS:
        raise CaptureBlocked("NOT_EXACT_HTTPS_ALLOWLIST")
    return url


def _public_dns(host: str, deadline: float):
    """Bound DNS wall time; reject every non-global answer and pin chosen IP."""
    q = thread_queue.Queue(maxsize=1)
    def run():
        try:
            q.put((socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM), None))
        except Exception as exc:
            q.put((None, type(exc).__name__))
    threading.Thread(target=run, daemon=True).start()
    try:
        addresses, error = q.get(timeout=max(0.001, min(CONNECT_TIMEOUT, deadline - time.monotonic())))
    except thread_queue.Empty as exc:
        raise CaptureBlocked("DNS_TIMEOUT") from exc
    if error or not addresses:
        raise CaptureBlocked("DNS_RESOLUTION_FAILED")
    for family, _, _, _, sockaddr in addresses:
        if family not in (socket.AF_INET, socket.AF_INET6):
            raise CaptureBlocked("UNSAFE_DNS_ADDRESS_FAMILY")
        ip = ipaddress.ip_address(sockaddr[0])
        if not ip.is_global or (getattr(ip, "ipv4_mapped", None) and not ip.ipv4_mapped.is_global):
            raise CaptureBlocked("NONPUBLIC_DNS_IP")
    return addresses


class PinnedHTTPS(http.client.HTTPSConnection):
    """TLS hostname verification with DNS-pinned public IP, no proxy."""
    def __init__(self, host: str, deadline: float):
        super().__init__(host, port=443, timeout=CONNECT_TIMEOUT,
                         context=ssl.create_default_context())
        self.deadline = deadline

    def connect(self):
        addresses = _public_dns(self.host, self.deadline)
        last_error = None
        for family, typ, proto, _, sockaddr in addresses:
            remaining = self.deadline - time.monotonic()
            if remaining <= 0:
                raise CaptureBlocked("TOTAL_DEADLINE")
            sock = socket.socket(family, typ, proto)
            try:
                sock.settimeout(min(CONNECT_TIMEOUT, remaining))
                sock.connect(sockaddr)
                remaining = self.deadline - time.monotonic()
                if remaining <= 0:
                    raise CaptureBlocked("TOTAL_DEADLINE")
                sock.settimeout(min(CONNECT_TIMEOUT, remaining))
                self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
                return
            except (OSError, ssl.SSLError) as exc:
                last_error = exc
                sock.close()
        raise CaptureBlocked("PUBLIC_CONNECTION_FAILED") from last_error


def _read_bounded(response, conn: PinnedHTTPS, deadline: float) -> bytes:
    length = response.getheader("Content-Length")
    if length and length.isdecimal() and int(length) > MAX_BYTES:
        raise CaptureBlocked("BODY_LIMIT_EXCEEDED")
    chunks = bytearray()
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise CaptureBlocked("TOTAL_DEADLINE")
        if conn.sock:
            conn.sock.settimeout(min(CONNECT_TIMEOUT, remaining))
        part = response.read(min(65536, MAX_BYTES + 1 - len(chunks)))
        if not part:
            break
        chunks.extend(part)
        if len(chunks) > MAX_BYTES:
            raise CaptureBlocked("BODY_LIMIT_EXCEEDED")
    return bytes(chunks)


def get_html(url: str) -> tuple[bytes, str, int, str]:
    """Exactly one HTTP GET, redirects OFF, no cookies/proxy/auth/retries."""
    allowed_article_url(url)
    p = urlsplit(url)
    deadline = time.monotonic() + TOTAL_TIMEOUT
    conn = PinnedHTTPS(p.hostname, deadline)
    path = (p.path or "/") + (("?" + p.query) if p.query else "")
    try:
        conn.request("GET", path, headers={
            "User-Agent": "ukraine-air-alerts-casualty-shadow/1.0",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Encoding": "gzip,deflate,identity",
            "Connection": "close",
        })
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise CaptureBlocked("TOTAL_DEADLINE")
        if conn.sock:
            conn.sock.settimeout(min(CONNECT_TIMEOUT, remaining))
        response = conn.getresponse()
        status = int(response.status)
        if 300 <= status < 400:
            raise CaptureBlocked("REDIRECT_BLOCKED")
        if status != 200:
            raise CaptureBlocked("HTTP_STATUS_NOT_200")
        kind = response.getheader("Content-Type", "")
        if not re.match(r"^(?:text/html|application/xhtml\+xml)(?:\s*;|$)", kind, re.I):
            raise CaptureBlocked("UNEXPECTED_CONTENT_TYPE")
        encoding = response.getheader("Content-Encoding", "identity").lower().strip()
        if encoding not in ("", "identity", "gzip", "deflate"):
            raise CaptureBlocked("UNEXPECTED_CONTENT_ENCODING")
        return _read_bounded(response, conn, deadline), kind, status, encoding
    finally:
        conn.close()


def _decode_limited(raw: bytes, encoding: str) -> bytes:
    if not isinstance(raw, bytes) or len(raw) > MAX_BYTES:
        raise CaptureBlocked("BODY_LIMIT_EXCEEDED")
    if encoding in ("", "identity"):
        return raw
    if encoding not in ("gzip", "deflate"):
        raise CaptureBlocked("UNEXPECTED_CONTENT_ENCODING")
    decoder = zlib.decompressobj(16 + zlib.MAX_WBITS if encoding == "gzip" else zlib.MAX_WBITS)
    try:
        body = decoder.decompress(raw, MAX_BYTES + 1)
        if len(body) > MAX_BYTES or decoder.unconsumed_tail:
            raise CaptureBlocked("DECOMPRESSED_BODY_LIMIT_EXCEEDED")
        body += decoder.flush(MAX_BYTES + 1 - len(body))
    except zlib.error as exc:
        raise CaptureBlocked("INVALID_COMPRESSION") from exc
    if len(body) > MAX_BYTES or not decoder.eof or decoder.unused_data:
        raise CaptureBlocked("DECOMPRESSED_BODY_LIMIT_EXCEEDED")
    return body


class ArticleText(HTMLParser):
    """Work J _TextExtractor: prefer article/main and ignore page chrome."""
    OMIT = {"script", "style", "nav", "footer", "aside", "form",
            "noscript", "template", "iframe", "svg"}
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.article, self.main = [], [], []
        self.skip_depth = self.in_article = self.in_main = self.title_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.OMIT:
            self.skip_depth += 1
        if tag == "article":
            self.in_article += 1
        if tag == "main":
            self.in_main += 1
        if tag == "title":
            self.title_depth += 1

    def handle_endtag(self, tag):
        if tag in self.OMIT:
            self.skip_depth = max(0, self.skip_depth - 1)
        if tag == "article":
            self.in_article = max(0, self.in_article - 1)
        if tag == "main":
            self.in_main = max(0, self.in_main - 1)
        if tag == "title":
            self.title_depth = max(0, self.title_depth - 1)

    def handle_data(self, data):
        s = " ".join(data.split())
        if s and not self.skip_depth:
            self.parts.append(s)
            if self.in_article:
                self.article.append(s)
            if self.in_main:
                self.main.append(s)

    def body(self):
        article = " ".join(self.article)
        main = " ".join(self.main)
        return article if (article and (len(article) >= 180 or not main)) else (main or " ".join(self.parts))


def _make_fact(candidate: dict, raw: bytes, encoding: str, now: datetime):
    page = _decode_limited(raw, encoding)  # expanded bytes are also bounded
    parser = ArticleText()
    parser.feed(page.decode("utf-8", "replace"))
    text = parser.body()
    if len(text) < 180 or re.search(r"captcha|access denied|enable javascript|sign in to read", text, re.I):
        raise CaptureBlocked("CONTENT_INACCESSIBLE_OR_NOT_ARTICLE")
    clues = context.retain_incident_review_clues(text)
    excerpts = []
    for m in clues.get("evidence_mentions", []):
        sentence = m.get("excerpt")
        if (sentence and m.get("context_status") == "COMPLETE" and
                "FATALITY_MENTION_NOT_A_CONFIRMED_TOTAL" in m.get("tags", [])):
            excerpts.append({"text": sentence, "excerpt_sha256": hashlib.sha256(
                sentence.encode("utf-8")).hexdigest(), "claim_number": None})
        if len(excerpts) >= 3:
            break
    reasons = ["NO_AUTOMATIC_CREDIT", "FATAL_TOTAL_NOT_PROVEN",
               "CROSS_SOURCE_IDENTITY_NOT_VERIFIED"]
    if not excerpts:
        reasons.append("INSUFFICIENT_EVIDENCE")
    if any(m.get("context_status") == "CONTEXT_INCOMPLETE"
           for m in clues.get("evidence_mentions", [])):
        reasons.append("CONTEXT_INCOMPLETE")
    return {
        "schema": "casualty-minimal-source-facts-v1",
        "candidate_id": candidate["candidate_id"], "source_role": "publisher",
        "source_url": allowed_article_url(candidate["url"]),
        "publication_date": candidate.get("published_at"),
        "source_capture_time_utc": timestamp(now),
        "attack_date_explicit": None,
        "city_key_candidate_not_verified": candidate.get("city_key"),
        "claim_deaths": None, "count_kind": "unverified",
        "document_sha256": hashlib.sha256(raw).hexdigest(),
        "extracted_text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "excerpts": excerpts, "incident_review": clues,
        "decision": "NEEDS_REVIEW", "reasons": reasons,
        "publication_allowed": False,
    }


def capture_cycle(queue: list[dict], state: dict, index: dict, now: datetime,
                  *, enabled: bool = False, fetch=None) -> tuple[dict, dict, dict]:
    """WIP-only evidence state and index; no I/O or mutations of input objects.

    RSS cursor is deliberately NOT here. A failed page fetch retains its queue
    candidate and allows another attempt on the next scheduled cycle.
    """
    import copy
    state = copy.deepcopy(state) if isinstance(state, dict) else {}
    index = copy.deepcopy(index) if isinstance(index, dict) else {}
    state.setdefault("schema_version", 1)
    state.setdefault("candidates", {})
    index.setdefault("schema", evidence.SCHEMA)
    index.setdefault("cards", [])
    if not isinstance(index["cards"], list) or not isinstance(state["candidates"], dict):
        raise CaptureBlocked("INVALID_SHADOW_STATE")
    stats = {"article_gets": 0, "article_success": 0, "article_errors": 0,
             "article_url_blocked": 0, "evidence_new": 0,
             "evidence_replay_duplicates": 0, "needs_review": 0,
             "automatic_credits": 0, "PROMOTE": "OFF",
             "publication_allowed": False}
    if not enabled:
        return state, index, stats
    fetch = fetch or get_html
    seen_keys = set()
    for candidate in queue:
        if not isinstance(candidate, dict) or candidate.get("source") != "Google News RSS":
            continue
        cid = candidate.get("candidate_id")
        if not cid or cid in seen_keys:
            continue
        seen_keys.add(cid)
        record = state["candidates"].setdefault(cid, {})
        if record.get("status") == "CAPTURED":
            next_due = parse_time(record.get("next_check_at"))
            if next_due and next_due > now:
                continue
        elif record.get("status") == "RETRY_PENDING":
            next_due = parse_time(record.get("next_check_at"))
            if next_due and next_due > now:
                continue
        try:
            url = allowed_article_url(candidate.get("url"))
        except CaptureBlocked as exc:
            record.update(status="SOURCE_URL_UNRESOLVED", reason=str(exc),
                          checked_at=timestamp(now))
            stats["article_url_blocked"] += 1
            continue
        if stats["article_gets"] >= MAX_ARTICLE_GETS:
            break
        # Counts attempts before I/O, including failed sockets and bad replies.
        stats["article_gets"] += 1
        record["last_attempt_at"] = timestamp(now)
        try:
            raw, content_type, status, encoding = fetch(url)
            if status != 200:
                raise CaptureBlocked("REDIRECT_BLOCKED" if 300 <= status < 400
                                     else "HTTP_STATUS_NOT_200")
            if not re.match(r"^(?:text/html|application/xhtml\+xml)(?:\s*;|$)", content_type, re.I):
                raise CaptureBlocked("UNEXPECTED_CONTENT_TYPE")
            fact = _make_fact(candidate, raw, encoding, now)
            prior = list(reversed(index["cards"]))
            result = evidence.build_review_index(
                {"facts": [fact], "automatic_credits": 0,
                 "publication_allowed": False},
                queue=[candidate], previous=prior, include_unretained=False)
            card = result["cards"][0]
            if card["automatic_credits"] != 0 or card["incident_id"] is not None:
                raise CaptureBlocked("UNSAFE_WORKX_INDEX")
            same = any(c.get("candidate_id") == cid and
                       c.get("response_sha256") == card["response_sha256"] and
                       c.get("original_source_url") == card["original_source_url"]
                       for c in index["cards"])
            if same:
                stats["evidence_replay_duplicates"] += 1
            else:
                index["cards"].append(card)
                stats["evidence_new"] += 1
            record.update(status="CAPTURED", reason=None,
                          capture_at=timestamp(now),
                          response_sha256=card["response_sha256"],
                          next_check_at=timestamp(now + timedelta(hours=24)))
            stats["article_success"] += 1
        except (CaptureBlocked, OSError, TimeoutError, ValueError,
                ssl.SSLError, UnicodeError) as exc:
            record.update(status="RETRY_PENDING", reason=(
                str(exc) if isinstance(exc, CaptureBlocked)
                else type(exc).__name__), next_check_at=timestamp(now + timedelta(hours=4)))
            stats["article_errors"] += 1
    stats["needs_review"] = sum(c.get("decision") == "NEEDS_REVIEW"
                                 for c in index["cards"])
    if any(c.get("automatic_credits") != 0 or c.get("publication_allowed") is not False
           or c.get("incident_id") is not None for c in index["cards"]):
        raise CaptureBlocked("UNSAFE_PERSISTED_INDEX")
    index["publication_allowed"] = False
    index["summary"] = dict(stats)
    return state, index, stats
