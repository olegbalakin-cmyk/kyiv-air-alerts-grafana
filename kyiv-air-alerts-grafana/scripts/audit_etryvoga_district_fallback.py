#!/usr/bin/env python3
from __future__ import annotations

import csv
import io
import json
import re
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

import expand_multicity_production as base
import extend_remaining_proxies as extra

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "etryvoga_district_fallback_audit.json"
OFFICIAL_URL = (
    "https://raw.githubusercontent.com/Vadimkin/ukrainian-air-raid-sirens-dataset/"
    "main/datasets/official_data_uk.csv"
)
CHANNEL = "UkraineAlarmSignal"
SOURCE_URL = f"https://t.me/s/{CHANNEL}"
UTC = timezone.utc
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/152 Safari/537.36",
    "Accept-Language": "uk,en;q=0.8",
}
BENCH_FROM = datetime(2026, 9, 1, tzinfo=UTC)
BENCH_TO = datetime(2026, 9, 8, tzinfo=UTC)
BRIDGE_FROM = BENCH_TO
# Keep one day before the benchmark so alerts opened just before midnight can close inside it.
SCAN_FROM = BENCH_FROM - timedelta(days=1)


def parse_dt(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def parse_page(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for wrap in soup.select(".tgme_widget_message_wrap"):
        msg = wrap.select_one(".tgme_widget_message")
        tm = wrap.select_one("time[datetime]")
        if not msg or not tm:
            continue
        post = msg.get("data-post", "")
        m = re.search(r"/(\d+)$", post)
        if not m:
            continue
        txt = wrap.select_one(".tgme_widget_message_text")
        text = "\n".join(txt.stripped_strings) if txt else ""
        rows.append({
            "id": int(m.group(1)),
            "at": parse_dt(tm["datetime"]),
            "text": text,
            "url": f"https://t.me/{CHANNEL}/{m.group(1)}",
        })
    return rows


def fetch_history(max_pages: int = 500) -> tuple[list[dict], dict]:
    """Walk the public Telegram channel backwards once; do all district filtering locally.

    Telegram's web search endpoint is not reliable for programmatic q= filtering and may
    silently return the ordinary latest page, so the benchmark must never depend on it.
    """
    sess = requests.Session()
    sess.headers.update(HEADERS)
    before = None
    seen: dict[int, dict] = {}
    last_min = None
    pages = 0
    stalled = 0

    for _ in range(max_pages):
        url = SOURCE_URL + (f"?before={before}" if before is not None else "")
        r = sess.get(url, timeout=30)
        r.raise_for_status()
        rows = parse_page(r.text)
        pages += 1
        if not rows:
            break
        for row in rows:
            seen[row["id"]] = row

        oldest_at = min(row["at"] for row in rows)
        cur_min = min(row["id"] for row in rows)
        if oldest_at < SCAN_FROM:
            break
        if last_min is not None and cur_min >= last_min:
            stalled += 1
            if stalled >= 2:
                break
        else:
            stalled = 0
        last_min = cur_min
        if cur_min <= 1:
            break
        before = cur_min
        time.sleep(0.04)

    messages = sorted(seen.values(), key=lambda x: (x["at"], x["id"]))
    return messages, {
        "pages_requested": pages,
        "messages_loaded": len(messages),
        "earliest_loaded_at": messages[0]["at"].isoformat() if messages else None,
        "latest_loaded_at": messages[-1]["at"].isoformat() if messages else None,
    }


def normalize(text: str) -> str:
    return " ".join(text.lower().replace("ё", "е").replace("\xa0", " ").split())


def mentions_raion(text: str, raion: str) -> bool:
    return raion.casefold() in text.casefold()


def red_transition(text: str, raion: str) -> str | None:
    if not mentions_raion(text, raion):
        return None
    s = normalize(text)

    # Explicit end of red while yellow may remain active.
    if "відбій червоної тривоги" in s:
        return "end"
    # Full all-clear also ends any active red alert.
    if "відбій тривоги" in s and ("🟢" in text or "відбій тривоги" in s):
        return "end"

    # New two-level format.
    if "червоний рівень тривоги" in s and "відбій" not in s:
        return "start"
    # Older explicit air-raid format.
    if "повітряна тривога" in s and "відбій" not in s:
        return "start"
    return None


def pair_raion(messages: list[dict], raion: str) -> tuple[list[dict], list[dict], list[dict]]:
    active = None
    pairs = []
    anomalies = []
    typed_samples = []
    for msg in messages:
        kind = red_transition(msg["text"], raion)
        if kind is None:
            continue
        if len(typed_samples) < 8:
            typed_samples.append({"id": msg["id"], "at": msg["at"].isoformat(), "kind": kind, "text": msg["text"][:500]})
        if kind == "start":
            if active is None:
                active = msg
            else:
                gap = (msg["at"] - active["at"]).total_seconds() / 60
                if gap <= 5:
                    continue
                anomalies.append({
                    "type": "repeated_start",
                    "start_id": active["id"],
                    "next_start_id": msg["id"],
                    "gap_min": round(gap, 2),
                })
                # Never fabricate an end; begin from the newer confirmed state transition.
                active = msg
        elif kind == "end":
            if active is None:
                continue
            if msg["at"] > active["at"]:
                pairs.append({
                    "start": active["at"].isoformat(),
                    "end": msg["at"].isoformat(),
                    "start_id": active["id"],
                    "end_id": msg["id"],
                    "duration_min": round((msg["at"] - active["at"]).total_seconds() / 60, 3),
                    "start_url": active["url"],
                    "end_url": msg["url"],
                })
            active = None
    if active is not None:
        anomalies.append({"type": "open_start", "start_id": active["id"], "start": active["at"].isoformat()})
    return pairs, anomalies, typed_samples


def union(intervals: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    merged: list[list[datetime]] = []
    for s, e in sorted(intervals):
        if e <= s:
            continue
        if not merged or s > merged[-1][1]:
            merged.append([s, e])
        elif e > merged[-1][1]:
            merged[-1][1] = e
    return [(s, e) for s, e in merged]


def to_intervals(pairs: list[dict], start: datetime, end: datetime) -> list[tuple[datetime, datetime]]:
    return union([
        (max(parse_dt(p["start"]), start), min(parse_dt(p["end"]), end))
        for p in pairs
        if parse_dt(p["end"]) > start and parse_dt(p["start"]) < end
    ])


def duration_h(intervals: list[tuple[datetime, datetime]]) -> float:
    return sum((e - s).total_seconds() for s, e in union(intervals)) / 3600


def overlap_h(a: list[tuple[datetime, datetime]], b: list[tuple[datetime, datetime]]) -> float:
    a = union(a); b = union(b)
    i = j = 0; sec = 0.0
    while i < len(a) and j < len(b):
        s = max(a[i][0], b[j][0]); e = min(a[i][1], b[j][1])
        if e > s:
            sec += (e - s).total_seconds()
        if a[i][1] <= b[j][1]: i += 1
        else: j += 1
    return sec / 3600


def load_official(cfg: dict) -> dict[str, list[tuple[datetime, datetime]]]:
    r = requests.get(OFFICIAL_URL, timeout=120)
    r.raise_for_status()
    text = r.content.decode("utf-8-sig")
    by_oblast = {v["oblast"]: k for k, v in cfg.items()}
    raw = defaultdict(list)
    for row in csv.DictReader(io.StringIO(text)):
        key = by_oblast.get((row.get("oblast") or "").strip())
        if not key:
            continue
        c = cfg[key]
        level = (row.get("level") or "").strip()
        raion = (row.get("raion") or "").strip()
        if level != "oblast" and not (level == "raion" and raion == c["raion"]):
            continue
        try:
            s = parse_dt((row.get("started_at") or "").strip())
            e = parse_dt((row.get("finished_at") or "").strip())
        except Exception:
            continue
        if e > s and e > BENCH_FROM and s < BENCH_TO:
            raw[key].append((max(s, BENCH_FROM), min(e, BENCH_TO)))
    return {k: union(v) for k, v in raw.items()}


def median(values: list[float]) -> float | None:
    if not values:
        return None
    x = sorted(values)
    n = len(x)
    return x[n//2] if n % 2 else (x[n//2-1] + x[n//2]) / 2


def main() -> None:
    cfg = dict(base.PROXY_CONFIG)
    cfg.update(extra.ADDITIONAL_PROXIES)
    official = load_official(cfg)
    messages, scan_meta = fetch_history()

    result = {
        "generated_at": datetime.now(UTC).isoformat(),
        "source": SOURCE_URL,
        "source_type": "independent_volunteer_telegram_channel",
        "benchmark_window": {"from": BENCH_FROM.isoformat(), "to": BENCH_TO.isoformat()},
        "red_level_rule": "count explicit air-raid/red alerts only; yellow-only alerts are excluded",
        "scan": scan_meta,
        "cities": {},
        "summary": {},
    }
    coverages = []
    matching = []
    ratios = []
    current_ends = []
    districts_with_typed = 0

    for key, c in cfg.items():
        raion = c["raion"]
        pairs, anomalies, typed_samples = pair_raion(messages, raion)
        if typed_samples:
            districts_with_typed += 1

        a = official.get(key, [])
        b = to_intervals(pairs, BENCH_FROM, BENCH_TO)
        ah = duration_h(a); bh = duration_h(b); oh = overlap_h(a, b)
        bench = {
            "official_hours": round(ah, 3),
            "etryvoga_hours": round(bh, 3),
            "overlap_hours": round(oh, 3),
            "official_covered_pct": round(100 * oh / ah, 2) if ah else None,
            "etryvoga_matching_official_pct": round(100 * oh / bh, 2) if bh else None,
            "duration_ratio_etryvoga_to_official": round(bh / ah, 3) if ah else None,
            "official_episodes": len(a),
            "etryvoga_episodes": len(b),
        }
        bridge_pairs = [p for p in pairs if parse_dt(p["end"]) > BRIDGE_FROM]
        latest = max((parse_dt(p["end"]) for p in bridge_pairs), default=None)
        if latest:
            current_ends.append(latest)
        result["cities"][key] = {
            "raion": raion,
            "typed_transition_count": sum(1 for m in messages if red_transition(m["text"], raion)),
            "complete_pairs": len(pairs),
            "anomaly_count": len(anomalies),
            "typed_samples": typed_samples,
            "benchmark": bench,
            "bridge_complete_pairs_after_2026_09_08": len(bridge_pairs),
            "bridge_latest_end": latest.isoformat() if latest else None,
        }
        if ah > 0 and bh > 0:
            coverages.append(oh / ah)
            matching.append(oh / bh)
            ratios.append(bh / ah)

    result["summary"] = {
        "proxy_city_count": len(cfg),
        "districts_with_typed_transitions": districts_with_typed,
        "cities_with_benchmark": len(coverages),
        "median_official_covered_pct": round(100 * median(coverages), 2) if coverages else None,
        "median_etryvoga_matching_official_pct": round(100 * median(matching), 2) if matching else None,
        "median_duration_ratio_etryvoga_to_official": round(median(ratios), 3) if ratios else None,
        "latest_bridge_end": max(current_ends).isoformat() if current_ends else None,
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
