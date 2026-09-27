#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

UTC = timezone.utc
DEFAULT_TIMEOUT_SECONDS = 15
DEFAULT_MAX_RETRIES = 2
DEFAULT_RATE_LIMIT_SECONDS = 0.2
DEFAULT_USER_AGENT = "Mozilla/5.0 (compatible; ukraine-air-alerts-historical-attack-event-source-adapter/1.0)"

HEADERS = {
    "User-Agent": DEFAULT_USER_AGENT,
    "Accept-Language": "uk,en;q=0.8",
}

TELEGRAM_POST_RE = re.compile(
    r"https?://(?:t\.me|telegram\.me)/(?:s/)?([A-Za-z0-9_]+)/([0-9]+)",
    re.IGNORECASE,
)
ARCHIVE_CARD_RE = re.compile(
    r"(?:вибух|атак|обстріл|удар|влуч|приліт|ракет|бпла|безпілот|дрон|шахед|ппо|протиповітр|пошкод|пожеж|загор|займан)",
    re.IGNORECASE,
)


def parse_dt(value: str) -> datetime:
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def content_hash(*parts: object) -> str:
    payload = "\n".join(str(x or "") for x in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def canonical_observation_id(channel: str, message_id: int) -> str:
    return hashlib.sha256(f"telegram|{channel}|{message_id}".encode("utf-8")).hexdigest()[:24]


def canonical_url(url: str) -> str:
    return str(url or "").split("#", 1)[0].strip()


@dataclass(frozen=True)
class NetworkBounds:
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    max_retries: int = DEFAULT_MAX_RETRIES
    rate_limit_seconds: float = DEFAULT_RATE_LIMIT_SECONDS
    max_archive_articles_per_day: int = 80
    max_telegram_pages: int = 100
    max_neighbor_previous: int = 3


class BoundedSession:
    def __init__(self, bounds: NetworkBounds | None = None):
        self.bounds = bounds or NetworkBounds()
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def get(self, url: str, *, timeout_seconds: int | None = None) -> requests.Response:
        timeout = timeout_seconds or self.bounds.timeout_seconds
        last_error = None
        for attempt in range(self.bounds.max_retries + 1):
            try:
                response = self.session.get(url, timeout=timeout, allow_redirects=True)
                response.raise_for_status()
                return response
            except requests.RequestException as exc:
                last_error = exc
                if attempt >= self.bounds.max_retries:
                    raise
                time.sleep(self.bounds.rate_limit_seconds)
        raise RuntimeError(str(last_error))


def extract_source_timestamp(soup: BeautifulSoup) -> str | None:
    candidates = []
    for selector, attr in (
        ('meta[property="article:published_time"]', "content"),
        ('meta[name="article:published_time"]', "content"),
        ('time[datetime]', "datetime"),
    ):
        node = soup.select_one(selector)
        if node and node.get(attr):
            candidates.append(str(node.get(attr)))
    for value in candidates:
        try:
            return iso(parse_dt(value))
        except Exception:
            continue
    return None


def extract_article_text_from_soup(soup: BeautifulSoup) -> str:
    for tag in soup.find_all(("script", "style", "nav", "header", "footer", "aside", "form", "svg", "noscript")):
        tag.decompose()
    container = soup.find("article") or soup.find("main")
    if container is not None:
        text = container.get_text(" ", strip=True)
    else:
        text = " ".join(p.get_text(" ", strip=True) for p in soup.find_all("p"))
    return " ".join(text.split())[:50000]


def extract_linked_telegram_refs(soup: BeautifulSoup) -> list[dict]:
    refs = {}
    for link in soup.select("a[href]"):
        href = str(link.get("href") or "")
        match = TELEGRAM_POST_RE.search(href)
        if not match:
            continue
        channel = match.group(1)
        message_id = int(match.group(2))
        refs[(channel.casefold(), message_id)] = {
            "channel": channel,
            "message_id": message_id,
            "url": f"https://t.me/{channel}/{message_id}",
        }
    return [refs[key] for key in sorted(refs)]


def parse_exact_telegram_post_html(html: str, channel: str, message_id: int) -> dict | None:
    soup = BeautifulSoup(html, "html.parser")
    for wrap in soup.select(".tgme_widget_message_wrap, .tgme_widget_message"):
        msg = wrap.select_one(".tgme_widget_message") if "tgme_widget_message_wrap" in (wrap.get("class") or []) else wrap
        if not msg:
            continue
        post = str(msg.get("data-post") or "")
        match = re.search(r"/([0-9]+)$", post)
        if not match or int(match.group(1)) != message_id:
            continue
        time_el = wrap.select_one("time[datetime]") or msg.select_one("time[datetime]")
        if not time_el:
            continue
        text_el = wrap.select_one(".tgme_widget_message_text") or msg.select_one(".tgme_widget_message_text")
        text = " ".join(text_el.stripped_strings) if text_el else ""
        return {
            "channel": channel,
            "message_id": message_id,
            "published_at": iso(parse_dt(time_el["datetime"])),
            "text": text,
            "url": f"https://t.me/{channel}/{message_id}",
        }
    return None


class PublicTelegramAdapter:
    source_type = "public_telegram"

    def __init__(self, bounds: NetworkBounds | None = None):
        self.bounds = bounds or NetworkBounds()
        self.http = BoundedSession(self.bounds)

    def fetch_exact_post(self, channel: str, message_id: int) -> tuple[dict | None, dict]:
        attempts = []
        urls = (
            f"https://t.me/s/{channel}/{message_id}",
            f"https://t.me/{channel}/{message_id}?embed=1&mode=tme",
        )
        for url in urls:
            try:
                response = self.http.get(url)
                attempts.append({"url": url, "status_code": response.status_code})
                parsed = parse_exact_telegram_post_html(response.text, channel, message_id)
                if parsed:
                    parsed["retrieval_url"] = url
                    return parsed, {"attempts": attempts, "resolved": True}
            except requests.RequestException as exc:
                attempts.append({"url": url, "error": f"{type(exc).__name__}: {exc}"})
        return None, {"attempts": attempts, "resolved": False}

    def fetch_neighbor_window(
        self,
        channel: str,
        center_message_id: int,
        previous_count: int = 3,
    ) -> tuple[list[dict], dict]:
        if previous_count < 0 or previous_count > self.bounds.max_neighbor_previous:
            raise ValueError(f"previous_count must be between 0 and {self.bounds.max_neighbor_previous}")
        url = f"https://t.me/s/{channel}?before={center_message_id + 1}"
        try:
            response = self.http.get(url)
        except requests.RequestException as exc:
            return [], {"url": url, "resolved": False, "error": f"{type(exc).__name__}: {exc}"}
        soup = BeautifulSoup(response.text, "html.parser")
        floor = max(1, center_message_id - previous_count)
        rows = []
        for wrap in soup.select(".tgme_widget_message_wrap"):
            msg = wrap.select_one(".tgme_widget_message")
            time_el = wrap.select_one("time[datetime]")
            if not msg or not time_el:
                continue
            post = str(msg.get("data-post") or "")
            match = re.search(r"/([0-9]+)$", post)
            if not match:
                continue
            message_id = int(match.group(1))
            if not (floor <= message_id < center_message_id):
                continue
            text_el = wrap.select_one(".tgme_widget_message_text")
            text = " ".join(text_el.stripped_strings) if text_el else ""
            rows.append({
                "channel": channel,
                "message_id": message_id,
                "published_at": iso(parse_dt(time_el["datetime"])),
                "text": text,
                "url": f"https://t.me/{channel}/{message_id}",
                "retrieval_url": url,
            })
        rows.sort(key=lambda row: row["message_id"])
        return rows, {
            "url": url,
            "resolved": True,
            "previous_count": previous_count,
            "returned_message_ids": [row["message_id"] for row in rows],
        }

    def search(
        self,
        channel: str,
        query: str,
        window_start: datetime,
        window_end: datetime,
        max_pages: int | None = None,
    ) -> tuple[list[dict], dict]:
        max_pages = min(max_pages or self.bounds.max_telegram_pages, self.bounds.max_telegram_pages)
        before = None
        last_min = None
        seen: dict[int, dict] = {}
        pages = 0
        requests_made = 0
        stopped_because_older = False
        for _ in range(max_pages):
            params = f"q={quote(query)}"
            if before is not None:
                params += f"&before={before}"
            url = f"https://t.me/s/{channel}?{params}"
            response = self.http.get(url, timeout_seconds=max(30, self.bounds.timeout_seconds))
            requests_made += 1
            pages += 1
            soup = BeautifulSoup(response.text, "html.parser")
            page_ids = []
            page_times = []
            for wrap in soup.select(".tgme_widget_message_wrap"):
                msg = wrap.select_one(".tgme_widget_message")
                time_el = wrap.select_one("time[datetime]")
                if not msg or not time_el:
                    continue
                post = str(msg.get("data-post") or "")
                match = re.search(r"/(\d+)$", post)
                if not match:
                    continue
                message_id = int(match.group(1))
                published = parse_dt(time_el["datetime"])
                text_el = wrap.select_one(".tgme_widget_message_text")
                text = " ".join(text_el.stripped_strings) if text_el else ""
                link_el = wrap.select_one("a.tgme_widget_message_date")
                link = link_el.get("href") if link_el else f"https://t.me/{channel}/{message_id}"
                page_ids.append(message_id)
                page_times.append(published)
                if window_start <= published <= window_end:
                    seen[message_id] = {
                        "channel": channel,
                        "message_id": message_id,
                        "published_at": iso(published),
                        "text": text,
                        "url": canonical_url(link),
                        "retrieval_url": url,
                    }
            if not page_ids or not page_times:
                break
            if min(page_times) < window_start:
                stopped_because_older = True
                break
            cur_min = min(page_ids)
            if last_min is not None and cur_min >= last_min:
                break
            last_min = cur_min
            if cur_min <= 1:
                break
            before = cur_min
            time.sleep(self.bounds.rate_limit_seconds)
        rows = sorted(seen.values(), key=lambda x: (x["published_at"], x["message_id"]))
        return rows, {
            "channel": channel,
            "query": query,
            "pages": pages,
            "requests_made": requests_made,
            "max_pages": max_pages,
            "stopped_because_older_than_window": stopped_because_older,
            "window_hits": len(rows),
        }


class SourceLocalHtmlArchiveAdapter:
    source_type = "source_local_html"

    def __init__(self, site_key: str, section: str, bounds: NetworkBounds | None = None):
        if site_key != "suspilne":
            raise ValueError(f"Unsupported source-local archive site: {site_key}")
        self.site_key = site_key
        self.section = section
        self.bounds = bounds or NetworkBounds()
        self.http = BoundedSession(self.bounds)

    def archive_url(self, local_day: str) -> str:
        year, month, day = local_day.split("-")
        return f"https://suspilne.media/{self.section}/archive/{year}/{int(month)}/{int(day)}/"

    def fetch_archive_day(self, local_day: str) -> tuple[list[str], str]:
        url = self.archive_url(local_day)
        response = self.http.get(url)
        soup = BeautifulSoup(response.text, "html.parser")
        urls = set()
        prefix = f"/{self.section}/"
        absolute_prefix = f"https://suspilne.media/{self.section}/"
        for link in soup.select("a[href]"):
            href = str(link.get("href") or "")
            card_text = " ".join(link.stripped_strings)
            if not ARCHIVE_CARD_RE.search(card_text):
                continue
            if href.startswith(prefix):
                href = "https://suspilne.media" + href
            href = canonical_url(href)
            if not href.startswith(absolute_prefix) or "/archive/" in href:
                continue
            urls.add(href)
        return sorted(urls), url

    def fetch_days(self, local_days: list[str]) -> tuple[list[dict], dict]:
        seen_urls = set()
        articles = []
        archive_pages = []
        article_requests = 0
        for local_day in local_days:
            urls, archive_url = self.fetch_archive_day(local_day)
            archive_pages.append({"local_day": local_day, "archive_url": archive_url, "article_links": len(urls)})
            for url in urls[: self.bounds.max_archive_articles_per_day]:
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                response = self.http.get(url)
                article_requests += 1
                soup = BeautifulSoup(response.text, "html.parser")
                title_node = soup.select_one("h1")
                title = " ".join(title_node.stripped_strings) if title_node else ""
                telegram_links = extract_linked_telegram_refs(soup)
                published_at = extract_source_timestamp(soup)
                text = extract_article_text_from_soup(soup)
                if title or text:
                    articles.append({
                        "url": canonical_url(str(response.url)),
                        "title": title,
                        "text": text,
                        "published_at": published_at,
                        "archive_local_day": local_day,
                        "telegram_links": telegram_links,
                        "content_hash": content_hash(str(response.url), published_at, title, text),
                        "raw_metadata": {"archive_url": archive_url},
                    })
                time.sleep(self.bounds.rate_limit_seconds)
        articles.sort(key=lambda x: ((x.get("published_at") or ""), x["url"]))
        return articles, {
            "source": f"suspilne.media/{self.section} date archive",
            "archive_days": len(local_days),
            "archive_requests": len(local_days),
            "article_requests": article_requests,
            "unique_article_urls": len(seen_urls),
            "archive_pages": archive_pages,
        }


class ExactUrlHtmlPreflightAdapter:
    source_type = "targeted_secondary_html_preflight"

    def __init__(self, bounds: NetworkBounds | None = None):
        self.bounds = bounds or NetworkBounds()
        self.http = BoundedSession(self.bounds)

    def fetch(self, source_cfg: dict) -> tuple[dict, dict]:
        response = self.http.get(source_cfg["url"])
        soup = BeautifulSoup(response.text, "html.parser")
        title_node = soup.select_one("h1")
        title = " ".join(title_node.stripped_strings) if title_node else ""
        published_at = extract_source_timestamp(soup)
        text = extract_article_text_from_soup(soup)
        article = {
            "url": canonical_url(str(response.url)),
            "title": title,
            "text": text,
            "published_at": published_at,
            "source": source_cfg["source"],
            "target_episode_id": source_cfg["target_episode_id"],
            "content_hash": content_hash(str(response.url), published_at, title, text),
            "source_family_onboarded": False,
        }
        return article, {
            "url": source_cfg["url"],
            "status_code": response.status_code,
            "published_at": published_at,
            "bytes": len(response.content),
            "source_family_onboarded": False,
        }


def fetch_suspilne_articles_for_days(
    local_days: list[str],
    sleep_seconds: float,
    max_articles_per_day: int = 80,
    section: str = "lviv",
) -> tuple[list[dict], dict]:
    bounds = NetworkBounds(
        rate_limit_seconds=sleep_seconds,
        max_archive_articles_per_day=max_articles_per_day,
    )
    return SourceLocalHtmlArchiveAdapter("suspilne", section, bounds).fetch_days(local_days)


def fetch_exact_linked_telegram_post(
    session: requests.Session,
    channel: str,
    message_id: int,
) -> tuple[dict | None, dict]:
    adapter = PublicTelegramAdapter()
    adapter.http.session = session
    return adapter.fetch_exact_post(channel, message_id)


def fetch_telegram_neighbor_window(
    session: requests.Session,
    channel: str,
    center_message_id: int,
    previous_count: int = 3,
) -> tuple[list[dict], dict]:
    adapter = PublicTelegramAdapter()
    adapter.http.session = session
    return adapter.fetch_neighbor_window(channel, center_message_id, previous_count)


def fetch_targeted_secondary_article(
    session: requests.Session,
    source_cfg: dict,
) -> tuple[dict, dict]:
    adapter = ExactUrlHtmlPreflightAdapter()
    adapter.http.session = session
    return adapter.fetch(source_cfg)


def fetch_telegram_search(
    channel: str,
    query: str,
    window_start: datetime,
    window_end: datetime,
    max_pages: int,
    sleep_seconds: float,
) -> tuple[list[dict], dict]:
    bounds = NetworkBounds(rate_limit_seconds=sleep_seconds, max_telegram_pages=max_pages)
    return PublicTelegramAdapter(bounds).search(channel, query, window_start, window_end, max_pages)
