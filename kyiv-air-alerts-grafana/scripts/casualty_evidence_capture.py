"""Bounded opt-in article capture for the existing casualty monitor/reviewer.

Only publisher text excerpts and provenance are persisted. No candidate mutations,
death decisions, REVIEW, PROMOTE, production publication, or new persistence service.
The reviewer alone interprets the articles through its existing articles contract.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from casualty_auto_review import fingerprint
from casualty_transport_policy import CaptureError, safe_url, diagnostic_host, GOOGLE_NEWS_HOST

MAX_CANDIDATES = 20
MAX_REQUESTS = 40
MAX_REDIRECTS = 3
MAX_RESPONSE_BYTES = 1_500_000
MAX_EXCERPT_CHARS = 4_500
MAX_BLOCK_CHARS = 1_000
MAX_BLOCKS = 16
TIMEOUT = (4, 12)
NEWS_HOST = GOOGLE_NEWS_HOST
USER_AGENT = "casualty-monitor-evidence-research/1.0 (+bounded-source-check)"
RELEVANT = {
    "fatality": r"загин|загиб|помер|померл|смерт|жертв",
    "attack": r"ракет|безпілот|дрон|бпла|бпіл|удар|атак|обстріл|вибух",
    "location_date": r"дніпр|одес|київ|харків|листопад|січн|лют|берез|квіт|травн|черв|липн|серпн|верес|жовт|груд|20\d{2}|вранці|вночі|вдень",
    "attribution": r"дснс|прокуратур|поліці|начальник.{0,20}мва|військов.{0,12}адміністрац|за даними|повідомил",
    "negation_update": r"не підтверд|непідтверд|спростув|попередн|без загибл|не загин|уточнен|зросл|збільшил|повторн|знову|ще раз|пізніше|згодом|оновлен",
    "military_context": r"військовослужбов|серед загиблих.{0,40}військов|загинул.{0,40}військов|військов.{0,15}(об.єкт|частин|технік)|боєприпас|склад.{0,15}військов",
}
RE = {key: re.compile(pattern, re.IGNORECASE) for key, pattern in RELEVANT.items()}


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _publisher_url_from_google(html_bytes: bytes, base_url: str) -> str:
    """Accept only explicit HTML links to an approved publisher, never guessed IDs."""
    soup = BeautifulSoup(html_bytes, "html.parser")
    candidates = []
    for tag in soup.select('link[rel="canonical"], link[rel="amphtml"], meta[property="og:url"], a[href]'):
        href = tag.get("href") or tag.get("content") or ""
        link = urljoin(base_url, href)
        try:
            safe_url(link, allow_google=False)
        except CaptureError:
            continue
        p = urlsplit(link)
        if p.path not in ("", "/") and len(p.path) >= 12:
            candidates.append(link)
    unique = list(dict.fromkeys(candidates))
    if len(unique) != 1:
        raise CaptureError("GOOGLE_WRAPPER_UNRESOLVED_OR_AMBIGUOUS")
    return unique[0]


def _publisher_url_from_google_rpc(html_bytes: bytes, article_url: str, *,
                                    session, counter: list[int], pause=0.0) -> str:
    """Decode one opaque RSS ID with Google's page-signed article response.

    This is an undocumented endpoint: any unexpected shape stays NEEDS_REVIEW.
    No guessed publisher URLs, browser automation, proxies or scraped credentials.
    Only the fixed Google HTTPS RPC is called, then safe_url() validates its answer.
    """
    article_id = urlsplit(article_url).path.rsplit("/", 1)[-1]
    if not re.fullmatch(r"[A-Za-z0-9_-]{16,900}", article_id):
        raise CaptureError("GOOGLE_RSS_ID_INVALID")
    soup = BeautifulSoup(html_bytes, "html.parser")
    candidates = [
        node for node in soup.select("[data-n-a-sg][data-n-a-ts]")
        if not node.get("data-n-a-id") or node.get("data-n-a-id") == article_id
    ]
    if len(candidates) != 1:
        raise CaptureError("GOOGLE_SIGNED_PARAMS_MISSING_OR_AMBIGUOUS")
    signature = str(candidates[0].get("data-n-a-sg", ""))
    timestamp = str(candidates[0].get("data-n-a-ts", ""))
    if (not 5 <= len(signature) <= 600
            or any(ord(c) < 33 or ord(c) > 126 for c in signature)
            or not re.fullmatch(r"[0-9]{9,13}", timestamp)):
        raise CaptureError("GOOGLE_SIGNED_PARAMS_INVALID")

    inner = [
        "garturlreq",
        [["X", "X", ["X", "X"], None, None, 1, 1, "US:en",
          None, 1, None, None, None, None, None, 0, 1],
         "X", "X", 1, [1, 1, 1], 1, 1, None, 0, 0, None, 0],
        article_id, int(timestamp), signature,
    ]
    form = {"f.req": json.dumps([[["Fbv4je", json.dumps(
        inner, ensure_ascii=True, separators=(",", ":"))]]],
        ensure_ascii=True, separators=(",", ":"))}
    if counter[0] >= MAX_REQUESTS:
        raise CaptureError("HTTP_REQUEST_BUDGET_EXHAUSTED")
    counter[0] += 1
    if pause:
        time.sleep(pause)
    try:
        response = session.post(
            "https://news.google.com/_/DotsSplashUi/data/batchexecute",
            data=form, timeout=TIMEOUT, allow_redirects=False, stream=True,
            headers={
                "User-Agent": USER_AGENT,
                "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                "Origin": "https://news.google.com",
                "Referer": "https://news.google.com/",
                "X-Same-Domain": "1",
            },
        )
    except requests.Timeout as exc:
        raise CaptureError("GOOGLE_RPC_TIMEOUT") from exc
    except requests.RequestException as exc:
        raise CaptureError("GOOGLE_RPC_TRANSPORT_" + type(exc).__name__.upper()) from exc
    try:
        if response.status_code != 200:
            raise CaptureError("GOOGLE_RPC_HTTP_" + str(response.status_code))
        limit = 128_000
        length = response.headers.get("Content-Length", "")
        if length.isdecimal() and int(length) > limit:
            raise CaptureError("GOOGLE_RPC_BODY_TOO_LARGE")
        chunks, used = [], 0
        for chunk in response.iter_content(chunk_size=8192):
            if not chunk:
                continue
            used += len(chunk)
            if used > limit:
                raise CaptureError("GOOGLE_RPC_BODY_TOO_LARGE")
            chunks.append(chunk)
        payload = b"".join(chunks).decode("utf-8", "replace")
    finally:
        response.close()

    for line in payload.splitlines():
        line = line.strip()
        if not line.startswith("[["):
            continue
        try:
            frames = json.loads(line)
        except (ValueError, TypeError):
            continue
        if not isinstance(frames, list):
            continue
        for frame in frames:
            if not (isinstance(frame, list) and len(frame) >= 3
                    and frame[0] == "wrb.fr" and frame[1] == "Fbv4je"
                    and isinstance(frame[2], str)):
                continue
            try:
                decoded = json.loads(frame[2])
            except ValueError:
                break
            if (isinstance(decoded, list) and len(decoded) >= 2
                    and decoded[0] == "garturlres"
                    and isinstance(decoded[1], str)):
                try:
                    return safe_url(decoded[1], allow_google=False)
                except CaptureError as exc:
                    raise CaptureError(
                        "GOOGLE_RPC_TARGET_NOT_ALLOWED",
                        resolved_host=diagnostic_host(decoded[1]),
                        transport_reason=str(exc),
                        resolved_url_sha256=sha256(decoded[1].encode("utf-8")),
                    ) from exc
        break
    raise CaptureError("GOOGLE_RPC_UNRESOLVED_OR_BAD_RESPONSE")


def get_publisher_document(url: str, *, session, counter: list[int], pause=0.0):
    """Manually controlled redirects and streamed response-size limit."""
    current = safe_url(url)
    redirects = []
    for attempt in range(MAX_REDIRECTS + 2):
        if counter[0] >= MAX_REQUESTS:
            raise CaptureError("HTTP_REQUEST_BUDGET_EXHAUSTED")
        counter[0] += 1
        if pause:
            time.sleep(pause)
        try:
            response = session.get(
                current, timeout=TIMEOUT, allow_redirects=False, stream=True,
                headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml",
                         "Accept-Language": "uk,en;q=0.7"},
            )
        except requests.Timeout as exc:
            raise CaptureError("HTTP_TIMEOUT") from exc
        except requests.RequestException as exc:
            raise CaptureError("HTTP_TRANSPORT_" + type(exc).__name__.upper()) from exc
        try:
            status = response.status_code
            if status in (301, 302, 303, 307, 308):
                target = response.headers.get("Location", "")
                if not target:
                    raise CaptureError("HTTP_REDIRECT_WITHOUT_LOCATION")
                candidate = safe_url(urljoin(current, target))
                redirects.append(current)
                if candidate in redirects or len(redirects) > MAX_REDIRECTS:
                    raise CaptureError("HTTP_REDIRECT_LOOP_OR_LIMIT")
                current = candidate
                continue
            if status != 200:
                raise CaptureError(
                    "HTTP_STATUS_" + str(status),
                    resolved_host=diagnostic_host(current),
                    resolved_url_sha256=sha256(current.encode("utf-8")),
                    redirect_count=len(redirects),
                )
            content_type = response.headers.get("Content-Type", "").split(";", 1)[0].lower().strip()
            if content_type not in ("text/html", "application/xhtml+xml"):
                raise CaptureError("HTTP_NON_HTML_CONTENT")
            length = response.headers.get("Content-Length")
            if length and length.isdecimal() and int(length) > MAX_RESPONSE_BYTES:
                raise CaptureError("HTTP_BODY_TOO_LARGE")
            parts, used = [], 0
            for chunk in response.iter_content(chunk_size=8192):
                if not chunk:
                    continue
                used += len(chunk)
                if used > MAX_RESPONSE_BYTES:
                    raise CaptureError("HTTP_BODY_TOO_LARGE")
                parts.append(chunk)
            body = b"".join(parts)
            if len(body) < 100:
                raise CaptureError("HTML_EMPTY_OR_TOO_SHORT")
        finally:
            response.close()
        if urlsplit(current).hostname == NEWS_HOST:
            redirects.append(current)
            if len(redirects) > MAX_REDIRECTS:
                raise CaptureError("GOOGLE_WRAPPER_REDIRECT_LIMIT")
            try:
                current = _publisher_url_from_google(body, current)
            except CaptureError as exc:
                if str(exc) != "GOOGLE_WRAPPER_UNRESOLVED_OR_AMBIGUOUS":
                    raise
                current = _publisher_url_from_google_rpc(
                    body, current, session=session, counter=counter, pause=pause)
            continue
        safe_url(current, allow_google=False)
        return {"url": current, "html": body, "redirects": redirects,
                "http_status": 200, "body_sha256": sha256(body), "body_bytes": len(body)}
    raise CaptureError("HTTP_REDIRECT_LIMIT")


def _text(node) -> str:
    return " ".join(node.get_text(" ", strip=True).replace("\u00a0", " ").split())


def select_excerpts(html_bytes: bytes):
    """Retain complete material paragraphs, including ALL detected conflicting/negative claims.

    If important passages do not fit the cap, stop rather than strip a
    qualifier and give the reviewer an incorrectly confident excerpt.
    """
    soup = BeautifulSoup(html_bytes, "html.parser")
    for node in soup.find_all(["script", "style", "nav", "footer", "aside", "form",
                               "noscript", "iframe", "svg", "button", "figure"]):
        node.decompose()
    # Large "article" elements can be unrelated teaser cards. Prefer the
    # publication body with actual death/attack paragraphs, not the longest card.
    selectors = ('[itemprop="articleBody"]', '.post__content', '.entry-content',
                 '.article__text', '.article-content', '.article-body',
                 '.news-text', 'article', 'main')
    candidates = []
    for rank, selector in enumerate(selectors):
        for node in soup.select(selector):
            body = " ".join(_text(x) for x in node.find_all("p")[:40])
            if len(body) < 25:
                continue
            score = (int(bool(RE["fatality"].search(body)) and
                         bool(RE["attack"].search(body))),
                     int(bool(RE["fatality"].search(body))),
                     int(bool(RE["attribution"].search(body))),
                     -rank, min(len(body), 4000))
            candidates.append((score, node))
    root = max(candidates, key=lambda value: value[0])[1] if candidates else soup
    raw = []
    headline = soup.find("h1")
    if headline:
        raw.append(_text(headline))
    raw += [_text(x) for x in root.find_all(["h1", "h2", "h3", "p", "li"])]
    blocks, seen = [], set()
    for value in raw:
        if len(value) < 14 or value in seen:
            continue
        seen.add(value)
        blocks.append(value)
    if not blocks:
        raise CaptureError("HTML_NO_ARTICLE_PARAGRAPHS")
    # A casualty headline alongside unrelated teaser text is not article proof.
    body_blocks = [v for v in blocks if not headline or v != _text(headline)]
    if not any(RE["fatality"].search(v) for v in body_blocks):
        raise CaptureError("INSUFFICIENT_ARTICLE_BODY_FACTS")
    tags = [sorted(k for k, pattern in RE.items() if pattern.search(text.casefold()))
            for text in blocks]
    vital = {"fatality", "negation_update", "military_context"}
    mandatory = {i for i, t in enumerate(tags) if vital.intersection(t)}
    # Keep adjacent attribution and event context when split into short paragraphs.
    for i in list(mandatory):
        if i > 0 and ("attribution" in tags[i - 1] or "attack" in tags[i - 1]):
            mandatory.add(i - 1)
        if i + 1 < len(blocks) and "attribution" in tags[i + 1]:
            mandatory.add(i + 1)
    # The headline, attack date, city and official origin help the existing reviewer.
    ordered = sorted(range(len(blocks)),
                     key=lambda i: (i not in mandatory, i != 0,
                                    -len(tags[i]), i))
    chosen, total_len = set(), 0
    for i in ordered:
        if not tags[i] and i != 0:
            continue
        # Air-raid warning times are not necessarily attack times. They are
        # extraneous to fatality evidence and can mislead time-slot extraction.
        low = blocks[i].casefold()
        if (re.search(r"повітрян\w* (?:тривог|сил)", low) and
                re.search(r"тривал|попередил", low) and
                not (vital.intersection(tags[i]))):
            continue
        size = len(blocks[i])
        if size > MAX_BLOCK_CHARS:
            if i in mandatory:
                raise CaptureError("CRITICAL_PARAGRAPH_EXCEEDS_LIMIT")
            continue
        if len(chosen) >= MAX_BLOCKS or total_len + size + 1 > MAX_EXCERPT_CHARS:
            if i in mandatory:
                raise CaptureError("CRITICAL_CONTEXT_EXCEEDS_LIMIT")
            continue
        chosen.add(i)
        total_len += size + 1
    if not mandatory.issubset(chosen):
        raise CaptureError("CRITICAL_CONTEXT_EXCEEDS_LIMIT")
    if not chosen:
        raise CaptureError("NO_RELEVANT_ARTICLE_EXCERPTS")
    fragments = [{"paragraph_index": i, "reason": tags[i] or ["headline"],
                  "sha256": sha256(blocks[i].encode("utf-8")), "length": len(blocks[i])}
                 for i in sorted(chosen)]
    selected = "\n".join(blocks[i] for i in sorted(chosen))
    if not RE["fatality"].search(selected) or not RE["attack"].search(selected):
        raise CaptureError("INSUFFICIENT_FATALITY_OR_ATTACK_CONTEXT")
    return selected, fragments


def _existing(path: Path):
    if not path.exists():
        return {"schema_version": 1, "articles": [], "receipts": [], "failures": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or not isinstance(data.get("articles"), list):
        raise ValueError("Existing evidence store has an unsupported schema")
    return data


def capture_snapshot(queue: list[dict], output: Path, *, limit: int = 4,
                     session=None, pause: float = 0.0):
    """Operate on an in-memory queue snapshot; never rewrite the queue."""
    if type(limit) is not int or not 1 <= limit <= MAX_CANDIDATES:
        raise ValueError("Evidence limit must be 1..20")
    if not isinstance(queue, list):
        raise ValueError("Queue snapshot must be a JSON list")
    output = Path(output).resolve()
    operational_data = (Path(__file__).resolve().parents[1] / "data").resolve()
    if output == operational_data or operational_data in output.parents:
        raise ValueError("Evidence output must not be inside operational data")
    initial = _existing(output)
    old_articles = {a["candidate_id"]: a for a in initial["articles"]}
    old_receipts = {a["candidate_id"]: a for a in initial.get("receipts", [])}
    articles = dict(old_articles)
    receipts = dict(old_receipts)
    failures = {e["candidate_id"]: e for e in initial.get("failures", [])}
    owned = session is None
    if owned:
        session = requests.Session()
        session.trust_env = False
    calls, attempted, succeeded, usable = [0], 0, 0, 0
    visited, checked = {}, set()
    try:
        for candidate in queue[:limit]:
            cid = str(candidate.get("candidate_id") or "")
            if not cid or cid in checked:
                continue
            checked.add(cid)
            attempted += 1
            origin_url = str(candidate.get("url") or "")
            stamp = now_iso()
            prior = receipts.get(cid)
            try:
                # The same published page can serve more than one candidate; fetch once.
                if origin_url not in visited:
                    visited[origin_url] = get_publisher_document(
                        origin_url, session=session, counter=calls, pause=pause)
                doc = visited[origin_url]
                succeeded += 1
                excerpt, fragments = select_excerpts(doc["html"])
                usable += 1
                fp = fingerprint(candidate)
                article = {"candidate_id": cid, "url": doc["url"], "text": excerpt,
                           "observed_at": stamp[:10]}
                same = (prior and prior.get("candidate_fingerprint") == fp
                        and prior.get("body_sha256") == doc["body_sha256"])
                if not same and prior and cid in articles:
                    history = list(prior.get("previous_captures", []))
                    history.append({"body_sha256": prior.get("body_sha256"),
                                    "excerpt_sha256": prior.get("excerpt_sha256"),
                                    "observed_at": prior.get("observed_at"),
                                    "text": articles[cid].get("text", "")})
                    history = history[-2:]
                else:
                    history = list((prior or {}).get("previous_captures", []))
                articles[cid] = article
                receipts[cid] = {
                    "candidate_id": cid, "candidate_fingerprint": fp,
                    "original_url": origin_url, "resolved_url": doc["url"],
                    "publisher": candidate.get("publisher"), "observed_at": stamp,
                    "first_observed_at": prior.get("first_observed_at", stamp) if same else stamp,
                    "last_checked_at": stamp, "http_status": 200,
                    "redirect_chain": doc["redirects"],
                    "body_sha256": doc["body_sha256"], "body_bytes": doc["body_bytes"],
                    "excerpt_sha256": sha256(excerpt.encode("utf-8")),
                    "fragments": fragments, "previous_captures": history,
                }
                failures.pop(cid, None)
            except CaptureError as exc:
                failures[cid] = {
                    "candidate_id": cid, "url": origin_url,
                    "checked_at": stamp, "reason": str(exc),
                    "previous_evidence_retained": bool(prior),
                    **({"resolved_host": exc.resolved_host} if exc.resolved_host else {}),
                    **({"transport_reason": exc.transport_reason} if exc.transport_reason else {}),
                    **({"resolved_url_sha256": exc.resolved_url_sha256}
                       if exc.resolved_url_sha256 else {}),
                    **({"redirect_count": exc.redirect_count}
                       if exc.redirect_count is not None else {}),
                }
                # Do not route stale evidence after the queue identity changed.
                if prior and prior.get("candidate_fingerprint") != fingerprint(candidate):
                    articles.pop(cid, None)
                    receipts.pop(cid, None)
    finally:
        if owned:
            session.close()
    initial.update({
        "schema_version": 1,
        "articles": sorted(articles.values(), key=lambda x: x["candidate_id"]),
        "receipts": sorted(receipts.values(), key=lambda x: x["candidate_id"]),
        "failures": sorted(failures.values(), key=lambda x: x["candidate_id"]),
        "last_capture_summary": {
            "urls_checked": attempted, "http_requests": calls[0],
            "articles_downloaded": succeeded, "usable_evidence_packages": usable,
            "failed_candidates": attempted - usable, "finished_at": now_iso(),
            "production_enabled": False, "publication_allowed": False,
        },
    })
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_suffix(output.suffix + ".tmp")
    temp.write_text(json.dumps(initial, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, output)
    return initial["last_capture_summary"]
