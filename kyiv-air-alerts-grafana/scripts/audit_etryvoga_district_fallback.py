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

import add_duration_unit_switch as exact_base
import expand_multicity_production as base
import extend_remaining_proxies as extra

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "etryvoga_district_fallback_audit.json"
CANDIDATES = ROOT / "data" / "etryvoga_bridge_candidates.json"
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
# We need enough history to overlap the tail of the frozen official source and
# simultaneously seed the post-freeze bridge. 600 public pages ~= 12k messages.
MAX_PAGES = 600
SECTION_MARKERS = {"🔴", "🟡", "🟢", "🚨", "⚠️"}


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


def fetch_history(max_pages: int = MAX_PAGES) -> tuple[list[dict], dict]:
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
        cur_min = min(row["id"] for row in rows)
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
        time.sleep(0.035)
    messages = sorted(seen.values(), key=lambda x: (x["at"], x["id"]))
    return messages, {
        "max_pages": max_pages,
        "pages_requested": pages,
        "messages_loaded": len(messages),
        "earliest_loaded_at": messages[0]["at"].isoformat() if messages else None,
        "latest_loaded_at": messages[-1]["at"].isoformat() if messages else None,
    }


def normalize_space(text: str) -> str:
    return " ".join(text.replace("\xa0", " ").split())


def location_name(line: str) -> str:
    # `Одеський район (Одеська обл.)` -> `Одеський район`.
    s = normalize_space(line)
    s = re.sub(r"\s*\([^()]*\)\s*$", "", s).strip()
    return s


def classify_section(lines: list[str]) -> str | None:
    s = normalize_space(" ".join(lines)).lower().replace("ё", "е")
    if "відбій червоної тривоги" in s:
        return "end"
    if "відбій тривоги" in s:
        return "end"
    if "червоний рівень тривоги" in s and "відбій" not in s:
        return "start"
    if "повітряна тривога" in s and "відбій" not in s:
        return "start"
    return None


def message_sections(text: str) -> list[tuple[str | None, list[str]]]:
    """Split a Telegram message into emoji-led status blocks.

    eTryvoga publishes both grouped blocks (heading then many locations) and
    one-location blocks (location then heading). Keeping the marker boundary is
    enough to avoid cross-contamination between red/yellow/green blocks.
    """
    lines = [normalize_space(x) for x in text.splitlines() if normalize_space(x)]
    sections: list[tuple[str | None, list[str]]] = []
    marker = None
    current: list[str] = []
    for line in lines:
        if line in SECTION_MARKERS:
            if current:
                sections.append((marker, current))
            marker = line
            current = []
        else:
            current.append(line)
    if current:
        sections.append((marker, current))
    # Some older messages have no standalone emoji marker; keep as one block.
    if not sections and lines:
        sections = [(None, lines)]
    return sections


def transition_for_location(text: str, target: str) -> str | None:
    target_norm = normalize_space(target).casefold()
    transitions = []
    for marker, lines in message_sections(text):
        locations = {location_name(line).casefold() for line in lines}
        if target_norm not in locations:
            continue
        kind = classify_section(lines)
        # Marker can disambiguate compact messages whose heading is abbreviated.
        if kind is None and marker == "🔴":
            kind = "start"
        elif kind is None and marker == "🚨":
            kind = "start"
        elif kind is None and marker == "🟢":
            kind = "end"
        if kind:
            transitions.append(kind)
    if not transitions:
        return None
    # A location should not legitimately have conflicting state transitions in one
    # message. If it does, prefer an explicit end to avoid inventing extra duration.
    return "end" if "end" in transitions else transitions[0]


def pair_target(messages: list[dict], target: str) -> tuple[list[dict], list[dict], list[dict]]:
    active = None
    pairs = []
    anomalies = []
    samples = []
    for msg in messages:
        kind = transition_for_location(msg["text"], target)
        if kind is None:
            continue
        if len(samples) < 10:
            samples.append({"id": msg["id"], "at": msg["at"].isoformat(), "kind": kind, "text": msg["text"][:700]})
        if kind == "start":
            if active is None:
                active = msg
            else:
                gap = (msg["at"] - active["at"]).total_seconds() / 60
                if gap <= 5:
                    continue
                anomalies.append({"type": "repeated_start", "start_id": active["id"], "next_start_id": msg["id"], "gap_min": round(gap, 2)})
                active = msg
        else:
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
    return pairs, anomalies, samples


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


def clip(intervals: list[tuple[datetime, datetime]], start: datetime, end: datetime) -> list[tuple[datetime, datetime]]:
    return union([(max(s, start), min(e, end)) for s, e in intervals if e > start and s < end])


def load_official(targets: dict) -> tuple[dict[str, list[tuple[datetime, datetime]]], datetime | None]:
    r = requests.get(OFFICIAL_URL, timeout=120)
    r.raise_for_status()
    text = r.content.decode("utf-8-sig")
    raw: dict[str, list[tuple[datetime, datetime]]] = defaultdict(list)
    latest_global = None

    proxy_by_oblast = {
        meta["oblast"]: key for key, meta in targets.items() if meta["source_type"] == "raion_proxy"
    }
    hromada_to_key = {
        exact_base.CITY_CONFIG[key]["hromada"]: key
        for key in ("kharkiv", "zaporizhzhia")
    }

    for row in csv.DictReader(io.StringIO(text)):
        s_raw = (row.get("started_at") or "").strip(); e_raw = (row.get("finished_at") or "").strip()
        if not s_raw or not e_raw:
            continue
        try:
            s = parse_dt(s_raw); e = parse_dt(e_raw)
        except Exception:
            continue
        if e <= s:
            continue
        latest_global = e if latest_global is None or e > latest_global else latest_global

        level = (row.get("level") or "").strip()
        if level == "hromada":
            key = hromada_to_key.get((row.get("hromada") or "").strip())
            if key:
                raw[key].append((s, e))
            continue

        oblast = (row.get("oblast") or "").strip()
        key = proxy_by_oblast.get(oblast)
        if not key:
            continue
        meta = targets[key]
        raion = (row.get("raion") or "").strip()
        if level == "oblast" or (level == "raion" and raion == meta["target"]):
            raw[key].append((s, e))

    return {k: union(v) for k, v in raw.items()}, latest_global


def median(values: list[float]) -> float | None:
    if not values:
        return None
    x = sorted(values); n = len(x)
    return x[n//2] if n % 2 else (x[n//2-1] + x[n//2]) / 2


def main() -> None:
    proxy_cfg = dict(base.PROXY_CONFIG); proxy_cfg.update(extra.ADDITIONAL_PROXIES)
    targets = {
        key: {
            "target": cfg["raion"],
            "label": f"{cfg['label']} ({cfg['raion']})" if "(" not in cfg["label"] else cfg["label"],
            "source_type": "raion_proxy",
            "oblast": cfg["oblast"],
        }
        for key, cfg in proxy_cfg.items()
    }
    targets.update({
        "kharkiv": {"target": "Харків", "label": "Харків", "source_type": "exact_city", "oblast": "Харківська область"},
        "zaporizhzhia": {"target": "Запоріжжя", "label": "Запоріжжя", "source_type": "exact_city", "oblast": "Запорізька область"},
    })

    official, latest_official = load_official(targets)
    messages, scan_meta = fetch_history()
    if not messages:
        raise RuntimeError("eTryvoga scan returned no Telegram messages")
    scan_start = messages[0]["at"]
    scan_end = messages[-1]["at"]
    # Benchmark only where both datasets can actually overlap.
    bench_end = min(latest_official, scan_end) if latest_official else scan_end
    bench_start = max(scan_start, bench_end - timedelta(hours=24))

    result = {
        "generated_at": datetime.now(UTC).isoformat(),
        "source": SOURCE_URL,
        "source_type": "independent_volunteer_telegram_channel",
        "red_level_rule": "count explicit air-raid/red alerts only; yellow-only alerts are excluded",
        "scan": scan_meta,
        "latest_official_end": latest_official.isoformat() if latest_official else None,
        "benchmark_window": {"from": bench_start.isoformat(), "to": bench_end.isoformat()},
        "cities": {},
        "summary": {},
    }
    candidates = {
        "meta": {
            "generated_at": result["generated_at"],
            "source": SOURCE_URL,
            "source_provenance": "independent_volunteer_telegram",
            "latest_official_end": result["latest_official_end"],
            "scan": scan_meta,
            "rule": result["red_level_rule"],
        },
        "targets": {},
    }

    coverages = []; matching = []; ratios = []; current_ends = []
    benchmarked = 0
    targets_with_pairs = 0
    for key, meta in targets.items():
        pairs, anomalies, samples = pair_target(messages, meta["target"])
        if pairs:
            targets_with_pairs += 1
        b_all = [(parse_dt(p["start"]), parse_dt(p["end"])) for p in pairs]
        a = clip(official.get(key, []), bench_start, bench_end)
        b = clip(b_all, bench_start, bench_end)
        ah = duration_h(a); bh = duration_h(b); oh = overlap_h(a, b)
        if ah > 0 and bh > 0:
            benchmarked += 1
            coverages.append(oh / ah); matching.append(oh / bh); ratios.append(bh / ah)

        bridge_pairs = []
        if latest_official:
            for p in pairs:
                s = parse_dt(p["start"]); e = parse_dt(p["end"])
                if e <= latest_official:
                    continue
                q = dict(p)
                if s < latest_official:
                    q["start_original"] = q["start"]
                    q["start"] = latest_official.isoformat()
                    q["duration_min"] = round((e - latest_official).total_seconds() / 60, 3)
                bridge_pairs.append(q)
        latest_bridge = max((parse_dt(p["end"]) for p in bridge_pairs), default=None)
        if latest_bridge:
            current_ends.append(latest_bridge)

        result["cities"][key] = {
            "target": meta["target"],
            "label": meta["label"],
            "source_type": meta["source_type"],
            "complete_pairs_in_scan": len(pairs),
            "anomaly_count": len(anomalies),
            "typed_samples": samples,
            "benchmark": {
                "official_hours": round(ah, 3),
                "etryvoga_hours": round(bh, 3),
                "overlap_hours": round(oh, 3),
                "official_covered_pct": round(100 * oh / ah, 2) if ah else None,
                "etryvoga_matching_official_pct": round(100 * oh / bh, 2) if bh else None,
                "duration_ratio_etryvoga_to_official": round(bh / ah, 3) if ah else None,
                "official_episodes": len(a),
                "etryvoga_episodes": len(b),
            },
            "bridge_complete_pairs": len(bridge_pairs),
            "bridge_latest_end": latest_bridge.isoformat() if latest_bridge else None,
        }
        candidates["targets"][key] = {
            "target": meta["target"],
            "label": meta["label"],
            "source_type": meta["source_type"],
            "pairs": bridge_pairs,
            "anomalies_in_scan": anomalies,
        }

    result["summary"] = {
        "target_count": len(targets),
        "targets_with_complete_pairs": targets_with_pairs,
        "targets_with_nonzero_overlap_benchmark": benchmarked,
        "median_official_covered_pct": round(100 * median(coverages), 2) if coverages else None,
        "median_etryvoga_matching_official_pct": round(100 * median(matching), 2) if matching else None,
        "median_duration_ratio_etryvoga_to_official": round(median(ratios), 3) if ratios else None,
        "latest_bridge_end": max(current_ends).isoformat() if current_ends else None,
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    CANDIDATES.write_text(json.dumps(candidates, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
