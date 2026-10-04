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
from urllib.parse import quote_plus, urlparse
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

import apply_ukrainealarm_bridge as ua

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
BASELINE_FILE = DATA_DIR / "explosion_audited_baseline.json"
BRIDGE_FILE = DATA_DIR / "ukrainealarm_bridge.json"
KYIV_ALERTS_FILE = DATA_DIR / "alerts_combined.json"
SEVASTOPOL_EVENTS_FILE = DATA_DIR / "sevastopol_events.json"
SPECIAL_ALERT_SOURCES = {"kyiv", "sevastopol"}
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
FULLTEXT_FETCH_TIMEOUT_SECONDS = 15
MAX_FULLTEXT_FETCHES_PER_CITY = 8
MAX_EXTRACTED_ARTICLE_CHARS = 50000
FULLTEXT_STRIP_TAGS = ("script", "style", "nav", "header", "footer", "aside", "form", "svg", "noscript")
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

ALL_CITY_CONFIG = {
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
    "zhytomyr": {"label": "Житомир", "aliases": ["житомир", "житомирі", "житомира", "житомиру", "житомиром"]},
    "kropyvnytskyi": {"label": "Кропивницький", "aliases": ["кропивницький", "кропивницькому", "кропивницького", "кропивницьким"]},
    "kherson": {"label": "Херсон", "aliases": ["херсон", "херсоні", "херсона", "херсону", "херсоном"]},
    "odesa": {"label": "Одеса", "aliases": ["одеса", "одесі", "одеси", "одесу", "одесою"]},
    "cherkasy": {"label": "Черкаси", "aliases": ["черкаси", "черкасах", "черкасами"]},
    "mykolaiv": {"label": "Миколаїв", "aliases": ["миколаїв", "миколаєві", "миколаєва", "миколаєву", "миколаєвом"]},
    "chernihiv": {"label": "Чернігів", "aliases": ["чернігів", "чернігові", "чернігова", "чернігову", "черніговом"]},
    "dnipro": {"label": "Дніпро", "aliases": ["дніпро", "дніпрі", "дніпра", "дніпру", "дніпром"]},
    "sumy": {"label": "Суми", "aliases": ["суми", "сумах", "сумами"]},
    "zaporizhzhia": {"label": "Запоріжжя", "aliases": ["запоріжжя", "запоріжжі", "запоріжжю"]},
    "kharkiv": {"label": "Харків", "aliases": ["харків", "харкові", "харкова", "харкову", "харковом"]},
    "kyiv": {"label": "Київ", "aliases": ["київ", "києві", "києва", "києву", "києвом"]},
    "sevastopol": {"label": "Севастополь", "aliases": ["севастополь", "севастополі", "севастополя", "севастополю", "севастополем"]},
}

_BASELINE_AT_IMPORT = json.loads(BASELINE_FILE.read_text(encoding="utf-8"))
_BASELINE_CITIES_AT_IMPORT = _BASELINE_AT_IMPORT.get("cities") or {}
if not _BASELINE_CITIES_AT_IMPORT:
    raise RuntimeError("Explosion audited baseline has no cities")

CITY_CONFIG = {}
for _key, _row in _BASELINE_CITIES_AT_IMPORT.items():
    _known = ALL_CITY_CONFIG.get(_key) or {}
    _label = str(_row.get("label") or _known.get("label") or _key)
    _aliases = list(_known.get("aliases") or [_label.casefold()])
    CITY_CONFIG[_key] = {"label": _label, "aliases": _aliases}


DISCOVERY_TERMS = (
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
    "удар",
    "влуч",
    "приліт",
    "пошкод",
    "пожеж",
    "загор",
    "займан",
)
# Backward-compatible alias for discovery/excerpt helpers. This is deliberately
# broader than strict explosion evidence.
EXPLOSION_TERMS = DISCOVERY_TERMS
AIR_CONTEXT_TERMS = (
    "повітрян",
    "тривог",
    "бпла",
    "безпілот",
    "дрон",
    "shahed",
    "шахед",
    "ракет",
    "каб",
    "авіабомб",
    "авіаційн",
    "баліст",
    "крилат",
    "іскандер",
    "бандерол",
    "молні",
    "fpv",
    "ппо",
    "повітряні сили",
    "швидкісн",
)
AUTO_MATCH_END_GRACE_MINUTES = 30
MATCH_REPRESENTATION_TOLERANCE_SECONDS = 90.0
# Historical sensitivity cases include explicit event times roughly 1-7 minutes
# outside a frozen alert boundary. Keep a conservative 10-minute ceiling, and
# use it only for sensitivity when the source states the event clock.
SENSITIVITY_NEAR_BOUNDARY_MAX_MINUTES = 10
COMPOSITION_MAX_GAP_MINUTES = 45
COMPOSITION_TIGHT_TRUSTED_GAP_MINUTES = 15
REVIEW_PROVENANCE_SCHEMA_VERSION = 1
REVIEW_PROVENANCE_METHODOLOGY_VERSION = "explosion-monitor-reviewed-provenance-v1"
PROVENANCE_HARDENING_ARTIFACT = (
    ROOT.parent / "research" / "explosion_monitor_provenance_persistence_hardening_dry_replay_2026-09-24.json"
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


def make_episode(city_key: str, start: datetime, end: datetime, source: str = "ukrainealarm_regionHistory") -> dict:
    start_s, end_s = iso(start), iso(end)
    return {
        "episode_id": event_id(city_key, start_s, end_s),
        "city_key": city_key,
        "city": CITY_CONFIG[city_key]["label"],
        "alert_source": source,
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


def load_kyiv_alert_episodes(path: Path) -> list[dict]:
    rows = load_json(path, [])
    if not isinstance(rows, list):
        raise RuntimeError(f"Kyiv alert store is not a list: {path}")
    episodes = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        start = parse_dt(row.get("start"))
        end = parse_dt(row.get("end"))
        if not start or not end or end <= start:
            continue
        ep = make_episode("kyiv", start, end, source="kyiv_combined_exact_city")
        episodes[ep["episode_id"]] = ep
    if not episodes:
        raise RuntimeError(f"Kyiv alert store produced no complete episodes: {path}")
    return sorted(episodes.values(), key=lambda x: x["alert_end"])


def load_sevastopol_alert_episodes(path: Path) -> list[dict]:
    store = load_json(path, {})
    pairs = store.get("pairs") if isinstance(store, dict) else None
    if not isinstance(pairs, list):
        raise RuntimeError(f"Sevastopol event store has no pairs: {path}")
    episodes = {}
    for row in pairs:
        if not isinstance(row, dict):
            continue
        start = parse_dt(row.get("start"))
        end = parse_dt(row.get("end"))
        if not start or not end or end <= start:
            continue
        ep = make_episode("sevastopol", start, end, source="sevastopol_verified_exact_city_pairs")
        episodes[ep["episode_id"]] = ep
    if not episodes:
        raise RuntimeError(f"Sevastopol event store produced no complete episodes: {path}")
    return sorted(episodes.values(), key=lambda x: x["alert_end"])


def special_source_alerts(
    kyiv_alerts_path: Path,
    sevastopol_events_path: Path,
) -> tuple[dict[str, list[dict]], dict[str, str]]:
    out: dict[str, list[dict]] = {}
    errors: dict[str, str] = {}
    if "kyiv" in CITY_CONFIG:
        try:
            out["kyiv"] = load_kyiv_alert_episodes(kyiv_alerts_path)
        except Exception as exc:
            errors["kyiv"] = f"{type(exc).__name__}: {exc}"
    if "sevastopol" in CITY_CONFIG:
        try:
            out["sevastopol"] = load_sevastopol_alert_episodes(sevastopol_events_path)
        except Exception as exc:
            errors["sevastopol"] = f"{type(exc).__name__}: {exc}"
    return out, errors


def poll_cached_bridge(
    bridge_path: Path,
    now: datetime,
    kyiv_alerts_path: Path = KYIV_ALERTS_FILE,
    sevastopol_events_path: Path = SEVASTOPOL_EVENTS_FILE,
) -> tuple[dict[str, list[dict]], dict[str, str]]:
    bridge = load_json(bridge_path, {})
    rows_by_city: dict[str, list[dict]] = {key: [] for key in CITY_CONFIG}
    errors: dict[str, str] = {}
    for row in bridge.get("events", []):
        if not isinstance(row, dict):
            continue
        city_key = str(row.get("city_key") or "")
        if city_key not in CITY_CONFIG or city_key in SPECIAL_ALERT_SOURCES:
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
        if city_key in SPECIAL_ALERT_SOURCES:
            continue
        region = regions.get(city_key) or {}
        checked = parse_dt(region.get("last_checked_at"))
        if not checked:
            errors[city_key] = "cached_bridge_missing_last_checked_at"
        elif now - checked > timedelta(hours=12):
            errors[city_key] = f"cached_bridge_stale:{iso(checked)}"
        dedup = {ep["episode_id"]: ep for ep in rows_by_city[city_key]}
        rows_by_city[city_key] = sorted(dedup.values(), key=lambda x: x["alert_end"])

    special, special_errors = special_source_alerts(kyiv_alerts_path, sevastopol_events_path)
    rows_by_city.update(special)
    errors.update(special_errors)
    return rows_by_city, errors


def poll_alerts(
    kyiv_alerts_path: Path = KYIV_ALERTS_FILE,
    sevastopol_events_path: Path = SEVASTOPOL_EVENTS_FILE,
) -> tuple[dict[str, list[dict]], dict[str, str]]:
    token = os.getenv(ua.TOKEN_ENV, "").strip()
    if not token:
        raise RuntimeError(f"{ua.TOKEN_ENV} is not configured")
    bridge = load_json(BRIDGE_FILE, {})
    regions = bridge.get("regions") or {}
    client = ua.UkraineAlarmClient(token)
    out: dict[str, list[dict]] = {}
    errors: dict[str, str] = {}

    normal_keys = [key for key in CITY_CONFIG if key not in SPECIAL_ALERT_SOURCES]
    for idx, city_key in enumerate(normal_keys, 1):
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
            print(f"[{idx}/{len(normal_keys)}] {city_key}: {len(out[city_key])} completed alerts", flush=True)
        except Exception as exc:
            errors[city_key] = f"{type(exc).__name__}: {exc}"
            print(f"[{idx}/{len(normal_keys)}] {city_key}: ERROR {errors[city_key]}", file=sys.stderr, flush=True)

    special, special_errors = special_source_alerts(kyiv_alerts_path, sevastopol_events_path)
    out.update(special)
    errors.update(special_errors)
    for key in sorted(special):
        print(f"[special] {key}: {len(special[key])} completed alerts", flush=True)
    for key, message in sorted(special_errors.items()):
        print(f"[special] {key}: ERROR {message}", file=sys.stderr, flush=True)
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


def matched_text_excerpt(text: str, max_chars: int = 480) -> str | None:
    normalized = " ".join((text or "").split())
    if not normalized:
        return None
    low = normalized.casefold()
    hits = [low.find(term) for term in EXPLOSION_TERMS if low.find(term) >= 0]
    if not hits:
        return normalized[:max_chars]
    pos = min(hits)
    start = max(0, pos - max_chars // 3)
    end = min(len(normalized), start + max_chars)
    if end == len(normalized):
        start = max(0, end - max_chars)
    fragment = normalized[start:end]
    return ("…" if start else "") + fragment + ("…" if end < len(normalized) else "")


def extract_article_text(raw_html: str, max_chars: int = MAX_EXTRACTED_ARTICLE_CHARS) -> str:
    soup = BeautifulSoup(raw_html or "", "html.parser")
    for tag in soup.find_all(FULLTEXT_STRIP_TAGS):
        tag.decompose()

    container = soup.find("article") or soup.find("main")
    if container is not None:
        text = container.get_text(" ", strip=True)
    else:
        text = " ".join(p.get_text(" ", strip=True) for p in soup.find_all("p"))
    return " ".join(text.split())[:max_chars]


def fetch_publisher_fulltext(url: str) -> tuple[str | None, str | None]:
    try:
        response = requests.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; ukraine-air-alerts-explosion-monitor/1.0)",
                "Accept-Language": "uk,en;q=0.7",
            },
            timeout=FULLTEXT_FETCH_TIMEOUT_SECONDS,
            allow_redirects=True,
        )
        response.raise_for_status()
        content_type = str(response.headers.get("Content-Type") or "").casefold()
        if "html" not in content_type:
            return None, None
        resolved_url = str(response.url or url)
        resolved_host = (urlparse(resolved_url).hostname or "").casefold()
        if resolved_host == "google.com" or resolved_host.endswith(".google.com"):
            return None, None
        body = extract_article_text(response.text)
        if not body:
            return None, None
        return body, resolved_url
    except Exception:
        return None, None


def build_google_news_candidate(
    city_key: str,
    title: str,
    description: str,
    link: str,
    publisher: str,
    publisher_url: str,
    published_at: str | None,
    fulltext_fetcher=None,
) -> tuple[dict | None, bool, bool]:
    combined = f"{title} {description}".strip()
    base = {
        "title": title,
        "url": link,
        "publisher": publisher or "Google News result",
        "publisher_url": publisher_url or None,
        "published_at": published_at,
        "snippet": description[:1200],
    }

    if city_mentioned(city_key, combined) and explosion_relevant(combined):
        return {
            **base,
            "discovery_basis": "rss_title_snippet",
            "resolved_url": None,
            "matched_text_excerpt": matched_text_excerpt(combined),
        }, False, False

    if fulltext_fetcher is None:
        return None, False, False

    try:
        body, resolved_url = fulltext_fetcher(link)
    except Exception:
        return None, True, False
    if not body:
        return None, True, False

    expanded = f"{combined} {body}".strip()
    if not city_mentioned(city_key, expanded) or not explosion_relevant(expanded):
        return None, True, False

    return {
        **base,
        "discovery_basis": "publisher_fulltext",
        "resolved_url": resolved_url,
        "matched_text_excerpt": matched_text_excerpt(expanded),
    }, True, True


def normalize_evidence_text(value: str | None) -> str:
    return " ".join((value or "").casefold().replace("’", "'").split())


def strip_publisher_branding(value: str | None, publisher: str | None) -> str:
    text = " ".join((value or "").split()).strip()
    brand = " ".join((publisher or "").split()).strip()
    if not text or not brand:
        return text
    return re.sub(
        rf"\s*(?:[-–—|]\s*)?{re.escape(brand)}\s*$",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()


def classification_text(row: dict) -> str:
    publisher = str(row.get("publisher") or "")
    parts = [
        strip_publisher_branding(row.get("title"), publisher),
        strip_publisher_branding(row.get("snippet"), publisher),
    ]
    if row.get("discovery_basis") == "publisher_fulltext" and row.get("matched_text_excerpt"):
        excerpt = str(row.get("matched_text_excerpt") or "")
        if publisher:
            excerpt = re.sub(re.escape(publisher), " ", excerpt, flags=re.IGNORECASE)
        parts.append(" ".join(excerpt.split()))
    return " ".join(part for part in parts if part).strip()


def classification_segments(row: dict) -> list[str]:
    text = classification_text(row)
    if not text:
        return []
    return [
        " ".join(part.split())
        for part in re.split(r"(?<=[.!?;])\s+|\n+", text)
        if part and part.strip()
    ]



def controlled_blast_signal(text: str) -> bool:
    low = normalize_evidence_text(text)
    return bool(
        re.search(
            r"(?:кар'єр\w*|вибухов\w*\s+робот\w*|планов\w*.{0,20}вибух\w*|підривн\w*\s+робот\w*)",
            low,
        )
    )


def military_strike_event_signal(text: str) -> bool:
    """
    Evidence that the event segment itself describes a military strike.

    Generic alert/PPO/aerial-threat wording is intentionally excluded: it may
    occur elsewhere in the same article and must not turn a clearly planned
    quarry/blasting event into a military explosion.
    """
    low = normalize_evidence_text(text)
    if not low:
        return False
    if re.search(r"\b(?:влуч\w*|поціл\w*|приліт\w*|вдарил\w*|атакув\w*)", low):
        return True
    if re.search(r"\b(?:завдал\w*|нанес\w*)\b.{0,50}\bудар\w*", low):
        return True
    if re.search(
        r"\b(?:ракет\w*|дрон\w*|бпла|безпілот\w*|шахед\w*|shahed\w*|каб\w*|авіабомб\w*)"
        r".{0,60}\b(?:удар\w*|влуч\w*|атак\w*|вибух\w*)",
        low,
    ):
        return True
    return False


def controlled_blast_nonmilitary_signal(text: str) -> bool:
    return controlled_blast_signal(text) and not military_strike_event_signal(text)


AIR_DEFENSE_CONTEXT_RE = re.compile(r"\b(?:ппо|пво|протиповітр\w*|противовоздуш\w*)", re.IGNORECASE)
AIR_DEFENSE_ACTUAL_RE = re.compile(
    r"(?:"
    r"(?:\bппо\b|\bпво\b|протиповітр\w*|противовоздуш\w*).{0,35}"
    r"(?:працю(?:є|ють|вала|вали)|відпрацю\w*|работа(?:ет|ют|ла|ли)|отработа\w*)|"
    r"(?:працю(?:є|ють|вала|вали)|відпрацю\w*|работа(?:ет|ют|ла|ли)|отработа\w*).{0,35}"
    r"(?:\bппо\b|\bпво\b|протиповітр\w*|противовоздуш\w*)|"
    r"(?:чути|чутно|було\s+чутно|слышно).{0,40}(?:робот\w*|работ\w*).{0,35}"
    r"(?:\bппо\b|\bпво\b|протиповітр\w*|противовоздуш\w*)|"
    r"(?:робот\w*|работ\w*).{0,35}(?:\bппо\b|\bпво\b|протиповітр\w*|противовоздуш\w*)"
    r")",
    re.IGNORECASE,
)
AIR_DEFENSE_PREDICTIVE_RE = re.compile(
    r"(?:можлив\w*|може|можуть|можливо|может|могут|возможн\w*|"
    r"готов\w*|напоготові|очіку\w*|ожида\w*|ймовірн\w*|вероятн\w*)"
    r".{0,60}(?:ппо|пво|протиповітр\w*|противовоздуш\w*|робот\w*|работ\w*|чути|чутно|слышно)|"
    r"(?:ппо|пво|протиповітр\w*|противовоздуш\w*).{0,60}"
    r"(?:можлив\w*|може|можуть|можливо|может|могут|возможн\w*|готов\w*|напоготові|очіку\w*|ожида\w*)",
    re.IGNORECASE,
)
INTERCEPTION_CLAIM_RE = re.compile(
    r"(?:збит\w*|збил\w*|знищен\w*|знешкоджен\w*|перехоп\w*|"
    r"сбит\w*|сбил\w*|уничтожен\w*|перехвачен\w*)",
    re.IGNORECASE,
)

def air_defense_context_signal(text: str) -> bool:
    low = normalize_evidence_text(text)
    return bool(low and AIR_DEFENSE_CONTEXT_RE.search(low))


def interception_claim_signal(text: str) -> bool:
    low = normalize_evidence_text(text)
    return bool(low and INTERCEPTION_CLAIM_RE.search(low))


def air_defense_action_signal(text: str) -> bool:
    """Confirmed actual air-defense activity, excluding warning/readiness language."""
    low = normalize_evidence_text(text)
    if not low or not AIR_DEFENSE_CONTEXT_RE.search(low):
        return False
    if AIR_DEFENSE_PREDICTIVE_RE.search(low):
        return False
    if AIR_DEFENSE_ACTUAL_RE.search(low):
        return True
    # An explicit interception by named/mentioned air defense is itself evidence
    # that air defense actually operated; interception remains a separate flag.
    return interception_claim_signal(low)


ATTACK_EVENT_TYPE_ORDER = ("explosion", "impact", "arrival", "strike", "damage", "fire", "air_defense_action")


def attack_event_types(text: str) -> list[str]:
    """Detect event types mentioned in text without deciding episode eligibility."""
    low = normalize_evidence_text(text)
    if not low:
        return []
    found = set()
    if re.search(r"\bвибух\w*", low):
        found.add("explosion")
    if re.search(r"\b(?:влуч\w*|поціл\w*)", low):
        found.add("impact")
    if re.search(r"\bприліт\w*", low):
        found.add("arrival")
    if re.search(r"\bвдарил\w*", low) or re.search(r"\b(?:завдал\w*|нанес\w*)\b.{0,50}\bудар\w*", low):
        found.add("strike")
    if re.search(r"\bудар(?:у|и|ів|ом|ами)?\b", low):
        threat_only = bool(re.search(r"\bзагроз\w*.{0,30}\bудар(?:у|и|ів|ом|ами)?\b", low))
        if not threat_only:
            found.add("strike")
    if re.search(r"\bпошкод\w*", low):
        found.add("damage")
    if re.search(r"\b(?:пожеж\w*|загор\w*|займан\w*)", low):
        found.add("fire")
    if air_defense_action_signal(low):
        found.add("air_defense_action")
    return [event_type for event_type in ATTACK_EVENT_TYPE_ORDER if event_type in found]


def attack_consequence_signal(text: str) -> bool:
    """Require damage/fire to be explicitly linked to an attack, not merely co-present with an alert."""
    low = normalize_evidence_text(text)
    if not low or not re.search(r"\b(?:пошкод\w*|пожеж\w*|загор\w*|займан\w*)", low):
        return False
    attack = r"(?:атак\w*|обстріл\w*|удар\w*|влуч\w*|приліт\w*|вибух\w*|бпла|безпілот\w*|дрон\w*|шахед\w*|shahed\w*|ракет\w*|каб\w*|авіабомб\w*)"
    consequence = r"(?:пошкод\w*|пожеж\w*|загор\w*|займан\w*)"
    return bool(
        re.search(rf"\b{attack}\b.{{0,120}}\b{consequence}\b", low)
        or re.search(rf"\b{consequence}\b.{{0,120}}\b(?:внаслідок|через)\b.{{0,80}}\b{attack}\b", low)
    )


def strict_attack_event_signal(text: str) -> bool:
    low = normalize_evidence_text(text)
    if not low or controlled_blast_nonmilitary_signal(low):
        return False
    event_types = attack_event_types(low)
    if any(event_type in event_types for event_type in ("explosion", "impact", "arrival", "strike")):
        return True
    if "air_defense_action" in event_types:
        return True
    if any(event_type in event_types for event_type in ("damage", "fire")):
        return attack_consequence_signal(low)
    return False


def strict_explosion_signal(text: str) -> bool:
    # Backward-compatible interface: the historical name now delegates to the
    # unified attack-event signal while existing city/air/temporal gates remain.
    return strict_attack_event_signal(text)

def air_military_context(text: str) -> bool:
    low = normalize_evidence_text(text)
    return any(term in low for term in AIR_CONTEXT_TERMS)


def air_context(text: str) -> bool:
    return air_military_context(text)


def explicit_alert_relation(text: str) -> bool:
    low = normalize_evidence_text(text)
    patterns = (
        r"\bпід\s+час\s+(?:повітрян\w*\s+)?тривог\w*",
        r"\bу\s+період\s+(?:повітрян\w*\s+)?тривог\w*",
        r"\bна\s+тлі\s+(?:активн\w*\s+)?повітрян\w*\s+тривог\w*",
        r"\bколи\s+(?:ще\s+)?тривал\w*\s+(?:повітрян\w*\s+)?тривог\w*",
        r"\bпоки\s+тривал\w*\s+(?:повітрян\w*\s+)?тривог\w*",
        r"\bтривог\w*\s+(?:ще\s+)?тривал\w*",
        r"\bпісля\s+(?:початку|оголошення)\s+(?:повітрян\w*\s+)?тривог\w*",
    )
    return any(re.search(pattern, low) for pattern in patterns)


def explicit_during_alert(text: str) -> bool:
    return explicit_alert_relation(text)


def retrospective_or_cumulative_wording(text: str) -> bool:
    low = normalize_evidence_text(text)
    patterns = (
        r"\bбуло[\s,:;–—-]+(?:чути|чутно)\b",
        r"\bраніше.{0,30}\b(?:чути|чутно|чули)\b",
        r"\bпротягом[\s,:;–—-]+(?:цього[\s,:;–—-]+)?дня\b",
        r"\bвдень\b",
        r"\bцілий[\s,:;–—-]+день\b",
        r"\bза[\s,:;–—-]+(?:минулий[\s,:;–—-]+)?(?:день|добу)\b",
        r"\bдобов\w*[\s,:;–—-]+(?:зведен|підсум)\w*",
        r"\bнаслідк\w*.{0,40}\b(?:нічн|ранков|денн|вечірн)\w*.{0,40}\bатак\w*",
        r"\bпісля[\s,:;–—-]+(?:нічн|ранков|денн|вечірн)\w*[\s,:;–—-]+атак\w*.{0,60}\b(?:пошкод\w*|пожеж\w*|загор\w*|займан\w*)",
    )
    return any(re.search(pattern, low) for pattern in patterns)


def trusted_live_publication_binding_extension_wording(text: str) -> bool:
    """Narrow live forms added for publication-time temporal binding."""
    low = normalize_evidence_text(text)
    if retrospective_or_cumulative_wording(low):
        return False
    return bool(
        re.search(
            r"(?:\bпрацю(?:є|ють)\s+(?:сили\s+)?ппо\b|"
            r"\bвибух\w*\s+(?:у|в)\s+[\w'’.-]+\s*,\s*повідомляють\b)",
            low,
        )
    )


def contemporaneous_live_wording(text: str) -> bool:
    low = normalize_evidence_text(text)
    if retrospective_or_cumulative_wording(low):
        return False
    sep = r"[\s,:;–—-]+"
    return bool(
        re.search(
            rf"(?:\bлуна(?:є|ють){sep}(?:повторн\w*{sep})?(?:сері\w*{sep})?вибух\w*|"
            rf"\b(?:чутно|чути){sep}(?:(?:звук\w*|сері\w*){sep})?вибух\w*|"
            rf"\bгримлять{sep}вибух\w*|"
            r"\bщойно.{0,40}\bвибух\w*|"
            r"\bпрямо\s+зараз.{0,40}\bвибух\w*)",
            low,
        )
    ) or trusted_live_publication_binding_extension_wording(low)


def trusted_same_attack_source(row: dict) -> bool:
    source = str(row.get("source") or "")
    publisher = str(row.get("publisher") or "")
    return source.startswith("Telegram /") or "суспільн" in f"{source} {publisher}".casefold()


def trusted_live_source(row: dict) -> bool:
    return str(row.get("source") or "").startswith("Telegram /")


def cherkasy_genitive_city_event(segment: str) -> bool:
    """Narrow exact-city support for the reviewed phrase 'жителі Черкас ... вибухи'."""
    low = normalize_evidence_text(segment)
    if not re.search(r"(?<![\w-])черкас(?![\w-])", low):
        return False
    return bool(
        re.search(
            r"\bжителі\s+черкас\b.{0,80}\b(?:чул\w*|чут\w*)\b"
            r".{0,35}\bвибух\w*",
            low,
        )
    )


def exact_city_classification_evidence(city_key: str, row: dict) -> dict:
    segments = [
        segment
        for segment in classification_segments(row)
        if city_mentioned(city_key, segment)
        or (city_key == "cherkasy" and cherkasy_genitive_city_event(segment))
    ]
    return {"present": bool(segments), "segments": segments[:4]}


def strict_explosion_evidence(city_key: str, row: dict) -> dict:
    # Historical interface retained; evidence now covers the unified attack-event taxonomy.
    exact = exact_city_classification_evidence(city_key, row)
    segments = [segment for segment in exact["segments"] if strict_attack_event_signal(segment)]
    event_types = []
    for segment in segments:
        for event_type in attack_event_types(segment):
            if event_type not in event_types:
                event_types.append(event_type)
    return {"present": bool(segments), "segments": segments[:4], "event_types": event_types}


def air_military_context_evidence(row: dict) -> dict:
    segments = [segment for segment in classification_segments(row) if air_military_context(segment)]
    return {"present": bool(segments), "segments": segments[:4]}


def audited_cities_in_text(text: str) -> list[str]:
    return sorted(key for key in CITY_CONFIG if city_mentioned(key, text))


_KYIV_OFFICIAL_TIMELINE_MONTHS = {
    "січня": 1,
    "лютого": 2,
    "березня": 3,
    "квітня": 4,
    "травня": 5,
    "червня": 6,
    "липня": 7,
    "серпня": 8,
    "вересня": 9,
    "жовтня": 10,
    "листопада": 11,
    "грудня": 12,
}
_KYIV_OFFICIAL_TIMELINE_MARKER_RE = re.compile(
    r"(?<!\d)(\d{1,2}):(\d{2})\s*,\s*(\d{1,2})\s+"
    r"(січня|лютого|березня|квітня|травня|червня|липня|серпня|"
    r"вересня|жовтня|листопада|грудня)\b",
    re.IGNORECASE,
)
_TIMELINE_SPECIFIC_AIR_RE = re.compile(
    r"\b(?:бпла|безпілот\w*|дрон\w*|shahed\w*|шахед\w*|ракет\w*|"
    r"каб\w*|авіабомб\w*|баліст\w*|крилат\w*|іскандер\w*|"
    r"бандерол\w*|молні\w*|fpv|ппо|повітряні\s+сили)\b",
    re.IGNORECASE,
)
_TIMELINE_ALL_CLEAR_RE = re.compile(
    r"\b(?:відбій|скасован\w*.{0,20}тривог\w*|тривог\w*.{0,20}скасован\w*)\b",
    re.IGNORECASE,
)


def trusted_kyiv_official_live_timeline(city_key: str, row: dict) -> bool:
    if city_key != "kyiv" or row.get("discovery_basis") != "publisher_fulltext":
        return False
    source_url = str(row.get("resolved_url") or row.get("url") or "")
    host = (urlparse(source_url).hostname or "").casefold()
    if host != "kyivcity.gov.ua" and not host.endswith(".kyivcity.gov.ua"):
        return False
    title = normalize_evidence_text(row.get("title"))
    return "інформація оновлюється" in title and "ворожа атака" in title


def kyiv_official_timeline_entries(row: dict) -> list[dict]:
    published = parse_dt(row.get("published_at"))
    text = classification_text(row)
    if not published or not text:
        return []
    published_local = published.astimezone(KYIV_TZ)
    hits = list(_KYIV_OFFICIAL_TIMELINE_MARKER_RE.finditer(text))
    entries = []
    for index, hit in enumerate(hits):
        hour = int(hit.group(1))
        minute = int(hit.group(2))
        day = int(hit.group(3))
        month = _KYIV_OFFICIAL_TIMELINE_MONTHS.get(hit.group(4).casefold())
        if hour > 23 or minute > 59 or month is None:
            continue
        try:
            local_dt = datetime(
                published_local.year,
                month,
                day,
                hour,
                minute,
                tzinfo=KYIV_TZ,
            )
        except ValueError:
            continue
        if local_dt.date() != published_local.date():
            continue
        end = hits[index + 1].start() if index + 1 < len(hits) else len(text)
        entries.append(
            {
                "index": index,
                "time": local_dt.astimezone(UTC),
                "text": " ".join(text[hit.start():end].split()),
            }
        )
    return entries


def _timeline_entry_overlaps_segments(entry_text: str, segments: list[str]) -> bool:
    entry_low = normalize_evidence_text(entry_text)
    for segment in segments or []:
        segment_low = normalize_evidence_text(segment)
        if segment_low and (segment_low in entry_low or entry_low in segment_low):
            return True
    return False


def _qualifying_specific_timeline_air_context(text: str) -> bool:
    low = normalize_evidence_text(text)
    return bool(low and air_military_context(low) and _TIMELINE_SPECIFIC_AIR_RE.search(low))


def _timeline_intervening_conflict(city_key: str, text: str) -> bool:
    mentioned = audited_cities_in_text(text)
    if any(key != city_key for key in mentioned):
        return True
    if _TIMELINE_ALL_CLEAR_RE.search(normalize_evidence_text(text)):
        return True
    return strict_attack_event_signal(text)


def same_source_timeline_air_context_evidence(
    city_key: str,
    row: dict,
    strict_evidence: dict,
    air_evidence: dict,
    temporal_binding: dict | None,
    episodes: list[dict] | None,
) -> dict:
    if not trusted_kyiv_official_live_timeline(city_key, row):
        return {"present": False, "reason": "unsupported_source_chronology"}
    if not strict_evidence.get("present") or not air_evidence.get("present"):
        return {"present": False, "reason": "missing_event_or_air_context"}
    temporal = temporal_binding or {}
    target_id = str(temporal.get("episode_id") or "")
    event_time = parse_dt(temporal.get("event_time"))
    if (
        not temporal.get("present")
        or not temporal.get("episode_specific")
        or not target_id
        or not event_time
    ):
        return {"present": False, "reason": "event_temporal_binding_not_unique"}
    target_episode = next(
        (
            ep
            for ep in (episodes or [])
            if str(ep.get("episode_id") or "") == target_id
        ),
        None,
    )
    if target_episode is None:
        return {"present": False, "reason": "target_episode_unavailable"}

    entries = kyiv_official_timeline_entries(row)
    strict_segments = list(strict_evidence.get("segments") or [])
    air_segments = list(air_evidence.get("segments") or [])
    event_entries = [
        entry
        for entry in entries
        if entry["time"] == event_time
        and strict_attack_event_signal(entry["text"])
        and _timeline_entry_overlaps_segments(entry["text"], strict_segments)
    ]
    if not event_entries:
        return {"present": False, "reason": "event_timeline_entry_not_recovered"}

    air_entries = [
        entry
        for entry in entries
        if entry["time"] < event_time
        and _qualifying_specific_timeline_air_context(entry["text"])
        and _timeline_entry_overlaps_segments(entry["text"], air_segments)
    ]
    if not air_entries:
        return {"present": False, "reason": "qualifying_air_timeline_entry_not_recovered"}

    for event_entry in event_entries:
        for air_entry in reversed(air_entries):
            event_other_cities = [
                key for key in audited_cities_in_text(event_entry["text"]) if key != city_key
            ]
            air_other_cities = [
                key for key in audited_cities_in_text(air_entry["text"]) if key != city_key
            ]
            if event_other_cities or air_other_cities:
                continue

            event_neighbor = composition_neighbor_check(
                event_entry["time"], target_episode, episodes or []
            )
            air_neighbor = composition_neighbor_check(
                air_entry["time"], target_episode, episodes or []
            )
            if not event_neighbor["passed"] or not air_neighbor["passed"]:
                continue

            gap_seconds = (event_entry["time"] - air_entry["time"]).total_seconds()
            if gap_seconds < 0 or gap_seconds > COMPOSITION_MAX_GAP_MINUTES * 60:
                continue

            between = [
                entry
                for entry in entries
                if air_entry["index"] < entry["index"] < event_entry["index"]
            ]
            if any(
                _timeline_intervening_conflict(city_key, entry["text"])
                for entry in between
            ):
                return {
                    "present": False,
                    "reason": "intervening_timeline_conflict",
                    "gap_seconds": gap_seconds,
                }
            if between:
                return {
                    "present": False,
                    "reason": "timeline_entries_not_adjacent",
                    "gap_seconds": gap_seconds,
                }

            return {
                "present": True,
                "reason": "same_source_timeline_air_context",
                "basis": [
                    "same_publisher_document",
                    "trusted_kyiv_official_live_timeline",
                    "adjacent_timeline_entries",
                    f"timestamps_within_{COMPOSITION_MAX_GAP_MINUTES}m",
                    "both_entries_inside_unique_target_episode",
                    "event_time_from_existing_temporal_binding",
                ],
                "gap_seconds": gap_seconds,
                "air_entry_time": iso(air_entry["time"]),
                "event_entry_time": iso(event_entry["time"]),
                "air_entry_text": air_entry["text"],
                "event_entry_text": event_entry["text"],
                "air_neighbor_check": air_neighbor,
                "event_neighbor_check": event_neighbor,
            }

    return {"present": False, "reason": "timeline_entries_not_same_unique_episode_or_gap"}


def same_attack_context_evidence(
    city_key: str,
    row: dict,
    strict_evidence: dict,
    air_evidence: dict,
    temporal_binding: dict | None = None,
    episodes: list[dict] | None = None,
) -> dict:
    if not strict_evidence.get("present") or not air_evidence.get("present"):
        return {"present": False, "reason": "missing_explosion_or_air_context"}
    if any(air_military_context(segment) for segment in strict_evidence.get("segments") or []):
        return {"present": True, "reason": "air_context_in_exact_city_event_segment"}
    mentioned = audited_cities_in_text(classification_text(row))
    if trusted_same_attack_source(row) and len(mentioned) <= 1:
        return {"present": True, "reason": "trusted_source_adjacent_air_context"}
    timeline = same_source_timeline_air_context_evidence(
        city_key,
        row,
        strict_evidence,
        air_evidence,
        temporal_binding,
        episodes,
    )
    if timeline.get("present"):
        return timeline
    return {"present": False, "reason": "air_context_not_linked_to_exact_city_event"}



def _review_role(raw: dict, key: str) -> dict:
    value = raw.get(key)
    if isinstance(value, bool):
        present = value
        payload = {}
    elif isinstance(value, dict):
        payload = dict(value)
        present = value.get("present") is True
        if key == "same_attack_basis" and not present:
            present = bool(value.get("basis"))
    else:
        present = bool(value) if key == "same_attack_basis" else False
        payload = {"value": value} if value not in (None, "", [], {}) else {}
    evidence_text = payload.get("evidence_text") or payload.get("evidence")
    segments = []
    if isinstance(evidence_text, str) and evidence_text.strip():
        segments = [" ".join(evidence_text.split())]
    elif isinstance(evidence_text, list):
        segments = [" ".join(str(x).split()) for x in evidence_text if str(x).strip()]
    return {
        **payload,
        "present": bool(present),
        "segments": segments[:4],
        "evidence_source": "review_provenance",
    }


def _review_neighbor_passed(raw: dict, temporal: dict | None = None) -> bool:
    check = {}
    if isinstance(temporal, dict):
        check = temporal.get("neighboring_alert_check") or {}
    if not isinstance(check, dict) or not check:
        check = raw.get("neighboring_alert_check") or {}
    return isinstance(check, dict) and check.get("passed") is True


def reviewed_provenance_adapter(
    row: dict,
    city_key: str,
    episodes: list[dict],
    matching: dict,
) -> dict:
    raw = row.get("review_provenance")
    base = {
        "present": isinstance(raw, dict),
        "usable": False,
        "target_episode_id": None,
        "reason_codes": [],
        "exact_city": {"present": False, "segments": [], "evidence_source": "review_provenance"},
        "strict_explosion": {"present": False, "segments": [], "evidence_source": "review_provenance"},
        "air_military_context": {"present": False, "segments": [], "evidence_source": "review_provenance"},
        "same_attack_context": {"present": False, "reason": "no_reviewed_same_attack_basis", "evidence_source": "review_provenance"},
        "temporal_binding": {
            "present": False,
            "code": "NO_REVIEWED_TEMPORAL_BINDING",
            "evidence_type": None,
            "evidence": None,
            "event_time": None,
            "event_interval": None,
            "message_time": None,
            "timestamp_precision": None,
            "episode_specific": False,
            "supported_episode_ids": [],
            "episode_id": None,
            "near_boundary": empty_near_boundary(),
            "evidence_sources": [],
        },
        "sensitivity_binding": {
            "present": False,
            "basis": None,
            "episode_id": None,
            "supported_episode_ids": [],
            "evidence_source": "review_provenance",
        },
    }
    if not isinstance(raw, dict):
        return base

    try:
        schema_version = int(raw.get("schema_version"))
    except (TypeError, ValueError):
        schema_version = None
    if schema_version != REVIEW_PROVENANCE_SCHEMA_VERSION:
        base["reason_codes"].append("REVIEW_PROVENANCE_SCHEMA_UNSUPPORTED")
        return base

    target_id = str(raw.get("target_episode_id") or "")
    base["target_episode_id"] = target_id or None
    target_episode = next(
        (ep for ep in episodes if str(ep.get("episode_id") or "") == target_id),
        None,
    )
    if not target_id or target_episode is None:
        base["reason_codes"].append("REVIEW_PROVENANCE_TARGET_EPISODE_UNAVAILABLE")
        return base

    current_bound_id = str(row.get("matched_episode_id") or "")
    if current_bound_id and current_bound_id != target_id:
        base["reason_codes"].append("REVIEW_PROVENANCE_TARGET_MISMATCH")
        return base

    base["usable"] = True
    base["reason_codes"].append("REVIEW_PROVENANCE_USABLE")
    base["exact_city"] = _review_role(raw, "exact_city_evidence")
    base["strict_explosion"] = _review_role(raw, "explosion_evidence")
    base["air_military_context"] = _review_role(raw, "aerial_war_evidence")
    reviewed_same_attack = _review_role(raw, "same_attack_basis")
    base["same_attack_context"] = {
        **reviewed_same_attack,
        "reason": (
            "reviewed_same_attack_basis"
            if reviewed_same_attack.get("present")
            else "no_reviewed_same_attack_basis"
        ),
    }

    temporal = raw.get("temporal") or {}
    if isinstance(temporal, dict):
        status = str(temporal.get("status") or "")
        episode_specific = temporal.get("episode_specific") is True
        validated = temporal.get("validated_by_review") is True
        neighbor_passed = _review_neighbor_passed(raw, temporal)
        evidence_type = str(
            temporal.get("temporal_evidence_type")
            or temporal.get("evidence_type")
            or ""
        ) or None
        precision = temporal.get("timestamp_precision")
        event_time_raw = temporal.get("event_time")
        event_interval_raw = temporal.get("event_interval")
        temporal_positive = False
        event_time = None
        event_interval = None

        if status == "validated_event_time" and validated and episode_specific and neighbor_passed:
            event_dt = parse_dt(event_time_raw)
            start = parse_dt(target_episode.get("alert_start"))
            end = parse_dt(target_episode.get("alert_end"))
            if event_dt and start and end and start <= event_dt <= end:
                temporal_positive = True
                event_time = iso(event_dt)
        elif status == "validated_event_interval" and validated and episode_specific and neighbor_passed:
            if isinstance(event_interval_raw, dict):
                interval_start = parse_dt(event_interval_raw.get("start"))
                interval_end = parse_dt(event_interval_raw.get("end"))
            elif isinstance(event_interval_raw, (list, tuple)) and len(event_interval_raw) == 2:
                interval_start = parse_dt(event_interval_raw[0])
                interval_end = parse_dt(event_interval_raw[1])
            else:
                interval_start = interval_end = None
            target_start = parse_dt(target_episode.get("alert_start"))
            target_end = parse_dt(target_episode.get("alert_end"))
            if (
                interval_start and interval_end and target_start and target_end
                and interval_start <= interval_end
                and target_start <= interval_start
                and interval_end <= target_end
            ):
                temporal_positive = True
                event_interval = {
                    "start": iso(interval_start),
                    "end": iso(interval_end),
                }
        elif (
            status == "validated_episode_binding"
            and validated
            and episode_specific
            and neighbor_passed
            and evidence_type
        ):
            temporal_positive = True

        if temporal_positive:
            base["temporal_binding"] = {
                "present": True,
                "code": "TEMPORAL_REVIEWED_VALIDATED_BINDING",
                "evidence_type": evidence_type or status,
                "evidence": temporal.get("evidence_text") or event_time or event_interval,
                "event_time": event_time,
                "event_interval": event_interval,
                "message_time": temporal.get("message_time"),
                "publication_time": temporal.get("publication_time"),
                "update_time": temporal.get("update_time"),
                "timestamp_precision": precision,
                "episode_specific": True,
                "supported_episode_ids": [target_id],
                "episode_id": target_id,
                "near_boundary": empty_near_boundary(),
                "evidence_sources": ["review_provenance"],
                "source_identity": temporal.get("source_identity"),
            }
            base["reason_codes"].append("REVIEW_PROVENANCE_TEMPORAL_BINDING_USED")
        elif status in {"unsupported", "ambiguous", "negative"}:
            base["reason_codes"].append("REVIEW_PROVENANCE_TEMPORAL_UNSUPPORTED")

    sensitivity = raw.get("sensitivity_binding") or {}
    if (
        isinstance(sensitivity, dict)
        and sensitivity.get("present") is True
        and sensitivity.get("validated_by_review") is True
        and sensitivity.get("episode_specific") is True
        and _review_neighbor_passed(raw, sensitivity)
        and str(sensitivity.get("basis") or "") in {"inferred_same_attack", "near_boundary"}
    ):
        base["sensitivity_binding"] = {
            "present": True,
            "basis": str(sensitivity.get("basis")),
            "episode_id": target_id,
            "supported_episode_ids": [target_id],
            "reason": "reviewed_episode_specific_sensitivity_binding",
            "evidence_source": "review_provenance",
        }
        base["reason_codes"].append("REVIEW_PROVENANCE_SENSITIVITY_BINDING_USED")
    return base


def merge_reviewed_presence(candidate: dict, reviewed: dict) -> dict:
    candidate = dict(candidate or {})
    reviewed = dict(reviewed or {})
    sources = []
    if candidate.get("present"):
        sources.append("candidate_evidence")
    if reviewed.get("present"):
        sources.append("review_provenance")
    if not candidate.get("present") and reviewed.get("present"):
        out = dict(reviewed)
    else:
        out = candidate
        if reviewed.get("present"):
            out["reviewed_evidence"] = reviewed
    out["present"] = bool(candidate.get("present") or reviewed.get("present"))
    out["evidence_sources"] = sources
    return out


def merge_reviewed_temporal(candidate: dict, reviewed: dict) -> dict:
    candidate = dict(candidate or {})
    reviewed = dict(reviewed or {})
    if candidate.get("present"):
        out = candidate
        sources = ["candidate_evidence"]
        if reviewed.get("present"):
            sources.append("review_provenance")
            out["reviewed_evidence"] = reviewed
    elif reviewed.get("present"):
        out = reviewed
        sources = ["review_provenance"]
    else:
        out = candidate
        sources = []
    out["evidence_sources"] = sources
    return out


def reviewed_same_attack_basis_for_target(row: dict, target_id: str) -> bool:
    raw = row.get("review_provenance")
    if not isinstance(raw, dict):
        return False
    if raw.get("schema_version") != REVIEW_PROVENANCE_SCHEMA_VERSION:
        return False
    if str(raw.get("target_episode_id") or "") != target_id:
        return False
    if str(row.get("matched_episode_id") or "") not in {"", target_id}:
        return False
    role = _review_role(raw, "same_attack_basis")
    return bool(role.get("present"))


def reviewed_composition_binding_for_target(row: dict, target_id: str) -> dict | None:
    raw = row.get("review_provenance")
    if not isinstance(raw, dict):
        return None
    if raw.get("schema_version") != REVIEW_PROVENANCE_SCHEMA_VERSION:
        return None
    if str(raw.get("target_episode_id") or "") != target_id:
        return None
    if str(row.get("matched_episode_id") or "") not in {"", target_id}:
        return None
    composition = raw.get("composition")
    if not isinstance(composition, dict):
        return None
    if str(composition.get("target_episode_id") or target_id) != target_id:
        return None
    if composition.get("validated_by_review") is not True:
        return None
    if composition.get("same_attack_compatible") is not True:
        return None
    neighbor = composition.get("neighboring_alert_check") or {}
    if not isinstance(neighbor, dict) or neighbor.get("passed") is not True:
        return None
    anchor_id = str(composition.get("anchor_candidate_id") or "")
    contributor_ids = [
        str(value)
        for value in (composition.get("contributor_candidate_ids") or [])
        if str(value)
    ]
    if not anchor_id or not contributor_ids:
        return None
    return {
        **composition,
        "anchor_candidate_id": anchor_id,
        "contributor_candidate_ids": contributor_ids,
        "evidence_source": "review_provenance",
    }


def reviewed_composition_pair(
    temporal_row: dict,
    context_row: dict,
    target_id: str,
) -> dict | None:
    temporal_id = str(temporal_row.get("candidate_id") or "")
    context_id = str(context_row.get("candidate_id") or "")
    for owner in (temporal_row, context_row):
        binding = reviewed_composition_binding_for_target(owner, target_id)
        if not binding:
            continue
        ids = {
            str(binding.get("anchor_candidate_id") or ""),
            *[str(value) for value in binding.get("contributor_candidate_ids") or []],
        }
        if temporal_id in ids and context_id in ids:
            return binding
    return None


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


GOOGLE_NEWS_QUERY_FAMILIES = (
    (
        "explosion",
        '(вибух OR вибухи OR "було чутно" OR "пролунали вибухи" OR "чули вибухи")',
    ),
    (
        "impact_arrival",
        '(влучання OR влучив OR влучила OR влучили OR приліт OR прильот)',
    ),
    (
        "strike",
        '(удар OR вдарив OR вдарила OR вдарили OR атакував OR атакувала OR атакували OR "завдав удару" OR "завдала удару")',
    ),
    (
        "attack_consequence",
        '((пошкоджено OR пошкодження OR пожежа OR загоряння) (атака OR атакував OR атакувала OR удар OR влучання OR БпЛА OR безпілотник OR дрон OR ракета))',
    ),
    (
        "air_defense_action",
        '("працює ППО" OR "працювала ППО" OR "ППО збила" OR "ППО збили" OR "ППО знищила" OR "ППО знищили" OR "ППО перехопила" OR "збито БпЛА" OR "знищено БпЛА" OR "мобільна вогнева група збила")',
    ),
)


def google_news_query_families(city_label: str) -> list[tuple[str, str]]:
    return [
        (family, f'"{city_label}" {expression} when:8d')
        for family, expression in GOOGLE_NEWS_QUERY_FAMILIES
    ]


def google_news_query(city_label: str) -> str:
    # Backward-compatible legacy explosion query used for before/after proof.
    return google_news_query_families(city_label)[0][1]


def search_city_news(city_key: str, earliest: datetime, now: datetime) -> tuple[list[dict], str | None, dict]:
    label = CITY_CONFIG[city_key]["label"]
    lower_bound = earliest - timedelta(hours=3)
    upper_bound = now + timedelta(hours=1)
    merged = {}
    fulltext_fetches = 0
    fulltext_rescued_candidates = 0
    query_urls = {}
    family_result_counts = {}

    for family, query in google_news_query_families(label):
        url = f"{GOOGLE_NEWS_URL}?q={quote_plus(query)}&hl=uk&gl=UA&ceid=UA:uk"
        query_urls[family] = url
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
        family_rows = []

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

            fetcher = fetch_publisher_fulltext if fulltext_fetches < MAX_FULLTEXT_FETCHES_PER_CITY else None
            row, fetched, rescued = build_google_news_candidate(
                city_key,
                title,
                description,
                link,
                publisher,
                publisher_url,
                iso(published) if published else None,
                fulltext_fetcher=fetcher,
            )
            if fetched:
                fulltext_fetches += 1
            if rescued:
                fulltext_rescued_candidates += 1
            if not row:
                continue
            row["discovery_query_families"] = [family]
            family_rows.append(row)

        family_dedup = {(r["url"], r["title"]): r for r in family_rows}
        family_result_counts[family] = len(family_dedup)
        for key, row in family_dedup.items():
            if key not in merged:
                merged[key] = row
                continue
            families = set(merged[key].get("discovery_query_families") or [])
            families.update(row.get("discovery_query_families") or [])
            merged[key]["discovery_query_families"] = sorted(families)

    primary_url = query_urls.get("explosion")
    return list(merged.values()), primary_url, {
        "fulltext_fetches": fulltext_fetches,
        "fulltext_rescued_candidates": fulltext_rescued_candidates,
        "query_urls": query_urls,
        "query_family_result_counts": family_result_counts,
        "results_after_family_merge": len(merged),
    }


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


def due_check_counts(due: dict[str, list[tuple[dict, dict]]]) -> tuple[int, int, int]:
    total = sum(len(city_due) for city_due in due.values())
    checked = sum(
        1
        for city_due in due.values()
        for _, check in city_due
        if check.get("checked_at")
    )
    return total, checked, total - checked


def checks_became_due_between(state: dict, after: datetime, through: datetime) -> int:
    count = 0
    for cstate in state.get("cities", {}).values():
        for ep in cstate.get("episodes", []):
            for check in ep.get("checks", []):
                due = parse_dt(check.get("due_at"))
                if due and after < due <= through:
                    count += 1
    return count


def tracked_episodes_for_city(state: dict, city_key: str) -> list[dict]:
    cstate = (state.get("cities") or {}).get(city_key) or {}
    by_id = {
        str(ep.get("episode_id")): ep
        for ep in cstate.get("episodes", [])
        if isinstance(ep, dict) and ep.get("episode_id")
    }
    return sorted(
        by_id.values(),
        key=lambda ep: (ep.get("alert_start") or "", ep.get("alert_end") or "", ep.get("episode_id") or ""),
    )


def same_episode_representation(left: dict, right: dict) -> bool:
    left_start = parse_dt(left.get("alert_start"))
    left_end = parse_dt(left.get("alert_end"))
    right_start = parse_dt(right.get("alert_start"))
    right_end = parse_dt(right.get("alert_end"))
    if not left_start or not left_end or not right_start or not right_end:
        return False
    start_delta = abs((left_start - right_start).total_seconds())
    end_delta = abs((left_end - right_end).total_seconds())
    return (
        start_delta <= MATCH_REPRESENTATION_TOLERANCE_SECONDS
        and end_delta <= MATCH_REPRESENTATION_TOLERANCE_SECONDS
    )


def episode_representation_clusters(episodes: list[dict]) -> list[list[dict]]:
    rows = sorted(
        {
            str(ep.get("episode_id")): ep
            for ep in episodes
            if isinstance(ep, dict) and ep.get("episode_id")
        }.values(),
        key=lambda ep: str(ep.get("episode_id")),
    )
    parent = list(range(len(rows)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left_index: int, right_index: int) -> None:
        left_root = find(left_index)
        right_root = find(right_index)
        if left_root == right_root:
            return
        if left_root < right_root:
            parent[right_root] = left_root
        else:
            parent[left_root] = right_root

    for left_index, left in enumerate(rows):
        for right_index in range(left_index + 1, len(rows)):
            if same_episode_representation(left, rows[right_index]):
                union(left_index, right_index)

    grouped: dict[int, list[dict]] = {}
    for index, ep in enumerate(rows):
        grouped.setdefault(find(index), []).append(ep)

    clusters = [
        sorted(group, key=lambda ep: str(ep.get("episode_id")))
        for group in grouped.values()
    ]
    return sorted(clusters, key=lambda group: str(group[0].get("episode_id")) if group else "")


def logical_episode_support(episodes: list[dict]) -> dict:
    """Summarize raw episode rows at the shared logical alert-window level."""
    clusters = episode_representation_clusters(episodes)
    logical_groups = [
        [str(ep["episode_id"]) for ep in cluster]
        for cluster in clusters
    ]
    supported_ids = sorted(
        episode_id
        for group in logical_groups
        for episode_id in group
    )
    specific = len(logical_groups) == 1
    singleton_id = (
        logical_groups[0][0]
        if specific and len(logical_groups[0]) == 1
        else None
    )
    return {
        "episode_specific": specific,
        "supported_episode_ids": supported_ids,
        "logical_episode_groups": logical_groups,
        "episode_id": singleton_id,
    }


def match_candidate_to_episodes(row: dict, episodes: list[dict]) -> dict:
    """
    Deterministic temporal matching only.

    Publication time may identify alert windows that could contain the reported event,
    but it is not evidence of the event time and does not classify the candidate.
    """
    published = parse_dt(row.get("published_at"))
    if not published:
        return {
            "outcome": "no_match",
            "matched_episode_ids": [],
            "logical_episode_groups": [],
            "matched_episode_id": None,
            "reason": "missing_or_invalid_publication_time",
        }

    raw_matches = {}
    for ep in episodes:
        episode_id = str(ep.get("episode_id") or "")
        start = parse_dt(ep.get("alert_start"))
        end = parse_dt(ep.get("alert_end"))
        if not episode_id or not start or not end:
            continue
        if start <= published <= end + timedelta(minutes=AUTO_MATCH_END_GRACE_MINUTES):
            raw_matches[episode_id] = ep

    if not raw_matches:
        return {
            "outcome": "no_match",
            "matched_episode_ids": [],
            "logical_episode_groups": [],
            "matched_episode_id": None,
            "reason": "publication_outside_all_tracked_alert_windows",
        }

    matched = sorted(raw_matches.values(), key=lambda ep: str(ep.get("episode_id")))
    support = logical_episode_support(matched)
    matched_ids = [str(ep["episode_id"]) for ep in matched]
    logical_groups = list(support["logical_episode_groups"])

    if support["episode_specific"]:
        singleton_id = support["episode_id"]
        return {
            "outcome": "unique_match",
            "matched_episode_ids": matched_ids,
            "logical_episode_groups": logical_groups,
            "matched_episode_id": singleton_id,
            "reason": (
                "publication_within_unique_tracked_alert_window"
                if singleton_id
                else "near_duplicate_source_representations_reconciled_to_one_tracked_alert_window"
            ),
        }

    return {
        "outcome": "ambiguous_match",
        "matched_episode_ids": matched_ids,
        "logical_episode_groups": logical_groups,
        "matched_episode_id": None,
        "reason": "publication_matches_multiple_distinct_tracked_alert_windows",
    }


def apply_matching_result(item: dict, matching: dict) -> None:
    previous_id = item.get("matched_episode_id")
    matched_ids = list(matching.get("matched_episode_ids") or [])
    item["matching_outcome"] = matching.get("outcome")
    item["matched_episode_ids"] = matched_ids
    item["matching_logical_episode_groups"] = [
        list(group) for group in matching.get("logical_episode_groups") or []
    ]
    item["matching_reason"] = matching.get("reason")

    if matching.get("outcome") != "unique_match":
        item["matched_episode_id"] = None
        return

    singleton_id = matching.get("matched_episode_id")
    if singleton_id:
        item["matched_episode_id"] = singleton_id
    elif previous_id in matched_ids:
        item["matched_episode_id"] = previous_id
    else:
        # Multiple source representations of one logical alert window are unique
        # at the logical-window level, but there is no arbitrary raw-ID winner.
        item["matched_episode_id"] = None


def stored_matching_signature(item: dict) -> tuple:
    return (
        str(item.get("matching_outcome") or ""),
        item.get("matched_episode_id"),
        tuple(item.get("matched_episode_ids") or []),
        tuple(tuple(group) for group in item.get("matching_logical_episode_groups") or []),
        str(item.get("matching_outcome") or "") == "ambiguous_match",
    )


def classification_matching_is_stale(item: dict, matching: dict) -> bool:
    expected = {
        "unique_match": "MATCH_UNIQUE",
        "ambiguous_match": "MATCH_AMBIGUOUS",
        "no_match": "MATCH_NONE",
    }.get(str(matching.get("outcome") or "no_match"), "MATCH_NONE")
    match_codes = {
        code
        for code in (item.get("classification_reason_codes") or [])
        if code in {"MATCH_UNIQUE", "MATCH_AMBIGUOUS", "MATCH_NONE"}
    }
    return match_codes != {expected}


def refresh_queue_matching(
    queue: list[dict],
    state: dict,
    statuses: set[str] | None = None,
) -> dict:
    counts = {
        "candidates_checked": 0,
        "unique_match": 0,
        "ambiguous_match": 0,
        "no_match": 0,
        "material_match_changes": 0,
        "stale_classification_before": 0,
        "reclassified_after_match_refresh": 0,
        "stale_classification_repaired": 0,
        "status_changes": 0,
        "reclassified_episode_ids": [],
    }
    reclassified_episode_ids = set()
    for item in queue:
        if not isinstance(item, dict):
            continue
        status = str(item.get("status") or "")
        if statuses is not None and status not in statuses:
            continue
        city_key = str(item.get("city_key") or "")
        if city_key not in CITY_CONFIG:
            continue
        episodes = tracked_episodes_for_city(state, city_key)
        before_status = item.get("status")
        before_signature = stored_matching_signature(item)
        matching = match_candidate_to_episodes(item, episodes)
        stale_before = classification_matching_is_stale(item, matching)
        apply_matching_result(item, matching)
        after_signature = stored_matching_signature(item)
        material_change = before_signature != after_signature

        counts["candidates_checked"] += 1
        counts[matching["outcome"]] += 1
        if material_change:
            counts["material_match_changes"] += 1
        if stale_before:
            counts["stale_classification_before"] += 1

        if material_change or stale_before:
            decision = classify_candidate(item, city_key, episodes, matching)
            apply_classification_decision(item, decision, matching)
            counts["reclassified_after_match_refresh"] += 1
            reclassified_episode_ids.update(matching.get("matched_episode_ids") or [])
            if stale_before:
                counts["stale_classification_repaired"] += 1
            if classification_matching_is_stale(item, matching):
                raise AssertionError("Classification matching reason codes remain stale after refresh")

        if item.get("status") != before_status:
            counts["status_changes"] += 1

    counts["reclassified_episode_ids"] = sorted(reclassified_episode_ids)
    return counts



def matched_episode_rows(matching: dict, episodes: list[dict]) -> list[dict]:
    wanted = set(matching.get("matched_episode_ids") or [])
    return [ep for ep in episodes if str(ep.get("episode_id") or "") in wanted]


def publication_local_day(row: dict):
    published = parse_dt(row.get("published_at"))
    return published.astimezone(KYIV_TZ).date() if published else None


def episodes_intersecting_local_day(row: dict, episodes: list[dict]) -> list[dict]:
    local_day = publication_local_day(row)
    if local_day is None:
        return []
    next_day = local_day + timedelta(days=1)
    day_start = datetime(
        local_day.year, local_day.month, local_day.day, tzinfo=KYIV_TZ
    ).astimezone(UTC)
    day_end = datetime(
        next_day.year, next_day.month, next_day.day, tzinfo=KYIV_TZ
    ).astimezone(UTC)
    rows = {}
    for ep in episodes:
        episode_id = str(ep.get("episode_id") or "")
        start = parse_dt(ep.get("alert_start"))
        end = parse_dt(ep.get("alert_end"))
        if not episode_id or not start or not end:
            continue
        if start < day_end and end >= day_start:
            rows[episode_id] = ep
    return sorted(rows.values(), key=lambda ep: (ep.get("alert_start") or "", ep.get("episode_id") or ""))


def exact_active_episodes_at(moment: datetime, episodes: list[dict]) -> list[dict]:
    rows = {}
    for ep in episodes:
        episode_id = str(ep.get("episode_id") or "")
        start = parse_dt(ep.get("alert_start"))
        end = parse_dt(ep.get("alert_end"))
        if episode_id and start and end and start <= moment <= end:
            rows[episode_id] = ep
    return sorted(rows.values(), key=lambda ep: str(ep.get("episode_id") or ""))


def event_clock_mentions(text: str) -> list[tuple[int, int]]:
    low = normalize_evidence_text(text)
    event_hits = list(
        re.finditer(
            r"(?:вибух\w*|влуч\w*|поціл\w*|приліт\w*|вдарил\w*|"
            r"(?:завдал\w*|нанес\w*).{0,50}удар\w*)",
            low,
        )
    )
    if not event_hits:
        return []

    out = []
    prefixed_pattern = re.compile(
        r"(?:\bо\b|\bблизько\b|\bприблизно\b)\s*(\d{1,2})[:.](\d{2})",
        re.IGNORECASE,
    )
    # Kyiv City live timelines place an exact event clock at the start of the
    # event segment, e.g. "21:54, 30 вересня ... Влучання ...". Keep this
    # deliberately segment-leading: a bare clock elsewhere in prose is not
    # promoted to an explicit event time.
    timeline_leading_pattern = re.compile(r"^(\d{1,2}):(\d{2})\b", re.IGNORECASE)
    clock_hits = list(prefixed_pattern.finditer(low)) + list(timeline_leading_pattern.finditer(low))
    clock_hits.sort(key=lambda match: match.start())
    for hit in clock_hits:
        hour, minute = int(hit.group(1)), int(hit.group(2))
        if hour > 23 or minute > 59:
            continue
        if min(abs(hit.start() - event.start()) for event in event_hits) <= 100:
            out.append((hour, minute))
    return out


def relative_alert_chronology_relation(row: dict, episodes: list[dict]) -> dict:
    """
    Resolve narrow source-local chronology such as:
    "Повітряну тривогу оголосили о 23:36. Вже за 10 хвилин ... вибухи."

    This is parser hardening only: it does not create a new eligibility rule.
    Both the stated alert clock and derived event clock must fall inside the
    same tracked episode, and the text must contain explicit alert language
    followed by a bounded minute offset and an attack-event signal.
    """
    published = parse_dt(row.get("published_at"))
    text = classification_text(row)
    low = normalize_evidence_text(text)
    if not published or not low:
        return {
            "relation": None,
            "event_time": None,
            "alert_time": None,
            "offset_minutes": None,
            "episode_specific": False,
            "supported_episode_ids": [],
            "episode_id": None,
        }

    pattern = re.compile(
        r"(?:повітрян\w*\s+)?тривог\w*.{0,80}?(?:оголосил\w*|розпочал\w*|почал\w*)"
        r".{0,40}?\bо\s*(\d{1,2})[:.](\d{2})\b"
        r".{0,180}?\b(?:вже\s+)?за\s+(\d{1,2})\s+хвилин\w*\b"
        r".{0,180}?\b(?:вибух\w*|влуч\w*|приліт\w*|удар\w*|пошкод\w*|пожеж\w*)",
        re.IGNORECASE,
    )
    match = pattern.search(low)
    if not match:
        return {
            "relation": None,
            "event_time": None,
            "alert_time": None,
            "offset_minutes": None,
            "episode_specific": False,
            "supported_episode_ids": [],
            "episode_id": None,
        }

    alert_hour, alert_minute, offset_minutes = map(int, match.groups())
    if alert_hour > 23 or alert_minute > 59 or offset_minutes > 180:
        return {
            "relation": None,
            "event_time": None,
            "alert_time": None,
            "offset_minutes": None,
            "episode_specific": False,
            "supported_episode_ids": [],
            "episode_id": None,
        }

    published_local = published.astimezone(KYIV_TZ)
    local_day = published_local.date()
    day_offsets = (0, -1) if published_local.hour < 6 else (0,)
    candidates = []
    for day_offset in day_offsets:
        day = local_day + timedelta(days=day_offset)
        alert_dt = datetime(
            day.year, day.month, day.day, alert_hour, alert_minute, tzinfo=KYIV_TZ
        ).astimezone(UTC)
        event_dt = alert_dt + timedelta(minutes=offset_minutes)
        for ep in episodes:
            episode_id = str(ep.get("episode_id") or "")
            start = parse_dt(ep.get("alert_start"))
            end = parse_dt(ep.get("alert_end"))
            if not episode_id or not start or not end:
                continue
            if start <= alert_dt <= end and start <= event_dt <= end:
                candidates.append((event_dt, alert_dt, episode_id))

    if not candidates:
        return {
            "relation": None,
            "event_time": None,
            "alert_time": None,
            "offset_minutes": offset_minutes,
            "episode_specific": False,
            "supported_episode_ids": [],
            "episode_id": None,
        }

    candidates.sort(key=lambda x: (x[0], x[1], x[2]))
    best_event = candidates[0][0]
    best_alert = candidates[0][1]
    selected = [x for x in candidates if x[0] == best_event and x[1] == best_alert]
    supported_ids = sorted({x[2] for x in selected})
    supported_set = set(supported_ids)
    support = logical_episode_support([
        ep for ep in episodes
        if str(ep.get("episode_id") or "") in supported_set
    ])
    specific = bool(support["episode_specific"])
    return {
        "relation": "inside" if specific else None,
        "event_time": iso(best_event),
        "alert_time": iso(best_alert),
        "offset_minutes": offset_minutes,
        "episode_specific": specific,
        "supported_episode_ids": list(support["supported_episode_ids"]),
        "logical_episode_groups": list(support["logical_episode_groups"]),
        "episode_id": support["episode_id"] if specific else None,
    }


def explicit_event_time_relation(
    row: dict,
    event_segments: list[str],
    matching: dict,
    episodes: list[dict],
) -> dict:
    """
    Resolve a source-stated event clock against all tracked episodes.

    Publication time is used only to infer the calendar date for a clock-only
    expression such as "близько 16:18"; it never selects the alert episode.
    """
    published = parse_dt(row.get("published_at"))
    if not published:
        return {
            "relation": None,
            "event_time": None,
            "distance_seconds": None,
            "episode_specific": False,
            "supported_episode_ids": [],
            "episode_id": None,
        }

    published_local = published.astimezone(KYIV_TZ)
    local_day = published_local.date()
    # A clock-only source statement normally belongs to the publication local
    # day. Previous-day fallback is reserved for genuinely near-midnight
    # publication, where a late report can describe an event before midnight.
    # This prevents daytime reports such as "8 February ... at 08:48" from
    # accidentally binding to an unrelated alert at the same clock on 7 February.
    day_offsets = (0, -1) if published_local.hour < 6 else (0,)
    candidates = []
    limit = SENSITIVITY_NEAR_BOUNDARY_MAX_MINUTES * 60
    for segment in event_segments:
        for hour, minute in event_clock_mentions(segment):
            for day_offset in day_offsets:
                day = local_day + timedelta(days=day_offset)
                event_dt = datetime(
                    day.year, day.month, day.day, hour, minute, tzinfo=KYIV_TZ
                ).astimezone(UTC)
                for ep in episodes:
                    episode_id = str(ep.get("episode_id") or "")
                    start = parse_dt(ep.get("alert_start"))
                    end = parse_dt(ep.get("alert_end"))
                    if not episode_id or not start or not end:
                        continue
                    if start <= event_dt <= end:
                        candidates.append(("inside", 0.0, event_dt, episode_id))
                        continue
                    before = (start - event_dt).total_seconds()
                    after = (event_dt - end).total_seconds()
                    if 0 < before <= limit:
                        candidates.append(("near_before", before, event_dt, episode_id))
                    elif 0 < after <= limit:
                        candidates.append(("near_after", after, event_dt, episode_id))

    if not candidates:
        return {
            "relation": None,
            "event_time": None,
            "distance_seconds": None,
            "episode_specific": False,
            "supported_episode_ids": [],
            "episode_id": None,
        }

    candidates.sort(key=lambda item: (0 if item[0] == "inside" else 1, item[1], item[2], item[3]))
    best_priority = 0 if candidates[0][0] == "inside" else 1
    best_distance = candidates[0][1]
    best_time = candidates[0][2]
    selected = [
        item for item in candidates
        if (0 if item[0] == "inside" else 1) == best_priority
        and item[1] == best_distance
        and item[2] == best_time
    ]
    supported_ids = sorted({item[3] for item in selected})
    supported_set = set(supported_ids)
    support = logical_episode_support([
        ep for ep in episodes
        if str(ep.get("episode_id") or "") in supported_set
    ])
    relations = sorted({item[0] for item in selected})
    relation = relations[0] if len(relations) == 1 else None
    specific = relation is not None and bool(support["episode_specific"])
    return {
        "relation": relation,
        "event_time": iso(best_time),
        "distance_seconds": best_distance,
        "episode_specific": specific,
        "supported_episode_ids": list(support["supported_episode_ids"]),
        "logical_episode_groups": list(support["logical_episode_groups"]),
        "episode_id": support["episode_id"] if specific else None,
    }


def explicit_event_time_binding(row: dict, event_segments: list[str], matching: dict, episodes: list[dict]) -> dict:
    relation = explicit_event_time_relation(row, event_segments, matching, episodes)
    return {
        "present": relation.get("relation") == "inside" and relation.get("episode_specific") is True,
        "event_time": relation.get("event_time") if relation.get("relation") == "inside" else None,
        "episode_specific": bool(relation.get("episode_specific")),
        "supported_episode_ids": list(relation.get("supported_episode_ids") or []),
        "episode_id": relation.get("episode_id"),
    }



def _source_clock_not_after(reference: datetime, hour: int, minute: int) -> datetime | None:
    """Resolve a source-local clock without allowing it to become a future point."""
    if hour > 23 or minute > 59:
        return None
    reference_local = reference.astimezone(KYIV_TZ)
    day = reference_local.date()
    candidate = datetime(
        day.year, day.month, day.day, hour, minute, tzinfo=KYIV_TZ
    ).astimezone(UTC)
    if candidate <= reference:
        return candidate
    previous_day = day - timedelta(days=1)
    previous = datetime(
        previous_day.year,
        previous_day.month,
        previous_day.day,
        hour,
        minute,
        tzinfo=KYIV_TZ,
    ).astimezone(UTC)
    return previous if previous <= reference else None


def _event_already_occurred_by_publication(text: str) -> bool:
    """Narrow past-event wording gate for using publication time as an upper bound."""
    low = normalize_evidence_text(text)
    patterns = (
        r"\b(?:почул\w*|чул\w*)\b.{0,50}\bвибух\w*",
        r"\b(?:зафіксовано|сталося|відбулося)\b.{0,90}\b(?:вибух\w*|влуч\w*|удар\w*)",
        r"\b(?:влучил\w*|влучан\w*|поціл\w*)\b",
    )
    return any(re.search(pattern, low) for pattern in patterns)


def source_temporal_constraint(row: dict, event_segments: list[str]) -> dict:
    """
    Represent only the two narrow source relations needed by the frozen Kyiv proof.

    The result preserves bounds and inclusivity. Publication time may supply an
    upper bound for AFTER_TIME only when the same source wording states that the
    event had already occurred. Publication time is never converted to event time.
    """
    empty = {
        "recognized": False,
        "relation_type": None,
        "lower_bound": None,
        "upper_bound": None,
        "lower_bound_inclusive": None,
        "upper_bound_inclusive": None,
        "basis_for_lower_bound": None,
        "basis_for_upper_bound": None,
        "source_excerpt": None,
        "publication_time_used_as_event_time": False,
    }
    published = parse_dt(row.get("published_at"))
    if not published:
        return empty

    after_re = re.compile(
        r"\bпісля\s+(\d{1,2})(?:(?:[:.](\d{2}))|\s*)\s*(?:ранку\b)?",
        re.IGNORECASE,
    )
    as_of_re = re.compile(
        r"\bстаном\s+на\s+(\d{1,2})[:.](\d{2})\b",
        re.IGNORECASE,
    )

    for segment in event_segments:
        low = normalize_evidence_text(segment)
        if not low:
            continue
        after = after_re.search(low)
        as_of = as_of_re.search(low)
        if not after and not as_of:
            continue

        source_excerpt = " ".join(str(segment).split())

        if as_of:
            upper = _source_clock_not_after(
                published, int(as_of.group(1)), int(as_of.group(2))
            )
            if upper is None:
                return {
                    **empty,
                    "recognized": True,
                    "relation_type": "BEFORE_OR_BY_TIME",
                    "source_excerpt": source_excerpt,
                }

            lower = None
            lower_basis = None
            if after:
                lower_minute = int(after.group(2) or 0)
                lower = _source_clock_not_after(
                    upper, int(after.group(1)), lower_minute
                )
                if lower is not None and lower < upper:
                    lower_basis = "source_after_time_same_segment"
                else:
                    lower = None

            return {
                **empty,
                "recognized": True,
                "relation_type": "BEFORE_OR_BY_TIME",
                "lower_bound": iso(lower) if lower else None,
                "upper_bound": iso(upper),
                "lower_bound_inclusive": False if lower else None,
                "upper_bound_inclusive": True,
                "basis_for_lower_bound": lower_basis,
                "basis_for_upper_bound": "source_as_of_time",
                "source_excerpt": source_excerpt,
            }

        lower_minute = int(after.group(2) or 0)
        lower = _source_clock_not_after(
            published, int(after.group(1)), lower_minute
        )
        if lower is None:
            return {
                **empty,
                "recognized": True,
                "relation_type": "AFTER_TIME",
                "source_excerpt": source_excerpt,
            }

        upper = (
            published
            if published > lower and _event_already_occurred_by_publication(segment)
            else None
        )
        return {
            **empty,
            "recognized": True,
            "relation_type": "AFTER_TIME",
            "lower_bound": iso(lower),
            "upper_bound": iso(upper) if upper else None,
            "lower_bound_inclusive": False,
            "upper_bound_inclusive": True if upper else None,
            "basis_for_lower_bound": "source_after_time",
            "basis_for_upper_bound": (
                "publication_chronology_event_already_occurred"
                if upper
                else None
            ),
            "source_excerpt": source_excerpt,
        }

    return empty


def _interval_intersects_episode(
    lower: datetime | None,
    upper: datetime | None,
    lower_inclusive: bool | None,
    upper_inclusive: bool | None,
    episode: dict,
) -> bool:
    start = parse_dt(episode.get("alert_start"))
    end = parse_dt(episode.get("alert_end"))
    if not start or not end:
        return False
    if lower is not None:
        if end < lower or (end == lower and lower_inclusive is False):
            return False
    if upper is not None:
        if start > upper or (start == upper and upper_inclusive is False):
            return False
    return True


def _interval_fully_covered_by_episode_group(
    lower: datetime,
    upper: datetime,
    episodes: list[dict],
) -> bool:
    """Require the complete feasible interval, not merely an overlap, to be alert-covered."""
    if lower > upper:
        return False
    spans = []
    for episode in episodes:
        start = parse_dt(episode.get("alert_start"))
        end = parse_dt(episode.get("alert_end"))
        if not start or not end or end < lower or start > upper:
            continue
        spans.append((max(start, lower), min(end, upper)))
    if not spans:
        return False
    spans.sort()
    cursor = lower
    for start, end in spans:
        if start > cursor:
            return False
        if end > cursor:
            cursor = end
        if cursor >= upper:
            return True
    return cursor >= upper


def source_temporal_interval_relation(
    row: dict,
    event_segments: list[str],
    episodes: list[dict],
) -> dict:
    """
    Bind a source-derived non-point interval only when every allowed event time
    belongs to one logical canonical alert episode.
    """
    constraint = source_temporal_constraint(row, event_segments)
    base = {
        "recognized": bool(constraint.get("recognized")),
        "constraint": constraint,
        "episode_specific": False,
        "supported_episode_ids": [],
        "logical_episode_groups": [],
        "episode_id": None,
        "failure_reason": None,
    }
    if not constraint.get("recognized"):
        return base

    lower = parse_dt(constraint.get("lower_bound"))
    upper = parse_dt(constraint.get("upper_bound"))
    lower_inclusive = constraint.get("lower_bound_inclusive")
    upper_inclusive = constraint.get("upper_bound_inclusive")

    if lower and upper and lower > upper:
        return {**base, "failure_reason": "TEMPORAL_REPRESENTATION_UNSUPPORTED"}

    # For diagnostics only, bound an otherwise-open side to the publication
    # local day. These diagnostic bounds never satisfy the strict bound gate.
    published = parse_dt(row.get("published_at"))
    diagnostic_lower = lower
    diagnostic_upper = upper
    if published:
        published_local = published.astimezone(KYIV_TZ)
        local_day = published_local.date()
        next_day = local_day + timedelta(days=1)
        day_start = datetime(
            local_day.year, local_day.month, local_day.day, tzinfo=KYIV_TZ
        ).astimezone(UTC)
        day_end = datetime(
            next_day.year, next_day.month, next_day.day, tzinfo=KYIV_TZ
        ).astimezone(UTC)
        if diagnostic_lower is None:
            diagnostic_lower = day_start
        if diagnostic_upper is None:
            diagnostic_upper = day_end

    intersected = [
        episode
        for episode in episodes
        if _interval_intersects_episode(
            diagnostic_lower,
            diagnostic_upper,
            lower_inclusive if lower is not None else True,
            upper_inclusive if upper is not None else False,
            episode,
        )
    ]
    support = logical_episode_support(intersected)
    base = {
        **base,
        "supported_episode_ids": list(support["supported_episode_ids"]),
        "logical_episode_groups": list(support["logical_episode_groups"]),
    }

    if lower is None:
        return {**base, "failure_reason": "INSUFFICIENT_LOWER_BOUND"}
    if upper is None:
        return {**base, "failure_reason": "INSUFFICIENT_UPPER_BOUND"}

    groups = list(support["logical_episode_groups"])
    if len(groups) > 1:
        return {**base, "failure_reason": "MULTI_EPISODE_INTERVAL"}
    if not groups:
        return {**base, "failure_reason": "TEMPORAL_INTERVAL_STILL_AMBIGUOUS"}

    supported_set = set(support["supported_episode_ids"])
    group_episodes = [
        episode
        for episode in intersected
        if str(episode.get("episode_id") or "") in supported_set
    ]
    if not _interval_fully_covered_by_episode_group(lower, upper, group_episodes):
        return {**base, "failure_reason": "TEMPORAL_INTERVAL_STILL_AMBIGUOUS"}

    return {
        **base,
        "episode_specific": True,
        "episode_id": support["episode_id"],
        "failure_reason": None,
    }


def empty_near_boundary() -> dict:
    return {
        "present": False,
        "episode_specific": False,
        "supported_episode_ids": [],
        "logical_episode_groups": [],
        "episode_id": None,
    }


def temporal_binding_evidence(row: dict, strict_evidence: dict, matching: dict, episodes: list[dict]) -> dict:
    event_segments = list(strict_evidence.get("segments") or [])
    relative = relative_alert_chronology_relation(row, episodes)
    if relative.get("relation") == "inside":
        return {
            "present": True,
            "code": "TEMPORAL_RELATIVE_ALERT_CHRONOLOGY",
            "evidence_type": "relative_alert_chronology",
            "evidence": {
                "alert_time": relative.get("alert_time"),
                "offset_minutes": relative.get("offset_minutes"),
                "event_time": relative.get("event_time"),
            },
            "event_time": relative.get("event_time"),
            "event_interval": None,
            "message_time": None,
            "episode_specific": True,
            "supported_episode_ids": list(relative.get("supported_episode_ids") or []),
            "logical_episode_groups": [
                list(group) for group in relative.get("logical_episode_groups") or []
            ],
            "episode_id": relative.get("episode_id"),
            "near_boundary": empty_near_boundary(),
        }

    clock = explicit_event_time_relation(row, event_segments, matching, episodes)
    if clock.get("relation") == "inside":
        specific = bool(clock.get("episode_specific"))
        return {
            "present": specific,
            "code": (
                "TEMPORAL_EXPLICIT_EVENT_TIME_INSIDE_EPISODE"
                if specific
                else "TEMPORAL_EXPLICIT_EVENT_TIME_AMBIGUOUS_EPISODES"
            ),
            "evidence_type": "explicit_event_time",
            "evidence": clock.get("event_time"),
            "event_time": clock.get("event_time"),
            "event_interval": None,
            "message_time": None,
            "episode_specific": specific,
            "supported_episode_ids": list(clock.get("supported_episode_ids") or []),
            "logical_episode_groups": [
                list(group) for group in clock.get("logical_episode_groups") or []
            ],
            "episode_id": clock.get("episode_id"),
            "near_boundary": empty_near_boundary(),
        }
    if clock.get("relation") in {"near_before", "near_after"}:
        specific = bool(clock.get("episode_specific"))
        near = {
            "present": specific,
            "code": "TEMPORAL_EXPLICIT_EVENT_TIME_NEAR_BOUNDARY",
            "relation": clock.get("relation"),
            "event_time": clock.get("event_time"),
            "distance_seconds": clock.get("distance_seconds"),
            "episode_specific": specific,
            "supported_episode_ids": list(clock.get("supported_episode_ids") or []),
            "logical_episode_groups": [
                list(group) for group in clock.get("logical_episode_groups") or []
            ],
            "episode_id": clock.get("episode_id"),
        }
        return {
            "present": False,
            "code": (
                "TEMPORAL_EXPLICIT_EVENT_TIME_NEAR_BOUNDARY"
                if specific
                else "TEMPORAL_EXPLICIT_EVENT_TIME_NEAR_BOUNDARY_AMBIGUOUS"
            ),
            "evidence_type": "explicit_event_time",
            "evidence": clock.get("event_time"),
            "event_time": clock.get("event_time"),
            "event_interval": None,
            "message_time": None,
            "episode_specific": specific,
            "supported_episode_ids": list(clock.get("supported_episode_ids") or []),
            "logical_episode_groups": [
                list(group) for group in clock.get("logical_episode_groups") or []
            ],
            "episode_id": clock.get("episode_id"),
            "near_boundary": near,
        }

    interval = source_temporal_interval_relation(row, event_segments, episodes)
    if interval.get("recognized"):
        specific = bool(interval.get("episode_specific"))
        failure = interval.get("failure_reason")
        code = {
            None: "TEMPORAL_SOURCE_INTERVAL_INSIDE_EPISODE",
            "INSUFFICIENT_LOWER_BOUND": "TEMPORAL_SOURCE_INTERVAL_INSUFFICIENT_LOWER_BOUND",
            "INSUFFICIENT_UPPER_BOUND": "TEMPORAL_SOURCE_INTERVAL_INSUFFICIENT_UPPER_BOUND",
            "MULTI_EPISODE_INTERVAL": "TEMPORAL_SOURCE_INTERVAL_MULTIPLE_EPISODES",
            "TEMPORAL_INTERVAL_STILL_AMBIGUOUS": "TEMPORAL_SOURCE_INTERVAL_AMBIGUOUS",
            "TEMPORAL_REPRESENTATION_UNSUPPORTED": "TEMPORAL_SOURCE_INTERVAL_UNSUPPORTED",
        }.get(failure, "TEMPORAL_SOURCE_INTERVAL_AMBIGUOUS")
        constraint = dict(interval.get("constraint") or {})
        return {
            "present": specific,
            "code": code,
            "evidence_type": "source_temporal_interval",
            "evidence": constraint.get("source_excerpt"),
            "event_time": None,
            "event_interval": constraint,
            "message_time": None,
            "episode_specific": specific,
            "supported_episode_ids": list(interval.get("supported_episode_ids") or []),
            "logical_episode_groups": [
                list(group) for group in interval.get("logical_episode_groups") or []
            ],
            "episode_id": interval.get("episode_id") if specific else None,
            "near_boundary": empty_near_boundary(),
        }

    published = parse_dt(row.get("published_at"))
    if (
        published
        and trusted_live_source(row)
        and any(contemporaneous_live_wording(segment) for segment in event_segments)
    ):
        active = exact_active_episodes_at(published, episodes)
        support = logical_episode_support(active)
        supported_ids = list(support["supported_episode_ids"])
        specific = bool(support["episode_specific"])
        episode_id = support["episode_id"] if specific else None
        extension_form = any(
            trusted_live_publication_binding_extension_wording(segment)
            for segment in event_segments
        )
        if specific and not episode_id and extension_form:
            # The new bounded live forms may fall inside multiple persisted raw
            # rows already reconciled as one logical alert window. Reuse only an
            # existing persisted raw binding that belongs to that active logical
            # group; pre-existing live forms retain their previous no-winner rule.
            persisted_id = str(row.get("matched_episode_id") or "")
            if (
                str(matching.get("outcome") or "") == "unique_match"
                and persisted_id
                and persisted_id in supported_ids
            ):
                episode_id = persisted_id
        strict_specific = bool(specific and episode_id)
        return {
            "present": strict_specific,
            "code": (
                "TEMPORAL_CONTEMPORANEOUS_LIVE_WORDING"
                if strict_specific
                else "TEMPORAL_CONTEMPORANEOUS_LIVE_AMBIGUOUS_EPISODES"
            ),
            "evidence_type": "trusted_contemporaneous_live_message",
            "evidence": iso(published),
            "event_time": None,
            "event_interval": None,
            "message_time": iso(published),
            "episode_specific": strict_specific,
            "supported_episode_ids": supported_ids,
            "logical_episode_groups": list(support["logical_episode_groups"]),
            "episode_id": episode_id if strict_specific else None,
            "near_boundary": empty_near_boundary(),
        }

    explicit_segment = next((segment for segment in event_segments if explicit_alert_relation(segment)), None)
    if explicit_segment:
        same_day = episodes_intersecting_local_day(row, episodes)
        support = logical_episode_support(same_day)
        supported_ids = list(support["supported_episode_ids"])
        specific = bool(support["episode_specific"])
        return {
            "present": specific,
            "code": (
                "TEMPORAL_EXPLICIT_ALERT_RELATION"
                if specific
                else (
                    "TEMPORAL_EXPLICIT_ALERT_RELATION_AMBIGUOUS_DATE"
                    if supported_ids
                    else "TEMPORAL_EXPLICIT_ALERT_RELATION_NO_EPISODE"
                )
            ),
            "evidence_type": "generic_explicit_alert_relation",
            "evidence": explicit_segment,
            "event_time": None,
            "event_interval": None,
            "message_time": None,
            "episode_specific": specific,
            "supported_episode_ids": supported_ids,
            "logical_episode_groups": list(support["logical_episode_groups"]),
            "episode_id": support["episode_id"] if specific else None,
            "near_boundary": empty_near_boundary(),
        }

    return {
        "present": False,
        "code": "NO_STRICT_TEMPORAL_BINDING",
        "evidence_type": None,
        "evidence": None,
        "event_time": None,
        "event_interval": None,
        "message_time": None,
        "episode_specific": False,
        "supported_episode_ids": [],
        "logical_episode_groups": [],
        "episode_id": None,
        "near_boundary": empty_near_boundary(),
    }


def single_episode_day_inference(row: dict, matching: dict, episodes: list[dict]) -> dict:
    """
    Conservative sensitivity-only inference.

    A publication-time match can confirm that the report sits inside the sole
    tracked alert window of that local day, but it cannot choose among multiple
    episodes and is never treated as event-time proof.
    """
    same_day = episodes_intersecting_local_day(row, episodes)
    support = logical_episode_support(same_day)
    day_ids = list(support["supported_episode_ids"])
    local_day = publication_local_day(row)
    if not support["episode_specific"]:
        return {
            "present": False,
            "reason": "multiple_or_no_tracked_episodes_on_publication_local_date",
            "local_date": local_day.isoformat() if local_day else None,
            "supported_episode_ids": day_ids,
            "logical_episode_groups": list(support["logical_episode_groups"]),
            "episode_id": None,
        }
    matching_ids = set(matching.get("matched_episode_ids") or [])
    present = (
        matching.get("outcome") == "unique_match"
        and bool(matching_ids.intersection(day_ids))
    )
    return {
        "present": present,
        "reason": (
            "single_logical_episode_day_and_publication_window_consistent"
            if present
            else "single_logical_episode_day_but_publication_window_not_consistent"
        ),
        "local_date": local_day.isoformat() if local_day else None,
        "supported_episode_ids": day_ids,
        "logical_episode_groups": list(support["logical_episode_groups"]),
        "episode_id": support["episode_id"] if present else None,
    }

def dry_classify_existing_candidate(item: dict, state: dict) -> dict:
    city_key = str(item.get("city_key") or "")
    if city_key not in CITY_CONFIG:
        return {
            "proposed_outcome": "needs_review",
            "reason_codes": ["UNKNOWN_CITY"],
            "matching": {
                "outcome": "no_match",
                "matched_episode_ids": [],
                "logical_episode_groups": [],
                "matched_episode_id": None,
                "reason": "unknown_city",
            },
        }
    episodes = tracked_episodes_for_city(state, city_key)
    matching = match_candidate_to_episodes(item, episodes)
    return classify_candidate(item, city_key, episodes, matching)


def publisher_fulltext_requires_review(
    row: dict,
    reviewed: dict,
    *,
    strict_eligible: bool,
) -> bool:
    """Publisher full text is neutral evidence provenance, not a positive strict signal."""
    return (
        row.get("discovery_basis") == "publisher_fulltext"
        and not reviewed.get("usable")
        and not strict_eligible
    )


def classify_candidate(row: dict, city_key: str, episodes: list[dict], matching: dict | None = None) -> dict:
    matching = matching or match_candidate_to_episodes(row, episodes)

    candidate_exact = exact_city_classification_evidence(city_key, row)
    candidate_strict = strict_explosion_evidence(city_key, row)
    candidate_event_types = list(candidate_strict.get("event_types") or [])
    candidate_air_defense_context = air_defense_context_signal(classification_text(row))
    candidate_air_defense_action = air_defense_action_signal(classification_text(row))
    candidate_interception_claim = interception_claim_signal(classification_text(row))
    candidate_air = air_military_context_evidence(row)
    candidate_temporal = temporal_binding_evidence(
        row, candidate_strict, matching, episodes
    )
    candidate_same_attack = same_attack_context_evidence(
        city_key,
        row,
        candidate_strict,
        candidate_air,
        candidate_temporal,
        episodes,
    )
    candidate_inference = single_episode_day_inference(row, matching, episodes)

    reviewed = reviewed_provenance_adapter(row, city_key, episodes, matching)
    exact = merge_reviewed_presence(candidate_exact, reviewed["exact_city"])
    strict = merge_reviewed_presence(candidate_strict, reviewed["strict_explosion"])
    air = merge_reviewed_presence(candidate_air, reviewed["air_military_context"])
    same_attack = merge_reviewed_presence(
        candidate_same_attack, reviewed["same_attack_context"]
    )
    temporal = merge_reviewed_temporal(
        candidate_temporal, reviewed["temporal_binding"]
    )
    inference = dict(candidate_inference)
    if not inference.get("present") and reviewed["sensitivity_binding"].get("present"):
        inference = dict(reviewed["sensitivity_binding"])
        inference["local_date"] = publication_local_day(row).isoformat() if publication_local_day(row) else None
        inference["evidence_sources"] = ["review_provenance"]
    else:
        inference["evidence_sources"] = (
            ["candidate_evidence"] if inference.get("present") else []
        )

    text = classification_text(row)
    segments = classification_segments(row)
    publisher = str(row.get("publisher") or "")
    raw_title_snippet = f"{row.get('title') or ''} {row.get('snippet') or ''}"
    publisher_only_city = (
        not exact["present"]
        and bool(publisher)
        and city_mentioned(city_key, publisher)
        and city_mentioned(city_key, raw_title_snippet)
    )
    controlled_event_segments = [
        segment
        for segment in segments
        if city_mentioned(city_key, segment) and controlled_blast_nonmilitary_signal(segment)
    ]
    controlled = bool(controlled_event_segments)
    whole_message_non_air_defense_event = any(
        strict_attack_event_signal(segment)
        and any(event_type != "air_defense_action" for event_type in attack_event_types(segment))
        for segment in segments
    )
    pvo_only_complete_message = (
        trusted_live_source(row)
        and exact["present"]
        and not strict["present"]
        and not whole_message_non_air_defense_event
        and bool(AIR_DEFENSE_CONTEXT_RE.search(normalize_evidence_text(text)))
    )
    base_event_ok = (
        exact["present"]
        and strict["present"]
        and air["present"]
        and same_attack["present"]
    )
    strict_episode_id = (
        temporal.get("episode_id")
        if temporal.get("present") and temporal.get("episode_specific")
        else None
    )
    fulltext_requires_review = publisher_fulltext_requires_review(
        row,
        reviewed,
        strict_eligible=bool(base_event_ok and strict_episode_id),
    )

    reason_codes = []
    outcome = str(matching.get("outcome") or "no_match")
    if outcome == "unique_match":
        reason_codes.append("MATCH_UNIQUE")
        if not matching.get("matched_episode_id"):
            reason_codes.append("NO_CANONICAL_RAW_EPISODE_ID")
    elif outcome == "ambiguous_match":
        reason_codes.append("MATCH_AMBIGUOUS")
    else:
        reason_codes.append("MATCH_NONE")
    reason_codes.append("EXACT_CITY_EVENT_TEXT" if exact["present"] else "NO_EXACT_CITY_EVENT_TEXT")
    reason_codes.append("STRICT_EXPLOSION_EVIDENCE" if strict["present"] else "NO_STRICT_EXPLOSION_EVIDENCE")
    if candidate_event_types:
        reason_codes.append("ATTACK_EVENT_TYPES:" + ",".join(candidate_event_types))
    reason_codes.append("AIR_MILITARY_CONTEXT" if air["present"] else "NO_AIR_MILITARY_CONTEXT")
    if air["present"]:
        reason_codes.append("SAME_ATTACK_CONTEXT_SUPPORTED" if same_attack["present"] else "AIR_CONTEXT_NOT_LINKED_TO_EVENT")
    reason_codes.append(temporal.get("code") or "NO_STRICT_TEMPORAL_BINDING")
    for code in reviewed.get("reason_codes") or []:
        if code not in reason_codes:
            reason_codes.append(code)

    near_boundary = bool(
        (temporal.get("near_boundary") or {}).get("present")
        and (temporal.get("near_boundary") or {}).get("episode_specific")
    )
    if controlled:
        reason_codes.append("DETERMINISTIC_CONTROLLED_BLAST")
    if publisher_only_city:
        reason_codes.append("EXACT_CITY_ONLY_PUBLISHER_BRANDING")
    if pvo_only_complete_message:
        reason_codes.append("PVO_ONLY_COMPLETE_MESSAGE")
    if fulltext_requires_review:
        reason_codes.append("PUBLISHER_FULLTEXT_REQUIRES_REVIEW")

    near_boundary_episode_id = (
        (temporal.get("near_boundary") or {}).get("episode_id")
        if near_boundary
        else None
    )
    inferred_episode_id = inference.get("episode_id") if inference.get("present") else None

    proposed = "needs_review"
    proposed_matched_episode_id = None
    sensitivity_basis = None
    if controlled or publisher_only_city or pvo_only_complete_message:
        proposed = "rejected"
    elif fulltext_requires_review:
        proposed = "needs_review"
    elif base_event_ok and strict_episode_id:
        proposed = "approved_strict"
        proposed_matched_episode_id = strict_episode_id
    elif base_event_ok and near_boundary_episode_id:
        proposed = "approved_sensitivity"
        proposed_matched_episode_id = near_boundary_episode_id
        sensitivity_basis = "near_boundary"
        reason_codes.append("SENSITIVITY_NEAR_BOUNDARY")
    elif base_event_ok and inferred_episode_id:
        proposed = "approved_sensitivity"
        proposed_matched_episode_id = inferred_episode_id
        sensitivity_basis = str(inference.get("basis") or "inferred_same_attack")
        reason_codes.append(
            "SENSITIVITY_NEAR_BOUNDARY"
            if sensitivity_basis == "near_boundary"
            else "SENSITIVITY_INFERRED_SAME_ATTACK"
        )
    elif (
        base_event_ok
        and len(episode_representation_clusters(episodes_intersecting_local_day(row, episodes))) > 1
    ):
        reason_codes.append("MULTI_EPISODE_DATE_REQUIRES_EPISODE_SPECIFIC_TEMPORAL_PROOF")

    return {
        "proposed_outcome": proposed,
        "proposed_matched_episode_id": proposed_matched_episode_id,
        "matching": matching,
        "candidate_evidence": {
            "exact_city": candidate_exact,
            "strict_explosion": candidate_strict,
            "event_types": candidate_event_types,
            "air_military_context": candidate_air,
            "same_attack_context": candidate_same_attack,
            "temporal_binding": candidate_temporal,
            "single_episode_day_inference": candidate_inference,
        },
        "review_provenance_adapter": reviewed,
        "exact_city_classification_evidence": exact,
        "strict_explosion_evidence": strict,
        "event_types": candidate_event_types,
        "air_defense_context": candidate_air_defense_context,
        "air_defense_action": candidate_air_defense_action,
        "interception_claim": candidate_interception_claim,
        "air_military_context": air,
        "same_attack_context": same_attack,
        "temporal_binding": temporal,
        "single_episode_day_inference": inference,
        "controlled_blast_event_segments": controlled_event_segments,
        "sensitivity_basis": sensitivity_basis,
        "reason_codes": reason_codes,
    }

def classification_evidence_payload(decision: dict) -> dict:
    return {
        "exact_city": decision["exact_city_classification_evidence"],
        "strict_explosion": decision["strict_explosion_evidence"],
        "event_types": list(decision.get("event_types") or []),
        "air_defense_context": bool(decision.get("air_defense_context")),
        "air_defense_action": bool(decision.get("air_defense_action")),
        "interception_claim": bool(decision.get("interception_claim")),
        "air_military_context": decision["air_military_context"],
        "same_attack_context": decision["same_attack_context"],
        "temporal_binding": decision["temporal_binding"],
        "single_episode_day_inference": decision["single_episode_day_inference"],
        "controlled_blast_event_segments": decision["controlled_blast_event_segments"],
        "sensitivity_basis": decision["sensitivity_basis"],
        "classification_episode_id": decision["proposed_matched_episode_id"],
        "candidate_evidence": decision.get("candidate_evidence") or {},
        "review_provenance_adapter": decision.get("review_provenance_adapter") or {},
    }


def apply_classification_decision(item: dict, decision: dict, matching: dict) -> None:
    apply_matching_result(item, matching)
    status = str(decision.get("proposed_outcome") or "needs_review")
    item["status"] = status
    item["classification_reason_codes"] = list(decision.get("reason_codes") or [])
    item["classification_evidence"] = classification_evidence_payload(decision)
    item["event_types"] = list(decision.get("event_types") or [])
    item["review_note"] = (
        "evidence-layered auto-classification"
        if status in {"approved_strict", "approved_sensitivity", "rejected"}
        else "evidence-layered classification requires manual review"
    )
    if status in {"approved_strict", "approved_sensitivity"}:
        item["matched_episode_id"] = decision.get("proposed_matched_episode_id")


def composition_sequence_signals(text: str) -> list[str]:
    low = normalize_evidence_text(text)
    signals = []
    if re.search(r"\bповторн\w*.{0,20}\bвибух\w*", low):
        signals.append("repeated_explosions")
    if re.search(r"\bсері\w*.{0,20}\bвибух\w*", low):
        signals.append("explosion_series")
    if re.search(r"\bвибух\w*.{0,20}\b(?:не\s+вщух|не\s+припин)", low):
        signals.append("ongoing_explosions")
    if re.search(r"\b(?:знову|ще\s+раз).{0,25}\bвибух\w*", low):
        signals.append("renewed_explosion")
    return signals


def composition_weapon_families(text: str) -> set[str]:
    low = normalize_evidence_text(text)
    families = set()
    if re.search(r"\b(?:баліст\w*|іскандер\w*)", low):
        families.add("ballistic")
    if re.search(r"\b(?:ракет\w*|циркон\w*|крилат\w*)", low):
        families.add("missile")
    if re.search(r"\b(?:бпла|дрон\w*|безпілот\w*|шахед\w*|shahed\w*)", low):
        families.add("uav")
    if re.search(r"\b(?:каб\w*|авіабомб\w*)", low):
        families.add("guided_bomb")
    return families


def composition_neighbor_check(moment: datetime, target_episode: dict, episodes: list[dict]) -> dict:
    target_id = str(target_episode.get("episode_id") or "")
    active = exact_active_episodes_at(moment, episodes)
    active_ids = [str(ep.get("episode_id") or "") for ep in active]
    target_active = any(str(ep.get("episode_id") or "") == target_id for ep in active)
    conflicts = [
        str(ep.get("episode_id") or "")
        for ep in active
        if str(ep.get("episode_id") or "") != target_id
        and not same_episode_representation(ep, target_episode)
    ]
    return {
        "passed": target_active and not conflicts,
        "moment": iso(moment),
        "active_episode_ids": active_ids,
        "conflicting_neighbor_episode_ids": sorted(set(conflicts)),
    }


def composition_same_attack_compatibility(
    temporal_row: dict,
    context_row: dict,
    target_episode: dict,
    episodes: list[dict],
) -> dict:
    target_id = str(target_episode.get("episode_id") or "")
    reviewed_pair = reviewed_composition_pair(temporal_row, context_row, target_id)
    if reviewed_pair:
        return {
            "present": True,
            "reason": "reviewed_composition_same_attack_compatible",
            "basis": [
                "reviewed_exact_contributor_pair",
                "reviewed_same_attack_compatible",
                "reviewed_neighbor_check_passed",
            ],
            "gap_seconds": None,
            "temporal_neighbor_check": reviewed_pair.get("neighboring_alert_check"),
            "context_neighbor_check": reviewed_pair.get("neighboring_alert_check"),
            "evidence_source": "review_provenance",
        }

    temporal_time = parse_dt(temporal_row.get("published_at"))
    context_time = parse_dt(context_row.get("published_at"))
    if not temporal_time or not context_time:
        return {"present": False, "reason": "missing_publication_timestamp_for_compatibility_check"}

    temporal_text = classification_text(temporal_row)
    context_text = classification_text(context_row)
    if retrospective_or_cumulative_wording(temporal_text) or retrospective_or_cumulative_wording(context_text):
        return {"present": False, "reason": "retrospective_or_cumulative_wording"}

    temporal_neighbor = composition_neighbor_check(temporal_time, target_episode, episodes)
    context_neighbor = composition_neighbor_check(context_time, target_episode, episodes)
    if not temporal_neighbor["passed"] or not context_neighbor["passed"]:
        return {
            "present": False,
            "reason": "neighboring_alert_conflict",
            "temporal_neighbor_check": temporal_neighbor,
            "context_neighbor_check": context_neighbor,
        }

    gap_seconds = abs((context_time - temporal_time).total_seconds())
    if gap_seconds > COMPOSITION_MAX_GAP_MINUTES * 60:
        return {
            "present": False,
            "reason": "temporal_gap_too_large",
            "gap_seconds": gap_seconds,
        }

    basis = [f"timestamps_within_{COMPOSITION_MAX_GAP_MINUTES}m"]
    if (
        reviewed_same_attack_basis_for_target(temporal_row, str(target_episode.get("episode_id") or ""))
        or reviewed_same_attack_basis_for_target(context_row, str(target_episode.get("episode_id") or ""))
    ):
        basis.append("reviewed_same_attack_basis")
    sequence = composition_sequence_signals(temporal_text)
    if sequence:
        basis.extend(sequence)

    shared_weapons = sorted(
        composition_weapon_families(temporal_text)
        & composition_weapon_families(context_text)
    )
    if shared_weapons:
        basis.append("shared_weapon_family:" + ",".join(shared_weapons))

    if (
        trusted_same_attack_source(context_row)
        and gap_seconds <= COMPOSITION_TIGHT_TRUSTED_GAP_MINUTES * 60
    ):
        basis.append(f"trusted_context_within_{COMPOSITION_TIGHT_TRUSTED_GAP_MINUTES}m")

    if len(basis) == 1:
        return {
            "present": False,
            "reason": "insufficient_same_attack_link_beyond_timestamp_proximity",
            "gap_seconds": gap_seconds,
            "temporal_neighbor_check": temporal_neighbor,
            "context_neighbor_check": context_neighbor,
        }

    return {
        "present": True,
        "reason": "compatible_same_attack_sequence",
        "basis": basis,
        "gap_seconds": gap_seconds,
        "temporal_neighbor_check": temporal_neighbor,
        "context_neighbor_check": context_neighbor,
    }


def compose_episode_candidates(
    city_key: str,
    target_episode: dict,
    candidates: list[dict],
    episodes: list[dict],
) -> dict:
    target_id = str(target_episode.get("episode_id") or "")
    reviewed_composition_participants = set()
    for provenance_owner in candidates:
        binding = reviewed_composition_binding_for_target(provenance_owner, target_id)
        if not binding:
            continue
        reviewed_composition_participants.add(
            str(binding.get("anchor_candidate_id") or "")
        )
        reviewed_composition_participants.update(
            str(value) for value in binding.get("contributor_candidate_ids") or []
        )

    evaluated = []
    for item in sorted(candidates, key=lambda row: str(row.get("candidate_id") or "")):
        if str(item.get("city_key") or "") != city_key:
            continue
        if str(item.get("matched_episode_id") or "") != target_id:
            continue
        if str(item.get("status") or "") == "rejected":
            continue
        matching = match_candidate_to_episodes(item, episodes)
        decision = classify_candidate(item, city_key, episodes, matching)
        if (
            "DETERMINISTIC_CONTROLLED_BLAST" in decision["reason_codes"]
            or "PVO_ONLY_COMPLETE_MESSAGE" in decision["reason_codes"]
            or "PUBLISHER_FULLTEXT_REQUIRES_REVIEW" in decision["reason_codes"]
        ):
            continue
        if (
            retrospective_or_cumulative_wording(classification_text(item))
            and str(item.get("candidate_id") or "") not in reviewed_composition_participants
        ):
            continue
        evaluated.append((item, decision))

    anchors = []
    contexts = []
    for item, decision in evaluated:
        temporal = decision.get("temporal_binding") or {}
        if (
            decision["exact_city_classification_evidence"].get("present")
            and decision["strict_explosion_evidence"].get("present")
            and temporal.get("present")
            and temporal.get("episode_specific")
            and target_id in {
                str(value) for value in temporal.get("supported_episode_ids") or []
            }
        ):
            anchors.append((item, decision))
        if (
            decision["exact_city_classification_evidence"].get("present")
            and decision["strict_explosion_evidence"].get("present")
            and decision["air_military_context"].get("present")
            and decision["same_attack_context"].get("present")
        ):
            contexts.append((item, decision))

    compatible_pairs = []
    for anchor_item, anchor_decision in anchors:
        for context_item, context_decision in contexts:
            if anchor_item.get("candidate_id") == context_item.get("candidate_id"):
                continue
            compatibility = composition_same_attack_compatibility(
                anchor_item, context_item, target_episode, episodes
            )
            if not compatibility.get("present"):
                continue
            compatible_pairs.append((
                float(compatibility.get("gap_seconds") or 0),
                str(anchor_item.get("candidate_id") or ""),
                str(context_item.get("candidate_id") or ""),
                anchor_item,
                anchor_decision,
                context_item,
                context_decision,
                compatibility,
            ))

    if not compatible_pairs:
        return {
            "target_episode_id": target_id,
            "city_key": city_key,
            "final_composed_verdict": "no_composed_strict",
            "contributing_candidate_ids": [],
            "anchor_candidate_id": None,
            "reason_codes": ["NO_SAFE_EPISODE_LEVEL_COMPOSITION"],
            "candidate_count_considered": len(evaluated),
            "temporal_anchor_candidate_ids": sorted(
                str(item.get("candidate_id") or "") for item, _ in anchors
            ),
            "air_context_candidate_ids": sorted(
                str(item.get("candidate_id") or "") for item, _ in contexts
            ),
        }

    compatible_pairs.sort(key=lambda row: (row[0], row[1], row[2]))
    (
        _gap,
        _anchor_id,
        _context_id,
        anchor_item,
        anchor_decision,
        context_item,
        context_decision,
        compatibility,
    ) = compatible_pairs[0]
    anchor_id = str(anchor_item.get("candidate_id") or "")
    context_id = str(context_item.get("candidate_id") or "")
    temporal = anchor_decision["temporal_binding"]
    return {
        "target_episode_id": target_id,
        "city_key": city_key,
        "final_composed_verdict": "approved_strict",
        "anchor_candidate_id": anchor_id,
        "contributing_candidate_ids": [anchor_id, context_id],
        "contributing_candidates": [
            {
                "candidate_id": anchor_id,
                "roles": ["explosion_evidence", "temporal_proof"],
                "role_sources": {
                    "explosion_evidence": list(
                        anchor_decision["strict_explosion_evidence"].get("evidence_sources") or []
                    ),
                    "temporal_proof": list(temporal.get("evidence_sources") or []),
                },
                "temporal_code": temporal.get("code"),
                "temporal_evidence_type": temporal.get("evidence_type"),
            },
            {
                "candidate_id": context_id,
                "roles": ["explosion_evidence", "air_military_context"],
                "role_sources": {
                    "explosion_evidence": list(
                        context_decision["strict_explosion_evidence"].get("evidence_sources") or []
                    ),
                    "air_military_context": list(
                        context_decision["air_military_context"].get("evidence_sources") or []
                    ),
                    "same_attack_context": list(
                        context_decision["same_attack_context"].get("evidence_sources") or []
                    ),
                },
                "same_attack_reason": context_decision["same_attack_context"].get("reason"),
            },
        ],
        "same_attack_compatibility": compatibility,
        "neighboring_alert_check": {
            "passed": True,
            "temporal_source": compatibility.get("temporal_neighbor_check"),
            "air_context_source": compatibility.get("context_neighbor_check"),
        },
        "reason_codes": [
            "COMPOSED_STRICT_SAME_EPISODE",
            "COMPOSED_TEMPORAL_PROOF",
            "COMPOSED_AIR_MILITARY_CONTEXT",
            "COMPOSED_SAME_ATTACK_COMPATIBLE",
            "COMPOSED_NEIGHBOR_CHECK_PASSED",
        ],
    }


def apply_episode_composition(
    queue: list[dict],
    state: dict,
    target_episode_ids: set[str] | None = None,
) -> dict:
    groups: dict[tuple[str, str], list[dict]] = {}
    for item in queue:
        if not isinstance(item, dict):
            continue
        if str(item.get("status") or "") == "rejected":
            continue
        city_key = str(item.get("city_key") or "")
        episode_id = str(item.get("matched_episode_id") or "")
        if city_key not in CITY_CONFIG or not episode_id:
            continue
        if target_episode_ids is not None and episode_id not in target_episode_ids:
            continue
        groups.setdefault((city_key, episode_id), []).append(item)

    counts = {
        "episode_groups_checked": 0,
        "composed_strict": 0,
        "candidate_status_changes": 0,
        "composed_strict_episode_ids": [],
    }
    composed_ids = []
    for (city_key, episode_id), candidates in sorted(groups.items()):
        if len(candidates) < 2:
            continue
        episodes = tracked_episodes_for_city(state, city_key)
        target_episode = next(
            (ep for ep in episodes if str(ep.get("episode_id") or "") == episode_id),
            None,
        )
        if not target_episode:
            continue
        counts["episode_groups_checked"] += 1
        composition = compose_episode_candidates(
            city_key, target_episode, candidates, episodes
        )
        if composition.get("final_composed_verdict") != "approved_strict":
            continue

        existing_strict = [
            item
            for item in candidates
            if str(item.get("status") or "") == "approved_strict"
            and str(item.get("matched_episode_id") or "") == episode_id
        ]
        if existing_strict:
            continue

        anchor_id = str(composition.get("anchor_candidate_id") or "")
        anchor = next(
            (item for item in candidates if str(item.get("candidate_id") or "") == anchor_id),
            None,
        )
        if not anchor:
            raise AssertionError("Composed strict verdict has no deterministic anchor candidate")

        before_status = str(anchor.get("status") or "")
        anchor["status"] = "approved_strict"
        anchor["matched_episode_id"] = episode_id
        anchor["composition_provenance"] = composition
        evidence = dict(anchor.get("classification_evidence") or {})
        evidence["episode_level_composition"] = composition
        anchor["classification_evidence"] = evidence
        reason_codes = list(anchor.get("classification_reason_codes") or [])
        for code in composition.get("reason_codes") or []:
            if code not in reason_codes:
                reason_codes.append(code)
        anchor["classification_reason_codes"] = reason_codes
        anchor["review_note"] = "episode-level composed strict classification"

        counts["composed_strict"] += 1
        composed_ids.append(episode_id)
        if before_status != "approved_strict":
            counts["candidate_status_changes"] += 1

    counts["composed_strict_episode_ids"] = sorted(set(composed_ids))
    return counts


def add_candidates(
    queue: list[dict],
    city_key: str,
    rows: list[dict],
    due: list[tuple[dict, dict]],
    tracked_episodes: list[dict],
    now: datetime,
) -> tuple[int, int]:
    by_id = {str(x.get("candidate_id")): x for x in queue if isinstance(x, dict) and x.get("candidate_id")}
    episode_ids = sorted({ep["episode_id"] for ep, _ in due})
    check_labels = sorted({check["label"] for _, check in due})
    added = 0
    auto_approved_strict = 0
    for row in rows:
        cid = candidate_id(city_key, row["url"], row["title"])
        matching = match_candidate_to_episodes(row, tracked_episodes)
        existing = by_id.get(cid)
        if existing:
            existing["trigger_episode_ids"] = sorted(set(existing.get("trigger_episode_ids") or []) | set(episode_ids))
            existing["trigger_check_labels"] = sorted(set(existing.get("trigger_check_labels") or []) | set(check_labels))
            existing["last_seen_at"] = iso(now)
            if existing.get("status") == "needs_review":
                before_status = existing.get("status")
                apply_matching_result(existing, matching)
                if existing.get("status") != before_status:
                    raise AssertionError("Episode matching must not change candidate status")
            continue

        decision_input = {**row, "source": row.get("source") or "Google News RSS"}
        decision = classify_candidate(decision_input, city_key, tracked_episodes, matching)
        status = decision["proposed_outcome"]
        item = {
            "candidate_id": cid,
            "city_key": city_key,
            "city": CITY_CONFIG[city_key]["label"],
            "status": status,
            "source": decision_input["source"],
            "publisher": row.get("publisher"),
            "publisher_url": row.get("publisher_url"),
            "url": row["url"],
            "title": row["title"],
            "published_at": row.get("published_at"),
            "snippet": row.get("snippet"),
            "discovery_basis": row.get("discovery_basis"),
            "resolved_url": row.get("resolved_url"),
            "matched_text_excerpt": row.get("matched_text_excerpt"),
            "first_discovered_at": iso(now),
            "last_seen_at": iso(now),
            "trigger_episode_ids": episode_ids,
            "trigger_check_labels": check_labels,
            "matched_episode_id": None,
            "classification_reason_codes": decision["reason_codes"],
            "classification_evidence": classification_evidence_payload(decision),
            "review_note": (
                "evidence-layered auto-classification"
                if status in {"approved_strict", "approved_sensitivity", "rejected"}
                else "evidence-layered classification requires manual review"
            ),
            "note": (
                "Discovery relevance, publication-time episode matching, and strict/sensitivity classification are separate. "
                "Publication time may build a candidate episode set but never supplies event time or chooses an approved event episode. "
                "Strict requires exact-city explosion/strike evidence, aerial-war context, and episode-specific temporal proof. "
                "Sensitivity requires explicit near-boundary timing or conservative single-episode-day inference; multi-episode dates "
                "without episode-specific proof remain manual review. PVO-only and non-military controlled blasts are rejected."
            ),
        }
        apply_matching_result(item, matching)
        if status in {"approved_strict", "approved_sensitivity"}:
            item["matched_episode_id"] = decision.get("proposed_matched_episode_id")
        queue.append(item)
        by_id[cid] = item
        added += 1
        if status == "approved_strict":
            auto_approved_strict += 1
    return added, auto_approved_strict

def self_test() -> None:
    assert len(CITY_CONFIG) >= 23
    assert city_mentioned("poltava", "У Полтаві пролунали вибухи")
    assert not city_mentioned("poltava", "На Полтавщині пролунали вибухи")
    assert city_mentioned("vinnytsia", "У Вінниці було чутно вибух")
    assert not city_mentioned("vinnytsia", "На Вінниччині було гучно")

    # IR01-IR04: discovery is broad, strict explosion evidence is narrower,
    # and audited aerial-war vocabulary includes KAB/Banderol.
    assert explosion_relevant("У Львові було гучно, працювала ППО")
    assert explosion_relevant("У Львові зафіксували влучання")
    assert strict_explosion_signal("У Києві працюють сили ППО")
    assert not strict_explosion_signal("У Полтаві було гучно")
    assert strict_explosion_signal("У Дніпрі пролунав вибух")
    assert air_military_context("Повідомляли про КАБ у напрямку міста")
    assert air_military_context("Повітряні сили попередили про Бандероль")
    assert air_military_context("Ракета рухається у напрямку міста")
    assert explicit_alert_relation("Вибух стався після оголошення тривоги")
    assert explicit_alert_relation("У місті пролунав вибух, коли тривала повітряна тривога")
    assert attack_event_types("У Полтаві влучання пошкодило будинок і спричинило пожежу") == ["impact", "damage", "fire"]
    assert attack_event_types("У Полтаві працює ППО") == ["air_defense_action"]
    assert not air_defense_action_signal("У Полтаві можлива робота ППО")
    assert not air_defense_action_signal("У Полтаві не лякайтеся, може бути чутно роботу ППО")
    assert not air_defense_action_signal("У Полтаві ППО готова до роботи")
    assert strict_attack_event_signal("У Полтаві внаслідок атаки БпЛА пошкоджено будинок")
    assert strict_attack_event_signal("У Полтаві після удару БпЛА виникла пожежа")
    assert not strict_attack_event_signal("У Полтаві під час повітряної тривоги сталася пожежа у квартирі")
    assert not strict_attack_event_signal("У Полтаві пошкоджено водогін через аварію")
    for live_phrase in (
        "У Києві лунає вибух",
        "У Києві лунають вибухи",
        "У Києві лунають повторні вибухи",
        "У Києві чутно вибух",
        "У Києві чутно вибухи",
        "У Києві чутно серію вибухів",
        "У Києві чути вибух",
        "У Києві чути вибухи",
        "У Києві чути: серію вибухів",
    ):
        assert contemporaneous_live_wording(live_phrase), live_phrase
    for retrospective_phrase in (
        "У Києві було чути вибухи",
        "У Києві було чутно вибух",
        "У Києві раніше чули вибухи",
        "Протягом дня у Києві було чути вибухи",
        "Київ під ударом цілий день: вибухи лунали у різних районах",
    ):
        assert not contemporaneous_live_wording(retrospective_phrase), retrospective_phrase

    vinnytsia_branding = {
        "title": "Вибухи у кар’єрі на Вінниччині: де та коли проводитимуть роботи - Вінниця Преспоінт",
        "snippet": "Вибухи у кар’єрі на Вінниччині: де та коли проводитимуть роботи Вінниця Преспоінт",
        "publisher": "Вінниця Преспоінт",
        "source": "Google News RSS",
        "published_at": "2026-09-18T10:30:00Z",
    }
    assert not exact_city_classification_evidence("vinnytsia", vinnytsia_branding)["present"]

    dt = datetime(2026, 9, 18, 10, tzinfo=UTC)
    poltava_ep = make_episode("poltava", dt, dt + timedelta(hours=1))
    assert [x["label"] for x in poltava_ep["checks"]] == ["immediate", "24h", "72h", "7d"]
    assert poltava_ep["alert_start_date_kyiv"] == "2026-09-18"

    cutoff = datetime(2026, 9, 18, 12, tzinfo=UTC)
    timing_state = {"cities": {"poltava": {"episodes": [
        {"episode_id": "timing-a", "checks": [{"label": "A", "due_at": iso(cutoff - timedelta(seconds=1)), "checked_at": None}]},
        {"episode_id": "timing-b", "checks": [{"label": "B", "due_at": iso(cutoff + timedelta(seconds=1)), "checked_at": None}]},
    ]}}}
    timing_due = due_checks(timing_state, cutoff)
    assert len(timing_due["poltava"]) == 1
    for _, check in timing_due["poltava"]:
        check["checked_at"] = iso(cutoff)
    assert due_check_counts(timing_due) == (1, 1, 0)
    assert checks_became_due_between(timing_state, cutoff, cutoff + timedelta(seconds=2)) == 1
    assert len(due_checks(timing_state, cutoff + timedelta(seconds=2))["poltava"]) == 1

    fulltext_calls = []
    def unexpected_fulltext_fetch(url: str):
        fulltext_calls.append(url)
        raise AssertionError("full-text fetch should not run when RSS already passes")

    rss_row, fetched, rescued = build_google_news_candidate(
        "poltava", "У Полтаві пролунали вибухи", "", "https://news.google.test/rss-item-1",
        "Test", "", iso(dt), fulltext_fetcher=unexpected_fulltext_fetch,
    )
    assert rss_row and rss_row["discovery_basis"] == "rss_title_snippet"
    assert not fetched and not rescued and not fulltext_calls

    rescued_row, fetched, rescued = build_google_news_candidate(
        "poltava", "Новини Полтави", "Оперативне оновлення", "https://news.google.test/rss-item-2",
        "Test", "", iso(dt),
        fulltext_fetcher=lambda _url: ("У Полтаві пролунали вибухи під час повітряної тривоги.", "https://publisher.test/article-2"),
    )
    assert rescued_row and fetched and rescued and rescued_row["discovery_basis"] == "publisher_fulltext"

    discovery_queries = dict(google_news_query_families("Полтава"))
    assert "вибух" in discovery_queries["explosion"]
    assert "влучив" in discovery_queries["impact_arrival"]
    assert "приліт" in discovery_queries["impact_arrival"]
    assert "атакував" in discovery_queries["strike"]
    assert "пошкоджено" in discovery_queries["attack_consequence"]
    assert "пожежа" in discovery_queries["attack_consequence"]
    assert "ППО збила" in discovery_queries["air_defense_action"]
    assert len(discovery_queries) == len(GOOGLE_NEWS_QUERY_FAMILIES)

    strict_base = {
        "title": "У Полтаві під час повітряної тривоги пролунали вибухи",
        "publisher": "Test",
        "publisher_url": None,
        "published_at": iso(dt + timedelta(minutes=30)),
        "snippet": "",
        "resolved_url": None,
        "matched_text_excerpt": None,
        "source": "Google News RSS",
    }
    strict_decision = classify_candidate(strict_base, "poltava", [poltava_ep])
    assert strict_decision["proposed_outcome"] == "approved_strict"
    assert strict_decision["temporal_binding"]["code"] == "TEMPORAL_EXPLICIT_ALERT_RELATION"

    due = [(poltava_ep, poltava_ep["checks"][0])]
    rss_queue = []
    rss_added, rss_auto = add_candidates(
        rss_queue, "poltava",
        [{**strict_base, "url": "https://news.google.test/rss-auto", "discovery_basis": "rss_title_snippet"}],
        due, [poltava_ep], dt,
    )
    assert rss_added == 1 and rss_auto == 1 and rss_queue[0]["status"] == "approved_strict"

    # Publisher full-text provenance is neutral: it may auto-classify only
    # when every ordinary strict gate independently passes.
    fulltext_queue = []
    fulltext_added, fulltext_auto = add_candidates(
        fulltext_queue, "poltava",
        [{**strict_base, "url": "https://news.google.test/fulltext-review", "discovery_basis": "publisher_fulltext", "matched_text_excerpt": strict_base["title"]}],
        due, [poltava_ep], dt,
    )
    assert fulltext_added == 1 and fulltext_auto == 1
    assert fulltext_queue[0]["status"] == "approved_strict"
    assert "PUBLISHER_FULLTEXT_REQUIRES_REVIEW" not in fulltext_queue[0]["classification_reason_codes"]

    # Unified attack-event hardening: damage/fire require attack causality and
    # still pass exact-city, air-context and episode-specific temporal gates.
    attack_event_positive_cases = (
        ("У Полтаві під час повітряної тривоги внаслідок атаки БпЛА пошкоджено будинок.", ["damage"]),
        ("У Полтаві під час повітряної тривоги після удару БпЛА виникла пожежа.", ["strike", "fire"]),
        ("У Полтаві під час повітряної тривоги БпЛА влучив у будинок, пошкоджено фасад і виникла пожежа.", ["impact", "damage", "fire"]),
    )
    for title, expected_types in attack_event_positive_cases:
        row = {**strict_base, "title": title, "snippet": ""}
        decision = classify_candidate(row, "poltava", [poltava_ep])
        assert decision["proposed_outcome"] == "approved_strict", decision
        assert decision["event_types"] == expected_types, decision

    attack_event_negative_cases = (
        "У Полтаві під час повітряної тривоги сталася пожежа у квартирі.",
        "У Полтаві під час повітряної тривоги пошкоджено водогін через аварію.",
        "На Полтавщині під час повітряної тривоги внаслідок атаки БпЛА виникла пожежа.",
    )
    for title in attack_event_negative_cases:
        row = {**strict_base, "title": title, "snippet": ""}
        decision = classify_candidate(row, "poltava", [poltava_ep])
        assert decision["proposed_outcome"] != "approved_strict", decision

    retrospective_damage = {
        **strict_base,
        "title": "У Полтаві повідомили про наслідки нічної атаки: пошкоджено будинок.",
        "snippet": "",
    }
    retrospective_damage_decision = classify_candidate(retrospective_damage, "poltava", [poltava_ep])
    assert retrospective_damage_decision["proposed_outcome"] not in {"approved_strict", "approved_sensitivity"}, retrospective_damage_decision

    # Air-defense action is now a canonical event class. It must still pass
    # exact-city, same-attack/air-context and temporal attribution gates.
    ppo_action_controls = (
        (
            "ppo-action-only",
            "У Полтаві під час повітряної тривоги працює ППО.",
            ["air_defense_action"],
            False,
        ),
        (
            "ppo-action-plus-explosion",
            "У Полтаві під час повітряної тривоги чути вибухи — працює ППО.",
            ["explosion", "air_defense_action"],
            False,
        ),
        (
            "ppo-interception",
            "У Полтаві під час повітряної тривоги ППО збила БпЛА.",
            ["air_defense_action"],
            True,
        ),
    )
    for label, title, expected_types, expected_interception in ppo_action_controls:
        row = {**strict_base, "candidate_id": label, "title": title, "snippet": ""}
        decision = classify_candidate(row, "poltava", [poltava_ep])
        assert decision["air_defense_context"], decision
        assert decision["air_defense_action"], decision
        assert decision["interception_claim"] is expected_interception, decision
        assert decision["event_types"] == expected_types, decision
        assert decision["proposed_outcome"] == "approved_strict", decision

    # Prediction, warning and generic readiness/capability remain non-events.
    ppo_negative_controls = (
        "У Полтаві під час повітряної тривоги можлива робота ППО.",
        "У Полтаві під час повітряної тривоги не лякайтеся, може бути чутно роботу ППО.",
        "У Полтаві під час повітряної тривоги ППО готова до роботи.",
    )
    for title in ppo_negative_controls:
        row = {**strict_base, "title": title, "snippet": ""}
        decision = classify_candidate(row, "poltava", [poltava_ep])
        assert decision["air_defense_context"], decision
        assert not decision["air_defense_action"], decision
        assert "air_defense_action" not in decision["event_types"], decision
        assert decision["proposed_outcome"] != "approved_strict", decision

    # Explicit explosion + PPO remains strict and now preserves both event types.
    air_defense_positive_cases = (
        "У Полтаві під час повітряної тривоги вибухи, які було чутно у місті — робота нашої ППО.",
        "У Полтаві чути вибухи — працює ППО.",
        "Полтава: лунають вибухи — працює ППО.",
    )
    for title in air_defense_positive_cases:
        row = {
            **strict_base,
            "title": title,
            "snippet": "",
            "source": "Telegram / СУСПІЛЬНЕ НОВИНИ",
            "publisher": "СУСПІЛЬНЕ НОВИНИ",
        }
        decision = classify_candidate(row, "poltava", [poltava_ep])
        assert decision["strict_explosion_evidence"]["present"], decision
        assert decision["air_defense_action"], decision
        assert "air_defense_action" in decision["event_types"], decision
        assert decision["air_military_context"]["present"], decision
        assert decision["same_attack_context"]["present"], decision
        assert decision["proposed_outcome"] == "approved_strict", decision
        assert "PVO_ONLY_COMPLETE_MESSAGE" not in decision["reason_codes"], decision

    # Mandatory: Vinnytsia regional/quarry wording plus publisher branding is
    # neither semantic exact-city evidence nor strict.
    vinnytsia_decision = classify_candidate(vinnytsia_branding, "vinnytsia", [])
    assert not vinnytsia_decision["exact_city_classification_evidence"]["present"]
    assert vinnytsia_decision["proposed_outcome"] != "approved_strict"
    assert "EXACT_CITY_ONLY_PUBLISHER_BRANDING" in vinnytsia_decision["reason_codes"]

    # Mandatory: late-discovered Ternopil evidence can use an already tracked
    # episode, and explicit during-alert explosion wording is strict-eligible.
    ternopil_ep = make_episode("ternopil", dt, dt + timedelta(hours=1))
    ternopil_row = {
        **strict_base,
        "title": "У Тернополі пролунав вибух під час тривоги: перед цим повідомляли про рух БпЛА на місто",
        "trigger_check_labels": ["72h"],
    }
    ternopil_decision = classify_candidate(ternopil_row, "ternopil", [ternopil_ep])
    assert ternopil_decision["matching"]["outcome"] == "unique_match"
    assert ternopil_decision["proposed_outcome"] == "approved_strict"

    # Mandatory: Odesa explicit during-alert case is strict; explosion + drone
    # context without event-time evidence is sensitivity, never publication-time strict.
    odesa_ep = make_episode("odesa", dt, dt + timedelta(hours=1))
    odesa_explicit = {
        **strict_base,
        "title": "В Одесі під час повітряної тривоги пролунав вибух",
    }
    assert classify_candidate(odesa_explicit, "odesa", [odesa_ep])["proposed_outcome"] == "approved_strict"

    odesa_drone = {
        **strict_base,
        "title": "Вибух пролунав в Одесі: Росія атакує місто реактивними дронами",
    }
    odesa_drone_decision = classify_candidate(odesa_drone, "odesa", [odesa_ep])
    assert odesa_drone_decision["proposed_outcome"] == "approved_sensitivity"
    assert not odesa_drone_decision["temporal_binding"]["present"]
    assert odesa_drone_decision["sensitivity_basis"] == "inferred_same_attack"

    # Mandatory: Poltava heard-explosion + adjacent aerial context from a trusted
    # source is sensitivity when the event clock is unresolved.
    poltava_suspilne = {
        **strict_base,
        "title": "У Полтаві чули звук вибуху, над містом видно дим. Раніше Повітряні сили повідомляли про Бандероль у напрямку Полтавщини.",
        "snippet": "",
        "source": "Telegram / СУСПІЛЬНЕ НОВИНИ",
        "publisher": "СУСПІЛЬНЕ НОВИНИ",
    }
    poltava_decision = classify_candidate(poltava_suspilne, "poltava", [poltava_ep])
    assert poltava_decision["proposed_outcome"] == "approved_sensitivity"
    assert poltava_decision["sensitivity_basis"] == "inferred_same_attack"

    # Mandatory KAB case + IR17 Mykolaiv real overlap: KAB is recognized as
    # aerial context, but two distinct overlapping alerts stay review-required.
    mykolaiv_a = make_episode("mykolaiv", dt, dt + timedelta(hours=1))
    mykolaiv_b = make_episode("mykolaiv", dt + timedelta(minutes=20), dt + timedelta(hours=1, minutes=20))
    mykolaiv_kab = {
        **strict_base,
        "title": "Миколаїв під атакою КАБів: у місті пролунав вибух",
    }
    mykolaiv_decision = classify_candidate(mykolaiv_kab, "mykolaiv", [mykolaiv_a, mykolaiv_b])
    assert mykolaiv_decision["air_military_context"]["present"]
    assert mykolaiv_decision["matching"]["outcome"] == "ambiguous_match"
    assert mykolaiv_decision["proposed_outcome"] == "needs_review"

    # IR17 Sumy broad attack/PVO summary: broad multi-event text cannot become
    # strict without strict temporal binding.
    sumy_ep = make_episode("sumy", dt, dt + timedelta(hours=1))
    sumy_summary = {
        **strict_base,
        "title": (
            "Вночі росіяни атакували Україну безпілотниками — сили ППО збили БпЛА. "
            "Російські дрони двічі атакували Суми, зокрема вдарили біля житлового будинку."
        ),
        "source": "Telegram / Українська правда",
        "publisher": "Українська правда",
    }
    sumy_decision = classify_candidate(sumy_summary, "sumy", [sumy_ep])
    assert sumy_decision["proposed_outcome"] != "approved_strict"

    # IR17 Dnipro near-duplicate representations: logical unique is not enough
    # to invent a raw episode ID for classification/metric propagation.
    dnipro_a = make_episode("dnipro", dt, dt + timedelta(hours=1))
    dnipro_b = make_episode("dnipro", dt + timedelta(seconds=28), dt + timedelta(hours=1, seconds=30))
    dnipro_row = {
        **strict_base,
        "title": "Дніпро атакували безпілотниками: у місті пролунали вибухи",
    }
    dnipro_decision = classify_candidate(dnipro_row, "dnipro", [dnipro_a, dnipro_b])
    assert dnipro_decision["matching"]["outcome"] == "unique_match"
    assert dnipro_decision["matching"]["matched_episode_id"] is None
    assert dnipro_decision["proposed_outcome"] == "needs_review"
    assert "NO_CANONICAL_RAW_EPISODE_ID" in dnipro_decision["reason_codes"]

    # Publication inside an alert is matching evidence only, never strict
    # event-time proof.
    publication_only = {
        **strict_base,
        "title": "У Полтаві пролунав вибух на тлі руху Бандеролі до міста",
    }
    publication_decision = classify_candidate(publication_only, "poltava", [poltava_ep])
    assert publication_decision["matching"]["outcome"] == "unique_match"
    assert publication_decision["proposed_outcome"] == "approved_sensitivity"
    assert not publication_decision["temporal_binding"]["present"]

    # Explicit source-stated event clock inside the episode is strict.
    timed_row = {
        **strict_base,
        "title": "Близько 13:30 у Полтаві пролунав вибух після повідомлення про Бандероль",
        "published_at": iso(dt + timedelta(minutes=45)),
    }
    timed_decision = classify_candidate(timed_row, "poltava", [poltava_ep])
    assert timed_decision["proposed_outcome"] == "approved_strict"
    assert timed_decision["temporal_binding"]["code"] == "TEMPORAL_EXPLICIT_EVENT_TIME_INSIDE_EPISODE"

    # Historical sensitivity near_boundary: an explicit event clock five minutes
    # before the frozen alert remains sensitivity, never strict.
    near_boundary_row = {
        **strict_base,
        "title": "Близько 12:55 у Полтаві пролунав вибух на тлі руху Бандеролі до міста",
        "published_at": iso(dt + timedelta(minutes=10)),
    }
    near_boundary_decision = classify_candidate(near_boundary_row, "poltava", [poltava_ep])
    assert near_boundary_decision["proposed_outcome"] == "approved_sensitivity"
    assert near_boundary_decision["sensitivity_basis"] == "near_boundary"
    assert "SENSITIVITY_NEAR_BOUNDARY" in near_boundary_decision["reason_codes"]
    assert not near_boundary_decision["temporal_binding"]["present"]

    # A more specific explicit event clock wins over generic during-alert wording
    # when the clock is just outside the frozen boundary.
    conflicting_row = {
        **strict_base,
        "title": "Близько 12:55 у Полтаві пролунав вибух під час повітряної тривоги через Бандероль",
        "published_at": iso(dt + timedelta(minutes=10)),
    }
    conflicting_decision = classify_candidate(conflicting_row, "poltava", [poltava_ep])
    assert conflicting_decision["proposed_outcome"] == "approved_sensitivity"
    assert conflicting_decision["sensitivity_basis"] == "near_boundary"

    # IR14 deterministic predicted-PVO rejection remains intact.
    pvo_only = {
        **strict_base,
        "title": "У Полтаві можлива робота ППО. БпЛА заходять на місто.",
        "snippet": "",
        "source": "Telegram / СУСПІЛЬНЕ НОВИНИ",
        "publisher": "СУСПІЛЬНЕ НОВИНИ",
    }
    pvo_decision = classify_candidate(pvo_only, "poltava", [poltava_ep])
    assert pvo_decision["proposed_outcome"] == "rejected"
    assert not pvo_decision["air_defense_action"]
    assert "PVO_ONLY_COMPLETE_MESSAGE" in pvo_decision["reason_codes"]

    # IR16: dry classification of an existing needs_review row is pure and does
    # not mutate its status.
    existing = {
        **publication_only,
        "candidate_id": "existing-needs-review",
        "city_key": "poltava",
        "city": "Полтава",
        "status": "needs_review",
    }
    dry_state = {"cities": {"poltava": {"episodes": [poltava_ep]}}}
    before_status = existing["status"]
    dry_decision = dry_classify_existing_candidate(existing, dry_state)
    assert dry_decision["proposed_outcome"] == "approved_sensitivity"
    assert existing["status"] == before_status == "needs_review"

    # Matching refresh must keep matching and classification metadata coherent.
    existing_queue = [{
        **strict_base,
        "title": "У Полтаві пролунав вибух",
        "candidate_id": "existing-unmatched",
        "city_key": "poltava",
        "city": "Полтава",
        "status": "needs_review",
        "url": "https://news.google.test/existing-unmatched",
        "trigger_episode_ids": [],
        "trigger_check_labels": ["72h"],
        "matched_episode_id": None,
        "matching_outcome": "no_match",
        "matched_episode_ids": [],
        "matching_logical_episode_groups": [],
        "classification_reason_codes": [
            "MATCH_NONE",
            "EXACT_CITY_EVENT_TEXT",
            "STRICT_EXPLOSION_EVIDENCE",
            "NO_AIR_MILITARY_CONTEXT",
            "NO_STRICT_TEMPORAL_BINDING",
        ],
        "classification_evidence": {},
    }]
    no_match_refresh = refresh_queue_matching(
        existing_queue,
        {"cities": {"poltava": {"episodes": []}}},
        {"needs_review"},
    )
    assert no_match_refresh["no_match"] == 1
    unique_refresh = refresh_queue_matching(
        existing_queue,
        {"cities": {"poltava": {"episodes": [poltava_ep]}}},
        {"needs_review"},
    )
    assert unique_refresh["unique_match"] == 1
    assert unique_refresh["stale_classification_repaired"] == 1
    assert existing_queue[0]["matched_episode_id"] == poltava_ep["episode_id"]
    assert existing_queue[0]["status"] == "needs_review"
    assert "MATCH_UNIQUE" in existing_queue[0]["classification_reason_codes"]
    assert "MATCH_NONE" not in existing_queue[0]["classification_reason_codes"]

    overlap_a = make_episode("poltava", dt, dt + timedelta(hours=1))
    overlap_b = make_episode("poltava", dt + timedelta(minutes=20), dt + timedelta(hours=1, minutes=20))
    overlap_decision = classify_candidate(strict_base, "poltava", [overlap_a, overlap_b])
    assert overlap_decision["matching"]["outcome"] == "ambiguous_match"
    assert overlap_decision["proposed_outcome"] == "needs_review"

    near_a = make_episode("poltava", dt, dt + timedelta(hours=1))
    near_b = make_episode("poltava", dt + timedelta(seconds=35), dt + timedelta(hours=1, seconds=50))
    near_decision = classify_candidate(strict_base, "poltava", [near_a, near_b])
    assert near_decision["matching"]["outcome"] == "unique_match"
    assert near_decision["matching"]["matched_episode_id"] is None
    assert near_decision["proposed_outcome"] == "needs_review"

    assert match_candidate_to_episodes({"published_at": iso(dt + timedelta(hours=3))}, [poltava_ep])["outcome"] == "no_match"


    # Temporal attribution corrective regressions.
    # Odesa wrong-episode: publication falls in the later episode grace window,
    # but generic "during alert" wording on a multi-episode date cannot select it.
    odesa_prev = {
        "episode_id": "eb2580c2bec54ddc2e36eaf7",
        "city_key": "odesa",
        "city": "Одеса",
        "alert_start": "2026-09-21T12:14:59.835398Z",
        "alert_end": "2026-09-21T13:37:45.918693Z",
    }
    odesa_later = {
        "episode_id": "7a7da068c0efb7be80bd45e4",
        "city_key": "odesa",
        "city": "Одеса",
        "alert_start": "2026-09-21T15:23:04.352831Z",
        "alert_end": "2026-09-21T16:04:52.076994Z",
    }
    for odesa_candidate_id in (
        "5a61d62cac76456eb62cb386",
        "da37fd7a3b6c42dbff41d115",
    ):
        odesa_wrong_episode_row = {
            "candidate_id": odesa_candidate_id,
            "title": "Вибухи в Одесі під час тривоги: РФ атакувала місто реактивними дронами",
            "snippet": "",
            "publisher": "Test",
            "source": "Google News RSS",
            "published_at": "2026-09-21T16:20:00Z",
        }
        wrong_episode_decision = classify_candidate(
            odesa_wrong_episode_row,
            "odesa",
            [odesa_prev, odesa_later],
        )
        assert wrong_episode_decision["matching"]["matched_episode_id"] == "7a7da068c0efb7be80bd45e4"
        assert wrong_episode_decision["proposed_outcome"] == "needs_review"
        assert wrong_episode_decision["proposed_matched_episode_id"] is None
        assert not wrong_episode_decision["temporal_binding"]["episode_specific"]
        assert wrong_episode_decision["temporal_binding"]["code"] == "TEMPORAL_EXPLICIT_ALERT_RELATION_AMBIGUOUS_DATE"

    # Generic alert relation can bind a single episode on a single-episode
    # date even when publication itself is outside the matching window.
    ternopil_single_ep = {
        "episode_id": "542708c29f1a2e044db6876c",
        "city_key": "ternopil",
        "city": "Тернопіль",
        "alert_start": "2026-09-18T17:02:28.779103Z",
        "alert_end": "2026-09-18T17:20:23.075792Z",
    }
    ternopil_late_row = {
        "candidate_id": "cc64cf1fe5e06196cac9b4a3",
        "title": "У Тернополі пролунав вибух під час тривоги: перед цим повідомляли про рух БпЛА на місто",
        "snippet": "",
        "publisher": "tenews.org.ua",
        "source": "Google News RSS",
        "published_at": "2026-09-18T17:51:00Z",
    }
    ternopil_late_decision = classify_candidate(
        ternopil_late_row,
        "ternopil",
        [ternopil_single_ep],
    )
    assert ternopil_late_decision["matching"]["outcome"] == "no_match"
    assert ternopil_late_decision["proposed_outcome"] == "approved_strict"
    assert ternopil_late_decision["proposed_matched_episode_id"] == "542708c29f1a2e044db6876c"

    # Trusted contemporaneous live wording remains strict on a multi-episode date
    # when the live message itself falls inside exactly one active raw episode.
    kyiv_earlier = {
        "episode_id": "kyiv-earlier",
        "city_key": "kyiv",
        "city": "Київ",
        "alert_start": "2026-09-22T06:00:00Z",
        "alert_end": "2026-09-22T06:30:00Z",
    }
    kyiv_live_ep = {
        "episode_id": "baf3eaa558f606c14d6e385f",
        "city_key": "kyiv",
        "city": "Київ",
        "alert_start": "2026-09-22T09:55:00Z",
        "alert_end": "2026-09-22T10:20:00Z",
    }
    kyiv_live_row = {
        "candidate_id": "d4fb0e081e5be3bd609f0633",
        "title": (
            "У Києві лунають вибухи, повідомляють кореспонденти Суспільного. "
            "Міський голова Кличко інформує, що у столиці працює ППО."
        ),
        "snippet": "",
        "publisher": "СУСПІЛЬНЕ НОВИНИ",
        "source": "Telegram / СУСПІЛЬНЕ НОВИНИ",
        "published_at": "2026-09-22T10:07:54Z",
    }
    kyiv_live_decision = classify_candidate(kyiv_live_row, "kyiv", [kyiv_earlier, kyiv_live_ep])
    assert kyiv_live_decision["proposed_outcome"] == "approved_strict"
    assert kyiv_live_decision["proposed_matched_episode_id"] == "baf3eaa558f606c14d6e385f"
    assert kyiv_live_decision["temporal_binding"]["code"] == "TEMPORAL_CONTEMPORANEOUS_LIVE_WORDING"

    # Multi-episode inferred_same_attack cannot use a unique publication-window
    # match as episode attribution.
    multi_first = make_episode("poltava", dt, dt + timedelta(hours=1))
    multi_second = make_episode("poltava", dt + timedelta(hours=2), dt + timedelta(hours=3))
    multi_inferred_row = {
        **publication_only,
        "published_at": iso(dt + timedelta(minutes=30)),
    }
    multi_inferred_decision = classify_candidate(
        multi_inferred_row,
        "poltava",
        [multi_first, multi_second],
    )
    assert multi_inferred_decision["matching"]["outcome"] == "unique_match"
    assert multi_inferred_decision["proposed_outcome"] == "needs_review"
    assert "MULTI_EPISODE_DATE_REQUIRES_EPISODE_SPECIFIC_TEMPORAL_PROOF" in multi_inferred_decision["reason_codes"]

    # Explicit event time attributes the event independently of the publication
    # window, including when publication matching points to a different episode.
    event_time_earlier = {
        "episode_id": "event-time-earlier",
        "city_key": "poltava",
        "city": "Полтава",
        "alert_start": "2026-09-18T10:00:00Z",
        "alert_end": "2026-09-18T11:00:00Z",
    }
    publication_later = {
        "episode_id": "publication-later",
        "city_key": "poltava",
        "city": "Полтава",
        "alert_start": "2026-09-18T12:00:00Z",
        "alert_end": "2026-09-18T13:00:00Z",
    }
    explicit_clock_row = {
        **strict_base,
        "title": "Близько 13:30 у Полтаві пролунав вибух після повідомлення про Бандероль",
        "published_at": "2026-09-18T12:30:00Z",
    }
    explicit_clock_decision = classify_candidate(
        explicit_clock_row,
        "poltava",
        [event_time_earlier, publication_later],
    )
    assert explicit_clock_decision["matching"]["matched_episode_id"] == "publication-later"
    assert explicit_clock_decision["proposed_outcome"] == "approved_strict"
    assert explicit_clock_decision["proposed_matched_episode_id"] == "event-time-earlier"
    assert explicit_clock_decision["temporal_binding"]["event_time"] == "2026-09-18T10:30:00Z"

    # Narrow relative chronology: alert clock + bounded minute offset to
    # exact-city explosions resolves a cross-midnight historical article without
    # treating publication time as event time.
    relative_ep = {
        "episode_id": "relative-chronology-target",
        "city_key": "lviv",
        "city": "Львів",
        "alert_start": "2026-01-08T21:35:35Z",
        "alert_end": "2026-01-08T22:11:53Z",
    }
    relative_row = {
        **strict_base,
        "title": "У Львові під час повітряної тривоги пролунали вибухи",
        "snippet": (
            "Повітряну тривогу оголосили о 23:36. "
            "Вже за 10 хвилин у Львові було чутно звуки вибухів."
        ),
        "published_at": "2026-01-08T22:00:10Z",
    }
    relative_decision = classify_candidate(relative_row, "lviv", [relative_ep])
    assert relative_decision["proposed_outcome"] == "approved_strict", relative_decision
    assert relative_decision["proposed_matched_episode_id"] == "relative-chronology-target"
    assert relative_decision["temporal_binding"]["code"] == "TEMPORAL_RELATIVE_ALERT_CHRONOLOGY"
    assert relative_decision["temporal_binding"]["event_time"] == "2026-01-08T21:46:00Z"

    relative_negative = {
        **strict_base,
        "title": "У Львові повідомили про вибухи",
        "snippet": "Повітряну тривогу оголосили о 23:36. Через 10 хвилин опублікували оновлення.",
        "published_at": "2026-01-08T22:00:10Z",
    }
    relative_negative_decision = classify_candidate(relative_negative, "lviv", [relative_ep])
    assert relative_negative_decision["temporal_binding"]["code"] != "TEMPORAL_RELATIVE_ALERT_CHRONOLOGY"

    # A daytime article must not reinterpret a clock-only event as the
    # previous calendar day merely because an alert existed at that clock.
    prev_day = {
        "episode_id": "clock-prev-day",
        "city_key": "lviv",
        "city": "Львів",
        "alert_start": "2026-02-07T06:30:00Z",
        "alert_end": "2026-02-07T07:00:00Z",
    }
    same_day = {
        "episode_id": "clock-same-day",
        "city_key": "lviv",
        "city": "Львів",
        "alert_start": "2026-02-08T05:53:00Z",
        "alert_end": "2026-02-08T06:58:00Z",
    }
    daytime_clock_row = {
        **strict_base,
        "title": "У Львові о 08:48 було чути вибухи під час атаки БпЛА",
        "published_at": "2026-02-08T08:02:27Z",
    }
    daytime_clock_decision = classify_candidate(
        daytime_clock_row, "lviv", [prev_day, same_day]
    )
    assert daytime_clock_decision["proposed_outcome"] == "approved_strict"
    assert daytime_clock_decision["proposed_matched_episode_id"] == "clock-same-day"
    assert daytime_clock_decision["temporal_binding"]["event_time"] == "2026-02-08T06:48:00Z"

    # Genuine shortly-after-midnight publication may still describe a clock-only
    # event from the previous local day.
    cross_midnight_ep = {
        "episode_id": "clock-cross-midnight",
        "city_key": "lviv",
        "city": "Львів",
        "alert_start": "2026-01-08T21:35:00Z",
        "alert_end": "2026-01-08T22:11:59Z",
    }
    cross_midnight_row = {
        **strict_base,
        "title": "У Львові близько 23:50 пролунав вибух під час атаки БпЛА",
        "published_at": "2026-01-08T22:20:00Z",
    }
    cross_midnight_decision = classify_candidate(
        cross_midnight_row, "lviv", [cross_midnight_ep]
    )
    assert cross_midnight_decision["proposed_outcome"] == "approved_strict"
    assert cross_midnight_decision["proposed_matched_episode_id"] == "clock-cross-midnight"
    assert cross_midnight_decision["temporal_binding"]["event_time"] == "2026-01-08T21:50:00Z"

    # Explicit timing just outside a boundary remains episode-specific sensitivity.
    boundary_ep = {
        "episode_id": "boundary-episode",
        "city_key": "poltava",
        "city": "Полтава",
        "alert_start": "2026-09-18T10:00:00Z",
        "alert_end": "2026-09-18T11:00:00Z",
    }
    boundary_row = {
        **strict_base,
        "title": "Близько 12:55 у Полтаві пролунав вибух на тлі руху Бандеролі до міста",
        "published_at": "2026-09-18T10:10:00Z",
    }
    boundary_decision = classify_candidate(boundary_row, "poltava", [boundary_ep])
    assert boundary_decision["proposed_outcome"] == "approved_sensitivity"
    assert boundary_decision["sensitivity_basis"] == "near_boundary"
    assert boundary_decision["proposed_matched_episode_id"] == "boundary-episode"

    # Controlled blast remains deterministic reject even with unrelated alert/PPO
    # wording elsewhere in the message.
    controlled_with_unrelated_air = {
        **strict_base,
        "title": (
            "У Запоріжжі проведуть планові вибухові роботи на кар'єрі. "
            "У регіоні оголошена повітряна тривога, працює ППО."
        ),
        "snippet": "",
    }
    controlled_decision = classify_candidate(
        controlled_with_unrelated_air,
        "zaporizhzhia",
        [make_episode("zaporizhzhia", dt, dt + timedelta(hours=1))],
    )
    assert controlled_decision["proposed_outcome"] == "rejected"
    assert "DETERMINISTIC_CONTROLLED_BLAST" in controlled_decision["reason_codes"]

    # Bounded episode-level composition: one trusted live temporal anchor plus
    # a separate same-attack exact-city aerial-war source may support strict.
    composition_anchor = {
        **strict_base,
        "candidate_id": "composition-anchor",
        "city_key": "poltava",
        "city": "Полтава",
        "status": "needs_review",
        "source": "Telegram / СУСПІЛЬНЕ НОВИНИ",
        "publisher": "СУСПІЛЬНЕ НОВИНИ",
        "title": "У Полтаві чутно серію вибухів, повідомляють кореспонденти Суспільного.",
        "snippet": "",
        "published_at": iso(dt + timedelta(minutes=20)),
        "matched_episode_id": poltava_ep["episode_id"],
    }
    composition_context = {
        **strict_base,
        "candidate_id": "composition-context",
        "city_key": "poltava",
        "city": "Полтава",
        "status": "needs_review",
        "source": "Google News RSS",
        "publisher": "Test",
        "title": "У Полтаві пролунали вибухи через атаку балістикою",
        "snippet": "",
        "published_at": iso(dt + timedelta(minutes=35)),
        "matched_episode_id": poltava_ep["episode_id"],
    }
    composition_decision = compose_episode_candidates(
        "poltava",
        poltava_ep,
        [composition_anchor, composition_context],
        [poltava_ep],
    )
    assert composition_decision["final_composed_verdict"] == "approved_strict"
    assert composition_decision["anchor_candidate_id"] == "composition-anchor"
    assert composition_decision["contributing_candidate_ids"] == [
        "composition-anchor",
        "composition-context",
    ]

    cumulative_context = {
        **composition_context,
        "candidate_id": "composition-cumulative",
        "title": "Полтава під ударом цілий день: вибухи через атаки дронами",
    }
    cumulative_decision = compose_episode_candidates(
        "poltava",
        poltava_ep,
        [composition_anchor, cumulative_context],
        [poltava_ep],
    )
    assert cumulative_decision["final_composed_verdict"] == "no_composed_strict"

    overlapping_neighbor = make_episode(
        "poltava",
        dt + timedelta(minutes=25),
        dt + timedelta(minutes=45),
    )
    neighbor_decision = compose_episode_candidates(
        "poltava",
        poltava_ep,
        [composition_anchor, composition_context],
        [poltava_ep, overlapping_neighbor],
    )
    assert neighbor_decision["final_composed_verdict"] == "no_composed_strict"


    # Reviewed provenance persistence/consumption focused regressions.
    reviewed_target = {
        "episode_id": "reviewed-target",
        "city_key": "sumy",
        "city": "Суми",
        "alert_start": "2026-09-18T17:24:19Z",
        "alert_end": "2026-09-18T18:24:36Z",
    }
    reviewed_neighbor = {
        "episode_id": "reviewed-neighbor",
        "city_key": "sumy",
        "city": "Суми",
        "alert_start": "2026-09-18T12:00:00Z",
        "alert_end": "2026-09-18T13:00:00Z",
    }
    reviewed_strict_row = {
        "candidate_id": "6212f72cfd28e6a86fd5bc51",
        "city_key": "sumy",
        "city": "Суми",
        "title": "Вибухи у Сумах: росіяни вдарили КАБами по багатоповерхівках",
        "snippet": "",
        "publisher": "Ukr.net",
        "source": "Google News RSS",
        "published_at": "2026-09-18T20:16:49Z",
        "matched_episode_id": "reviewed-target",
    }
    no_review_strict = classify_candidate(
        dict(reviewed_strict_row), "sumy", [reviewed_neighbor, reviewed_target]
    )
    assert no_review_strict["proposed_outcome"] == "needs_review"
    reviewed_strict_row["review_provenance"] = {
        "schema_version": REVIEW_PROVENANCE_SCHEMA_VERSION,
        "methodology_version": REVIEW_PROVENANCE_METHODOLOGY_VERSION,
        "target_episode_id": "reviewed-target",
        "exact_city_evidence": {"present": True, "evidence_text": "Exact-city Sumy KAB strike"},
        "explosion_evidence": {"present": True, "evidence_text": "Explosions / impacts in Sumy"},
        "aerial_war_evidence": {"present": True, "evidence_text": "KAB aerial attack"},
        "same_attack_basis": {"present": True, "basis": ["same reviewed KAB strike"]},
        "temporal": {
            "status": "validated_event_time",
            "validated_by_review": True,
            "event_time": "2026-09-18T18:00:00Z",
            "timestamp_precision": "approximate_minute",
            "temporal_evidence_type": "reviewed_source_event_time",
            "episode_specific": True,
            "neighboring_alert_check": {"passed": True},
            "publication_time": "2026-09-18T20:16:49Z",
        },
    }
    reviewed_strict = classify_candidate(
        reviewed_strict_row, "sumy", [reviewed_neighbor, reviewed_target]
    )
    assert reviewed_strict["proposed_outcome"] == "approved_strict"
    assert reviewed_strict["proposed_matched_episode_id"] == "reviewed-target"
    assert reviewed_strict["temporal_binding"]["event_time"] == "2026-09-18T18:00:00Z"
    assert reviewed_strict["temporal_binding"]["timestamp_precision"] == "approximate_minute"

    sev_target = {
        "episode_id": "reviewed-sevastopol",
        "city_key": "sevastopol",
        "city": "Севастополь",
        "alert_start": "2026-09-19T15:04:00Z",
        "alert_end": "2026-09-19T15:16:00Z",
    }
    reviewed_sensitivity_row = {
        "candidate_id": "70265845b367fea065fbd077",
        "city_key": "sevastopol",
        "city": "Севастополь",
        "title": "У Севастополі прогриміли потужні вибухи",
        "snippet": "",
        "publisher": "ukr.net",
        "source": "Google News RSS",
        "published_at": "2026-09-19T15:10:00Z",
        "matched_episode_id": "reviewed-sevastopol",
        "review_provenance": {
            "schema_version": REVIEW_PROVENANCE_SCHEMA_VERSION,
            "methodology_version": REVIEW_PROVENANCE_METHODOLOGY_VERSION,
            "target_episode_id": "reviewed-sevastopol",
            "exact_city_evidence": {"present": True},
            "explosion_evidence": {"present": True},
            "aerial_war_evidence": {"present": True, "evidence_text": "reviewed mobile-fire-group / aerial context"},
            "same_attack_basis": {"present": True, "basis": ["reviewed contemporaneous same attack"]},
            "temporal": {
                "status": "unsupported",
                "validated_by_review": True,
                "episode_specific": False,
                "publication_time": "2026-09-19T15:10:00Z",
            },
            "sensitivity_binding": {
                "present": True,
                "validated_by_review": True,
                "episode_specific": True,
                "basis": "inferred_same_attack",
                "neighboring_alert_check": {"passed": True},
            },
        },
    }
    no_review_sensitivity = dict(reviewed_sensitivity_row)
    no_review_sensitivity.pop("review_provenance")
    assert classify_candidate(
        no_review_sensitivity, "sevastopol", [sev_target]
    )["proposed_outcome"] == "needs_review"
    reviewed_sensitivity = classify_candidate(
        reviewed_sensitivity_row, "sevastopol", [sev_target]
    )
    assert reviewed_sensitivity["proposed_outcome"] == "approved_sensitivity"
    assert reviewed_sensitivity["sensitivity_basis"] == "inferred_same_attack"

    zap_target = {
        "episode_id": "reviewed-zap-target",
        "city_key": "zaporizhzhia",
        "city": "Запоріжжя",
        "alert_start": "2026-09-18T16:21:56Z",
        "alert_end": "2026-09-18T17:49:19Z",
    }
    zap_neighbor = {
        "episode_id": "reviewed-zap-neighbor",
        "city_key": "zaporizhzhia",
        "city": "Запоріжжя",
        "alert_start": "2026-09-18T12:00:00Z",
        "alert_end": "2026-09-18T13:00:00Z",
    }
    zap_negative = {
        "candidate_id": "e7461ec759e4d79020dfd1ba",
        "city_key": "zaporizhzhia",
        "city": "Запоріжжя",
        "title": "У Запоріжжі пролунали вибухи під час атаки, є влучання в інфраструктуру",
        "snippet": "",
        "publisher": "061.ua",
        "source": "Google News RSS",
        "published_at": "2026-09-18T17:10:00Z",
        "matched_episode_id": "reviewed-zap-target",
        "review_provenance": {
            "schema_version": REVIEW_PROVENANCE_SCHEMA_VERSION,
            "methodology_version": REVIEW_PROVENANCE_METHODOLOGY_VERSION,
            "target_episode_id": "reviewed-zap-target",
            "exact_city_evidence": {"present": True},
            "explosion_evidence": {"present": True},
            "aerial_war_evidence": {"present": True},
            "same_attack_basis": {"present": True, "basis": ["reviewed attack identity"]},
            "temporal": {
                "status": "unsupported",
                "validated_by_review": True,
                "episode_specific": False,
                "event_time": None,
                "publication_time": "2026-09-18T19:57:00+03:00",
                "temporal_evidence_type": "publication_time_not_event_time",
                "neighboring_alert_check": {"passed": False},
            },
        },
    }
    zap_negative_decision = classify_candidate(
        zap_negative, "zaporizhzhia", [zap_neighbor, zap_target]
    )
    assert zap_negative_decision["proposed_outcome"] == "needs_review"
    assert zap_negative_decision["temporal_binding"].get("event_time") is None

    rematched = json.loads(json.dumps(reviewed_strict_row))
    rematch_ep = {
        "episode_id": "reviewed-rematch-B",
        "city_key": "sumy",
        "city": "Суми",
        "alert_start": "2026-09-18T20:00:00Z",
        "alert_end": "2026-09-18T21:00:00Z",
    }
    apply_matching_result(
        rematched,
        {
            "outcome": "unique_match",
            "matched_episode_ids": ["reviewed-rematch-B"],
            "logical_episode_groups": [["reviewed-rematch-B"]],
            "matched_episode_id": "reviewed-rematch-B",
            "reason": "test_rematch",
        },
    )
    rematch_decision = classify_candidate(
        rematched, "sumy", [reviewed_target, rematch_ep]
    )
    assert rematch_decision["proposed_outcome"] == "needs_review"
    assert "REVIEW_PROVENANCE_TARGET_MISMATCH" in rematch_decision["reason_codes"]
    assert rematched["review_provenance"]["target_episode_id"] == "reviewed-target"

    serialized = json.loads(json.dumps(reviewed_strict_row))
    before_provenance = json.loads(json.dumps(serialized["review_provenance"]))
    serialized_decision = classify_candidate(
        serialized, "sumy", [reviewed_neighbor, reviewed_target]
    )
    apply_classification_decision(
        serialized, serialized_decision, serialized_decision["matching"]
    )
    serialized = json.loads(json.dumps(serialized))
    assert serialized["review_provenance"] == before_provenance

    composition_review_anchor = {
        **composition_anchor,
        "candidate_id": "composition-reviewed-anchor",
        "matched_episode_id": poltava_ep["episode_id"],
        "review_provenance": {
            "schema_version": REVIEW_PROVENANCE_SCHEMA_VERSION,
            "methodology_version": REVIEW_PROVENANCE_METHODOLOGY_VERSION,
            "target_episode_id": poltava_ep["episode_id"],
            "exact_city_evidence": {"present": True},
            "explosion_evidence": {"present": True},
            "same_attack_basis": {"present": True, "basis": ["reviewed same attack"]},
            "temporal": {
                "status": "validated_event_time",
                "validated_by_review": True,
                "event_time": iso(dt + timedelta(minutes=20)),
                "timestamp_precision": "minute",
                "temporal_evidence_type": "reviewed_source_event_time",
                "episode_specific": True,
                "neighboring_alert_check": {"passed": True},
            },
        },
    }
    composition_review_anchor["title"] = "У Полтаві пролунав вибух"
    composition_review_anchor["source"] = "Google News RSS"
    composition_review_anchor["publisher"] = "Test"
    mixed_composition = compose_episode_candidates(
        "poltava",
        poltava_ep,
        [composition_review_anchor, composition_context],
        [poltava_ep],
    )
    assert mixed_composition["final_composed_verdict"] == "approved_strict"
    mixed_anchor = next(
        row for row in mixed_composition["contributing_candidates"]
        if row["candidate_id"] == "composition-reviewed-anchor"
    )
    assert "review_provenance" in mixed_anchor["role_sources"]["temporal_proof"]

    # Data-driven frozen replay. The research artifact carries only in-memory
    # review_provenance fixtures; live queue/state files are never written.
    if PROVENANCE_HARDENING_ARTIFACT.exists():
        hardening = load_json(PROVENANCE_HARDENING_ARTIFACT, {})
        fixture = hardening.get("replay_fixture") or {}
        cases = list(fixture.get("candidate_cases") or [])
        queue_rows = load_json(QUEUE_FILE, [])
        state_rows = load_json(STATE_FILE, {})
        queue_by_id = {
            str(item.get("candidate_id")): item
            for item in queue_rows
            if isinstance(item, dict) and item.get("candidate_id")
        }
        replayed = {}
        for case in cases:
            cid = str(case.get("candidate_id") or "")
            if cid not in queue_by_id:
                raise AssertionError(f"Frozen replay candidate missing from queue: {cid}")
            item = json.loads(json.dumps(queue_by_id[cid]))
            if isinstance(case.get("review_provenance"), dict):
                item["review_provenance"] = json.loads(json.dumps(case["review_provenance"]))
                if case.get("target_episode_id"):
                    item["matched_episode_id"] = case["target_episode_id"]
            else:
                item.pop("review_provenance", None)
            decision = dry_classify_existing_candidate(item, state_rows)
            apply_classification_decision(item, decision, decision["matching"])
            replayed[cid] = item

        composition_fixture = fixture.get("composition_only_case") or {}
        composition_anchor_id = str(composition_fixture.get("anchor_candidate_id") or "")
        if composition_anchor_id:
            anchor = replayed[composition_anchor_id]
            city_key = str(composition_fixture["city_key"])
            target_id = str(composition_fixture["target_episode_id"])
            # Standalone needs_review classification refreshes publication-based
            # matching metadata. Restore only the already-reviewed target binding
            # on this in-memory composition fixture before episode composition.
            anchor["matched_episode_id"] = target_id
            episodes = tracked_episodes_for_city(state_rows, city_key)
            target = next(
                ep for ep in episodes if str(ep.get("episode_id") or "") == target_id
            )
            group = [anchor]
            for context_id in composition_fixture.get("context_candidate_ids") or []:
                context = json.loads(json.dumps(queue_by_id[str(context_id)]))
                context["matched_episode_id"] = target_id
                group.append(context)
            composed = compose_episode_candidates(city_key, target, group, episodes)
            assert composed["final_composed_verdict"] == "approved_strict"
            assert composed["anchor_candidate_id"] == composition_anchor_id
            anchor["status"] = "approved_strict"
            anchor["matched_episode_id"] = target_id
            anchor["composition_provenance"] = composed

        mismatches = []
        positive_count = 0
        positive_strict = 0
        positive_sensitivity = 0
        negative_count = 0
        for case in cases:
            cid = str(case["candidate_id"])
            expected = str(case["expected_status"])
            actual = str(replayed[cid].get("status") or "")
            if expected in {"approved_strict", "approved_sensitivity"}:
                positive_count += 1
                positive_strict += expected == "approved_strict"
                positive_sensitivity += expected == "approved_sensitivity"
            else:
                negative_count += bool(case.get("deterministic_negative"))
            if actual != expected:
                mismatches.append((cid, expected, actual))
        assert positive_count == 50
        assert positive_strict == 35
        assert positive_sensitivity == 15
        assert negative_count == 2
        assert not mismatches, mismatches

        transition_cases = list(fixture.get("transition_cases") or [])
        transition_types = {"strict_to_needs_review": 0, "sensitivity_to_needs_review": 0}
        for transition in transition_cases:
            old_status = str(transition.get("old_live_status") or "")
            new_status = str(transition.get("expected_status") or "")
            if old_status == "approved_strict" and new_status == "needs_review":
                transition_types["strict_to_needs_review"] += 1
            elif old_status == "approved_sensitivity" and new_status == "needs_review":
                transition_types["sensitivity_to_needs_review"] += 1
        assert len(transition_cases) == 8
        assert transition_types == {
            "strict_to_needs_review": 7,
            "sensitivity_to_needs_review": 1,
        }

        episode_results = {}
        for episode_case in fixture.get("episode_cases") or []:
            supporting_ids = list(episode_case.get("supporting_candidate_ids") or [])
            if not supporting_ids:
                supporting_ids = [
                    str(case["candidate_id"])
                    for case in cases
                    if str(case.get("target_episode_id") or "")
                    == str(episode_case.get("episode_id") or "")
                ]
            supporting = [
                replayed[str(cid)].get("status")
                for cid in supporting_ids
            ]
            if "approved_strict" in supporting:
                live_status = "approved_strict"
                result = "KEEP_STRICT"
            elif "approved_sensitivity" in supporting:
                live_status = "approved_sensitivity"
                result = "KEEP_SENSITIVITY"
            else:
                live_status = "needs_review"
                result = "DOWNGRADE_TO_UNRESOLVED"
            assert live_status == episode_case["expected_status"], (episode_case, supporting)
            assert result == episode_case["expected_result"], (episode_case, supporting)
            episode_results[str(episode_case["episode_id"])] = result
        assert len(episode_results) == 20
        assert list(episode_results.values()).count("KEEP_STRICT") == 15
        assert list(episode_results.values()).count("KEEP_SENSITIVITY") == 1
        assert list(episode_results.values()).count("DOWNGRADE_TO_UNRESOLVED") == 4

        no_adapter_mismatches = []
        for case in cases:
            expected_raw = case.get("expected_without_review_provenance")
            if expected_raw is None:
                continue
            item = json.loads(json.dumps(queue_by_id[str(case["candidate_id"])]))
            item.pop("review_provenance", None)
            actual_raw = dry_classify_existing_candidate(item, state_rows)["proposed_outcome"]
            if actual_raw != expected_raw:
                no_adapter_mismatches.append(
                    (case["candidate_id"], expected_raw, actual_raw)
                )
        assert not no_adapter_mismatches, no_adapter_mismatches

        # Current non-reviewed records are an additional backward-
        # compatibility control sample. Persisted status is not a valid
        # pre-hardening oracle because older manual/auto approvals can already
        # be stale under current methodology. Instead prove that, when
        # review_provenance is absent, the adapter is an identity transform on
        # every decision-bearing evidence concept and cannot widen status.
        ordinary_checked = 0
        ordinary_persisted_deltas = []
        ordinary_outcome_counts = {}
        adapter_widening = []
        frozen_ids = {str(case["candidate_id"]) for case in cases}
        for item in queue_rows:
            if ordinary_checked >= 50:
                break
            if not isinstance(item, dict) or str(item.get("candidate_id") or "") in frozen_ids:
                continue
            if item.get("review_provenance") is not None:
                continue
            if not str(item.get("review_note") or "").startswith("evidence-layered"):
                continue
            if item.get("composition_provenance"):
                continue
            city_key = str(item.get("city_key") or "")
            if city_key not in CITY_CONFIG:
                continue
            episodes = tracked_episodes_for_city(state_rows, city_key)
            matching = match_candidate_to_episodes(item, episodes)
            if classification_matching_is_stale(item, matching):
                continue
            decision = classify_candidate(item, city_key, episodes, matching)
            reviewed_adapter = decision["review_provenance_adapter"]
            assert reviewed_adapter["present"] is False
            assert reviewed_adapter["usable"] is False
            assert reviewed_adapter["reason_codes"] == []
            candidate_evidence = decision["candidate_evidence"]
            for merged_key, candidate_key in (
                ("exact_city_classification_evidence", "exact_city"),
                ("strict_explosion_evidence", "strict_explosion"),
                ("air_military_context", "air_military_context"),
                ("same_attack_context", "same_attack_context"),
            ):
                assert decision[merged_key]["present"] == candidate_evidence[candidate_key]["present"]
            assert (
                decision["temporal_binding"].get("present")
                == candidate_evidence["temporal_binding"].get("present")
            )
            assert (
                decision["temporal_binding"].get("episode_id")
                == candidate_evidence["temporal_binding"].get("episode_id")
            )
            assert (
                decision["single_episode_day_inference"].get("present")
                == candidate_evidence["single_episode_day_inference"].get("present")
            )
            proposed = str(decision["proposed_outcome"])
            ordinary_outcome_counts[proposed] = ordinary_outcome_counts.get(proposed, 0) + 1
            ordinary_checked += 1
            if proposed != item.get("status"):
                ordinary_persisted_deltas.append(
                    (item.get("candidate_id"), item.get("status"), proposed)
                )
            if proposed in {"approved_strict", "approved_sensitivity"} and any(
                code.startswith("REVIEW_PROVENANCE_")
                for code in decision.get("reason_codes") or []
            ):
                adapter_widening.append(item.get("candidate_id"))
        assert ordinary_checked >= 20
        assert not adapter_widening, adapter_widening

        composition_regression_results = []
        for composed_case in fixture.get("composition_positive_cases") or []:
            city_key = str(composed_case["city_key"])
            target_id = str(composed_case["target_episode_id"])
            episodes = tracked_episodes_for_city(state_rows, city_key)
            target = next(
                ep for ep in episodes if str(ep.get("episode_id") or "") == target_id
            )
            group = []
            for contributor_id in composed_case.get("contributor_candidate_ids") or []:
                contributor = json.loads(json.dumps(queue_by_id[str(contributor_id)]))
                contributor["matched_episode_id"] = target_id
                group.append(contributor)
            result = compose_episode_candidates(city_key, target, group, episodes)
            composition_regression_results.append(
                {
                    "episode_id": target_id,
                    "verdict": result["final_composed_verdict"],
                    "anchor_candidate_id": result.get("anchor_candidate_id"),
                }
            )
            assert result["final_composed_verdict"] == "approved_strict", result
            assert result.get("anchor_candidate_id") == composed_case["anchor_candidate_id"], result
        assert len(composition_regression_results) == 3
        frozen_strict_episode_ids = {
            episode_id
            for episode_id, result in episode_results.items()
            if result == "KEEP_STRICT"
        }
        composition_strict_episode_ids = {
            str(row["episode_id"]) for row in composition_regression_results
        }
        strict_event_ids = frozen_strict_episode_ids | composition_strict_episode_ids
        assert len(frozen_strict_episode_ids) == 15
        assert len(composition_strict_episode_ids) == 3
        assert not (frozen_strict_episode_ids & composition_strict_episode_ids)
        assert len(strict_event_ids) == 18

        future_queue = json.loads(json.dumps(queue_rows))
        future_by_id = {
            str(item.get("candidate_id")): item
            for item in future_queue
            if isinstance(item, dict) and item.get("candidate_id")
        }
        intended_status = {}
        for case in cases:
            cid = str(case["candidate_id"])
            item = future_by_id[cid]
            if isinstance(case.get("review_provenance"), dict):
                item["review_provenance"] = json.loads(json.dumps(case["review_provenance"]))
            else:
                item.pop("review_provenance", None)
            item["status"] = str(case["expected_status"])
            intended_status[cid] = str(case["expected_status"])
            if case.get("target_episode_id") and item["status"] in {
                "approved_strict", "approved_sensitivity"
            }:
                item["matched_episode_id"] = case["target_episode_id"]

        for composed_case in fixture.get("composition_positive_cases") or []:
            anchor = future_by_id[str(composed_case["anchor_candidate_id"])]
            anchor["status"] = "approved_strict"
            anchor["matched_episode_id"] = str(composed_case["target_episode_id"])
            intended_status[str(composed_case["anchor_candidate_id"])] = "approved_strict"

        persisted_before = {
            cid: json.loads(json.dumps(future_by_id[cid].get("review_provenance")))
            for cid in future_by_id
            if future_by_id[cid].get("review_provenance") is not None
        }
        future_queue = json.loads(json.dumps(future_queue))
        matching_result = refresh_queue_matching(future_queue, state_rows, {"needs_review"})
        future_episode_ids = {
            str(case.get("target_episode_id") or "")
            for case in cases
            if case.get("target_episode_id")
        } | {
            str(case.get("target_episode_id") or "")
            for case in fixture.get("composition_positive_cases") or []
            if case.get("target_episode_id")
        }
        apply_episode_composition(future_queue, state_rows, future_episode_ids)
        future_by_id_after = {
            str(item.get("candidate_id")): item
            for item in future_queue
            if isinstance(item, dict) and item.get("candidate_id")
        }
        unexpected = [
            (cid, status, future_by_id_after[cid].get("status"))
            for cid, status in intended_status.items()
            if future_by_id_after[cid].get("status") != status
        ]
        assert not unexpected, unexpected
        for cid, provenance in persisted_before.items():
            assert future_by_id_after[cid].get("review_provenance") == provenance

        stale_unique_match_none = 0
        for item in future_queue:
            if not isinstance(item, dict):
                continue
            if item.get("matching_outcome") != "unique_match":
                continue
            if "MATCH_NONE" in (item.get("classification_reason_codes") or []):
                stale_unique_match_none += 1
        assert stale_unique_match_none == 0

        for composed_case in fixture.get("composition_positive_cases") or []:
            anchor = future_by_id_after[str(composed_case["anchor_candidate_id"])]
            assert anchor.get("status") == "approved_strict"
            assert str(anchor.get("matched_episode_id") or "") == str(
                composed_case["target_episode_id"]
            )

        print(
            "Provenance hardening frozen replay OK: "
            f"50/50 approvals ({positive_strict} strict, {positive_sensitivity} sensitivity); "
            "2/2 deterministic negatives; 58/58 no-adapter regression; "
            "20/20 episode replay (15 strict, 1 sensitivity, 4 unresolved); "
            "8/8 transitions (7 strict, 1 sensitivity -> needs_review); "
            f"{ordinary_checked} ordinary unreviewed controls; "
            f"3/3 composition-positive recomputations; strict episode event IDs unique (18/18); "
            f"{ordinary_checked} ordinary unreviewed identity controls "
            f"(persisted deltas={len(ordinary_persisted_deltas)}, adapter widening=0); "
            f"future-run unexpected status changes=0; stale unique+MATCH_NONE={stale_unique_match_none}; "
            f"matching refresh checked={matching_result['candidates_checked']}"
        )


    if "kyiv" in CITY_CONFIG:
        assert load_kyiv_alert_episodes(KYIV_ALERTS_FILE)[-1]["alert_source"] == "kyiv_combined_exact_city"
    if "sevastopol" in CITY_CONFIG:
        assert load_sevastopol_alert_episodes(SEVASTOPOL_EVENTS_FILE)[-1]["alert_source"] == "sevastopol_verified_exact_city_pairs"

    print(
        f"Self-test OK: {len(CITY_CONFIG)} audited cities; classification requirements IR01-IR20 covered; "
        "PVO-only, controlled-blast, and publisher-branding guards; KAB/UAV/missile context; episode-specific "
        "explicit/clock/live temporal attribution; near-boundary and conservative single-episode sensitivity; "
        "late discovery; overlap/near-duplicate guards; dry replay purity"
    )

def main() -> None:
    parser = argparse.ArgumentParser(description="Monitor completed-alert explosion candidates with separated discovery, matching, and evidence-layered classification.")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--local-only", action="store_true", help="Read completed alerts from a cached UkraineAlarm bridge instead of calling the API.")
    parser.add_argument("--bridge-file", default=str(BRIDGE_FILE), help="Bridge JSON used with --local-only.")
    parser.add_argument("--kyiv-alerts-file", default=str(KYIV_ALERTS_FILE), help="Completed Kyiv exact-city alert store.")
    parser.add_argument("--sevastopol-events-file", default=str(SEVASTOPOL_EVENTS_FILE), help="Verified completed Sevastopol event store.")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return

    started = now_utc()
    followup_cutoff = started
    state = ensure_state()
    queue = load_json(QUEUE_FILE, [])
    if not isinstance(queue, list):
        queue = []

    if args.local_only:
        polled, errors = poll_cached_bridge(
            Path(args.bridge_file),
            started,
            Path(args.kyiv_alerts_file),
            Path(args.sevastopol_events_file),
        )
        mode = "cached_bridge"
    else:
        polled, errors = poll_alerts(
            Path(args.kyiv_alerts_file),
            Path(args.sevastopol_events_file),
        )
        mode = "network"
    new_episodes = process_events(state, polled, errors, started)
    matching_refresh = refresh_queue_matching(queue, state, {"needs_review"})
    telegram_errors = refresh_telegram_cache(state, started)
    errors.update({f"telegram:{key}": value for key, value in telegram_errors.items()})
    due = due_checks(state, followup_cutoff)
    searches = {}
    composition_target_episode_ids = set()
    new_candidates = 0
    fulltext_fetches = 0
    fulltext_rescued_candidates = 0
    for city_key, city_due in sorted(due.items()):
        composition_target_episode_ids.update(
            str(ep.get("episode_id") or "") for ep, _ in city_due if ep.get("episode_id")
        )
        earliest = min(parse_dt(ep.get("alert_start")) or started for ep, _ in city_due)
        rows = telegram_candidates_for_city(state, city_key, earliest, started)
        telegram_count = len(rows)
        query_url = None
        google_error = None
        google_stats = {"fulltext_fetches": 0, "fulltext_rescued_candidates": 0}
        try:
            google_rows, query_url, google_stats = search_city_news(city_key, earliest, started)
            rows.extend(google_rows)
        except Exception as exc:
            google_error = f"{type(exc).__name__}: {exc}"
            errors[f"search:{city_key}"] = google_error

        dedup = {(row["url"], row["title"]): row for row in rows}
        rows = list(dedup.values())
        added, auto_approved = add_candidates(
            queue,
            city_key,
            rows,
            city_due,
            tracked_episodes_for_city(state, city_key),
            started,
        )
        new_candidates += added
        fulltext_fetches += int(google_stats.get("fulltext_fetches") or 0)
        fulltext_rescued_candidates += int(google_stats.get("fulltext_rescued_candidates") or 0)
        searches[city_key] = {
            "due_checks": len(city_due),
            "telegram_results": telegram_count,
            "results_after_filter": len(rows),
            "new_candidates": added,
            "auto_approved_strict": auto_approved,
            "fulltext_fetches": int(google_stats.get("fulltext_fetches") or 0),
            "fulltext_rescued_candidates": int(google_stats.get("fulltext_rescued_candidates") or 0),
            "query_url": query_url,
            "query_urls": google_stats.get("query_urls") or {},
            "query_family_result_counts": google_stats.get("query_family_result_counts") or {},
            "results_after_family_merge": int(google_stats.get("results_after_family_merge") or 0),
            "google_error": google_error,
        }
        for _, check in city_due:
            check["checked_at"] = iso(started)
            check["new_candidates"] = added

    composition_refresh = apply_episode_composition(
        queue,
        state,
        composition_target_episode_ids,
    )
    (
        due_checks_at_cutoff,
        checked_due_checks_at_cutoff,
        unchecked_due_checks_at_cutoff,
    ) = due_check_counts(due)
    finished = now_utc()
    became_due_during_run = checks_became_due_between(state, followup_cutoff, finished)

    queue.sort(key=lambda x: (x.get("first_discovered_at") or "", x.get("city_key") or ""), reverse=True)
    state["last_run_at"] = iso(started)
    state["followup_schedule_hours"] = [hours for _, hours in FOLLOWUP_HOURS]
    report = {
        "ok": not errors,
        "started_at": iso(started),
        "finished_at": iso(finished),
        "followup_cutoff_at": iso(followup_cutoff),
        "due_checks_at_cutoff": due_checks_at_cutoff,
        "checked_due_checks_at_cutoff": checked_due_checks_at_cutoff,
        "unchecked_due_checks_at_cutoff": unchecked_due_checks_at_cutoff,
        "became_due_during_run": became_due_during_run,
        "city_count": len(CITY_CONFIG),
        "mode": mode,
        "new_alert_episodes": new_episodes,
        "cities_searched": sorted(searches),
        "searches": searches,
        "new_review_candidates": new_candidates,
        "review_queue_size": len(queue),
        "matching_refresh": matching_refresh,
        "composition_refresh": composition_refresh,
        "fulltext_fetches": fulltext_fetches,
        "fulltext_rescued_candidates": fulltext_rescued_candidates,
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
