#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import quote_plus
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

import apply_ukrainealarm_bridge as ua

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
BASELINE_FILE = DATA_DIR / "explosion_baseline_2026-09-17.json"
BRIDGE_FILE = DATA_DIR / "ukrainealarm_bridge.json"
STATE_FILE = DATA_DIR / "explosion_candidate_monitor_state.json"
QUEUE_FILE = DATA_DIR / "explosion_review_queue.json"
LAST_RUN_FILE = DATA_DIR / "explosion_candidate_monitor_last_run.json"

UTC = timezone.utc
KYIV_TZ = ZoneInfo("Europe/Kyiv")
GOOGLE_NEWS_URL = "https://news.google.com/rss/search"
FOLLOWUP_HOURS = [("immediate", 0), ("24h", 24), ("72h", 72), ("7d", 24 * 7)]
MAX_EPISODES_PER_CITY = 10000
TELEGRAM_RETENTION_DAYS = 9
TELEGRAM_MAX_PAGES = 100
TELEGRAM_CHANNELS = {
    "suspilne": {
        "handle": "suspilnenews",
        "label": "СУСПІЛЬНЕ НОВИНИ",
        "baseline_after": "2026-09-17T21:00:00Z",
    },
    "ukrpravda": {
        "handle": "ukrpravda_news",
        "label": "Українська правда",
        "baseline_after": "2026-09-17T21:00:00Z",
    },
}

CITY_CONFIG = {
    "poltava": {"label": "Полтава", "aliases": ["полтава", "полтаві", "полтави", "полтаву", "полтавою"]},
    "uzhhorod": {"label": "Ужгород", "aliases": ["ужгород", "ужгороді", "ужгорода", "ужгороду", "ужгородом"]},
    "ivano_frankivsk": {"label": "Івано-Франківськ", "aliases": ["івано-франківськ", "івано-франківську", "івано-франківська", "івано-франківськом"]},
    "chernivtsi": {"label": "Чернівці", "aliases": ["чернівці", "чернівцях", "чернівців", "чернівцями"]},
    "ternopil": {"label": "Тернопіль", "aliases": ["тернопіль", "тернополі", "тернополя", "тернополю", "тернополем"]},
    "lviv": {"label": "Львів", "aliases": ["львів", "львові", "львова", "львову", "львовом"]},
    "lutsk": {"label": "Луцьк", "aliases": ["луцьк", "луцьку", "луцька", "луцьком"]},
    "rivne": {"label": "Рівне", "aliases": ["рівне", "рівному", "рівного", "рівним"]},
    "khmelnytskyi": {"label": "Хмельницький", "aliases": ["хмельницький", "хмельницькому", "хмельницького", "хмельницьким"]},
    "vinnytsia": {"label": "Вінниця", "aliases": ["вінниця", "вінниці", "вінницю", "вінницею"]},
}

EXPLOSION_TERMS = (
    "вибух",
    "пролунав",
    "пролунали",
    "було чутно",
    "чули",
    "гучно",
    "звук вибух",
    "звуки вибух",
    "серія вибух",
    "ппо",
)


def now_utc() -> datetime:
    return datetime.now(UTC)


def iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def atomic_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def event_id(city_key: str, start: str, end: str) -> str:
    return hashlib.sha256(f"{city_key}|{start}|{end}".encode("utf-8")).hexdigest()[:24]


def candidate_id(city_key: str, url: str, title: str) -> str:
    return hashlib.sha256(f"{city_key}|{url}|{title}".encode("utf-8")).hexdigest()[:24]


def baseline_ends() -> dict[str, str]:
    baseline = load_json(BASELINE_FILE, {})
    cities = baseline.get("cities") or {}
    out = {}
    for key in CITY_CONFIG:
        row = cities.get(key) or {}
        end = str(row.get("coverage_end") or "")
        if not end:
            raise RuntimeError(f"Missing frozen coverage_end for {key}")
        out[key] = end
    return out


def make_episode(city_key: str, start: datetime, end: datetime) -> dict:
    start_s, end_s = iso(start), iso(end)
    return {
        "episode_id": event_id(city_key, start_s, end_s),
        "city_key": city_key,
        "city": CITY_CONFIG[city_key]["label"],
        "alert_source": "ukrainealarm_regionHistory",
        "alert_start": start_s,
        "alert_end": end_s,
        "alert_start_date_kyiv": start.astimezone(KYIV_TZ).date().isoformat(),
        "checks": [
            {
                "label": label,
                "due_at": iso(end + timedelta(hours=hours)),
                "checked_at": None,
                "new_candidates": None,
            }
            for label, hours in FOLLOWUP_HOURS
        ],
    }


def poll_cached_bridge(bridge_path: Path, now: datetime) -> tuple[dict[str, list[dict]], dict[str, str]]:
    bridge = load_json(bridge_path, {})
    rows_by_city: dict[str, list[dict]] = {key: [] for key in CITY_CONFIG}
    errors: dict[str, str] = {}
    for row in bridge.get("events", []):
        if not isinstance(row, dict):
            continue
        city_key = str(row.get("city_key") or "")
        if city_key not in CITY_CONFIG:
            continue
        start = parse_dt(row.get("start"))
        end = parse_dt(row.get("end"))
        if not start or not end or end <= start:
            continue
        ep = make_episode(city_key, start, end)
        ep["alert_source"] = "ukrainealarm_bridge_cached"
        rows_by_city[city_key].append(ep)

    regions = bridge.get("regions") or {}
    for city_key in CITY_CONFIG:
        region = regions.get(city_key) or {}
        checked = parse_dt(region.get("last_checked_at"))
        if not checked:
            errors[city_key] = "cached_bridge_missing_last_checked_at"
        elif now - checked > timedelta(hours=12):
            errors[city_key] = f"cached_bridge_stale:{iso(checked)}"
        dedup = {ep["episode_id"]: ep for ep in rows_by_city[city_key]}
        rows_by_city[city_key] = sorted(dedup.values(), key=lambda x: x["alert_end"])
    return rows_by_city, errors


def poll_alerts() -> tuple[dict[str, list[dict]], dict[str, str]]:
    token = os.getenv(ua.TOKEN_ENV, "").strip()
    if not token:
        raise RuntimeError(f"{ua.TOKEN_ENV} is not configured")
    bridge = load_json(BRIDGE_FILE, {})
    regions = bridge.get("regions") or {}
    client = ua.UkraineAlarmClient(token)
    out: dict[str, list[dict]] = {}
    errors: dict[str, str] = {}

    for idx, city_key in enumerate(CITY_CONFIG, 1):
        region = regions.get(city_key) or {}
        region_id = str(region.get("region_id") or "")
        api_name = str(region.get("api_region_name") or region.get("target") or CITY_CONFIG[city_key]["label"])
        if not region_id:
            errors[city_key] = "missing_region_id"
            continue
        try:
            rows = ua.history_rows(client, region_id, api_name)
            episodes = {}
            for row in rows:
                start, end = row.get("start"), row.get("end")
                if start and end and end > start:
                    ep = make_episode(city_key, start, end)
                    episodes[ep["episode_id"]] = ep
            out[city_key] = sorted(episodes.values(), key=lambda x: x["alert_end"])
            print(f"[{idx}/{len(CITY_CONFIG)}] {city_key}: {len(out[city_key])} completed alerts", flush=True)
        except Exception as exc:
            errors[city_key] = f"{type(exc).__name__}: {exc}"
            print(f"[{idx}/{len(CITY_CONFIG)}] {city_key}: ERROR {errors[city_key]}", file=sys.stderr, flush=True)
    return out, errors


def clean_text(value: str) -> str:
    text = BeautifulSoup(html.unescape(value or ""), "html.parser").get_text(" ", strip=True)
    return " ".join(text.split())


def parse_pubdate(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def city_mentioned(city_key: str, text: str) -> bool:
    low = " ".join((text or "").casefold().replace("’", "'").split())
    for alias in CITY_CONFIG[city_key]["aliases"]:
        if re.search(rf"(?<![\w-]){re.escape(alias)}(?![\w-])", low, flags=re.IGNORECASE):
            return True
    return False


def explosion_relevant(text: str) -> bool:
    low = " ".join((text or "").casefold().split())
    return any(term in low for term in EXPLOSION_TERMS)


def any_audited_city_mentioned(text: str) -> bool:
    return any(city_mentioned(key, text) for key in CITY_CONFIG)


def telegram_page(handle: str, before: int | None = None) -> tuple[list[dict], str]:
    url = f"https://t.me/s/{handle}"
    if before is not None:
        url += f"?before={before}"
    response = requests.get(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; ukraine-air-alerts-explosion-monitor/1.0)",
            "Accept-Language": "uk,en;q=0.7",
        },
        timeout=45,
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    posts = []
    for wrap in soup.select(".tgme_widget_message_wrap"):
        message = wrap.select_one(".tgme_widget_message")
        time_el = wrap.select_one("time[datetime]")
        if message is None or time_el is None:
            continue
        data_post = str(message.get("data-post") or "")
        if "/" not in data_post:
            continue
        post_handle, raw_id = data_post.rsplit("/", 1)
        try:
            message_id = int(raw_id)
        except ValueError:
            continue
        published = parse_dt(time_el.get("datetime"))
        if not published:
            continue
        text_el = wrap.select_one(".tgme_widget_message_text")
        text = clean_text(text_el.get_text(" ", strip=True) if text_el else "")
        posts.append({
            "message_id": message_id,
            "published_at": iso(published),
            "text": text,
            "url": f"https://t.me/{post_handle}/{message_id}",
        })
    posts.sort(key=lambda row: row["message_id"])
    return posts, url


def refresh_telegram_cache(state: dict, now: datetime) -> dict[str, str]:
    tg_state = state.setdefault("telegram", {})
    errors: dict[str, str] = {}
    retention_floor = now - timedelta(days=TELEGRAM_RETENTION_DAYS)

    for source_key, cfg in TELEGRAM_CHANNELS.items():
        cstate = tg_state.setdefault(source_key, {
            "handle": cfg["handle"],
            "label": cfg["label"],
            "last_seen_at": cfg["baseline_after"],
            "posts": [],
        })
        cutoff = parse_dt(cstate.get("last_seen_at")) or parse_dt(cfg["baseline_after"])
        if cutoff is None:
            cutoff = retention_floor

        collected: dict[int, dict] = {}
        before = None
        newest_seen = cutoff
        try:
            for _ in range(TELEGRAM_MAX_PAGES):
                page, _ = telegram_page(cfg["handle"], before)
                if not page:
                    break
                parsed_times = [parse_dt(row["published_at"]) for row in page]
                parsed_times = [dt for dt in parsed_times if dt]
                if not parsed_times:
                    break
                page_oldest = min(parsed_times)
                page_newest = max(parsed_times)
                if page_newest > newest_seen:
                    newest_seen = page_newest
                for row in page:
                    published = parse_dt(row["published_at"])
                    if not published or published <= cutoff:
                        continue
                    text = row.get("text") or ""
                    if explosion_relevant(text) and any_audited_city_mentioned(text):
                        collected[int(row["message_id"])] = row
                if page_oldest <= cutoff:
                    break
                next_before = min(int(row["message_id"]) for row in page)
                if before is not None and next_before >= before:
                    break
                before = next_before

            merged = {
                int(row["message_id"]): row
                for row in cstate.get("posts", [])
                if isinstance(row, dict) and str(row.get("message_id") or "").isdigit()
            }
            merged.update(collected)
            kept = []
            for row in merged.values():
                published = parse_dt(row.get("published_at"))
                if published and published >= retention_floor:
                    kept.append(row)
            kept.sort(key=lambda row: int(row["message_id"]))
            cstate["posts"] = kept
            cstate["last_seen_at"] = iso(newest_seen)
            cstate["last_poll_at"] = iso(now)
            cstate["last_error"] = None
            cstate["new_relevant_posts"] = len(collected)
        except Exception as exc:
            message = f"{type(exc).__name__}: {exc}"
            cstate["last_poll_at"] = iso(now)
            cstate["last_error"] = message
            errors[source_key] = message
    return errors


def telegram_candidates_for_city(state: dict, city_key: str, earliest: datetime, now: datetime) -> list[dict]:
    lower = earliest - timedelta(hours=3)
    upper = now + timedelta(hours=1)
    rows = []
    for source_key, cfg in TELEGRAM_CHANNELS.items():
        cstate = (state.get("telegram") or {}).get(source_key) or {}
        for post in cstate.get("posts", []):
            published = parse_dt(post.get("published_at"))
            text = str(post.get("text") or "")
            if not published or not (lower <= published <= upper):
                continue
            if not city_mentioned(city_key, text) or not explosion_relevant(text):
                continue
            rows.append({
                "source": f"Telegram / {cfg['label']}",
                "title": text[:240] or f"Telegram post {post.get('message_id')}",
                "url": post["url"],
                "publisher": cfg["label"],
                "publisher_url": f"https://t.me/{cfg['handle']}",
                "published_at": post.get("published_at"),
                "snippet": text[:1200],
            })
    dedup = {(row["url"], row["title"]): row for row in rows}
    return list(dedup.values())


def google_news_query(city_label: str) -> str:
    return (
        f'"{city_label}" '
        '(вибух OR вибухи OR "було чутно" OR "пролунали вибухи" OR "чули вибухи") '
        'when:8d'
    )


def search_city_news(city_key: str, earliest: datetime, now: datetime) -> tuple[list[dict], str]:
    label = CITY_CONFIG[city_key]["label"]
    url = f"{GOOGLE_NEWS_URL}?q={quote_plus(google_news_query(label))}&hl=uk&gl=UA&ceid=UA:uk"
    response = requests.get(
        url,
        headers={
            "User-Agent": "ukraine-air-alerts-explosion-monitor/1.0",
            "Accept-Language": "uk,en;q=0.7",
        },
        timeout=45,
    )
    response.raise_for_status()
    root = ET.fromstring(response.content)
    lower_bound = earliest - timedelta(hours=3)
    upper_bound = now + timedelta(hours=1)
    rows = []
    for item in root.findall(".//item"):
        title = clean_text(item.findtext("title") or "")
        description = clean_text(item.findtext("description") or "")
        link = (item.findtext("link") or "").strip()
        published = parse_pubdate(item.findtext("pubDate"))
        source_el = item.find("source")
        publisher = clean_text(source_el.text or "") if source_el is not None else ""
        publisher_url = (source_el.attrib.get("url") or "").strip() if source_el is not None else ""
        if not title or not link:
            continue
        if published and not (lower_bound <= published <= upper_bound):
            continue
        combined = f"{title} {description}"
        if not city_mentioned(city_key, combined):
            continue
        if not explosion_relevant(combined):
            continue
        rows.append({
            "title": title,
            "url": link,
            "publisher": publisher or "Google News result",
            "publisher_url": publisher_url or None,
            "published_at": iso(published) if published else None,
            "snippet": description[:1200],
        })
    dedup = {(r["url"], r["title"]): r for r in rows}
    return list(dedup.values()), url


def ensure_state() -> dict:
    state = load_json(STATE_FILE, {})
    if not isinstance(state, dict) or state.get("schema_version") != 1:
        state = {"schema_version": 1, "created_at": iso(now_utc()), "cities": {}}
    state.setdefault("cities", {})
    return state


def process_events(state: dict, polled: dict[str, list[dict]], errors: dict[str, str], now: datetime) -> int:
    frozen_end = baseline_ends()
    new_count = 0
    for city_key in CITY_CONFIG:
        cstate = state["cities"].setdefault(city_key, {
            "city": CITY_CONFIG[city_key]["label"],
            "baseline_coverage_end": frozen_end[city_key],
            "episodes": [],
        })
        cstate["last_poll_at"] = iso(now)
        rows = polled.get(city_key, [])
        previous_latest_end = parse_dt(cstate.get("latest_api_alert_end"))
        if city_key not in errors and previous_latest_end and rows:
            current_ids = {str(ep.get("episode_id") or "") for ep in rows}
            known_ids = {
                str(ep.get("episode_id") or "")
                for ep in cstate.get("episodes", [])
                if ep.get("episode_id")
            }
            overlaps_known = bool(current_ids & known_ids)
            oldest_end = parse_dt(rows[0].get("alert_end"))
            if not overlaps_known and oldest_end and oldest_end > previous_latest_end:
                errors[city_key] = (
                    "history_window_no_overlap:"
                    f"previous_latest_end={iso(previous_latest_end)};"
                    f"current_oldest_end={iso(oldest_end)}"
                )

        cstate["last_poll_error"] = errors.get(city_key)
        if city_key not in errors:
            cstate["last_successful_poll_at"] = iso(now)
        known = {str(ep.get("episode_id")) for ep in cstate.get("episodes", []) if ep.get("episode_id")}
        if city_key in errors:
            continue
        for ep in rows:
            if ep["alert_start_date_kyiv"] <= frozen_end[city_key]:
                continue
            if ep["episode_id"] in known:
                continue
            cstate.setdefault("episodes", []).append(ep)
            known.add(ep["episode_id"])
            new_count += 1
        cstate["episodes"] = sorted(cstate.get("episodes", []), key=lambda x: x.get("alert_start") or "")[-MAX_EPISODES_PER_CITY:]
        if rows:
            latest = rows[-1]
            cstate["latest_api_alert_start"] = latest["alert_start"]
            cstate["latest_api_alert_end"] = latest["alert_end"]
    return new_count


def due_checks(state: dict, now: datetime) -> dict[str, list[tuple[dict, dict]]]:
    out: dict[str, list[tuple[dict, dict]]] = {}
    for city_key, cstate in state.get("cities", {}).items():
        if city_key not in CITY_CONFIG:
            continue
        for ep in cstate.get("episodes", []):
            for check in ep.get("checks", []):
                if check.get("checked_at"):
                    continue
                due = parse_dt(check.get("due_at"))
                if due and due <= now:
                    out.setdefault(city_key, []).append((ep, check))
    return out


def add_candidates(queue: list[dict], city_key: str, rows: list[dict], due: list[tuple[dict, dict]], now: datetime) -> int:
    by_id = {str(x.get("candidate_id")): x for x in queue if isinstance(x, dict) and x.get("candidate_id")}
    episode_ids = sorted({ep["episode_id"] for ep, _ in due})
    check_labels = sorted({check["label"] for _, check in due})
    added = 0
    for row in rows:
        cid = candidate_id(city_key, row["url"], row["title"])
        existing = by_id.get(cid)
        if existing:
            existing["trigger_episode_ids"] = sorted(set(existing.get("trigger_episode_ids") or []) | set(episode_ids))
            existing["trigger_check_labels"] = sorted(set(existing.get("trigger_check_labels") or []) | set(check_labels))
            existing["last_seen_at"] = iso(now)
            continue
        item = {
            "candidate_id": cid,
            "city_key": city_key,
            "city": CITY_CONFIG[city_key]["label"],
            "status": "needs_review",
            "source": row.get("source") or "Google News RSS",
            "publisher": row.get("publisher"),
            "publisher_url": row.get("publisher_url"),
            "url": row["url"],
            "title": row["title"],
            "published_at": row.get("published_at"),
            "snippet": row.get("snippet"),
            "first_discovered_at": iso(now),
            "last_seen_at": iso(now),
            "trigger_episode_ids": episode_ids,
            "trigger_check_labels": check_labels,
            "matched_episode_id": None,
            "review_note": None,
            "note": (
                "Automatically discovered after a completed alert episode. "
                "Do not count it in strict automatically. Review exact-city geography, war/air context, "
                "event time (publication time is not explosion time), deduplication, and match to one concrete alert episode. "
                "Set status=approved_strict with matched_episode_id only after review; use approved_sensitivity for a sensitivity-only case."
            ),
        }
        queue.append(item)
        by_id[cid] = item
        added += 1
    return added


def self_test() -> None:
    assert len(CITY_CONFIG) == 10
    assert city_mentioned("poltava", "У Полтаві пролунали вибухи")
    assert not city_mentioned("poltava", "На Полтавщині пролунали вибухи")
    assert city_mentioned("vinnytsia", "У Вінниці було чутно вибух")
    assert not city_mentioned("vinnytsia", "На Вінниччині було гучно")
    assert explosion_relevant("У Львові пролунали вибухи")
    assert explosion_relevant("У Львові було гучно, працювала ППО")
    dt = datetime(2026, 9, 18, 10, tzinfo=UTC)
    ep = make_episode("poltava", dt, dt + timedelta(hours=1))
    assert [x["label"] for x in ep["checks"]] == ["immediate", "24h", "72h", "7d"]
    assert ep["alert_start_date_kyiv"] == "2026-09-18"
    print("Self-test OK: 10 audited cities, exact-city filter, explosion filter, follow-up schedule")


def main() -> None:
    parser = argparse.ArgumentParser(description="Monitor new completed alerts for explosion-report candidates. Discovery never auto-promotes strict matches.")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--local-only", action="store_true", help="Read completed alerts from a cached UkraineAlarm bridge instead of calling the API.")
    parser.add_argument("--bridge-file", default=str(BRIDGE_FILE), help="Bridge JSON used with --local-only.")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return

    started = now_utc()
    state = ensure_state()
    queue = load_json(QUEUE_FILE, [])
    if not isinstance(queue, list):
        queue = []

    if args.local_only:
        polled, errors = poll_cached_bridge(Path(args.bridge_file), started)
        mode = "cached_bridge"
    else:
        polled, errors = poll_alerts()
        mode = "network"
    new_episodes = process_events(state, polled, errors, started)
    telegram_errors = refresh_telegram_cache(state, started)
    errors.update({f"telegram:{key}": value for key, value in telegram_errors.items()})
    due = due_checks(state, started)
    searches = {}
    new_candidates = 0
    for city_key, city_due in sorted(due.items()):
        earliest = min(parse_dt(ep.get("alert_start")) or started for ep, _ in city_due)
        rows = telegram_candidates_for_city(state, city_key, earliest, started)
        telegram_count = len(rows)
        query_url = None
        google_error = None
        try:
            google_rows, query_url = search_city_news(city_key, earliest, started)
            rows.extend(google_rows)
        except Exception as exc:
            google_error = f"{type(exc).__name__}: {exc}"
            errors[f"search:{city_key}"] = google_error

        dedup = {(row["url"], row["title"]): row for row in rows}
        rows = list(dedup.values())
        added = add_candidates(queue, city_key, rows, city_due, started)
        new_candidates += added
        searches[city_key] = {
            "due_checks": len(city_due),
            "telegram_results": telegram_count,
            "results_after_filter": len(rows),
            "new_candidates": added,
            "query_url": query_url,
            "google_error": google_error,
        }
        for _, check in city_due:
            check["checked_at"] = iso(started)
            check["new_candidates"] = added

    queue.sort(key=lambda x: (x.get("first_discovered_at") or "", x.get("city_key") or ""), reverse=True)
    state["last_run_at"] = iso(started)
    state["followup_schedule_hours"] = [hours for _, hours in FOLLOWUP_HOURS]
    report = {
        "ok": not errors,
        "started_at": iso(started),
        "finished_at": iso(now_utc()),
        "city_count": len(CITY_CONFIG),
        "mode": mode,
        "new_alert_episodes": new_episodes,
        "cities_searched": sorted(searches),
        "searches": searches,
        "new_review_candidates": new_candidates,
        "review_queue_size": len(queue),
        "telegram": {
            key: {
                "last_seen_at": ((state.get("telegram") or {}).get(key) or {}).get("last_seen_at"),
                "cached_relevant_posts": len(((state.get("telegram") or {}).get(key) or {}).get("posts") or []),
                "last_error": ((state.get("telegram") or {}).get(key) or {}).get("last_error"),
            }
            for key in TELEGRAM_CHANNELS
        },
        "errors": errors,
        "strict_series_modified_by_discovery": False,
    }
    atomic_json(STATE_FILE, state)
    atomic_json(QUEUE_FILE, queue)
    atomic_json(LAST_RUN_FILE, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
