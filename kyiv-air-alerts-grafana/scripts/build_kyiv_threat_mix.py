#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

SOURCE = "https://kyiv.digital/open-api/air-alert/history"
TZ = ZoneInfo("Europe/Kyiv")
FIRST_DIFFERENTIATED_DATE = "2026-09-07"
BUCKETS = ["drone", "massive-drone", "missile", "ballistic", "mig", "combined", "unknown"]


def parse_ts(value):
    if not value:
        return None
    s = str(value).strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def is_active(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return int(value) == 1
    return str(value).strip().lower() in {"1", "true", "active", "alarm", "on"}


def bucket_for(causes):
    values = set(causes)
    if len(values) >= 2 or "missile-drone" in values:
        return "combined"
    if not values:
        return "unknown"
    value = next(iter(values))
    return value if value in {"drone", "massive-drone", "missile", "ballistic", "mig"} else "unknown"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    response = requests.get(SOURCE, headers={"Accept": "application/json"}, timeout=60)
    response.raise_for_status()
    raw = response.json()

    if isinstance(raw, list):
        records = raw
    elif isinstance(raw, dict):
        lists = [v for v in raw.values() if isinstance(v, list)]
        if len(lists) != 1:
            raise RuntimeError(f"Unexpected Kyiv history root: {sorted(raw.keys())}")
        records = lists[0]
    else:
        raise RuntimeError(f"Unexpected Kyiv history root type: {type(raw).__name__}")

    normalized = []
    for record in records:
        if not isinstance(record, dict):
            continue
        ts = parse_ts(record.get("created_at"))
        if ts is None:
            continue
        causes = record.get("causes")
        if not isinstance(causes, list):
            causes = []
        normalized.append({
            "created_at": ts,
            "state": is_active(record.get("state")),
            "causes": sorted({str(x).strip() for x in causes if str(x).strip()}),
        })
    normalized.sort(key=lambda x: x["created_at"])

    episodes = []
    current = None
    for record in normalized:
        if record["state"]:
            if current is None:
                current = record
        else:
            if current is None:
                continue
            if record["created_at"] > current["created_at"]:
                episodes.append({
                    "start": current["created_at"],
                    "end": record["created_at"],
                    "causes": current["causes"],
                })
            current = None

    differentiated = [
        episode for episode in episodes
        if episode["causes"]
        and episode["start"].astimezone(TZ).date().isoformat() >= FIRST_DIFFERENTIATED_DATE
    ]

    minutes = defaultdict(lambda: defaultdict(float))
    first_day = last_day = None
    for episode in differentiated:
        start = episode["start"].astimezone(TZ)
        end = episode["end"].astimezone(TZ)
        bucket = bucket_for(episode["causes"])
        cursor = start
        while cursor < end:
            day = cursor.date()
            next_midnight = datetime.combine(day + timedelta(days=1), datetime.min.time(), TZ)
            segment_end = min(end, next_midnight)
            minutes[day.isoformat()][bucket] += max(0.0, (segment_end - cursor).total_seconds() / 60.0)
            first_day = day if first_day is None or day < first_day else first_day
            last_day = day if last_day is None or day > last_day else last_day
            cursor = segment_end

    if first_day is None:
        raise RuntimeError("No differentiated completed Kyiv episodes found")

    last_completed = datetime.now(TZ).date() - timedelta(days=1)
    last_visible = min(last_day, last_completed)
    visible_start = max(first_day, last_visible - timedelta(days=27))

    rows = []
    day = visible_start
    while day <= last_visible:
        key = day.isoformat()
        by_bucket = {bucket: round(minutes[key].get(bucket, 0.0), 3) for bucket in BUCKETS}
        total = round(sum(by_bucket.values()), 3)
        shares = {
            bucket: round(by_bucket[bucket] / total * 100.0, 6) if total > 0 else 0.0
            for bucket in BUCKETS
        }
        rows.append({"date": key, "total_minutes": total, "minutes": by_bucket, "shares": shares})
        day += timedelta(days=1)

    output = {
        "meta": {
            "source": SOURCE,
            "timezone": "Europe/Kyiv",
            "semantics": "episode_level_cause_assignment",
            "first_differentiated_date": FIRST_DIFFERENTIATED_DATE,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "visible_start": visible_start.isoformat(),
            "visible_end": last_visible.isoformat(),
            "visible_day_count": len(rows),
            "note": "Historical Kyiv Digital causes are assigned to the whole alert episode. Intra-alert cause transitions are not reconstructed.",
        },
        "rows": rows,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output["meta"], ensure_ascii=False))


if __name__ == "__main__":
    main()
