#!/usr/bin/env python3
from __future__ import annotations

import csv
import io
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import requests

import expand_multicity_production as base
import extend_remaining_proxies as extra

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "tryvoha_fallback_audit.json"
OFFICIAL_URL = (
    "https://raw.githubusercontent.com/Vadimkin/ukrainian-air-raid-sirens-dataset/"
    "main/datasets/official_data_uk.csv"
)
TRYVOHA = "https://tryvoha.online/api/v1"
UTC = timezone.utc


def dt(value: str) -> datetime:
    x = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if x.tzinfo is None:
        x = x.replace(tzinfo=UTC)
    return x.astimezone(UTC)


def union(intervals: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    out: list[list[datetime]] = []
    for start, end in sorted(intervals):
        if end <= start:
            continue
        if not out or start > out[-1][1]:
            out.append([start, end])
        elif end > out[-1][1]:
            out[-1][1] = end
    return [(a, b) for a, b in out]


def hours(intervals: list[tuple[datetime, datetime]]) -> float:
    return sum((b - a).total_seconds() for a, b in union(intervals)) / 3600


def overlap_hours(a: list[tuple[datetime, datetime]], b: list[tuple[datetime, datetime]]) -> float:
    a = union(a)
    b = union(b)
    i = j = 0
    total = 0.0
    while i < len(a) and j < len(b):
        s = max(a[i][0], b[j][0])
        e = min(a[i][1], b[j][1])
        if e > s:
            total += (e - s).total_seconds()
        if a[i][1] < b[j][1]:
            i += 1
        else:
            j += 1
    return total / 3600


def main() -> None:
    session = requests.Session()
    session.headers.update({"User-Agent": "kyiv-air-alerts-grafana/1.0 (+fallback audit)"})

    cfg = dict(base.PROXY_CONFIG)
    cfg.update(extra.ADDITIONAL_PROXIES)

    result = {
        "generated_at": datetime.now(UTC).isoformat(),
        "source": TRYVOHA,
        "purpose": "benchmark public district-level fallback before production use",
        "terms_note": "Tryvoha.online is an independent open-source-derived informational service, not an official alert channel.",
        "cities": {},
        "summary": {},
    }

    try:
        rr = session.get(f"{TRYVOHA}/regions", timeout=30)
        rr.raise_for_status()
        directory_payload = rr.json()
    except Exception as exc:
        result["error"] = f"regions fetch failed: {type(exc).__name__}: {exc}"
        OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if isinstance(directory_payload, dict):
        directory = directory_payload.get("regions") or directory_payload.get("items") or directory_payload.get("data") or []
    else:
        directory = directory_payload

    by_name = {}
    for item in directory if isinstance(directory, list) else []:
        name = str(item.get("name_uk") or item.get("name") or "").strip()
        if name:
            by_name[name.casefold()] = item

    official_text = session.get(OFFICIAL_URL, timeout=120).content.decode("utf-8-sig")
    official_by_city: dict[str, list[tuple[datetime, datetime]]] = defaultdict(list)
    latest_official = None
    by_oblast = {v["oblast"]: k for k, v in cfg.items()}
    for row in csv.DictReader(io.StringIO(official_text)):
        key = by_oblast.get((row.get("oblast") or "").strip())
        if not key:
            continue
        c = cfg[key]
        level = (row.get("level") or "").strip()
        raion = (row.get("raion") or "").strip()
        if level != "oblast" and not (level == "raion" and raion == c["raion"]):
            continue
        try:
            s = dt((row.get("started_at") or "").strip())
            e = dt((row.get("finished_at") or "").strip())
        except Exception:
            continue
        if e <= s:
            continue
        official_by_city[key].append((s, e))
        latest_official = e if latest_official is None or e > latest_official else latest_official

    matched = 0
    with_recent = 0
    benchmarkable = 0
    duration_ratios = []
    coverages = []

    for key, c in cfg.items():
        raion = c["raion"]
        item = by_name.get(raion.casefold())
        city_out = {
            "raion": raion,
            "directory_match": bool(item),
            "slug": item.get("slug") if item else None,
        }
        if not item or not item.get("slug"):
            result["cities"][key] = city_out
            continue
        matched += 1
        slug = item["slug"]
        try:
            sr = session.get(f"{TRYVOHA}/stats/{slug}", params={"period": "30d"}, timeout=30)
            sr.raise_for_status()
            payload = sr.json()
        except Exception as exc:
            city_out["error"] = f"stats fetch failed: {type(exc).__name__}: {exc}"
            result["cities"][key] = city_out
            continue

        alert_block = payload.get("alerts") if isinstance(payload, dict) else None
        recent = alert_block.get("recent", []) if isinstance(alert_block, dict) else []
        city_out.update({
            "period_from": payload.get("from") if isinstance(payload, dict) else None,
            "period_to": payload.get("to") if isinstance(payload, dict) else None,
            "stats_count": alert_block.get("count") if isinstance(alert_block, dict) else None,
            "stats_minutes_total": alert_block.get("minutes_total") if isinstance(alert_block, dict) else None,
            "recent_count": len(recent) if isinstance(recent, list) else 0,
        })
        episodes = []
        if isinstance(recent, list):
            for ep in recent:
                if not ep.get("started_at") or not ep.get("ended_at"):
                    continue
                try:
                    s = dt(ep["started_at"])
                    e = dt(ep["ended_at"])
                except Exception:
                    continue
                if e > s:
                    episodes.append((s, e))
        if episodes:
            with_recent += 1
            city_out["recent_earliest_start"] = min(s for s, _ in episodes).isoformat()
            city_out["recent_latest_end"] = max(e for _, e in episodes).isoformat()
        else:
            city_out["recent_earliest_start"] = None
            city_out["recent_latest_end"] = None

        # Benchmark only the time slice that both sources actually expose.
        if episodes and latest_official:
            api_from = min(s for s, _ in episodes)
            api_to = min(max(e for _, e in episodes), latest_official)
            if api_to > api_from:
                a = [(max(s, api_from), min(e, api_to)) for s, e in official_by_city[key] if e > api_from and s < api_to]
                b = [(max(s, api_from), min(e, api_to)) for s, e in episodes if e > api_from and s < api_to]
                ah = hours(a)
                bh = hours(b)
                oh = overlap_hours(a, b)
                city_out["benchmark"] = {
                    "from": api_from.isoformat(),
                    "to": api_to.isoformat(),
                    "official_hours": round(ah, 3),
                    "tryvoha_hours": round(bh, 3),
                    "overlap_hours": round(oh, 3),
                    "official_covered_pct": round(100 * oh / ah, 2) if ah else None,
                    "tryvoha_matching_official_pct": round(100 * oh / bh, 2) if bh else None,
                    "duration_ratio_tryvoha_to_official": round(bh / ah, 3) if ah else None,
                    "official_episodes": len(union(a)),
                    "tryvoha_episodes": len(union(b)),
                }
                benchmarkable += 1
                if ah:
                    duration_ratios.append(bh / ah)
                    coverages.append(oh / ah)
        result["cities"][key] = city_out

    result["summary"] = {
        "proxy_city_count": len(cfg),
        "directory_matches": matched,
        "cities_with_closed_recent_episodes": with_recent,
        "benchmarkable_cities": benchmarkable,
        "latest_official_end": latest_official.isoformat() if latest_official else None,
        "median_duration_ratio": round(sorted(duration_ratios)[len(duration_ratios)//2], 3) if duration_ratios else None,
        "median_official_coverage_pct": round(100 * sorted(coverages)[len(coverages)//2], 2) if coverages else None,
    }

    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
