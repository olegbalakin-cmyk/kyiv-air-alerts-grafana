#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import quote_plus
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
BASELINE_FILE = DATA / "explosion_audited_baseline.json"
SEED_FILE = DATA / "explosion_daily_alert_seed.json"
OUTPUT_FILE = DATA / "explosions_test.json"
STATE_FILE = DATA / "explosion_monitor_state.json"
QUEUE_FILE = DATA / "explosion_review_queue.json"
LAST_RUN_FILE = DATA / "explosion_monitor_last_run.json"
DASHBOARD_FILE = DATA / "dashboard_data.json"

UTC = timezone.utc
KYIV_TZ = ZoneInfo("Europe/Kyiv")
ROLLING_DAYS = 90
FOLLOWUPS = [("immediate", 0), ("24h", 24), ("72h", 72), ("7d", 168)]
CITY_ALIASES = {
    "poltava": ["полтава", "полтаві", "полтави", "полтаву", "полтавою"],
    "uzhhorod": ["ужгород", "ужгороді", "ужгорода", "ужгороду", "ужгородом"],
    "ivano_frankivsk": ["івано-франківськ", "івано-франківську", "івано-франківська", "івано-франківськом"],
    "chernivtsi": ["чернівці", "чернівцях", "чернівців", "чернівцями"],
    "ternopil": ["тернопіль", "тернополі", "тернополя", "тернополю", "тернополем"],
    "lviv": ["львів", "львові", "львова", "львову", "львовом"],
    "lutsk": ["луцьк", "луцьку", "луцька", "луцьком"],
    "rivne": ["рівне", "рівному", "рівного", "рівним"],
    "khmelnytskyi": ["хмельницький", "хмельницькому", "хмельницького", "хмельницьким"],
    "vinnytsia": ["вінниця", "вінниці", "вінницю", "вінницею"],
    "zhytomyr": ["житомир", "житомирі", "житомира", "житомиру", "житомиром"],
    "kropyvnytskyi": ["кропивницький", "кропивницькому", "кропивницького", "кропивницьким"],
    "kherson": ["херсон", "херсоні", "херсона", "херсону", "херсоном"],
    "odesa": ["одеса", "одесі", "одеси", "одесу", "одесою"],
    "cherkasy": ["черкаси", "черкасах", "черкасами"],
    "mykolaiv": ["миколаїв", "миколаєві", "миколаєва", "миколаєву", "миколаєвом"],
    "chernihiv": ["чернігів", "чернігові", "чернігова", "чернігову", "черніговом"],
    "dnipro": ["дніпро", "дніпрі", "дніпра", "дніпру", "дніпром"],
    "sumy": ["суми", "сумах", "сумами"],
    "zaporizhzhia": ["запоріжжя", "запоріжжі", "запоріжжю"],
    "kharkiv": ["харків", "харкові", "харкова", "харкову", "харковом"],
    "kyiv": ["київ", "києві", "києва", "києву", "києвом"],
    "sevastopol": ["севастополь", "севастополі", "севастополя", "севастополю", "севастополем"],
}
TELEGRAM_CHANNELS = {
    "Суспільне Новини": "suspilnenews",
    "Українська правда": "ukrpravda_news",
}
EXPLOSION_TERMS = (
    "вибух", "вибухи", "вибухів", "вибухнул", "було гучно", "гучно",
    "пролунав", "пролунали", "чути вибух", "чутно вибух",
)
AIR_TERMS = (
    "повітрян", "тривог", "дрон", "бпла", "безпілот", "шахед", "ракет",
    "ппо", "повітряна атака", "атака рф", "ворож",
)
EXPLICIT_DURING = (
    "під час повітряної тривоги",
    "під час тривоги",
    "у період повітряної тривоги",
)
GOOGLE_NEWS = "https://news.google.com/rss/search"


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def atomic_json(path: Path, obj) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def baseline_data() -> dict:
    baseline = load_json(BASELINE_FILE, {})
    cities = baseline.get("cities") if isinstance(baseline, dict) else None
    if not isinstance(cities, dict) or not cities:
        raise RuntimeError("Explosion baseline has no audited cities")
    return baseline


def audited_keys(baseline: dict) -> list[str]:
    return list((baseline.get("cities") or {}).keys())


def city_label(baseline: dict, city_key: str) -> str:
    city = (baseline.get("cities") or {}).get(city_key) or {}
    return str(city.get("label") or city_key)


def baseline_end(baseline: dict, city_key: str) -> date:
    city = (baseline.get("cities") or {}).get(city_key) or {}
    value = str(city.get("coverage_end") or "").strip()
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise RuntimeError(f"{city_key}: invalid baseline coverage_end={value!r}") from exc


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def norm(text: str) -> str:
    return " ".join((text or "").casefold().replace("’", "'").split())


def city_aliases(baseline: dict, city_key: str) -> list[str]:
    configured = CITY_ALIASES.get(city_key)
    if configured:
        return configured
    # Safe fallback for a newly audited city outside the known 23-city set:
    # exact nominative label only. This may reduce recall, but will not broaden
    # geography beyond the audited city.
    return [city_label(baseline, city_key).casefold()]


def city_mentioned(baseline: dict, city_key: str, text: str) -> bool:
    low = norm(text)
    return any(
        re.search(rf"(?<![\w-]){re.escape(alias)}(?![\w-])", low, re.IGNORECASE)
        for alias in city_aliases(baseline, city_key)
    )


def explosion_relevant(text: str) -> bool:
    low = norm(text)
    return any(term in low for term in EXPLOSION_TERMS)


def air_context(text: str) -> bool:
    low = norm(text)
    return any(term in low for term in AIR_TERMS)


def explicit_during_alert(text: str) -> bool:
    low = norm(text)
    return any(term in low for term in EXPLICIT_DURING)


def episode_id(city_key: str, start: str, end: str) -> str:
    return hashlib.sha256(f"{city_key}|{start}|{end}".encode()).hexdigest()[:24]


def candidate_id(city_key: str, url: str, text: str) -> str:
    return hashlib.sha256(f"{city_key}|{url}|{text}".encode()).hexdigest()[:24]


def load_bridge(path: Path, keys: list[str]) -> dict[str, list[dict]]:
    bridge = load_json(path, {})
    out = {key: [] for key in keys}
    for row in bridge.get("events", []):
        key = str(row.get("city_key") or "")
        if key not in out:
            continue
        start = parse_dt(row.get("start"))
        end = parse_dt(row.get("end"))
        if not start or not end or end <= start:
            continue
        start_s, end_s = iso(start), iso(end)
        out[key].append({
            "episode_id": episode_id(key, start_s, end_s),
            "city_key": key,
            "alert_start": start_s,
            "alert_end": end_s,
        })
    for key in out:
        uniq = {x["episode_id"]: x for x in out[key]}
        out[key] = sorted(uniq.values(), key=lambda x: x["alert_start"])
    return out


def completed_cutoff(now: datetime) -> date:
    return now.astimezone(KYIV_TZ).date() - timedelta(days=1)


def ensure_state(keys: list[str]) -> dict:
    state = load_json(STATE_FILE, {})
    if state.get("schema_version") != 1:
        state = {"schema_version": 1, "cities": {}}
    state.setdefault("cities", {})
    for key in keys:
        state["cities"].setdefault(key, {"episodes": []})
    return state


def make_monitored_episode(ep: dict) -> dict:
    end = parse_dt(ep["alert_end"])
    assert end
    return {
        **ep,
        "checks": [
            {
                "label": label,
                "due_at": iso(end + timedelta(hours=hours)),
                "checked_at": None,
                "new_candidates": None,
            }
            for label, hours in FOLLOWUPS
        ],
    }


def ingest_episodes(state: dict, bridge: dict[str, list[dict]], baseline: dict, keys: list[str], cutoff: date) -> int:
    added = 0
    for key in keys:
        cstate = state["cities"][key]
        known = {x["episode_id"] for x in cstate.get("episodes", [])}
        for ep in bridge.get(key, []):
            start = parse_dt(ep["alert_start"])
            if not start:
                continue
            local_day = start.astimezone(KYIV_TZ).date()
            if local_day <= baseline_end(baseline, key) or local_day > cutoff:
                continue
            if ep["episode_id"] in known:
                continue
            cstate.setdefault("episodes", []).append(make_monitored_episode(ep))
            known.add(ep["episode_id"])
            added += 1
        cstate["episodes"] = sorted(cstate["episodes"], key=lambda x: x["alert_start"])
    return added


def due_checks(state: dict, keys: list[str], now: datetime) -> dict[str, list[tuple[dict, dict]]]:
    out: dict[str, list[tuple[dict, dict]]] = {}
    for key in keys:
        for ep in state["cities"][key].get("episodes", []):
            for check in ep.get("checks", []):
                if check.get("checked_at"):
                    continue
                due = parse_dt(check.get("due_at"))
                if due and due <= now:
                    out.setdefault(key, []).append((ep, check))
    return out


def parse_pubdate(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def telegram_rows() -> list[dict]:
    rows = []
    for source, channel in TELEGRAM_CHANNELS.items():
        url = f"https://t.me/s/{channel}"
        response = requests.get(
            url,
            headers={"User-Agent": "ukraine-air-alerts-explosion-monitor/1.0"},
            timeout=30,
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        for node in soup.select(".tgme_widget_message"):
            post = node.get("data-post") or ""
            text_node = node.select_one(".tgme_widget_message_text")
            time_node = node.select_one("time[datetime]")
            text = text_node.get_text(" ", strip=True) if text_node else ""
            if not post or not text:
                continue
            published = parse_dt(time_node.get("datetime") if time_node else None)
            rows.append({
                "source": f"Telegram — {source}",
                "publisher": source,
                "url": f"https://t.me/{post}",
                "text": text,
                "published_at": iso(published) if published else None,
            })
    return rows


def google_rows(baseline: dict, city_key: str) -> tuple[list[dict], str]:
    label = city_label(baseline, city_key)
    query = (
        f'"{label}" '
        '(вибух OR вибухи OR "було гучно" OR "пролунали вибухи" OR "чути вибухи") '
        'when:8d'
    )
    url = f"{GOOGLE_NEWS}?q={quote_plus(query)}&hl=uk&gl=UA&ceid=UA:uk"
    response = requests.get(
        url,
        headers={"User-Agent": "ukraine-air-alerts-explosion-monitor/1.0", "Accept-Language": "uk,en;q=0.7"},
        timeout=30,
    )
    response.raise_for_status()
    root = ET.fromstring(response.content)
    rows = []
    for item in root.findall(".//item"):
        title = BeautifulSoup(html.unescape(item.findtext("title") or ""), "html.parser").get_text(" ", strip=True)
        desc = BeautifulSoup(html.unescape(item.findtext("description") or ""), "html.parser").get_text(" ", strip=True)
        link = (item.findtext("link") or "").strip()
        if not title or not link:
            continue
        source_el = item.find("source")
        publisher = (source_el.text or "").strip() if source_el is not None else "Google News"
        published = parse_pubdate(item.findtext("pubDate"))
        rows.append({
            "source": "Google News RSS",
            "publisher": publisher,
            "url": link,
            "text": f"{title} {desc}".strip(),
            "published_at": iso(published) if published else None,
        })
    return rows, url


def relevant_rows(baseline: dict, city_key: str, rows: list[dict], earliest: datetime, now: datetime) -> list[dict]:
    out = []
    lower = earliest - timedelta(hours=3)
    upper = now + timedelta(hours=1)
    for row in rows:
        text = row.get("text") or ""
        if not city_mentioned(baseline, city_key, text) or not explosion_relevant(text):
            continue
        published = parse_dt(row.get("published_at"))
        if published and not (lower <= published <= upper):
            continue
        out.append(row)
    dedup = {(r["url"], r["text"]): r for r in out}
    return list(dedup.values())


def unique_same_day_episode(row: dict, due: list[tuple[dict, dict]]) -> dict | None:
    published = parse_dt(row.get("published_at"))
    if not published or not explicit_during_alert(row.get("text") or "") or not air_context(row.get("text") or ""):
        return None
    day = published.astimezone(KYIV_TZ).date()
    episodes = {}
    for ep, _ in due:
        start = parse_dt(ep.get("alert_start"))
        if start and start.astimezone(KYIV_TZ).date() == day:
            episodes[ep["episode_id"]] = ep
    return next(iter(episodes.values())) if len(episodes) == 1 else None


def add_candidates(queue: list[dict], baseline: dict, city_key: str, rows: list[dict], due: list[tuple[dict, dict]], now: datetime) -> tuple[int, int]:
    by_id = {x.get("candidate_id"): x for x in queue if isinstance(x, dict) and x.get("candidate_id")}
    trigger_ids = sorted({ep["episode_id"] for ep, _ in due})
    labels = sorted({check["label"] for _, check in due})
    new_count = auto_count = 0
    for row in rows:
        cid = candidate_id(city_key, row["url"], row["text"])
        existing = by_id.get(cid)
        if existing:
            existing["last_seen_at"] = iso(now)
            existing["trigger_episode_ids"] = sorted(set(existing.get("trigger_episode_ids") or []) | set(trigger_ids))
            existing["trigger_check_labels"] = sorted(set(existing.get("trigger_check_labels") or []) | set(labels))
            continue

        matched = unique_same_day_episode(row, due)
        status = "confirmed_strict_auto" if matched else "needs_review"
        item = {
            "candidate_id": cid,
            "city_key": city_key,
            "city": city_label(baseline, city_key),
            "status": status,
            "source": row.get("source"),
            "publisher": row.get("publisher"),
            "url": row["url"],
            "text": row["text"][:4000],
            "published_at": row.get("published_at"),
            "first_discovered_at": iso(now),
            "last_seen_at": iso(now),
            "trigger_episode_ids": trigger_ids,
            "trigger_check_labels": labels,
            "matched_episode_id": matched["episode_id"] if matched else None,
            "match_basis": "explicit_during_alert_unique_local_day" if matched else None,
            "note": (
                "Auto-strict is allowed only for exact-city wording with confirmed air context, "
                "explicit wording that the explosions occurred during an alert, and one unique alert "
                "episode on that local calendar day. All other candidates require review."
            ),
        }
        queue.append(item)
        by_id[cid] = item
        new_count += 1
        if matched:
            auto_count += 1
    return new_count, auto_count


def accepted_episode_ids(queue: list[dict], city_key: str) -> tuple[set[str], set[str]]:
    strict, sensitivity = set(), set()
    for item in queue:
        if item.get("city_key") != city_key:
            continue
        eid = item.get("matched_episode_id")
        if not eid:
            continue
        status = item.get("status")
        if status in {"confirmed_strict", "confirmed_strict_auto", "approved_strict"}:
            strict.add(eid)
            sensitivity.add(eid)
        elif status in {"confirmed_sensitivity", "approved_sensitivity"}:
            sensitivity.add(eid)
    return strict, sensitivity


def rebuild_output(state: dict, queue: list[dict], baseline: dict, keys: list[str], cutoff: date) -> dict:
    seed = load_json(SEED_FILE, {})
    out = json.loads(json.dumps(baseline))
    out["meta"] = {
        **out.get("meta", {}),
        "snapshot_date": cutoff.isoformat(),
        "rolling_window_days": ROLLING_DAYS,
        "test_only": True,
        "automatic_updates": True,
        "automatic_denominator": True,
        "automatic_candidate_discovery": True,
        "auto_strict_rule": "exact city + air context + explicit during-alert wording + unique alert episode on local day",
        "manual_review_required_for_ambiguous_candidates": True,
        "city_count": len(keys),
        "city_membership_source": BASELINE_FILE.name,
    }

    for key in keys:
        base = baseline["cities"][key]
        city = out["cities"][key]
        episodes = [
            ep for ep in state["cities"][key].get("episodes", [])
            if (parse_dt(ep.get("alert_start")) or datetime.min.replace(tzinfo=UTC)).astimezone(KYIV_TZ).date() <= cutoff
        ]
        strict_ids, sens_ids = accepted_episode_ids(queue, key)
        by_id = {ep["episode_id"]: ep for ep in episodes}

        daily_new = Counter()
        for ep in episodes:
            start = parse_dt(ep["alert_start"])
            if start:
                daily_new[start.astimezone(KYIV_TZ).date().isoformat()] += 1

        strict_daily = Counter({d: int(n) for d, n in (base.get("strict_daily") or {}).items()})
        sens_new = set()
        for eid in strict_ids:
            ep = by_id.get(eid)
            if ep:
                start = parse_dt(ep["alert_start"])
                if start:
                    strict_daily[start.astimezone(KYIV_TZ).date().isoformat()] += 1
        for eid in sens_ids:
            if eid in by_id:
                sens_new.add(eid)

        strict_n = int(base["strict_n"]) + len(strict_ids & set(by_id))
        sensitivity_n = int(base.get("sensitivity_n", base["strict_n"])) + len(sens_new)
        total_alerts = int(base["total_alerts"]) + len(episodes)

        city["coverage_end"] = cutoff.isoformat()
        city["total_alerts"] = total_alerts
        city["strict_n"] = strict_n
        city["strict_pct"] = round(strict_n / total_alerts * 100, 2) if total_alerts else 0
        city["sensitivity_n"] = sensitivity_n
        city["sensitivity_pct"] = round(sensitivity_n / total_alerts * 100, 2) if total_alerts else 0
        city["strict_daily"] = dict(sorted(strict_daily.items()))

        seed_city = (seed.get("cities") or {}).get(key)
        if not seed_city:
            raise RuntimeError(
                f"{key}: denominator seed missing. Add the audited city baseline and run "
                f"scripts/sync_explosion_seed.py before the scheduled monitor."
            )
        daily_alerts = {d: int(n) for d, n in seed_city["daily_alerts"].items()}
        for d, n in daily_new.items():
            daily_alerts[d] = int(n)

        rolling = list(base.get("rolling90") or [])
        last_base = parse_dt((rolling[-1]["date"] + "T00:00:00Z") if rolling else None)
        start_day = baseline_end(baseline, key) + timedelta(days=1)
        if last_base:
            start_day = max(start_day, last_base.date() + timedelta(days=1))

        d = start_day
        while d <= cutoff:
            window = [(d - timedelta(days=i)).isoformat() for i in range(ROLLING_DAYS)]
            if all(day in daily_alerts for day in window):
                alerts_n = sum(daily_alerts[day] for day in window)
                strict_window = sum(strict_daily.get(day, 0) for day in window)
                rolling.append({
                    "date": d.isoformat(),
                    "strict_n": strict_window,
                    "alerts_n": alerts_n,
                    "pct": round(strict_window / alerts_n * 100, 2) if alerts_n else None,
                })
            d += timedelta(days=1)
        city["rolling90"] = rolling

    return out


def inject_dashboard(explosion: dict) -> None:
    dashboard = load_json(DASHBOARD_FILE, {})
    if not isinstance(dashboard, dict) or not dashboard:
        return
    dashboard["explosion_metric_test"] = explosion
    atomic_json(DASHBOARD_FILE, dashboard)


def self_test() -> None:
    baseline = {"cities": {"poltava": {"label": "Полтава", "coverage_end": "2026-09-17"}}}
    assert city_mentioned(baseline, "poltava", "У Полтаві пролунали вибухи")
    assert not city_mentioned(baseline, "poltava", "На Полтавщині пролунали вибухи")
    assert explosion_relevant("У місті було чутно вибухи")
    assert explicit_during_alert("Під час повітряної тривоги у місті пролунали вибухи")
    assert not explicit_during_alert("У місті пролунали вибухи")
    print("Self-test OK")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bridge-file", type=Path, default=DATA / "ukrainealarm_bridge.json")
    parser.add_argument("--no-network", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return

    now = datetime.now(UTC)
    cutoff = completed_cutoff(now)
    baseline = baseline_data()
    keys = audited_keys(baseline)
    state = ensure_state(keys)
    queue = load_json(QUEUE_FILE, [])
    if not isinstance(queue, list):
        queue = []

    bridge = load_bridge(args.bridge_file, keys)
    new_episodes = ingest_episodes(state, bridge, baseline, keys, cutoff)

    telegram = []
    errors = {}
    if not args.no_network:
        try:
            telegram = telegram_rows()
        except Exception as exc:
            errors["telegram"] = f"{type(exc).__name__}: {exc}"

    due = due_checks(state, keys, now)
    searches = {}
    new_candidates = auto_confirmed = 0
    for key, checks in sorted(due.items()):
        earliest = min(parse_dt(ep["alert_start"]) or now for ep, _ in checks)
        rows = list(telegram)
        query_url = None
        if not args.no_network:
            try:
                grow, query_url = google_rows(baseline, key)
                rows.extend(grow)
            except Exception as exc:
                errors[f"google:{key}"] = f"{type(exc).__name__}: {exc}"
        filtered = relevant_rows(baseline, key, rows, earliest, now)
        added, auto = add_candidates(queue, baseline, key, filtered, checks, now)
        new_candidates += added
        auto_confirmed += auto
        searches[key] = {
            "due_checks": len(checks),
            "candidate_rows": len(filtered),
            "new_candidates": added,
            "auto_confirmed_strict": auto,
            "google_query_url": query_url,
        }
        for _, check in checks:
            check["checked_at"] = iso(now)
            check["new_candidates"] = added

    queue.sort(key=lambda x: (x.get("first_discovered_at") or "", x.get("city_key") or ""), reverse=True)
    explosion = rebuild_output(state, queue, baseline, keys, cutoff)
    inject_dashboard(explosion)

    state["last_run_at"] = iso(now)
    report = {
        "ok": not errors,
        "started_at": iso(now),
        "cutoff_completed_day": cutoff.isoformat(),
        "audited_city_count": len(keys),
        "new_alert_episodes": new_episodes,
        "cities_searched": sorted(searches),
        "searches": searches,
        "new_review_candidates": new_candidates,
        "auto_confirmed_strict": auto_confirmed,
        "review_queue_size": len(queue),
        "needs_review": sum(1 for x in queue if x.get("status") == "needs_review"),
        "errors": errors,
        "output_city_count": len(explosion.get("cities", {})),
    }

    atomic_json(STATE_FILE, state)
    atomic_json(QUEUE_FILE, queue)
    atomic_json(OUTPUT_FILE, explosion)
    atomic_json(LAST_RUN_FILE, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
