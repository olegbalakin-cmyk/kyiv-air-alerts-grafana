#!/usr/bin/env python3
"""Preview-only daily-start counts, built read-only from production's own event collectors.

DO NOT call any producer main() or write to site-prod. Imports only the
established pure alert-map functions; external public source reads may fail.
All claimed per-city histories are checked against committed monthly/day data.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime, timedelta, timezone
import json
import math
import os
from pathlib import Path
import sys


def _month_end(month: str) -> date:
    y, m = map(int, month.split("-"))
    if m == 12:
        return date(y + 1, 1, 1) - timedelta(days=1)
    return date(y, m + 1, 1) - timedelta(days=1)


def day_count(alerts: list, local_tz) -> Counter:
    return Counter(a.start.astimezone(local_tz).date() for a in alerts)


def produce(root: Path, site_sha: str, generated_at: str | None = None) -> dict:
    scripts = root / "scripts"
    sys.path.insert(0, str(scripts))
    # These imports provide the exact alert normalizations used by site-prod.
    import apply_site_rolling_7d as historical
    from update_data import TZ, round3, daterange, union_daily_seconds, day_counts_and_durations
    source = json.loads((root / "data" / "dashboard_data.json").read_text(encoding="utf-8"))
    cities = source.get("cities", {})
    keys = source.get("multicity_meta", {}).get("production_city_keys")
    if not isinstance(keys, list) or len(keys) != 23 or len(set(keys)) != 23:
        raise RuntimeError("Expected the exact 23-city production index, no extras or duplicates")
    if any(key not in cities for key in keys):
        raise RuntimeError("Production 23-city metadata disagrees with city payload")
    generated_at = generated_at or datetime.now(timezone.utc).isoformat()
    payload = {
        "schema": "verified-historical-daily-start-counts-v1",
        "meta": {"source_ref": "site-prod", "source_commit": site_sha,
                 "generated_at": generated_at, "timezone": "Europe/Kyiv",
                 "meaning": "alerts started on each Kyiv-local calendar date",
                 "expected_cities": 23},
        "cities": {}
    }
    sources: dict[str, list] = {}
    external_error = None
    try:
        sources = historical.build_alert_map(source)
    except Exception as exc:
        # A public mirror failure cannot justify silently inventing 21 proxy histories.
        external_error = f"{type(exc).__name__}: {str(exc)[:160]}"
        print("PREVIEW_PUBLIC_SOURCE_LIMITATION: " + external_error, file=sys.stderr)
        sources = {
            "kyiv": historical.load_kyiv_alerts(),
            "sevastopol": historical.load_sevastopol_alerts()
        }
    for key in keys:
        city = cities[key]
        record = {"status": "unverified", "source_type": city.get("meta", {}).get("source_type"),
                  "reason": "source_unavailable", "coverage_start": city.get("meta", {}).get("coverage_start")}
        if key not in sources or not sources[key]:
            payload["cities"][key] = record
            continue
        try:
            alerts = sources[key]
            # The initial source day can start midway through the day. Treat the
            # following full calendar day as the first certified daily bucket.
            first_day = historical.first_coverage_day(city, alerts) + timedelta(days=1)
            last_day = historical.analysis_end(city)
            if first_day > last_day:
                raise ValueError("no complete days between coverage and analysis end")
            if (last_day - first_day).days > 38000:
                raise ValueError("unexpected historical span")
            counts = day_count(alerts, TZ)
            # Same overlap-deduplication and complete-episode start attribution
            # as the existing production generator, never sum raw overlaps.
            duration_seconds = union_daily_seconds(alerts, first_day, last_day)
            counted, durations_by_start = day_counts_and_durations(alerts, last_day)
            days, daily_seconds, started_seconds = [], [], []
            current = first_day
            while current <= last_day:
                n = int(counts.get(current, 0))
                if n != int(counted.get(current, 0)):
                    raise ValueError("daily start attribution mismatch")
                elapsed = float(duration_seconds.get(current, 0.0))
                started = sum(float(v) * 60 for v in durations_by_start.get(current, []))
                if not (math.isfinite(elapsed) and elapsed >= 0 and
                        math.isfinite(started) and started >= 0):
                    raise ValueError("invalid daily seconds")
                days.append(n)
                daily_seconds.append(elapsed)
                started_seconds.append(started)
                current += timedelta(days=1)
            if not (len(days) == len(daily_seconds) == len(started_seconds)):
                raise ValueError("daily metric lengths diverged")
            def count_range(start: date, end: date) -> int:
                left = (start - first_day).days
                right = (end - first_day).days + 1
                return sum(days[left:right])
            # Match every published complete calendar month for which the new
            # daily series claims FULL coverage. Never check partial months as whole.
            checked_months = 0
            verified_seconds = {}
            seconds_mismatch = []
            verified_metric_months = []
            for row in city.get("monthly", []):
                m = row.get("month") or str(row.get("time", ""))[:7]
                if not isinstance(m, str) or len(m) != 7 or row.get("is_partial_period"):
                    continue
                m_start = date.fromisoformat(m + "-01")
                m_end = _month_end(m)
                if m_start < first_day or m_end > last_day:
                    continue
                expected = int(row["alerts_started"])
                actual = count_range(m_start, m_end)
                if actual != expected:
                    raise ValueError(f"monthly parity {m} expected={expected}, observed={actual}")
                checked_months += 1
                seconds = sum(duration_seconds.get(d, 0.0) for d in daterange(m_start, m_end))
                source_average = row.get("avg_daily_alert_hours")
                if (math.isfinite(seconds) and seconds >= 0 and
                    isinstance(source_average, (float, int)) and
                    round3(seconds / (m_end.day * 3600.0)) == float(source_average)):
                    verified_seconds[m] = {"seconds": seconds, "alerts_started": expected}
                else:
                    seconds_mismatch.append(m)
                # Both time-under-alert and mean full duration of alerts
                # started in the month must match the published rounded values.
                started_total = sum(
                    started_seconds[(d-first_day).days] for d in daterange(m_start, m_end)
                )
                published_duration = row.get("avg_alert_duration_min")
                duration_ok = (
                    (actual == 0 and published_duration is None) or
                    (actual > 0 and isinstance(published_duration, (int, float))
                     and round3(started_total / actual / 60.0) == float(published_duration))
                )
                if m in verified_seconds and duration_ok:
                    verified_metric_months.append(m)
            # Also match completed 28-day production rows, which overlap the
            # latest history and detect source-version drift at the right edge.
            checked_days = 0
            verified_metric_days = []
            for row in city.get("daily28", []):
                d = date.fromisoformat(row["date"])
                if d < first_day or d > last_day or row.get("is_partial_period"):
                    continue
                actual = days[(d-first_day).days]
                expected = int(row["alerts_started"])
                if actual != expected:
                    raise ValueError(f"daily parity {d.isoformat()} expected={expected}, observed={actual}")
                checked_days += 1
                pos = (d-first_day).days
                published_hours = row.get("total_alert_duration_hours")
                published_duration = row.get("avg_alert_duration_minutes")
                duration_ok = (
                    (expected == 0 and published_duration is None) or
                    (expected > 0 and isinstance(published_duration, (int, float))
                     and round3(started_seconds[pos] / expected / 60.0) == float(published_duration))
                )
                hours_ok = (
                    isinstance(published_hours, (int, float)) and
                    round3(daily_seconds[pos] / 3600.0) == float(published_hours)
                )
                if duration_ok and hours_ok:
                    verified_metric_days.append(d.isoformat())
            if checked_months < 1 or checked_days < 1:
                raise ValueError(f"insufficient independent aggregate parity {checked_months}/{checked_days}")
            record = {
                "status": "verified", "source_type": record["source_type"],
                "start": first_day.isoformat(), "end": last_day.isoformat(),
                "counts": days,
                "daily_total_alert_duration_seconds": daily_seconds,
                "daily_started_alert_duration_seconds": started_seconds,
                "verified_metric_months": verified_metric_months,
                "verified_metric_days": verified_metric_days,
                "checked_complete_months": checked_months,
                "checked_recent_days": checked_days, "total_starts": sum(days),
                "max": max(days),
                "monthly_total_alert_duration_seconds": verified_seconds,
                "monthly_seconds_verified": len(verified_seconds),
                "monthly_seconds_unmatched": seconds_mismatch,
                "reason": None
            }
        except Exception as exc:
            record["reason"] = f"{type(exc).__name__}: {str(exc)[:160]}"
        payload["cities"][key] = record
    verified = [key for key, row in payload["cities"].items() if row["status"] == "verified"]
    payload["meta"]["verified_cities"] = verified
    payload["meta"]["verified_count"] = len(verified)
    payload["meta"]["exact_month_seconds_count"] = sum(
        payload["cities"][key].get("monthly_seconds_verified", 0) for key in verified
    )
    payload["meta"]["verified_full_metric_months"] = sum(
        len(payload["cities"][key].get("verified_metric_months", []))
        for key in verified
    )
    payload["meta"]["metric_day_seconds_definition"] = (
        "daily union of overlap-deduplicated local alert intervals; "
        "started-duration sum contains full episodes by local start date"
    )
    payload["meta"]["external_source_error"] = external_error
    if "kyiv" not in verified:
        raise RuntimeError("Fail closed: verified Kyiv daily index was not produced")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--production-root", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not (len(args.source_sha) == 40 and all(ch in "0123456789abcdef" for ch in args.source_sha)):
        raise RuntimeError("Source commit must be a full immutable hex Git SHA")
    result = produce(args.production_root.resolve(), args.source_sha)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n",
                           encoding="utf-8")
    print("HISTORICAL_DAILY_INDEX: verified", result["meta"]["verified_count"],
          "of 23; source_site_prod", args.source_sha)
    for key, row in result["cities"].items():
        print("INDEX_CITY", key, row["status"],
              (f"{row['start']}..{row['end']} max={row['max']} months={row['checked_complete_months']} "
               f"days={row['checked_recent_days']}" if row["status"] == "verified" else row["reason"]))


if __name__ == "__main__":
    main()
