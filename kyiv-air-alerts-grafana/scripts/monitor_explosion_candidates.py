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


def strict_explosion_signal(text: str) -> bool:
    low = normalize_evidence_text(text)
    if not low:
        return False
    if controlled_blast_signal(low) and not air_military_context(low):
        return False
    if re.search(r"\bвибух\w*", low):
        return True
    if re.search(r"\b(?:влуч\w*|поціл\w*|приліт\w*|вдарил\w*)", low):
        return True
    if re.search(r"\b(?:завдал\w*|нанес\w*)\b.{0,50}\bудар\w*", low):
        return True
    if re.search(r"\bудар(?:у|и|ів|ом|ами)?\b", low):
        threat_only = bool(re.search(r"\bзагроз\w*.{0,30}\bудар(?:у|и|ів|ом|ами)?\b", low))
        if not threat_only:
            return True
    return False


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


def contemporaneous_live_wording(text: str) -> bool:
    low = normalize_evidence_text(text)
    return bool(
        re.search(
            r"(?:лунають\s+(?:повторн\w*\s+)?вибух\w*|"
            r"чути\s+(?:звук\w*\s+)?вибух\w*|"
            r"гримлять\s+вибух\w*|"
            r"щойно.{0,40}вибух\w*|"
            r"прямо\s+зараз.{0,40}вибух\w*)",
            low,
        )
    )


def trusted_same_attack_source(row: dict) -> bool:
    source = str(row.get("source") or "")
    publisher = str(row.get("publisher") or "")
    return source.startswith("Telegram /") or "суспільн" in f"{source} {publisher}".casefold()


def trusted_live_source(row: dict) -> bool:
    return str(row.get("source") or "").startswith("Telegram /")


def exact_city_classification_evidence(city_key: str, row: dict) -> dict:
    segments = [segment for segment in classification_segments(row) if city_mentioned(city_key, segment)]
    return {"present": bool(segments), "segments": segments[:4]}


def strict_explosion_evidence(city_key: str, row: dict) -> dict:
    exact = exact_city_classification_evidence(city_key, row)
    segments = [segment for segment in exact["segments"] if strict_explosion_signal(segment)]
    return {"present": bool(segments), "segments": segments[:4]}


def air_military_context_evidence(row: dict) -> dict:
    segments = [segment for segment in classification_segments(row) if air_military_context(segment)]
    return {"present": bool(segments), "segments": segments[:4]}


def audited_cities_in_text(text: str) -> list[str]:
    return sorted(key for key in CITY_CONFIG if city_mentioned(key, text))


def same_attack_context_evidence(city_key: str, row: dict, strict_evidence: dict, air_evidence: dict) -> dict:
    if not strict_evidence.get("present") or not air_evidence.get("present"):
        return {"present": False, "reason": "missing_explosion_or_air_context"}
    if any(air_military_context(segment) for segment in strict_evidence.get("segments") or []):
        return {"present": True, "reason": "air_context_in_exact_city_event_segment"}
    mentioned = audited_cities_in_text(classification_text(row))
    if trusted_same_attack_source(row) and len(mentioned) <= 1:
        return {"present": True, "reason": "trusted_source_adjacent_air_context"}
    return {"present": False, "reason": "air_context_not_linked_to_exact_city_event"}


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


def search_city_news(city_key: str, earliest: datetime, now: datetime) -> tuple[list[dict], str, dict]:
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
    fulltext_fetches = 0
    fulltext_rescued_candidates = 0
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
        if row:
            rows.append(row)

    dedup = {(r["url"], r["title"]): r for r in rows}
    return list(dedup.values()), url, {
        "fulltext_fetches": fulltext_fetches,
        "fulltext_rescued_candidates": fulltext_rescued_candidates,
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
    clusters = episode_representation_clusters(matched)
    matched_ids = [str(ep["episode_id"]) for ep in matched]
    logical_groups = [
        [str(ep["episode_id"]) for ep in cluster]
        for cluster in clusters
    ]

    if len(clusters) == 1:
        singleton_id = logical_groups[0][0] if len(logical_groups[0]) == 1 else None
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
        "status_changes": 0,
    }
    for item in queue:
        if not isinstance(item, dict):
            continue
        status = str(item.get("status") or "")
        if statuses is not None and status not in statuses:
            continue
        city_key = str(item.get("city_key") or "")
        if city_key not in CITY_CONFIG:
            continue
        before_status = item.get("status")
        matching = match_candidate_to_episodes(item, tracked_episodes_for_city(state, city_key))
        apply_matching_result(item, matching)
        counts["candidates_checked"] += 1
        counts[matching["outcome"]] += 1
        if item.get("status") != before_status:
            counts["status_changes"] += 1
            raise AssertionError("Episode matching must not change candidate status")
    return counts


def matched_episode_rows(matching: dict, episodes: list[dict]) -> list[dict]:
    wanted = set(matching.get("matched_episode_ids") or [])
    return [ep for ep in episodes if str(ep.get("episode_id") or "") in wanted]


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
    pattern = re.compile(r"(?:\bо\b|\bблизько\b|\bприблизно\b)\s*(\d{1,2})[:.](\d{2})", re.IGNORECASE)
    for hit in pattern.finditer(low):
        hour, minute = int(hit.group(1)), int(hit.group(2))
        if hour > 23 or minute > 59:
            continue
        if min(abs(hit.start() - event.start()) for event in event_hits) <= 100:
            out.append((hour, minute))
    return out


def explicit_event_time_relation(
    row: dict,
    event_segments: list[str],
    matching: dict,
    episodes: list[dict],
) -> dict:
    published = parse_dt(row.get("published_at"))
    if not published or matching.get("outcome") != "unique_match":
        return {"relation": None, "event_time": None, "distance_seconds": None}

    matched = matched_episode_rows(matching, episodes)
    if not matched:
        return {"relation": None, "event_time": None, "distance_seconds": None}

    local_day = published.astimezone(KYIV_TZ).date()
    candidates = []
    for segment in event_segments:
        for hour, minute in event_clock_mentions(segment):
            for day_offset in (0, -1):
                day = local_day + timedelta(days=day_offset)
                event_dt = datetime(day.year, day.month, day.day, hour, minute, tzinfo=KYIV_TZ).astimezone(UTC)
                for ep in matched:
                    start = parse_dt(ep.get("alert_start"))
                    end = parse_dt(ep.get("alert_end"))
                    if not start or not end:
                        continue
                    if start <= event_dt <= end:
                        candidates.append(("inside", 0.0, event_dt))
                        continue
                    before = (start - event_dt).total_seconds()
                    after = (event_dt - end).total_seconds()
                    limit = SENSITIVITY_NEAR_BOUNDARY_MAX_MINUTES * 60
                    if 0 < before <= limit:
                        candidates.append(("near_before", before, event_dt))
                    elif 0 < after <= limit:
                        candidates.append(("near_after", after, event_dt))

    if not candidates:
        return {"relation": None, "event_time": None, "distance_seconds": None}

    candidates.sort(key=lambda item: (0 if item[0] == "inside" else 1, item[1], item[2]))
    relation, distance_seconds, event_dt = candidates[0]
    return {
        "relation": relation,
        "event_time": iso(event_dt),
        "distance_seconds": distance_seconds,
    }


def explicit_event_time_binding(row: dict, event_segments: list[str], matching: dict, episodes: list[dict]) -> dict:
    relation = explicit_event_time_relation(row, event_segments, matching, episodes)
    return {
        "present": relation.get("relation") == "inside",
        "event_time": relation.get("event_time") if relation.get("relation") == "inside" else None,
    }


def temporal_binding_evidence(row: dict, strict_evidence: dict, matching: dict, episodes: list[dict]) -> dict:
    event_segments = list(strict_evidence.get("segments") or [])
    clock = explicit_event_time_relation(row, event_segments, matching, episodes)
    if clock.get("relation") == "inside":
        return {
            "present": True,
            "code": "TEMPORAL_EXPLICIT_EVENT_TIME_INSIDE_EPISODE",
            "evidence": clock.get("event_time"),
            "near_boundary": {"present": False},
        }
    if clock.get("relation") in {"near_before", "near_after"}:
        return {
            "present": False,
            "code": "NO_STRICT_TEMPORAL_BINDING",
            "evidence": None,
            "near_boundary": {
                "present": True,
                "code": "TEMPORAL_EXPLICIT_EVENT_TIME_NEAR_BOUNDARY",
                "relation": clock.get("relation"),
                "event_time": clock.get("event_time"),
                "distance_seconds": clock.get("distance_seconds"),
            },
        }

    explicit_segment = next((segment for segment in event_segments if explicit_alert_relation(segment)), None)
    if explicit_segment:
        return {
            "present": True,
            "code": "TEMPORAL_EXPLICIT_ALERT_RELATION",
            "evidence": explicit_segment,
            "near_boundary": {"present": False},
        }

    published = parse_dt(row.get("published_at"))
    if (
        published
        and matching.get("outcome") == "unique_match"
        and trusted_live_source(row)
        and any(contemporaneous_live_wording(segment) for segment in event_segments)
    ):
        for ep in matched_episode_rows(matching, episodes):
            start = parse_dt(ep.get("alert_start"))
            end = parse_dt(ep.get("alert_end"))
            if start and end and start <= published <= end:
                return {
                    "present": True,
                    "code": "TEMPORAL_CONTEMPORANEOUS_LIVE_WORDING",
                    "evidence": iso(published),
                    "near_boundary": {"present": False},
                }

    return {
        "present": False,
        "code": "NO_STRICT_TEMPORAL_BINDING",
        "evidence": None,
        "near_boundary": {"present": False},
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

def classify_candidate(row: dict, city_key: str, episodes: list[dict], matching: dict | None = None) -> dict:
    matching = matching or match_candidate_to_episodes(row, episodes)
    exact = exact_city_classification_evidence(city_key, row)
    strict = strict_explosion_evidence(city_key, row)
    air = air_military_context_evidence(row)
    same_attack = same_attack_context_evidence(city_key, row, strict, air)
    temporal = temporal_binding_evidence(row, strict, matching, episodes)
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
    controlled = controlled_blast_signal(text) and not air["present"]
    whole_message_event = any(strict_explosion_signal(segment) for segment in segments)
    pvo_only_complete_message = (
        trusted_live_source(row)
        and exact["present"]
        and not whole_message_event
        and "ппо" in normalize_evidence_text(text)
    )
    fulltext_requires_review = row.get("discovery_basis") == "publisher_fulltext"

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
    reason_codes.append("AIR_MILITARY_CONTEXT" if air["present"] else "NO_AIR_MILITARY_CONTEXT")
    if air["present"]:
        reason_codes.append("SAME_ATTACK_CONTEXT_SUPPORTED" if same_attack["present"] else "AIR_CONTEXT_NOT_LINKED_TO_EVENT")
    reason_codes.append(temporal["code"] if temporal["present"] else "NO_STRICT_TEMPORAL_BINDING")
    near_boundary = bool((temporal.get("near_boundary") or {}).get("present"))
    if controlled:
        reason_codes.append("DETERMINISTIC_CONTROLLED_BLAST")
    if publisher_only_city:
        reason_codes.append("EXACT_CITY_ONLY_PUBLISHER_BRANDING")
    if pvo_only_complete_message:
        reason_codes.append("PVO_ONLY_COMPLETE_MESSAGE")
    if fulltext_requires_review:
        reason_codes.append("PUBLISHER_FULLTEXT_REQUIRES_REVIEW")

    proposed = "needs_review"
    if controlled or publisher_only_city or pvo_only_complete_message:
        proposed = "rejected"
    elif fulltext_requires_review:
        proposed = "needs_review"
    elif (
        outcome == "unique_match"
        and matching.get("matched_episode_id")
        and exact["present"]
        and strict["present"]
        and air["present"]
        and same_attack["present"]
        and temporal["present"]
    ):
        proposed = "approved_strict"
    elif (
        outcome == "unique_match"
        and matching.get("matched_episode_id")
        and exact["present"]
        and strict["present"]
        and air["present"]
        and same_attack["present"]
    ):
        proposed = "approved_sensitivity"
        reason_codes.append(
            "SENSITIVITY_NEAR_BOUNDARY"
            if near_boundary
            else "SENSITIVITY_INFERRED_SAME_ATTACK"
        )
    return {
        "proposed_outcome": proposed,
        "matching": matching,
        "exact_city_classification_evidence": exact,
        "strict_explosion_evidence": strict,
        "air_military_context": air,
        "same_attack_context": same_attack,
        "temporal_binding": temporal,
        "sensitivity_basis": (
            "near_boundary"
            if proposed == "approved_sensitivity" and near_boundary
            else ("inferred_same_attack" if proposed == "approved_sensitivity" else None)
        ),
        "reason_codes": reason_codes,
    }

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
            "classification_evidence": {
                "exact_city": decision["exact_city_classification_evidence"],
                "strict_explosion": decision["strict_explosion_evidence"],
                "air_military_context": decision["air_military_context"],
                "same_attack_context": decision["same_attack_context"],
                "temporal_binding": decision["temporal_binding"],
                "sensitivity_basis": decision["sensitivity_basis"],
            },
            "review_note": (
                "evidence-layered auto-classification"
                if status in {"approved_strict", "approved_sensitivity", "rejected"}
                else "evidence-layered classification requires manual review"
            ),
            "note": (
                "Discovery relevance, episode matching, and strict/sensitivity classification are separate. "
                "Publication time can build a candidate episode set but is never event-time proof. "
                "Strict requires exact-city explosion/strike evidence, aerial-war context, a single raw matched episode, "
                "and historical-method temporal binding. Sensitivity requires the same event/context evidence and a single raw match "
                "but allows inferred-same-attack timing. PVO-only evidence is never strict."
            ),
        }
        apply_matching_result(item, matching)
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
    assert not strict_explosion_signal("У Києві працюють сили ППО")
    assert not strict_explosion_signal("У Полтаві було гучно")
    assert strict_explosion_signal("У Дніпрі пролунав вибух")
    assert air_military_context("Повідомляли про КАБ у напрямку міста")
    assert air_military_context("Повітряні сили попередили про Бандероль")
    assert air_military_context("Ракета рухається у напрямку міста")
    assert explicit_alert_relation("Вибух стався після оголошення тривоги")
    assert explicit_alert_relation("У місті пролунав вибух, коли тривала повітряна тривога")

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

    # IR13: publisher full-text rescue remains manual-review-only.
    fulltext_queue = []
    fulltext_added, fulltext_auto = add_candidates(
        fulltext_queue, "poltava",
        [{**strict_base, "url": "https://news.google.test/fulltext-review", "discovery_basis": "publisher_fulltext", "matched_text_excerpt": strict_base["title"]}],
        due, [poltava_ep], dt,
    )
    assert fulltext_added == 1 and fulltext_auto == 0
    assert fulltext_queue[0]["status"] == "needs_review"
    assert "PUBLISHER_FULLTEXT_REQUIRES_REVIEW" in fulltext_queue[0]["classification_reason_codes"]

    # Mandatory: Kyiv PVO-only must never be strict.
    kyiv_ep = make_episode("kyiv", dt, dt + timedelta(hours=1))
    kyiv_pvo = {
        **strict_base,
        "title": "Київ — повітряна тривога через загрозу дронів. У столиці працює ППО.",
        "snippet": "",
        "source": "Telegram / СУСПІЛЬНЕ НОВИНИ",
        "publisher": "СУСПІЛЬНЕ НОВИНИ",
    }
    kyiv_pvo_decision = classify_candidate(kyiv_pvo, "kyiv", [kyiv_ep])
    assert kyiv_pvo_decision["proposed_outcome"] != "approved_strict"
    assert not kyiv_pvo_decision["strict_explosion_evidence"]["present"]
    assert "PVO_ONLY_COMPLETE_MESSAGE" in kyiv_pvo_decision["reason_codes"]

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

    # IR14 deterministic PVO-only rejection.
    pvo_only = {
        **strict_base,
        "title": "У Полтаві працює ППО. БпЛА заходять на місто.",
        "snippet": "",
        "source": "Telegram / СУСПІЛЬНЕ НОВИНИ",
        "publisher": "СУСПІЛЬНЕ НОВИНИ",
    }
    pvo_decision = classify_candidate(pvo_only, "poltava", [poltava_ep])
    assert pvo_decision["proposed_outcome"] == "rejected"
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

    # Matching invariants remain intact.
    existing_queue = [{
        **strict_base,
        "candidate_id": "existing-unmatched",
        "city_key": "poltava",
        "city": "Полтава",
        "status": "needs_review",
        "url": "https://news.google.test/existing-unmatched",
        "trigger_episode_ids": [],
        "trigger_check_labels": ["72h"],
        "matched_episode_id": None,
    }]
    assert refresh_queue_matching(existing_queue, {"cities": {"poltava": {"episodes": []}}}, {"needs_review"})["no_match"] == 1
    assert refresh_queue_matching(existing_queue, {"cities": {"poltava": {"episodes": [poltava_ep]}}}, {"needs_review"})["unique_match"] == 1
    assert existing_queue[0]["matched_episode_id"] == poltava_ep["episode_id"]
    assert existing_queue[0]["status"] == "needs_review"

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

    if "kyiv" in CITY_CONFIG:
        assert load_kyiv_alert_episodes(KYIV_ALERTS_FILE)[-1]["alert_source"] == "kyiv_combined_exact_city"
    if "sevastopol" in CITY_CONFIG:
        assert load_sevastopol_alert_episodes(SEVASTOPOL_EVENTS_FILE)[-1]["alert_source"] == "sevastopol_verified_exact_city_pairs"

    print(
        f"Self-test OK: {len(CITY_CONFIG)} audited cities; classification requirements IR01-IR20 covered; "
        "PVO-only and publisher-branding guards; KAB/UAV/missile context; explicit/clock/live temporal binding; "
        "near-boundary and inferred-same-attack sensitivity; late discovery; overlap/near-duplicate guards; dry replay purity"
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
    new_candidates = 0
    fulltext_fetches = 0
    fulltext_rescued_candidates = 0
    for city_key, city_due in sorted(due.items()):
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
            "google_error": google_error,
        }
        for _, check in city_due:
            check["checked_at"] = iso(started)
            check["new_candidates"] = added

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
