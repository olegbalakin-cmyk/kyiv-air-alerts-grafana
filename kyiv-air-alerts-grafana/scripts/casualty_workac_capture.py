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
import casualty_workj_rules as workj

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
    except CaptureBlocked:
        raise  # Never swallow our own security rejection (ValueError subclass).
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


def resolve_original_url(candidate: dict) -> tuple[str, str]:
    """RSS 2.0 <link> and isPermaLink=true <guid> ONLY.

    An RSS <source url> is the publisher's SITE URL, not an article link.
    Google News opaque article IDs cannot be unwrapped offline without a
    documented reliable mapping; redirects, guesses and decoders are forbidden.
    This resolves the article address, NOT the identity of any attack.
    """
    if candidate.get("rss_guid_conflict"):
        raise CaptureBlocked("SOURCE_URL_CONFLICT")
    options = []
    direct = candidate.get("url")
    if isinstance(direct, str) and direct:
        host = (urlsplit(direct).hostname or "").lower()
        if host not in {"news.google.com", "www.google.com", "google.com"}:
            options.append((direct, "rss_item_link"))
    guid = candidate.get("rss_guid_url")
    if candidate.get("rss_guid_is_permalink") is True and isinstance(guid, str) and guid:
        host = (urlsplit(guid).hostname or "").lower()
        if host not in {"news.google.com", "www.google.com", "google.com"}:
            options.append((guid, "rss_guid_permalink"))
    if not options:
        raise CaptureBlocked("SOURCE_URL_UNRESOLVED")
    validated = []
    for url, method in options:
        try:
            validated.append((allowed_article_url(url), method))
        except (CaptureBlocked, ValueError) as exc:
            raise CaptureBlocked("SOURCE_URL_BLOCKED:" + str(exc)) from exc
    if len({url for url, _ in validated}) != 1:
        raise CaptureBlocked("SOURCE_URL_CONFLICT")
    return validated[0]


def _attack_date_directly_stated(scope: str, published_at: str | None) -> str | None:
    """Work J date signal, but never silently fill a missing year from RSS."""
    day, _ = workj._date_signals(scope, published_at)
    if not day:
        return None
    if day in scope:
        return day
    year = day[:4]
    month_words = "|".join(re.escape(k) for k, v in workj.MONTHS.items()
                           if v == int(day[5:7]))
    if re.search(r"\b" + str(int(day[8:10])) + r"\s+(?:" + month_words +
                 r")\s+" + year + r"\b", scope):
        return day
    return None


def _make_fact(candidate: dict, raw: bytes, encoding: str, now: datetime,
               *, resolved_url: str | None = None,
               resolution_method: str | None = None) -> dict:
    """Work J claims + Work AA complete quotations + Work X, shadow ONLY."""
    page = _decode_limited(raw, encoding)
    parser = ArticleText()
    parser.feed(page.decode("utf-8", "replace"))
    text = parser.body()
    if len(text) < 180 or re.search(r"captcha|access denied|enable javascript|sign in to read", text, re.I):
        raise CaptureBlocked("CONTENT_INACCESSIBLE_OR_NOT_ARTICLE")
    if resolved_url is None:
        resolved_url, resolution_method = resolve_original_url(candidate)
    low = text.casefold()
    scopes = workj._incident_scopes(low)
    fatal_scopes = [s for s in scopes if workj._fatal_total(s) is not None]
    # Work J requires a unique incident scope. Be stricter when another attack
    # appears in the same page, even when only one paragraph reports deaths.
    attack_scopes = sum(bool(re.search(r"атакув\w*|обстрілял\w*|"
                                      r"(?:ракетн\w*|авіаційн\w*)\s+удар\w*",
                                      s)) for s in scopes)
    multi_attack = len(fatal_scopes) > 1 or (len(scopes) > 1 and attack_scopes > 1)
    daily_aggregate = bool(re.search(
        r"\b(?:за|протягом)\s+доб[иу]\b|"
        r"\b(?:унаслідок|після)\s+кількох\s+(?:атак|ударів|обстрілів)\b", low))
    scope = fatal_scopes[0] if len(fatal_scopes) == 1 and not multi_attack else ""
    total = workj._fatal_total(scope) if scope and not daily_aggregate else None
    kind = "cumulative" if total is not None else "unknown"
    delta = bool(re.search(
        r"\b(?:померл[аои]?|помер|загинул[аои]?|загинув)\s+ще\s+"
        r"(?:один|одна|двоє|дві|троє|три|\d+)\b|"
        r"\bще\s+(?:один|одна|двоє|дві|троє|три|\d+)\s+"
        r"(?:люд\w*\s+)?(?:загинул\w*|померл\w*)\b", low))
    if total is None and delta and not multi_attack:
        kind = "delta"
    attack_date = _attack_date_directly_stated(scope, candidate.get("published_at")) if scope else None
    origin_id, origin_name = workj._origin_attribution(scope) if scope else ("unattributed", None)
    clues = context.retain_incident_review_clues(text)
    excerpts = []
    for mention in clues.get("evidence_mentions", []):
        quote = mention.get("excerpt")
        if (total is not None and isinstance(quote, str) and
                mention.get("context_status") == "COMPLETE" and
                workj._fatal_total(quote.casefold()) == total and len(quote) <= 170):
            excerpts.append({"text": quote,
                             "excerpt_sha256": hashlib.sha256(quote.encode("utf-8")).hexdigest(),
                             "claim_number": total})
        if len(excerpts) >= 3:
            break
    reasons = ["NO_AUTOMATIC_CREDIT", "CROSS_SOURCE_IDENTITY_NOT_VERIFIED",
               "PRIOR_DEATH_CREDIT_NOT_RECONCILED"]
    if multi_attack:
        reasons.append("MULTIPLE_POSSIBLE_INCIDENTS")
    if daily_aggregate:
        reasons.append("DAILY_OR_MULTIPLE_ATTACK_AGGREGATE")
    if kind == "delta":
        reasons.append("DELTA_WITHOUT_INCIDENT_BASELINE")
    elif total is None:
        reasons.append("NO_PARSEABLE_SINGLE_ATTACK_CUMULATIVE_TOTAL")
    if not attack_date:
        reasons.append("ATTACK_DATE_NOT_EXPLICIT")
    if total is not None and not excerpts:
        # Do not retain a purported number without a complete source quote.
        total, kind = None, "unknown"
        reasons.append("NO_SAFE_COMPLETE_CLAIM_QUOTE")
    if any(m.get("context_status") == "CONTEXT_INCOMPLETE"
           for m in clues.get("evidence_mentions", [])):
        reasons.append("CONTEXT_INCOMPLETE")
    if not excerpts:
        reasons.append("INSUFFICIENT_EVIDENCE")
    return {
        "schema": "casualty-minimal-source-facts-v1",
        "candidate_id": candidate["candidate_id"], "source_role": "publisher",
        "source_url": allowed_article_url(resolved_url),
        "source_url_resolution_method": resolution_method,
        "feed_original_url": candidate.get("url"),
        "publication_date": candidate.get("published_at"),
        "publication_date_origin": "google_news_rss_not_article_confirmed",
        "source_capture_time_utc": timestamp(now),
        "attack_date_explicit": attack_date,
        "attack_slot_hint_not_identity": workj._attack_slot(scope) if scope else None,
        "city_key_candidate_not_verified": candidate.get("city_key"),
        "place_verified": None, "struck_object_verified": None,
        "claim_deaths": total, "count_kind": kind,
        "claim_origin": {"origin_id": origin_id, "name": origin_name,
                         "source_role": "publisher"},
        "fatal_claim_context_status": (
            "COMPLETE_QUOTED_SOURCE_CLAIM_NOT_INCIDENT_VERIFICATION"
            if total is not None else "INSUFFICIENT_EVIDENCE"),
        "parser_version": "workj-pr121-ported-exact-count-rules",
        "document_sha256": hashlib.sha256(raw).hexdigest(),
        "extracted_text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "excerpts": excerpts, "incident_review": clues,
        "decision": "NEEDS_REVIEW", "reasons": sorted(set(reasons)),
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
             "article_url_blocked": 0, "source_url_unresolved": 0,
             "numeric_cumulative": 0, "numeric_delta_held": 0,
             "numeric_ambiguous_or_blocked": 0, "evidence_new": 0,
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
            url, method = resolve_original_url(candidate)
        except (CaptureBlocked, ValueError) as exc:
            unresolved = str(exc) == "SOURCE_URL_UNRESOLVED"
            record.update(status=("SOURCE_URL_UNRESOLVED" if unresolved
                                  else "SOURCE_URL_BLOCKED"), reason=str(exc),
                          checked_at=timestamp(now))
            stats["source_url_unresolved" if unresolved else "article_url_blocked"] += 1
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
            fact = _make_fact(candidate, raw, encoding, now,
                              resolved_url=url, resolution_method=method)
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
                if fact["claim_deaths"] is not None and fact["count_kind"] == "cumulative":
                    stats["numeric_cumulative"] += 1
                elif fact["count_kind"] == "delta":
                    stats["numeric_delta_held"] += 1
                else:
                    stats["numeric_ambiguous_or_blocked"] += 1
            record.update(status="CAPTURED", reason=None,
                          resolved_url=url, resolution_method=method,
                          capture_at=timestamp(now),
                          response_sha256=card["response_sha256"],
                          next_check_at=timestamp(now + timedelta(hours=4)))
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
