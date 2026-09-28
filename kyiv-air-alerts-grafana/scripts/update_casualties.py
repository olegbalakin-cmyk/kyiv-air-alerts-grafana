#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data" / "dashboard_data.json"
CASUALTY_DIR = ROOT / "data" / "casualties"
BASELINE_FILE = CASUALTY_DIR / "baseline_monthly.csv"
REVISIONS_FILE = CASUALTY_DIR / "revisions.csv"
REVIEW_QUEUE_FILE = CASUALTY_DIR / "review_queue.json"
SOURCE_STATE_FILE = CASUALTY_DIR / "source_state.json"
CITY_SERIES_DIR = CASUALTY_DIR / "cities"
MASTER_WIDE_FILE = CASUALTY_DIR / "master_20cities_monthly_wide.csv"
MASTER_MANIFEST_FILE = CASUALTY_DIR / "master_20cities_manifest.json"

TZ = ZoneInfo("Europe/Kyiv")
BASELINE_CUTOFF = date(2026, 9, 15)

SOURCE_PAGES = [
    {
        "name": "Суспільне Київ",
        "kind": "html",
        "url": "https://suspilne.media/kyiv/",
        "allowed_host": "suspilne.media",
    },
    {
        "name": "hromadske Київ",
        "kind": "html",
        "url": "https://hromadske.ua/kyyiv",
        "allowed_host": "hromadske.ua",
    },
    {
        "name": "Українська правда",
        "kind": "rss",
        "url": "https://www.pravda.com.ua/rss/view_news/",
        "allowed_host": "www.pravda.com.ua",
    },
]

ATTACK_TERMS = (
    "атак", "обстріл", "удар", "ракета", "ракет", "дрон", "бпла", "шахед", "влуч", "вибух"
)
CASUALTY_TERMS = ("загиб", "загин", "помер", "смерт")
LOCALITY_TERMS = ("київ", "києв", "столиц")

MONTH_NAMES = {
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

BASELINE_YEAR_TOTALS = {2022: 50, 2023: 41, 2024: 44, 2025: 166, 2026: 153}


def http_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (compatible; KyivCasualtyMonitor/1.0; "
                "+https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana)"
            ),
            "Accept-Language": "uk,en;q=0.8",
        }
    )
    return session


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def atomic_write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def load_baseline() -> list[dict]:
    if not BASELINE_FILE.exists():
        raise RuntimeError(f"Missing casualty baseline: {BASELINE_FILE}")
    rows = []
    with BASELINE_FILE.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            month = (row.get("month") or "").strip()
            if not re.fullmatch(r"20\d{2}-(0[1-9]|1[0-2])", month):
                raise RuntimeError(f"Invalid baseline month: {month!r}")
            try:
                deaths = int((row.get("deaths") or "0").strip())
            except ValueError as exc:
                raise RuntimeError(f"Invalid death count for {month}: {row.get('deaths')!r}") from exc
            if deaths < 0:
                raise RuntimeError(f"Negative baseline death count for {month}")
            rows.append(
                {
                    "month": month,
                    "deaths": deaths,
                    "coverage_through": (row.get("coverage_through") or "").strip() or None,
                    "note": (row.get("note") or "").strip() or None,
                }
            )
    if not rows:
        raise RuntimeError("Casualty baseline is empty")
    if len({r["month"] for r in rows}) != len(rows):
        raise RuntimeError("Duplicate months in casualty baseline")
    return sorted(rows, key=lambda r: r["month"])


def validate_baseline(rows: list[dict]) -> None:
    totals = defaultdict(int)
    for row in rows:
        totals[int(row["month"][:4])] += row["deaths"]
    for year, expected in BASELINE_YEAR_TOTALS.items():
        actual = totals.get(year, 0)
        if actual != expected:
            raise RuntimeError(f"Baseline control failed for {year}: {actual} != {expected}")
    last = rows[-1]
    if last["month"] != "2026-09" or last.get("coverage_through") != BASELINE_CUTOFF.isoformat():
        raise RuntimeError("Baseline cutoff metadata must be 2026-09 through 2026-09-15")


def load_revisions() -> list[dict]:
    if not REVISIONS_FILE.exists():
        return []
    rows = []
    seen_ids = set()
    with REVISIONS_FILE.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            record_id = (row.get("record_id") or "").strip()
            if not record_id:
                continue
            if record_id in seen_ids:
                raise RuntimeError(f"Duplicate casualty revision record_id: {record_id}")
            seen_ids.add(record_id)
            attack_date = (row.get("attack_date") or "").strip()
            try:
                attack_day = date.fromisoformat(attack_date)
            except ValueError as exc:
                raise RuntimeError(f"Invalid attack_date in revision {record_id}: {attack_date!r}") from exc
            try:
                delta = int((row.get("deaths_delta") or "0").strip())
            except ValueError as exc:
                raise RuntimeError(f"Invalid deaths_delta in revision {record_id}") from exc
            status = (row.get("status") or "").strip().lower()
            if status not in {"confirmed", "needs_review", "rejected"}:
                raise RuntimeError(f"Invalid status in revision {record_id}: {status!r}")
            rows.append(
                {
                    "record_id": record_id,
                    "observed_at": (row.get("observed_at") or "").strip(),
                    "attack_date": attack_day,
                    "deaths_delta": delta,
                    "status": status,
                    "source_name": (row.get("source_name") or "").strip(),
                    "source_url": (row.get("source_url") or "").strip(),
                    "note": (row.get("note") or "").strip(),
                }
            )
    return rows


def month_timestamp(month: str) -> str:
    year, mon = map(int, month.split("-"))
    return datetime(year, mon, 1, tzinfo=TZ).isoformat()


def build_monthly(baseline: list[dict], revisions: list[dict]) -> list[dict]:
    base = {row["month"]: row for row in baseline}
    deltas = defaultdict(int)
    for row in revisions:
        if row["status"] != "confirmed":
            continue
        month = row["attack_date"].strftime("%Y-%m")
        deltas[month] += row["deaths_delta"]

    all_months = sorted(set(base) | set(deltas))
    output = []
    for month in all_months:
        baseline_deaths = base.get(month, {}).get("deaths", 0)
        delta = deltas.get(month, 0)
        deaths = baseline_deaths + delta
        if deaths < 0:
            raise RuntimeError(f"Confirmed revisions make {month} negative: {deaths}")
        row = {
            "time": month_timestamp(month),
            "month": month,
            "deaths": deaths,
            "baseline_deaths": baseline_deaths,
            "revision_delta": delta,
        }
        if month in base and base[month].get("coverage_through"):
            row["baseline_coverage_through"] = base[month]["coverage_through"]
        output.append(row)
    return output


def looks_relevant(text: str) -> bool:
    text = " ".join((text or "").lower().split())
    return (
        any(term in text for term in LOCALITY_TERMS)
        and any(term in text for term in ATTACK_TERMS)
        and any(term in text for term in CASUALTY_TERMS)
    )


def normalize_url(base_url: str, href: str) -> str | None:
    if not href:
        return None
    url = urljoin(base_url, href.strip())
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return None
    return parsed._replace(fragment="").geturl()


def discover_html(session: requests.Session, cfg: dict) -> list[tuple[str, str]]:
    response = session.get(cfg["url"], timeout=45)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    out = []
    for a in soup.find_all("a", href=True):
        text = " ".join(a.stripped_strings)
        if not looks_relevant(text):
            continue
        url = normalize_url(cfg["url"], a.get("href", ""))
        if not url or urlparse(url).netloc != cfg["allowed_host"]:
            continue
        out.append((url, text))
    return list(dict.fromkeys(out))


def discover_rss(session: requests.Session, cfg: dict) -> list[tuple[str, str]]:
    import xml.etree.ElementTree as ET

    response = session.get(cfg["url"], timeout=45)
    response.raise_for_status()
    root = ET.fromstring(response.content)
    out = []
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        desc = BeautifulSoup(item.findtext("description") or "", "html.parser").get_text(" ", strip=True)
        text = f"{title} {desc}"
        if not looks_relevant(text):
            continue
        url = normalize_url(cfg["url"], link)
        if not url or urlparse(url).netloc != cfg["allowed_host"]:
            continue
        out.append((url, title))
    return list(dict.fromkeys(out))


def extract_article(session: requests.Session, url: str) -> tuple[str, str, str]:
    response = session.get(url, timeout=45)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    title_tag = soup.find("h1") or soup.find("title")
    title = " ".join(title_tag.stripped_strings) if title_tag else ""
    article = soup.find("article") or soup.find("main") or soup.body or soup
    text = " ".join(article.stripped_strings)
    text = re.sub(r"\s+", " ", text).strip()
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return title, text, digest


def extract_death_counts(text: str) -> list[int]:
    text = text.lower()
    patterns = [
        r"\b(\d{1,3})\s+(?:люд\w*\s+)?загин\w*",
        r"\b(\d{1,3})\s+загибл\w*",
        r"загибл\w*\s+(?:щонайменше\s+|понад\s+)?(\d{1,3})\b",
        r"відомо\s+про\s+(\d{1,3})\s+загибл\w*",
        r"кільк\w*\s+загибл\w*[^.]{0,60}?\b(\d{1,3})\b",
    ]
    values = []
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            value = int(match.group(1))
            if 0 < value <= 200:
                values.append(value)
    return sorted(set(values))


def extract_dates(text: str) -> list[str]:
    lowered = text.lower()
    found = []
    current_year = datetime.now(TZ).year
    month_alt = "|".join(MONTH_NAMES)
    pattern = re.compile(rf"\b([0-3]?\d)\s+({month_alt})(?:\s+(20\d{{2}})\s+року)?\b")
    for match in pattern.finditer(lowered):
        day = int(match.group(1))
        month = MONTH_NAMES[match.group(2)]
        year = int(match.group(3)) if match.group(3) else current_year
        try:
            found.append(date(year, month, day).isoformat())
        except ValueError:
            continue
    return sorted(set(found))


def discover_candidates() -> tuple[list[dict], dict]:
    session = http_session()
    queue = load_json(REVIEW_QUEUE_FILE, [])
    if not isinstance(queue, list):
        queue = []
    by_url = {item.get("url"): item for item in queue if isinstance(item, dict) and item.get("url")}

    state = load_json(SOURCE_STATE_FILE, {})
    if isinstance(state, list):
        state = {url: "" for url in state if isinstance(url, str)}
    if not isinstance(state, dict):
        state = {}

    now = datetime.now(TZ).isoformat()
    for cfg in SOURCE_PAGES:
        try:
            links = discover_rss(session, cfg) if cfg["kind"] == "rss" else discover_html(session, cfg)
        except Exception as exc:
            print(f"WARNING: casualty source discovery failed for {cfg['name']}: {exc}", file=sys.stderr)
            continue
        for url, link_text in links:
            try:
                title, text, digest = extract_article(session, url)
            except Exception as exc:
                print(f"WARNING: casualty article fetch failed for {url}: {exc}", file=sys.stderr)
                continue
            if not looks_relevant(f"{title} {text[:4000]}"):
                continue
            if state.get(url) == digest:
                continue
            counts = extract_death_counts(f"{title} {text[:12000]}")
            dates = extract_dates(f"{title} {text[:12000]}")
            old = by_url.get(url, {})
            by_url[url] = {
                "url": url,
                "source": cfg["name"],
                "title": title or link_text,
                "status": "needs_review",
                "first_discovered_at": old.get("first_discovered_at", now),
                "updated_at": now,
                "detected_death_counts": counts,
                "detected_dates": dates,
                "snippet": text[:1800],
                "content_sha256": digest,
            }
            state[url] = digest

    queue = sorted(by_url.values(), key=lambda x: x.get("updated_at", ""), reverse=True)
    atomic_write_json(REVIEW_QUEUE_FILE, queue)
    atomic_write_json(SOURCE_STATE_FILE, state)
    return queue, state




def load_master_city_series() -> dict[str, dict]:
    manifest = load_json(MASTER_MANIFEST_FILE, {})
    if not MASTER_WIDE_FILE.exists() or not isinstance(manifest, dict):
        return {}
    cities = manifest.get("cities") or []
    meta_by_slug = {
        str(item.get("slug")): item
        for item in cities
        if isinstance(item, dict) and item.get("slug")
    }
    out = {
        slug: {
            "meta": {
                "city_slug": slug,
                "city": item.get("label") or slug,
                "series_status": "validated_structured_output",
                "confirmed_deaths": int(item.get("confirmed_deaths") or 0),
                "source": manifest.get("source"),
                "date_attribution": manifest.get("date_attribution"),
                "geography": manifest.get("geography"),
                "current_month_partial": bool(manifest.get("current_month_partial")),
            },
            "monthly": [],
        }
        for slug, item in meta_by_slug.items()
    }
    with MASTER_WIDE_FILE.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            month = (row.get("month") or "").strip()
            if not re.fullmatch(r"20\d{2}-(0[1-9]|1[0-2])", month):
                raise RuntimeError(f"Invalid month in casualty master: {month!r}")
            for slug in out:
                raw = (row.get(slug) or "0").strip()
                deaths = int(raw)
                if deaths < 0:
                    raise RuntimeError(f"Negative casualty count for {slug} {month}")
                out[slug]["monthly"].append({
                    "time": month_timestamp(month),
                    "month": month,
                    "deaths": deaths,
                })
    for slug, series in out.items():
        actual = sum(r["deaths"] for r in series["monthly"])
        expected = int(series["meta"]["confirmed_deaths"])
        if actual != expected:
            raise RuntimeError(f"{slug} casualty master total mismatch: {actual} != {expected}")
    return out


def load_validated_city_series() -> dict[str, dict]:
    out: dict[str, dict] = load_master_city_series()
    if not CITY_SERIES_DIR.exists():
        return out
    for city_dir in sorted(p for p in CITY_SERIES_DIR.iterdir() if p.is_dir()):
        manifest = load_json(city_dir / "manifest.json", {})
        if not isinstance(manifest, dict):
            continue
        slug = str(manifest.get("city_slug") or city_dir.name).strip()
        monthly_name = str(manifest.get("monthly_file") or f"{slug}_air_attack_deaths_monthly.csv")
        monthly_path = city_dir / monthly_name
        if not slug or not monthly_path.exists():
            continue
        rows = []
        with monthly_path.open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                month = (row.get("month") or "").strip()
                if not re.fullmatch(r"20\d{2}-(0[1-9]|1[0-2])", month):
                    raise RuntimeError(f"Invalid month in {monthly_path}: {month!r}")
                deaths = int((row.get("deaths_confirmed") or row.get("deaths") or "0").strip())
                item = {
                    "time": month_timestamp(month),
                    "month": month,
                    "deaths": deaths,
                }
                for key in ("event_count", "late_deaths_included"):
                    raw = (row.get(key) or "").strip()
                    if raw:
                        item[key] = int(raw)
                rows.append(item)
        expected = manifest.get("confirmed_deaths")
        actual = sum(r["deaths"] for r in rows)
        if expected is not None and actual != int(expected):
            raise RuntimeError(f"{slug} casualty total mismatch: {actual} != {expected}")
        out[slug] = {"meta": manifest, "monthly": rows}
    return out


def update_dashboard_data(no_network: bool) -> None:
    baseline = load_baseline()
    validate_baseline(baseline)
    revisions = load_revisions()
    queue = load_json(REVIEW_QUEUE_FILE, [])
    if not no_network:
        queue, _ = discover_candidates()
    if not isinstance(queue, list):
        queue = []

    monthly = build_monthly(baseline, revisions)
    confirmed = [r for r in revisions if r["status"] == "confirmed"]
    pending = [item for item in queue if isinstance(item, dict) and item.get("status") == "needs_review"]

    if DATA_FILE.exists():
        dashboard_data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    else:
        dashboard_data = {}

    dashboard_data["casualties"] = {
        "meta": {
            "city": "Київ",
            "scope": "Kyiv city only; missile, drone and other aerial attacks",
            "baseline_cutoff": BASELINE_CUTOFF.isoformat(),
            "baseline_source": "audited monthly reconstruction completed 2026-09-15",
            "late_deaths_attributed_to_attack_date": True,
            "ground_combat_and_artillery_excluded": True,
            "year_2025_reconstructed_deaths": 166,
            "year_2025_kmva_cumulative": 171,
            "year_2025_note": (
                "The five-person difference could not be attributed to specific attacks in public sources; "
                "the audited attack-level reconstruction is used in the chart."
            ),
            "confirmed_revision_records": len(confirmed),
            "pending_review_candidates": len(pending),
            "generated_at": datetime.now(TZ).isoformat(),
        },
        "monthly": monthly,
    }
    city_series = load_validated_city_series()
    city_series["kyiv"] = dashboard_data["casualties"]
    dashboard_data["casualties_by_city"] = city_series

    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(dashboard_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(
        f"Updated casualty series: {len(monthly)} months, "
        f"{len(confirmed)} confirmed revision records, {len(pending)} review candidates"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build city air-attack casualty series and collect Kyiv review candidates")
    parser.add_argument("--no-network", action="store_true", help="Skip source discovery and only rebuild from local files")
    args = parser.parse_args()
    update_dashboard_data(no_network=args.no_network)


if __name__ == "__main__":
    main()
