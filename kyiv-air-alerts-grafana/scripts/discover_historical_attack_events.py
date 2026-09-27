#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

import monitor_explosion_candidates as monitor

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ALERTS = ROOT / "data" / "explosion_metric_handoff" / "source_slices" / "lviv-replay_alerts.json"
DEFAULT_EVIDENCE = ROOT / "data" / "explosion_research" / "lviv" / "final_evidence.json"
UTC = timezone.utc
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ukraine-air-alerts-historical-attack-event-pilot/1.0)",
    "Accept-Language": "uk,en;q=0.8",
}
ATTACK_DISCOVERY_RE = re.compile(
    r"\b(?:вибух\w*|влуч\w*|поціл\w*|приліт\w*|удар\w*|вдар\w*|"
    r"пошкод\w*|пожеж\w*|загор\w*|займан\w*|ппо|протиповітр\w*)",
    re.IGNORECASE,
)
PPO_RE = re.compile(r"\b(?:ппо|протиповітр\w*)", re.IGNORECASE)


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


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def choose_anchor(evidence: dict, episode_order: dict[str, int]) -> dict:
    candidates = []
    for row in evidence.get("strict_events") or []:
        text = " ".join(
            str(x or "")
            for x in (
                row.get("evidence"),
                (row.get("raw_record") or {}).get("notes"),
                (row.get("raw_record") or {}).get("telegram_source"),
            )
        )
        raw = row.get("raw_record") or {}
        episode_id = str(row.get("episode_id") or "")
        if not episode_id or episode_id not in episode_order or not PPO_RE.search(text):
            continue
        telegram_message_id = str(raw.get("telegram_message_id") or "")
        candidates.append(
            {
                "episode_id": episode_id,
                "event_id": row.get("event_id"),
                "source_url": row.get("source_url"),
                "telegram_source": raw.get("telegram_source"),
                "telegram_message_id": telegram_message_id or None,
                "episode_index": episode_order[episode_id],
                "has_direct_telegram_provenance": bool(telegram_message_id and raw.get("telegram_source")),
            }
        )
    if not candidates:
        raise RuntimeError("No retained PPO control found for deterministic pilot anchor")
    candidates.sort(
        key=lambda x: (
            0 if x["has_direct_telegram_provenance"] else 1,
            x["episode_index"],
            str(x["event_id"] or ""),
        )
    )
    return candidates[0]


def select_episode_window(episodes: list[dict], anchor_episode_id: str, limit: int) -> list[dict]:
    if limit < 1:
        raise ValueError("limit must be positive")
    if limit > len(episodes):
        limit = len(episodes)
    idx = next(i for i, ep in enumerate(episodes) if str(ep["episode_id"]) == anchor_episode_id)
    left = limit // 2
    start = max(0, idx - left)
    end = start + limit
    if end > len(episodes):
        end = len(episodes)
        start = max(0, end - limit)
    selected = episodes[start:end]
    if len(selected) != limit or anchor_episode_id not in {str(x["episode_id"]) for x in selected}:
        raise AssertionError("deterministic episode selection failed")
    return selected


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


def fetch_suspilne_archive_day(session: requests.Session, local_day: str) -> tuple[list[str], str]:
    year, month, day = local_day.split("-")
    url = f"https://suspilne.media/lviv/archive/{year}/{int(month)}/{int(day)}/"
    response = session.get(url, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    urls = set()
    for link in soup.select('a[href]'):
        href = str(link.get("href") or "")
        if href.startswith("/lviv/"):
            href = "https://suspilne.media" + href
        if not href.startswith("https://suspilne.media/lviv/"):
            continue
        if "/archive/" in href:
            continue
        urls.add(href.split("#", 1)[0])
    return sorted(urls), url


def fetch_suspilne_articles_for_days(
    local_days: list[str],
    sleep_seconds: float,
    max_articles_per_day: int = 80,
) -> tuple[list[dict], dict]:
    session = requests.Session()
    session.headers.update(HEADERS)
    seen_urls = set()
    articles = []
    archive_pages = []
    article_requests = 0

    for local_day in local_days:
        urls, archive_url = fetch_suspilne_archive_day(session, local_day)
        archive_pages.append({"local_day": local_day, "archive_url": archive_url, "article_links": len(urls)})
        for url in urls[:max_articles_per_day]:
            if url in seen_urls:
                continue
            seen_urls.add(url)
            response = session.get(url, timeout=30)
            article_requests += 1
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            title_node = soup.select_one("h1")
            title = " ".join(title_node.stripped_strings) if title_node else ""
            text = extract_article_text_from_soup(soup)
            published_at = extract_source_timestamp(soup)
            if not title and not text:
                continue
            articles.append({
                "url": str(response.url),
                "title": title,
                "text": text,
                "published_at": published_at,
                "archive_local_day": local_day,
            })
            time.sleep(sleep_seconds)

    articles.sort(key=lambda x: ((x.get("published_at") or ""), x["url"]))
    return articles, {
        "source": "suspilne.media/lviv date archive",
        "archive_days": len(local_days),
        "archive_requests": len(local_days),
        "article_requests": article_requests,
        "unique_article_urls": len(seen_urls),
        "archive_pages": archive_pages,
    }


def fetch_telegram_search(
    channel: str,
    query: str,
    window_start: datetime,
    window_end: datetime,
    max_pages: int,
    sleep_seconds: float,
) -> tuple[list[dict], dict]:
    session = requests.Session()
    session.headers.update(HEADERS)
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
        response = session.get(url, timeout=30)
        requests_made += 1
        response.raise_for_status()
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
                    "message_id": message_id,
                    "published_at": iso(published),
                    "text": text,
                    "url": link,
                }

        if not page_ids or not page_times:
            break
        page_oldest = min(page_times)
        if page_oldest < window_start:
            stopped_because_older = True
            break
        cur_min = min(page_ids)
        if last_min is not None and cur_min >= last_min:
            break
        last_min = cur_min
        if cur_min <= 1:
            break
        before = cur_min
        time.sleep(sleep_seconds)

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


def classifier_row(channel: str, label: str, post: dict) -> dict:
    text = str(post.get("text") or "")
    return {
        "source": f"Telegram / {label}",
        "title": text[:240] or f"Telegram post {post['message_id']}",
        "url": post["url"],
        "publisher": label,
        "publisher_url": f"https://t.me/{channel}",
        "published_at": post["published_at"],
        "snippet": text[:1200],
        "discovery_basis": "historical_public_telegram_search",
    }


def matched_terms(text: str) -> list[str]:
    low = monitor.normalize_evidence_text(text)
    terms = []
    for event_type in monitor.ATTACK_EVENT_TYPE_ORDER:
        if event_type in monitor.attack_event_types(low):
            terms.append(event_type)
    if "ппо" in low or "протиповітр" in low:
        terms.append("air_defense_context")
    return terms


def retained_control_ids(evidence: dict, selected_ids: set[str]) -> list[str]:
    ids = []
    for row in evidence.get("strict_events") or []:
        episode_id = str(row.get("episode_id") or "")
        if episode_id in selected_ids:
            ids.append(episode_id)
    return sorted(set(ids))


def build_pilot(
    alerts_path: Path,
    evidence_path: Path,
    city_key: str,
    max_episodes: int,
    channel: str,
    channel_label: str,
    max_pages: int,
    sleep_seconds: float,
) -> dict:
    alerts_doc = load_json(alerts_path)
    evidence = load_json(evidence_path)
    if str(alerts_doc.get("city_key") or "") != city_key:
        raise RuntimeError("alert corpus city mismatch")
    if str(evidence.get("city_key") or "") != city_key:
        raise RuntimeError("evidence corpus city mismatch")

    episodes = list(alerts_doc.get("episodes") or [])
    if len(episodes) != int(alerts_doc.get("episode_count") or len(episodes)):
        raise RuntimeError("alert corpus count mismatch")
    episode_order = {str(ep["episode_id"]): i for i, ep in enumerate(episodes)}
    anchor = choose_anchor(evidence, episode_order)
    selected = select_episode_window(episodes, anchor["episode_id"], max_episodes)
    selected_ids = {str(ep["episode_id"]) for ep in selected}

    search_start = min(parse_dt(ep["alert_start"]) for ep in selected) - timedelta(hours=3)
    search_end = max(parse_dt(ep["alert_end"]) for ep in selected) + timedelta(hours=72)
    local_days = sorted({str(ep["alert_start_date_kyiv"]) for ep in selected})
    articles, fetch_meta = fetch_suspilne_articles_for_days(local_days, sleep_seconds)

    observations = []
    for article in articles:
        text = " ".join(x for x in (str(article.get("title") or ""), str(article.get("text") or "")) if x)
        if not monitor.city_mentioned(city_key, text):
            continue
        if not ATTACK_DISCOVERY_RE.search(text):
            continue
        row = {
            "source": "Suspilne Lviv archive",
            "title": str(article.get("title") or "")[:240],
            "url": article["url"],
            "publisher": "Суспільне Львів",
            "publisher_url": "https://suspilne.media/lviv/",
            "published_at": article.get("published_at"),
            "snippet": str(article.get("text") or "")[:1200],
            "matched_text_excerpt": str(article.get("text") or "")[:50000],
            "discovery_basis": "historical_source_local_html",
        }
        matching = monitor.match_candidate_to_episodes(row, selected)
        decision = monitor.classify_candidate(row, city_key, selected, matching)
        obs_id = hashlib.sha256(("html|" + article["url"]).encode("utf-8")).hexdigest()[:24]
        temporal = decision.get("temporal_binding") or {}
        observations.append(
            {
                "observation_id": obs_id,
                "source_type": "source_local_html",
                "source": "Суспільне Львів",
                "source_url": article["url"],
                "telegram_channel": None,
                "telegram_message_id": None,
                "source_timestamp": article.get("published_at"),
                "event_timestamp_if_stated": temporal.get("event_time"),
                "excerpt": str(article.get("text") or "")[:1200],
                "matched_terms": matched_terms(text),
                "event_types_supported": list(decision.get("event_types") or []),
                "exact_city_binding": decision.get("exact_city_classification_evidence"),
                "air_attack_context": decision.get("air_military_context"),
                "same_attack_context": decision.get("same_attack_context"),
                "temporal_binding": temporal,
                "classification_outcome": decision.get("proposed_outcome"),
                "classification_episode_id": decision.get("proposed_matched_episode_id"),
                "classification_reason_codes": list(decision.get("reason_codes") or []),
                "content_hash": content_hash(article["url"], article.get("published_at"), text),
                "provenance": {
                    "retrieval_method": "suspilne.media/lviv/archive/YYYY/M/D/ bounded date-local crawl",
                    "query": article.get("archive_local_day"),
                    "classifier": "monitor_explosion_candidates.py current branch version",
                },
            }
        )

    observations.sort(key=lambda x: ((x.get("source_timestamp") or ""), x["source_url"]))
    by_episode: dict[str, list[dict]] = {str(ep["episode_id"]): [] for ep in selected}
    for obs in observations:
        episode_id = str(obs.get("classification_episode_id") or "")
        if episode_id in by_episode:
            by_episode[episode_id].append(obs)

    canonical_events = []
    episode_results = []
    for ep in selected:
        episode_id = str(ep["episode_id"])
        ep_obs = by_episode[episode_id]
        strict_obs = [x for x in ep_obs if x["classification_outcome"] == "approved_strict"]
        sensitivity_obs = [x for x in ep_obs if x["classification_outcome"] == "approved_sensitivity"]
        event_types = []
        for obs in strict_obs:
            for event_type in obs["event_types_supported"]:
                if event_type not in event_types:
                    event_types.append(event_type)
            canonical_events.append(
                {
                    "canonical_event_id": hashlib.sha256(
                        f"{city_key}|{episode_id}|{obs['observation_id']}".encode("utf-8")
                    ).hexdigest()[:24],
                    "episode_id": episode_id,
                    "event_types": list(obs["event_types_supported"]),
                    "observation_ids": [obs["observation_id"]],
                    "deduplication_status": "observation_level_unmerged_pilot",
                    "ambiguity_flag": len(strict_obs) > 1,
                }
            )
        episode_results.append(
            {
                **ep,
                "has_confirmed_event": bool(strict_obs),
                "confirmed_event_count": len(strict_obs),
                "event_types": event_types,
                "strict_observation_ids": [x["observation_id"] for x in strict_obs],
                "sensitivity_observation_ids": [x["observation_id"] for x in sensitivity_obs],
            }
        )

    controls = retained_control_ids(evidence, selected_ids)
    discovered_strict_ids = {
        row["episode_id"] for row in episode_results if row["has_confirmed_event"]
    }
    anchor_rediscovered = anchor["episode_id"] in discovered_strict_ids
    retained_controls_rediscovered = sorted(set(controls) & discovered_strict_ids)
    newly_strict_episode_ids = sorted(discovered_strict_ids - set(controls))

    return {
        "schema_version": 1,
        "kind": "historical_attack_event_discovery_pilot",
        "generated_at": iso(datetime.now(UTC)),
        "city_key": city_key,
        "city": monitor.CITY_CONFIG[city_key]["label"],
        "scope": {
            "max_alert_episodes": max_episodes,
            "selected_episode_count": len(selected),
            "network_source": "suspilne.media/lviv source-local date archives",
            "historical_baseline_mutated": False,
            "final_evidence_mutated": False,
            "live_metric_mutated": False,
            "dashboard_mutated": False,
            "production_mutated": False,
        },
        "selection": {
            "rule": "READY city with smallest historical episode universe; 40-episode centered window around earliest retained PPO control with direct Telegram provenance",
            "anchor": anchor,
            "window_start_episode_id": selected[0]["episode_id"],
            "window_end_episode_id": selected[-1]["episode_id"],
            "window_start": selected[0]["alert_start"],
            "window_end": selected[-1]["alert_end"],
        },
        "retrieval": {
            **fetch_meta,
            "search_window_start": iso(search_start),
            "search_window_end": iso(search_end),
            "rate_limit_sleep_seconds": sleep_seconds,
            "timeout_seconds": 30,
            "fallback_telegram_source_not_used": f"@{channel}",
            "fallback_reason": "public Telegram search did not provide sufficient historical depth in first pilot attempt",
        },
        "event_taxonomy": list(monitor.ATTACK_EVENT_TYPE_ORDER),
        "episode_results": episode_results,
        "canonical_events": canonical_events,
        "evidence_observations": observations,
        "controls": {
            "retained_strict_control_episode_ids_in_window": controls,
            "retained_control_count": len(controls),
            "rediscovered_strict_control_episode_ids": retained_controls_rediscovered,
            "rediscovered_strict_control_count": len(retained_controls_rediscovered),
            "anchor_rediscovered_strict": anchor_rediscovered,
            "newly_strict_episode_ids_vs_retained_controls": newly_strict_episode_ids,
        },
        "summary": {
            "selected_episode_count": len(selected),
            "retrieved_city_attack_observation_count": len(observations),
            "approved_strict_observation_count": sum(
                1 for x in observations if x["classification_outcome"] == "approved_strict"
            ),
            "approved_sensitivity_observation_count": sum(
                1 for x in observations if x["classification_outcome"] == "approved_sensitivity"
            ),
            "needs_review_observation_count": sum(
                1 for x in observations if x["classification_outcome"] == "needs_review"
            ),
            "rejected_observation_count": sum(
                1 for x in observations if x["classification_outcome"] == "rejected"
            ),
            "event_positive_episode_count": len(discovered_strict_ids),
            "event_positive_episode_share": round(len(discovered_strict_ids) / len(selected), 6),
        },
        "metric_rule": "An alert episode contributes at most 1 to the numerator when has_confirmed_event=true. Multiple observations/events do not inflate the numerator.",
        "verdict": (
            "HISTORICAL ATTACK-EVENT DISCOVERY PILOT CLEAN"
            if observations and anchor_rediscovered
            else "HISTORICAL ATTACK-EVENT DISCOVERY PILOT BLOCKED"
        ),
    }


def self_test() -> None:
    fake = [
        {"episode_id": f"e{i}", "alert_start": f"2026-01-{i+1:02d}T00:00:00Z", "alert_end": f"2026-01-{i+1:02d}T01:00:00Z"}
        for i in range(10)
    ]
    selected = select_episode_window(fake, "e5", 5)
    assert [x["episode_id"] for x in selected] == ["e3", "e4", "e5", "e6", "e7"]
    assert matched_terms("У Львові влучання пошкодило будинок і спричинило пожежу") == ["impact", "damage", "fire"]
    print("Historical attack-event pilot helper self-test OK")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--city", default="lviv")
    parser.add_argument("--max-episodes", type=int, default=40)
    parser.add_argument("--alerts", type=Path, default=DEFAULT_ALERTS)
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--channel", default="suspilnenews")
    parser.add_argument("--channel-label", default="СУСПІЛЬНЕ НОВИНИ")
    parser.add_argument("--max-pages", type=int, default=100)
    parser.add_argument("--sleep-seconds", type=float, default=0.2)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return
    if not args.output:
        parser.error("--output is required")
    if args.city != "lviv":
        parser.error("This first pilot is intentionally locked to lviv")

    result = build_pilot(
        args.alerts,
        args.evidence,
        args.city,
        args.max_episodes,
        args.channel,
        args.channel_label,
        args.max_pages,
        args.sleep_seconds,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"verdict": result["verdict"], "summary": result["summary"], "controls": result["controls"], "retrieval": result["retrieval"]}, ensure_ascii=False, indent=2))
    if result["verdict"].endswith("BLOCKED"):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
