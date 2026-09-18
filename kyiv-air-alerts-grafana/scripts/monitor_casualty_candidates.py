#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

import add_sevastopol_exact as sev
import apply_ukrainealarm_bridge as ua
import update_data as kyivdata

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
CASUALTY_DIR = DATA_DIR / "casualties"
STATE_FILE = CASUALTY_DIR / "candidate_monitor_state.json"
QUEUE_FILE = CASUALTY_DIR / "multicity_review_queue.json"
LAST_RUN_FILE = CASUALTY_DIR / "candidate_monitor_last_run.json"
BRIDGE_FILE = DATA_DIR / "ukrainealarm_bridge.json"
KYIV_EVENTS_FILE = DATA_DIR / "alerts_combined.json"
SEVASTOPOL_EVENTS_FILE = DATA_DIR / "sevastopol_events.json"

UTC = timezone.utc
FOLLOWUP_HOURS = [
    ("immediate", 0),
    ("24h", 24),
    ("72h", 72),
    ("7d", 24 * 7),
]
MAX_EPISODES_PER_CITY = 250
GOOGLE_NEWS_URL = "https://news.google.com/rss/search"

CITY_CONFIG = {
    "kyiv": {"label": "Київ", "alert_key": "kyiv", "scope": "exact_city"},
    "kharkiv": {"label": "Харків", "alert_key": "kharkiv", "scope": "exact_city"},
    "sevastopol": {"label": "Севастополь", "alert_key": "sevastopol", "scope": "exact_city"},
    "cherkasy": {"label": "Черкаси", "alert_key": "cherkasy", "scope": "district_proxy"},
    "zhytomyr": {"label": "Житомир", "alert_key": "zhytomyr", "scope": "district_proxy"},
    "dnipro": {"label": "Дніпро", "alert_key": "dnipro", "scope": "district_proxy"},
    "khmelnytskyi": {"label": "Хмельницький", "alert_key": "khmelnytskyi", "scope": "district_proxy"},
    "poltava": {"label": "Полтава", "alert_key": "poltava", "scope": "district_proxy"},
    "rivne": {"label": "Рівне", "alert_key": "rivne", "scope": "district_proxy"},
    "sumy": {"label": "Суми", "alert_key": "sumy", "scope": "district_proxy"},
    "vinnytsia": {"label": "Вінниця", "alert_key": "vinnytsia", "scope": "district_proxy"},
    "kropyvnytskyi": {"label": "Кропивницький", "alert_key": "kropyvnytskyi", "scope": "district_proxy"},
    "lviv": {"label": "Львів", "alert_key": "lviv", "scope": "district_proxy"},
    "chernihiv": {"label": "Чернігів", "alert_key": "chernihiv", "scope": "district_proxy"},
    "mykolaiv": {"label": "Миколаїв", "alert_key": "mykolaiv", "scope": "district_proxy"},
    "lutsk": {"label": "Луцьк", "alert_key": "lutsk", "scope": "district_proxy"},
    "uzhhorod": {"label": "Ужгород", "alert_key": "uzhhorod", "scope": "district_proxy"},
    "ivano-frankivsk": {
        "label": "Івано-Франківськ",
        "alert_key": "ivano_frankivsk",
        "scope": "district_proxy",
    },
    "ternopil": {"label": "Тернопіль", "alert_key": "ternopil", "scope": "district_proxy"},
    "chernivtsi": {"label": "Чернівці", "alert_key": "chernivtsi", "scope": "district_proxy"},
    "odesa": {"label": "Одеса", "alert_key": "odesa", "scope": "district_proxy"},
    "zaporizhzhia": {"label": "Запоріжжя", "alert_key": "zaporizhzhia", "scope": "exact_city"},
    "kherson": {"label": "Херсон", "alert_key": "kherson", "scope": "district_proxy"},
}

CITY_NEWS_ALIASES = {
    "kyiv": ["київ", "києві", "києва", "києву", "києвом"],
    "kharkiv": ["харків", "харкові", "харкова", "харкову", "харковом"],
    "sevastopol": ["севастополь", "севастополі", "севастополя", "севастополю", "севастополем"],
    "cherkasy": ["черкаси", "черкасах", "черкасами"],
    "zhytomyr": ["житомир", "житомирі", "житомира", "житомиру", "житомиром"],
    "dnipro": ["дніпро", "дніпрі", "дніпра", "дніпру", "дніпром"],
    "khmelnytskyi": ["хмельницький", "хмельницькому", "хмельницького", "хмельницьким"],
    "poltava": ["полтава", "полтаві", "полтави", "полтаву", "полтавою"],
    "rivne": ["рівне", "рівному", "рівного", "рівним"],
    "sumy": ["суми", "сумах", "сумами"],
    "vinnytsia": ["вінниця", "вінниці", "вінницю", "вінницею"],
    "kropyvnytskyi": ["кропивницький", "кропивницькому", "кропивницького", "кропивницьким"],
    "lviv": ["львів", "львові", "львова", "львову", "львовом"],
    "chernihiv": ["чернігів", "чернігові", "чернігова", "чернігову", "черніговом"],
    "mykolaiv": ["миколаїв", "миколаєві", "миколаєва", "миколаєву", "миколаєвом"],
    "lutsk": ["луцьк", "луцьку", "луцька", "луцьком"],
    "uzhhorod": ["ужгород", "ужгороді", "ужгорода", "ужгороду", "ужгородом"],
    "ivano-frankivsk": [
        "івано-франківськ",
        "івано-франківську",
        "івано-франківська",
        "івано-франківськом",
    ],
    "ternopil": ["тернопіль", "тернополі", "тернополя", "тернополю", "тернополем"],
    "chernivtsi": ["чернівці", "чернівцях", "чернівців", "чернівцями"],
    "odesa": ["одеса", "одесі", "одеси", "одесу", "одесою"],
    "zaporizhzhia": ["запоріжжя", "запоріжжі", "запоріжжю"],
    "kherson": ["херсон", "херсоні", "херсона", "херсону", "херсоном"],
}

CASUALTY_TERMS = (
    "загиб",
    "загин",
    "помер",
    "померл",
    "смерт",
)
AERIAL_TERMS = (
    "дрон",
    "бпла",
    "безпілот",
    "шахед",
    "ракет",
    "каб",
    "авіа",
    "повітр",
    "удар",
    "атак",
    "вибух",
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
    raw = f"{city_key}|{start}|{end}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:24]


def candidate_id(city_key: str, url: str, title: str) -> str:
    raw = f"{city_key}|{url}|{title}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:24]


def make_episode(city_key: str, start: datetime, end: datetime, source: str) -> dict:
    start_s = iso(start)
    end_s = iso(end)
    return {
        "episode_id": event_id(city_key, start_s, end_s),
        "city_key": city_key,
        "city": CITY_CONFIG[city_key]["label"],
        "alert_scope": CITY_CONFIG[city_key]["scope"],
        "alert_source": source,
        "alert_start": start_s,
        "alert_end": end_s,
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


def normalize_events(rows: list[tuple[datetime, datetime]], city_key: str, source: str) -> list[dict]:
    out = {}
    for start, end in rows:
        start = start.astimezone(UTC)
        end = end.astimezone(UTC)
        if end <= start:
            continue
        ep = make_episode(city_key, start, end, source)
        out[ep["episode_id"]] = ep
    return sorted(out.values(), key=lambda x: x["alert_end"])


def local_bridge_events() -> dict[str, list[dict]]:
    bridge = load_json(BRIDGE_FILE, {})
    out: dict[str, list[dict]] = {key: [] for key in CITY_CONFIG}
    by_alert_key = {}
    for row in bridge.get("events", []):
        if not isinstance(row, dict):
            continue
        akey = str(row.get("city_key") or "")
        start = parse_dt(row.get("start"))
        end = parse_dt(row.get("end"))
        if akey and start and end:
            by_alert_key.setdefault(akey, []).append((start, end))

    for city_key, cfg in CITY_CONFIG.items():
        if city_key in {"kyiv", "sevastopol"}:
            continue
        out[city_key] = normalize_events(
            by_alert_key.get(cfg["alert_key"], []),
            city_key,
            "ukrainealarm_regionHistory_cached",
        )

    kyiv_rows = []
    for row in load_json(KYIV_EVENTS_FILE, []):
        if not isinstance(row, dict):
            continue
        start = parse_dt(row.get("start"))
        end = parse_dt(row.get("end"))
        if start and end:
            kyiv_rows.append((start, end))
    out["kyiv"] = normalize_events(kyiv_rows, "kyiv", "kyiv_exact_cached")

    sev_rows = []
    sev_store = load_json(SEVASTOPOL_EVENTS_FILE, {})
    for row in sev_store.get("pairs", []):
        if not isinstance(row, dict):
            continue
        start = parse_dt(row.get("start"))
        end = parse_dt(row.get("end"))
        if start and end:
            sev_rows.append((start, end))
    out["sevastopol"] = normalize_events(
        sev_rows,
        "sevastopol",
        "sevastopol_city_signal_cached",
    )
    return out


def poll_kyiv() -> list[dict]:
    session = kyivdata.http_session()
    official_response = session.get(kyivdata.OFFICIAL_JSON_URL, timeout=45)
    official_response.raise_for_status()
    official = kyivdata.parse_official(official_response.json())

    live_response = session.get(kyivdata.LIVE_HISTORY_URL, timeout=45)
    live_response.raise_for_status()
    live_alerts, live_events = kyivdata.parse_live_history(live_response.text)
    if not live_events:
        raise RuntimeError("Kyiv live source returned no parsable events")
    alerts, _ = kyivdata.merge_sources(official, live_alerts)
    rows = [(a.start.astimezone(UTC), a.end.astimezone(UTC)) for a in alerts]
    return normalize_events(rows, "kyiv", "kyiv_exact_sources")


def poll_sevastopol() -> list[dict]:
    store, _ = sev.update_event_store()
    rows = []
    for row in store.get("pairs", []):
        start = parse_dt(row.get("start"))
        end = parse_dt(row.get("end"))
        if start and end:
            rows.append((start, end))
    return normalize_events(rows, "sevastopol", "sevastopol_city_signal")


def poll_ukrainealarm() -> tuple[dict[str, list[dict]], dict[str, str]]:
    token = os.getenv(ua.TOKEN_ENV, "").strip()
    if not token:
        raise RuntimeError(f"{ua.TOKEN_ENV} is not configured")

    bridge = load_json(BRIDGE_FILE, {})
    regions = bridge.get("regions") or {}
    client = ua.UkraineAlarmClient(token)
    output: dict[str, list[dict]] = {}
    errors: dict[str, str] = {}

    api_cities = [
        key for key in CITY_CONFIG
        if key not in {"kyiv", "sevastopol"}
    ]
    for index, city_key in enumerate(api_cities, 1):
        cfg = CITY_CONFIG[city_key]
        region = regions.get(cfg["alert_key"]) or {}
        region_id = str(region.get("region_id") or "")
        api_name = str(region.get("api_region_name") or region.get("target") or cfg["label"])
        if not region_id:
            errors[city_key] = "missing_region_id"
            continue
        try:
            history = ua.history_rows(client, region_id, api_name)
            rows = [(row["start"], row["end"]) for row in history]
            output[city_key] = normalize_events(
                rows,
                city_key,
                "ukrainealarm_regionHistory",
            )
            print(
                f"[{index}/{len(api_cities)}] {city_key}: "
                f"{len(output[city_key])} completed alerts",
                flush=True,
            )
        except Exception as exc:
            errors[city_key] = f"{type(exc).__name__}: {exc}"
            print(
                f"[{index}/{len(api_cities)}] {city_key}: ERROR {errors[city_key]}",
                file=sys.stderr,
                flush=True,
            )
    return output, errors


def poll_all(local_only: bool) -> tuple[dict[str, list[dict]], dict[str, str]]:
    if local_only:
        return local_bridge_events(), {}

    out: dict[str, list[dict]] = {}
    errors: dict[str, str] = {}
    api_rows, api_errors = poll_ukrainealarm()
    out.update(api_rows)
    errors.update(api_errors)

    try:
        out["kyiv"] = poll_kyiv()
    except Exception as exc:
        errors["kyiv"] = f"{type(exc).__name__}: {exc}"

    try:
        out["sevastopol"] = poll_sevastopol()
    except Exception as exc:
        errors["sevastopol"] = f"{type(exc).__name__}: {exc}"

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
    for alias in CITY_NEWS_ALIASES.get(city_key, []):
        pattern = rf"(?<![\\w-]){re.escape(alias)}(?![\\w-])"
        if re.search(pattern, low, flags=re.IGNORECASE):
            return True
    return False


def relevant_news(text: str) -> bool:
    low = " ".join((text or "").casefold().split())
    return (
        any(term in low for term in CASUALTY_TERMS)
        and any(term in low for term in AERIAL_TERMS)
    )


def google_news_query(city_label: str) -> str:
    return (
        f'"{city_label}" '
        "(загинув OR загиблі OR загинули OR помер OR померла) "
        "(дрон OR БПЛА OR шахед OR ракета OR КАБ OR авіаудар OR повітряна атака) "
        "when:8d"
    )


def search_city_news(city_key: str, earliest: datetime, now: datetime) -> tuple[list[dict], str]:
    label = CITY_CONFIG[city_key]["label"]
    query = google_news_query(label)
    url = (
        f"{GOOGLE_NEWS_URL}?q={quote_plus(query)}"
        "&hl=uk&gl=UA&ceid=UA:uk"
    )
    response = requests.get(
        url,
        headers={
            "User-Agent": "ukraine-air-alerts-casualty-monitor/1.0",
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
        if not relevant_news(combined):
            continue

        rows.append(
            {
                "title": title,
                "url": link,
                "publisher": publisher or "Google News result",
                "publisher_url": publisher_url or None,
                "published_at": iso(published) if published else None,
                "snippet": description[:1200],
            }
        )

    dedup = {}
    for row in rows:
        key = (row["url"], row["title"])
        dedup[key] = row
    return list(dedup.values()), url


def ensure_state() -> dict:
    state = load_json(STATE_FILE, {})
    if not isinstance(state, dict) or state.get("schema_version") != 1:
        state = {
            "schema_version": 1,
            "created_at": iso(now_utc()),
            "cities": {},
        }
    state.setdefault("cities", {})
    return state


def due_checks(state: dict, now: datetime) -> dict[str, list[tuple[dict, dict]]]:
    out: dict[str, list[tuple[dict, dict]]] = {}
    for city_key, cstate in state.get("cities", {}).items():
        for episode in cstate.get("episodes", []):
            for check in episode.get("checks", []):
                if check.get("checked_at"):
                    continue
                due = parse_dt(check.get("due_at"))
                if due and due <= now:
                    out.setdefault(city_key, []).append((episode, check))
    return out


def add_news_candidates(
    queue: list[dict],
    city_key: str,
    rows: list[dict],
    due: list[tuple[dict, dict]],
    now: datetime,
) -> int:
    by_id = {
        str(item.get("candidate_id")): item
        for item in queue
        if isinstance(item, dict) and item.get("candidate_id")
    }
    episode_ids = sorted({episode["episode_id"] for episode, _ in due})
    check_labels = sorted({check["label"] for _, check in due})
    added = 0

    for row in rows:
        cid = candidate_id(city_key, row["url"], row["title"])
        existing = by_id.get(cid)
        if existing:
            existing_ids = set(existing.get("trigger_episode_ids") or [])
            existing["trigger_episode_ids"] = sorted(existing_ids | set(episode_ids))
            existing_checks = set(existing.get("trigger_check_labels") or [])
            existing["trigger_check_labels"] = sorted(existing_checks | set(check_labels))
            existing["last_seen_at"] = iso(now)
            continue

        item = {
            "candidate_id": cid,
            "city_key": city_key,
            "city": CITY_CONFIG[city_key]["label"],
            "alert_trigger_scope": CITY_CONFIG[city_key]["scope"],
            "status": "needs_review",
            "source": "Google News RSS",
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
            "note": (
                "Automatically discovered after a completed alert episode. "
                "Do not add to confirmed deaths without manual validation of "
                "city geography, aerial-attack causality, deduplication, and attack date."
            ),
        }
        queue.append(item)
        by_id[cid] = item
        added += 1
    return added


def process_events(
    state: dict,
    polled: dict[str, list[dict]],
    errors: dict[str, str],
    now: datetime,
) -> tuple[int, list[str]]:
    new_count = 0
    bootstrapped = []

    for city_key in CITY_CONFIG:
        rows = polled.get(city_key)
        cstate = state["cities"].setdefault(
            city_key,
            {
                "city": CITY_CONFIG[city_key]["label"],
                "alert_scope": CITY_CONFIG[city_key]["scope"],
                "last_seen_alert_end": None,
                "episodes": [],
            },
        )
        cstate["last_poll_at"] = iso(now)
        cstate["last_poll_error"] = errors.get(city_key)

        if not rows:
            continue
        rows = sorted(rows, key=lambda x: x["alert_end"])
        latest_end = parse_dt(rows[-1]["alert_end"])
        if latest_end is None:
            continue

        last_seen = parse_dt(cstate.get("last_seen_alert_end"))
        if last_seen is None:
            cstate["last_seen_alert_end"] = rows[-1]["alert_end"]
            cstate["last_seen_alert_start"] = rows[-1]["alert_start"]
            cstate["bootstrapped_at"] = iso(now)
            cstate["bootstrap_latest_episode_id"] = rows[-1]["episode_id"]
            bootstrapped.append(city_key)
            continue

        known_ids = {
            str(ep.get("episode_id"))
            for ep in cstate.get("episodes", [])
            if ep.get("episode_id")
        }
        for episode in rows:
            end = parse_dt(episode.get("alert_end"))
            if end is None or end <= last_seen:
                continue
            if episode["episode_id"] in known_ids:
                continue
            cstate.setdefault("episodes", []).append(episode)
            known_ids.add(episode["episode_id"])
            new_count += 1

        if latest_end > last_seen:
            cstate["last_seen_alert_end"] = rows[-1]["alert_end"]
            cstate["last_seen_alert_start"] = rows[-1]["alert_start"]

        episodes = sorted(
            cstate.get("episodes", []),
            key=lambda x: x.get("alert_end") or "",
        )
        cstate["episodes"] = episodes[-MAX_EPISODES_PER_CITY:]

    return new_count, bootstrapped


def self_test() -> None:
    assert len(CITY_CONFIG) == 23
    assert CITY_CONFIG["ivano-frankivsk"]["alert_key"] == "ivano_frankivsk"
    dt = parse_dt("2026-09-18T10:00:00Z")
    assert dt and iso(dt) == "2026-09-18T10:00:00Z"
    ep = make_episode("kyiv", dt, dt + timedelta(hours=1), "test")
    assert [x["label"] for x in ep["checks"]] == ["immediate", "24h", "72h", "7d"]
    assert parse_dt(ep["checks"][-1]["due_at"]) == dt + timedelta(hours=169)
    assert relevant_news("У Києві загинула людина після атаки дрона")
    assert not relevant_news("У Києві оголосили повітряну тривогу")
    assert city_mentioned("zhytomyr", "У Житомирі внаслідок удару загинули двоє")
    assert not city_mentioned("zhytomyr", "На Житомирщині внаслідок удару загинули двоє")
    assert city_mentioned("odesa", "В Одесі після атаки загинула людина")
    print("Self-test OK: 23 cities, follow-up schedule, relevance filter")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Gate casualty-source searches behind newly completed city alert episodes. "
            "Candidates are queued for manual review; confirmed casualty data is never changed."
        )
    )
    parser.add_argument(
        "--local-only",
        action="store_true",
        help="Use cached alert stores only. Intended for safe bootstrap/testing.",
    )
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return

    started = now_utc()
    state = ensure_state()
    queue = load_json(QUEUE_FILE, [])
    if not isinstance(queue, list):
        queue = []

    # Automatically generated, still-unreviewed items that do not actually
    # mention the target city are safe to prune. Human-reviewed statuses are
    # never removed automatically.
    before_prune = len(queue)
    queue = [
        item for item in queue
        if not (
            isinstance(item, dict)
            and item.get("source") == "Google News RSS"
            and item.get("status") == "needs_review"
            and item.get("city_key") in CITY_CONFIG
            and not city_mentioned(
                str(item.get("city_key")),
                f"{item.get('title') or ''} {item.get('snippet') or ''}",
            )
        )
    ]
    pruned_candidates = before_prune - len(queue)

    polled, errors = poll_all(args.local_only)
    new_episodes, bootstrapped = process_events(state, polled, errors, started)

    searches = {}
    new_candidates = 0
    due = due_checks(state, started)
    for city_key, city_due in sorted(due.items()):
        earliest = min(
            parse_dt(ep["alert_start"]) or started
            for ep, _ in city_due
        )
        try:
            rows, query_url = search_city_news(city_key, earliest, started)
            added = add_news_candidates(queue, city_key, rows, city_due, started)
            new_candidates += added
            searches[city_key] = {
                "due_checks": len(city_due),
                "results_after_filter": len(rows),
                "new_candidates": added,
                "query_url": query_url,
            }
            for _, check in city_due:
                check["checked_at"] = iso(started)
                check["new_candidates"] = added
        except Exception as exc:
            message = f"{type(exc).__name__}: {exc}"
            errors[f"search:{city_key}"] = message
            searches[city_key] = {
                "due_checks": len(city_due),
                "error": message,
            }

    queue.sort(
        key=lambda item: (
            item.get("first_discovered_at") or "",
            item.get("city_key") or "",
        ),
        reverse=True,
    )
    state["last_run_at"] = iso(started)
    state["last_run_mode"] = "local_only" if args.local_only else "network"
    state["followup_schedule_hours"] = [hours for _, hours in FOLLOWUP_HOURS]

    report = {
        "ok": not errors,
        "started_at": iso(started),
        "finished_at": iso(now_utc()),
        "mode": state["last_run_mode"],
        "city_count": len(CITY_CONFIG),
        "polled_city_count": len([k for k, v in polled.items() if v]),
        "bootstrapped_cities": bootstrapped,
        "new_alert_episodes": new_episodes,
        "cities_searched": sorted(searches),
        "searches": searches,
        "new_review_candidates": new_candidates,
        "pruned_geo_false_positives": pruned_candidates,
        "review_queue_size": len(queue),
        "errors": errors,
        "confirmed_series_modified": False,
    }

    atomic_json(STATE_FILE, state)
    atomic_json(QUEUE_FILE, queue)
    atomic_json(LAST_RUN_FILE, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
