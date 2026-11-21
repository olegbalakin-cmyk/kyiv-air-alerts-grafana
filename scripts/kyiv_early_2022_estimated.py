#!/usr/bin/env python3
"""Offline Kyiv 24-27 Feb 2022 approximate-end overlay on start-only source audit.

Both start and source-exported end are preserved, with strict separate
confidence fields. This script NEVER outputs canonical completed intervals or
changes Neon, Git production JSON, alert KPIs, or scheduled data jobs.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, date, time, timedelta, timezone
from pathlib import Path

from kyiv_early_2022_shadow import build_report, KYIV_TZ, CANONICAL_NAMES

START_DATE = date(2022, 2, 24)
END_DATE = date(2022, 2, 27)
SOURCE_METHOD = "alerts.in.ua early-history open-source reconstruction; ends may be imputed"


def aware_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Naive evidence timestamp")
    return parsed.astimezone(KYIV_TZ)


def split_days(starts_ends: list[tuple[datetime, datetime]]) -> dict[str, int]:
    """Estimated union occupied seconds for each local calendar day; no double counting."""
    segments = defaultdict(list)
    for s, e in starts_ends:
        cursor = s
        while cursor < e:
            next_midnight = datetime.combine(cursor.date() + timedelta(days=1), time.min, tzinfo=KYIV_TZ)
            clip = min(e, next_midnight)
            if clip <= cursor:
                raise ValueError("Non-forward calendar-day clip")
            segments[cursor.date().isoformat()].append((cursor.astimezone(timezone.utc), clip.astimezone(timezone.utc)))
            cursor = clip
    output = {}
    for day, intervals in segments.items():
        merged = []
        for a, b in sorted(intervals):
            if not merged or a > merged[-1][1]:
                merged.append([a, b])
            else:
                merged[-1][1] = max(merged[-1][1], b)
        output[day] = int(sum((b - a).total_seconds() for a, b in merged))
    return output


def add_estimates(start_only: dict) -> dict:
    """Upgrade a v1 immutable start-only audit to an explicitly provisional estimate.

    The canonical end / duration_seconds and exact hourly fields remain NULL.
    Proposed estimate values live exclusively under estimated_ keys.
    """
    if (start_only.get("schema") != "kyiv-early-2022-start-only-shadow-v1" or
            start_only.get("publish_allowed") is not False or
            start_only.get("neon_write_allowed") is not False or
            start_only.get("canonical_intervals") != []):
        raise ValueError("Unsafe or unexpected starting audit contract")
    result = json.loads(json.dumps(start_only))
    ranges = []
    event_seconds = 0
    thirty_minute_ends = 0
    by_start_day = defaultdict(list)
    for row in result["candidates"]:
        if (row.get("city_key") != "kyiv" or row.get("end") is not None or
                row.get("duration_seconds") is not None or
                row.get("end_status") != "UNVERIFIED_EXPORT_PLACEHOLDER" or
                not row.get("evidence")):
            raise ValueError("Unexpected canonical, other-city or unsupported candidate")
        start = aware_timestamp(row["start"])
        estimate = aware_timestamp(row["raw_exported_end_not_for_statistics"])
        seconds = (estimate.astimezone(timezone.utc) - start.astimezone(timezone.utc)).total_seconds()
        if not START_DATE <= start.date() <= END_DATE or not 0 < seconds <= 24 * 60 * 60:
            raise ValueError("Invalid early Kyiv start / exported end")
        if int(seconds) != seconds:
            raise ValueError("Non-second interval in source")
        seconds = int(seconds)
        if seconds == 30 * 60:
            thirty_minute_ends += 1
        event_seconds += seconds
        ranges.append((start, estimate))
        by_start_day[start.date().isoformat()].append(seconds)
        row.update({
            "estimated_end": estimate.isoformat(),
            "estimated_duration_seconds": seconds,
            "estimated_duration_minutes": round(seconds / 60, 3),
            "estimated_end_status": "SOURCE_REPORTED_OR_IMPUTED_UNVERIFIED",
            "end_confidence": "UNVERIFIED",
            "source_method": SOURCE_METHOD,
        })
        assert row["end"] is None and row["duration_seconds"] is None
    per_day = split_days(ranges)
    for row in result["daily_preview"]:
        day = row["date"]
        lengths = by_start_day[day]
        row.update({
            "estimated_occupied_minutes": round(per_day.get(day, 0) / 60, 3),
            "estimated_occupied_hours": round(per_day.get(day, 0) / 3600, 4),
            "estimated_mean_alert_duration_minutes": round(sum(lengths) / len(lengths) / 60, 3),
            "estimated_end_count": len(lengths),
            "duration_quality": "APPROXIMATE_UNVERIFIED",
        })
        assert row["hours_under_alert"] is None and row["average_alert_duration"] is None
    spillover = {d: seconds for d, seconds in per_day.items() if d > END_DATE.isoformat()}
    if any(d != "2022-02-28" for d in spillover):
        raise ValueError("Unexpected post-window export carryover")
    result["schema"] = "kyiv-early-2022-approximate-end-shadow-v2"
    result["disclaimer_uk"] = (
        "Дані за 24–27 лютого 2022 року орієнтовні. Час завершення може бути умовним "
        "(зокрема 30 хвилин за відсутності відбою). Кількість оголошень і тривалість неповні та неточні."
    )
    result["summary"].update({
        "exported_end_count": len(ranges),
        "exported_end_verified_count": 0,
        "exported_ends_exactly_30min_count": thirty_minute_ends,
        "estimated_total_event_minutes": round(event_seconds / 60, 3),
        "estimated_union_minutes_24_27": round(sum(per_day.get(d.isoformat(), 0)
            for d in (START_DATE + timedelta(days=n) for n in range(4))) / 60, 3),
        "estimated_carryover_minutes_2022_02_28": round(spillover.get("2022-02-28", 0) / 60, 3),
        "estimated_end_quality": "ALL_UNVERIFIED",
    })
    result["estimated_carryover_not_official"] = [
        {"date": d, "estimated_occupied_minutes": round(s / 60, 3),
         "canonical_daily_kpi_included": False} for d, s in sorted(spillover.items())
    ]
    return result


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--csv", action="append", required=True, type=Path)
    p.add_argument("--existing", type=Path, help="Optional read-only canonical alerts for duplicate checking")
    p.add_argument("--out", required=True, type=Path, help="New standalone JSON shadow file")
    args = p.parse_args()
    if args.out.name in CANONICAL_NAMES or args.out.exists():
        p.error("Refusing to overwrite canonical or existing file")
    report = add_estimates(build_report(args.csv, args.existing))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"schema": report["schema"], "summary": report["summary"],
                      "publish_allowed": report["publish_allowed"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
