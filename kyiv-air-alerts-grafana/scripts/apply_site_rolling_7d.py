#!/usr/bin/env python3
from __future__ import annotations

import json
import math
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from statistics import mean

import add_duration_unit_switch as exactmod
import add_sevastopol_exact as sevastopol
import apply_ukrainealarm_bridge as bridge
import expand_multicity_production as proxybase
import extend_remaining_proxies as extended
from update_data import (
    Alert,
    TZ,
    daterange,
    day_counts_and_durations,
    round3,
    union_daily_seconds,
)

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data" / "dashboard_data.json"
KYIV_ALERTS_FILE = ROOT / "data" / "alerts_combined.json"
SEVASTOPOL_EVENTS_FILE = ROOT / "data" / "sevastopol_events.json"

UTC = timezone.utc
SLOT_MINUTES = 15
SLOT_SECONDS = SLOT_MINUTES * 60
PROFILE_PERIODS = {"7d": 7, "30d": 30, "90d": 90, "year": 365, "all": None}


def load_kyiv_alerts() -> list[Alert]:
    rows = json.loads(KYIV_ALERTS_FILE.read_text(encoding="utf-8"))
    alerts = []
    for row in rows:
        start = datetime.fromisoformat(row["start"]).astimezone(TZ)
        end = datetime.fromisoformat(row["end"]).astimezone(TZ)
        if end > start:
            alerts.append(Alert(start=start, end=end, source=row.get("source", "kyiv_combined")))
    return sorted(alerts, key=lambda a: a.start)


def load_sevastopol_alerts() -> list[Alert]:
    store = json.loads(SEVASTOPOL_EVENTS_FILE.read_text(encoding="utf-8"))
    alerts = []
    for row in store.get("pairs", []):
        start = datetime.fromisoformat(row["start"]).astimezone(TZ)
        end = datetime.fromisoformat(row["end"]).astimezone(TZ)
        if end > start:
            alerts.append(
                Alert(start=start, end=end, source="sevastopol_occupation_admin_telegram")
            )
    return sorted(alerts, key=lambda a: a.start)


def rolling_rows(alerts: list[Alert], first_city_day: date, end_day: date) -> list[dict]:
    """Build one point per completed day, each covering the previous 7 days.

    The first city-level/coverage day is excluded conservatively because coverage can
    start part-way through that date. Each point is timestamped by the final day of
    its seven-day window, matching the rolling view previously used in Grafana.
    """
    first_window_start = first_city_day + timedelta(days=1)
    first_window_end = first_window_start + timedelta(days=6)
    if first_window_end > end_day:
        return []

    counts, durations_by_start = day_counts_and_durations(alerts, end_day)
    daily_seconds = union_daily_seconds(alerts, first_window_start, end_day)

    rows: list[dict] = []
    window_end = first_window_end
    while window_end <= end_day:
        window_start = window_end - timedelta(days=6)
        days = list(daterange(window_start, window_end))
        starts = sum(counts.get(d, 0) for d in days)
        seconds = sum(daily_seconds.get(d, 0.0) for d in days)
        event_durations = [
            duration
            for d in days
            for duration in durations_by_start.get(d, [])
        ]
        rows.append(
            {
                "time": datetime.combine(window_end, time.min, tzinfo=TZ).isoformat(),
                "week_start": window_start.isoformat(),
                "week_end": window_end.isoformat(),
                "alerts_per_day": round3(starts / 7.0),
                "avg_daily_alert_hours": round3(seconds / 7.0 / 3600.0),
                "avg_alert_duration_min": round3(
                    mean(event_durations) if event_durations else None
                ),
                "alerts_started": starts,
            }
        )
        window_end += timedelta(days=1)
    return rows


def rolling_window_rows(
    alerts: list[Alert],
    first_city_day: date,
    end_day: date,
    window_days: int,
) -> list[dict]:
    first_window_start = first_city_day + timedelta(days=1)
    first_window_end = first_window_start + timedelta(days=window_days - 1)
    if first_window_end > end_day:
        return []

    counts, durations_by_start = day_counts_and_durations(alerts, end_day)
    daily_seconds = union_daily_seconds(alerts, first_window_start, end_day)

    rows: list[dict] = []
    window_end = first_window_end
    while window_end <= end_day:
        window_start = window_end - timedelta(days=window_days - 1)
        days = list(daterange(window_start, window_end))
        starts = sum(counts.get(d, 0) for d in days)
        seconds = sum(daily_seconds.get(d, 0.0) for d in days)
        event_durations = [
            duration
            for d in days
            for duration in durations_by_start.get(d, [])
        ]
        rows.append(
            {
                "time": datetime.combine(window_end, time.min, tzinfo=TZ).isoformat(),
                "window_start": window_start.isoformat(),
                "window_end": window_end.isoformat(),
                "window_days": window_days,
                "alerts_per_day": round3(starts / float(window_days)),
                "avg_daily_alert_hours": round3(seconds / float(window_days) / 3600.0),
                "avg_alert_duration_min": round3(
                    mean(event_durations) if event_durations else None
                ),
                "alerts_started": starts,
            }
        )
        window_end += timedelta(days=1)
    return rows


def period_summary(alerts: list[Alert], start_day: date, end_day: date) -> dict:
    counts, durations_by_start = day_counts_and_durations(alerts, end_day)
    daily_seconds = union_daily_seconds(alerts, start_day, end_day)
    days = list(daterange(start_day, end_day))
    starts = sum(counts.get(d, 0) for d in days)
    seconds = sum(daily_seconds.get(d, 0.0) for d in days)
    event_durations = [
        duration
        for d in days
        for duration in durations_by_start.get(d, [])
    ]
    return {
        "range_start": start_day.isoformat(),
        "range_end": end_day.isoformat(),
        "days": len(days),
        "alerts_started": starts,
        "alert_hours": round3(seconds / 3600.0),
        "avg_alert_duration_min": round3(
            mean(event_durations) if event_durations else None
        ),
    }


def slot_index(local_dt: datetime) -> int:
    return local_dt.hour * 4 + local_dt.minute // SLOT_MINUTES


def add_interval_seconds(buckets: list[float], start: datetime, end: datetime) -> None:
    cur = start.astimezone(UTC)
    stop = end.astimezone(UTC)
    while cur < stop:
        ts = cur.timestamp()
        next_boundary_ts = (math.floor(ts / SLOT_SECONDS) + 1) * SLOT_SECONDS
        nxt = min(stop, datetime.fromtimestamp(next_boundary_ts, UTC))
        midpoint = cur + (nxt - cur) / 2
        buckets[slot_index(midpoint.astimezone(TZ))] += (nxt - cur).total_seconds()
        cur = nxt


def merged_active_intervals(alerts: list[Alert]) -> list[tuple[datetime, datetime]]:
    merged: list[list[datetime]] = []
    for alert in sorted(alerts, key=lambda a: a.start.astimezone(UTC)):
        start = alert.start.astimezone(UTC)
        end = alert.end.astimezone(UTC)
        if end <= start:
            continue
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        elif end > merged[-1][1]:
            merged[-1][1] = end
    return [(a, b) for a, b in merged]


def format_slot(index: int) -> tuple[str, str]:
    start_minutes = index * SLOT_MINUTES
    end_minutes = (start_minutes + SLOT_MINUTES) % (24 * 60)
    sh, sm = divmod(start_minutes, 60)
    eh, em = divmod(end_minutes, 60)
    start = f"{sh:02d}:{sm:02d}"
    end = f"{eh:02d}:{em:02d}"
    return start, f"{start}–{end}"


def time_profile(
    alerts: list[Alert],
    coverage_day: date,
    end_day: date,
    requested_days: int | None,
) -> dict:
    safe_start = coverage_day + timedelta(days=1)
    start_day = safe_start if requested_days is None else max(
        safe_start, end_day - timedelta(days=requested_days - 1)
    )
    start_local = datetime.combine(start_day, time.min, tzinfo=TZ)
    end_local = datetime.combine(end_day + timedelta(days=1), time.min, tzinfo=TZ)
    start_utc = start_local.astimezone(UTC)
    end_utc = end_local.astimezone(UTC)

    possible = [0.0] * 96
    active = [0.0] * 96
    add_interval_seconds(possible, start_utc, end_utc)
    for raw_start, raw_end in merged_active_intervals(alerts):
        a0=max(raw_start,start_utc)
        a1=min(raw_end,end_utc)
        if a1>a0:
            add_interval_seconds(active,a0,a1)

    shares=[
        (active[i]/possible[i]*100.0) if possible[i]>0 else 0.0
        for i in range(96)
    ]
    peak=max(shares) if shares else 0.0
    peak_index=shares.index(peak) if peak>0 else None
    slots=[]
    for i,share in enumerate(shares):
        start_label,label=format_slot(i)
        slots.append({
            "index": i,
            "start": start_label,
            "label": label,
            "alert_share_pct": round(share,3),
            "relative_intensity": round((share/peak*100.0) if peak>0 else 0.0,2),
        })
    return {
        "range_start": start_day.isoformat(),
        "range_end": end_day.isoformat(),
        "days": (end_day-start_day).days+1,
        "requested_days": requested_days,
        "peak_slot": format_slot(peak_index)[1] if peak_index is not None else None,
        "peak_alert_share_pct": round(peak,3),
        "slots": slots,
    }


def add_partial_month(city: dict, alerts: list[Alert], first_day: date, end_day: date) -> None:
    month_start=end_day.replace(day=1)
    next_month=(date(month_start.year+1,1,1) if month_start.month==12 else date(month_start.year,month_start.month+1,1))
    month_last=next_month-timedelta(days=1)
    safe_start=first_day+timedelta(days=1)
    if end_day>=month_last or month_start<safe_start:
        return
    summary=period_summary(alerts,month_start,end_day)
    elapsed=summary["days"]
    row={
        "time": datetime.combine(month_start,time.min,tzinfo=TZ).isoformat(),
        "month": month_start.strftime("%Y-%m"),
        "alerts_per_day": round3(summary["alerts_started"]/float(elapsed)),
        "avg_daily_alert_hours": round3(summary["alert_hours"]/float(elapsed)),
        "avg_alert_duration_min": summary["avg_alert_duration_min"],
        "alerts_started": summary["alerts_started"],
        "is_partial_period": True,
        "partial_through": end_day.isoformat(),
    }
    monthly=city.setdefault("monthly",[])
    if monthly and monthly[-1].get("month")==row["month"]:
        monthly[-1]=row
    else:
        monthly.append(row)


def first_coverage_day(city: dict, alerts: list[Alert]) -> date:
    meta = city.get("meta", {})
    raw = meta.get("coverage_start") or meta.get("first_city_level_date")
    if raw:
        return date.fromisoformat(str(raw)[:10])
    return min(a.start.astimezone(TZ).date() for a in alerts)


def analysis_end(city: dict) -> date:
    raw = city.get("meta", {}).get("analysis_end")
    if raw:
        return date.fromisoformat(str(raw)[:10])
    return datetime.now(TZ).date() - timedelta(days=1)


def update_city_rolling(city: dict, alerts: list[Alert]) -> None:
    if not alerts:
        raise RuntimeError("Cannot build rolling 7-day series from an empty alert list")
    first_day = first_coverage_day(city, alerts)
    end_day = analysis_end(city)
    rows = rolling_rows(alerts, first_day, end_day)
    city["weekly"] = rows
    city["rolling30"] = rolling_window_rows(alerts, first_day, end_day, 30)
    city["rolling90"] = rolling_window_rows(alerts, first_day, end_day, 90)
    add_partial_month(city, alerts, first_day, end_day)

    meta = city.setdefault("meta", {})
    meta["weekly_mode"] = "rolling_7d"
    meta["rolling_7d_definition"] = (
        "7 completed calendar days, one point per completed day, timestamped by window end"
    )
    meta["rolling_7d_analysis_end"] = end_day.isoformat()
    if rows:
        meta["first_rolling_7d_start"] = rows[0]["week_start"]
        meta["first_rolling_7d_end"] = rows[0]["week_end"]
        meta["latest_rolling_7d_start"] = rows[-1]["week_start"]
        meta["latest_rolling_7d_end"] = rows[-1]["week_end"]
        # Keep legacy keys aligned with the payload used by old Grafana queries.
        meta["first_complete_week_start"] = rows[0]["week_start"]
        meta["last_complete_week_start"] = rows[-1]["week_start"]
        meta["last_complete_week_end"] = rows[-1]["week_end"]


def build_alert_map(data: dict) -> dict[str, list[Alert]]:
    proxy_cfg = extended.configure_all_proxies()
    static, _ = bridge.load_static_bridge()
    store = bridge.load_store()
    exact_base = exactmod.fetch_city_alerts()
    proxy_base = proxybase.fetch_proxy_alerts()

    out: dict[str, list[Alert]] = {"kyiv": load_kyiv_alerts()}

    for key in exactmod.CITY_CONFIG:
        region_status = store.get("regions", {}).get(key, {})
        api_alerts = bridge.api_store_alerts(store, key) if region_status.get("continuous") else []
        out[key] = bridge.union_alerts(
            [*exact_base[key], *static.get(key, []), *api_alerts],
            "rolling_exact_city_combined",
        )

    for key in proxy_cfg:
        region_status = store.get("regions", {}).get(key, {})
        api_alerts = bridge.api_store_alerts(store, key) if region_status.get("continuous") else []
        out[key] = bridge.union_alerts(
            [*proxy_base[key], *static.get(key, []), *api_alerts],
            "rolling_raion_combined",
        )

    out[sevastopol.CITY_KEY] = load_sevastopol_alerts()
    return out


def main() -> None:
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    cities = data.get("cities", {})
    meta = data.setdefault("multicity_meta", {})
    keys = list(meta.get("production_city_keys", []))
    if len(keys) != 23:
        raise RuntimeError(f"Expected 23 production rows before rolling conversion, found {len(keys)}")

    alerts_by_city = build_alert_map(data)
    missing = [key for key in keys if key not in alerts_by_city or not alerts_by_city[key]]
    if missing:
        raise RuntimeError("Missing event history for rolling rows: " + ", ".join(missing))

    for key in keys:
        update_city_rolling(cities[key], alerts_by_city[key])
        city_mm = meta.setdefault("cities", {}).setdefault(key, {})
        city_mm["weekly_mode"] = "rolling_7d"
        city_mm["first_rolling_7d_start"] = cities[key]["meta"].get("first_rolling_7d_start")
        city_mm["latest_rolling_7d_end"] = cities[key]["meta"].get("latest_rolling_7d_end")

    # Keep the legacy top-level aliases consistent with Kyiv.
    data["weekly"] = cities["kyiv"]["weekly"]
    data.setdefault("meta", {})["weekly_mode"] = "rolling_7d"
    data["meta"]["rolling_7d_definition"] = (
        "7 completed calendar days, one point per completed day, timestamped by window end"
    )

    data.setdefault("comparison", {})["weekly"] = bridge.generic_comparison(
        cities, keys, "weekly"
    )
    meta["weekly_mode"] = "rolling_7d"
    meta["rolling_7d_definition"] = (
        "7 completed calendar days; adjacent points overlap by 6 days"
    )

    coverage_days = {key: first_coverage_day(cities[key], alerts_by_city[key]) for key in keys}
    analysis_days = {key: analysis_end(cities[key]) for key in keys}
    common_start = max(day + timedelta(days=1) for day in coverage_days.values())
    common_end = min(analysis_days.values())
    table_specs = {"7d": 7, "30d": 30, "90d": 90, "year": 365, "common": None}

    profile_cities = {}
    table_cities = {}
    for key in keys:
        city_profiles = {
            period: time_profile(alerts_by_city[key], coverage_days[key], analysis_days[key], requested)
            for period, requested in PROFILE_PERIODS.items()
        }
        profile_cities[key] = {
            "coverage_start": coverage_days[key].isoformat(),
            "analysis_end": analysis_days[key].isoformat(),
            "source_type": meta.get("cities", {}).get(key, {}).get("source_type"),
            "periods": city_profiles,
        }

        periods = {}
        for period, requested in table_specs.items():
            start = common_start if requested is None else max(
                common_start, common_end - timedelta(days=requested - 1)
            )
            periods[period] = period_summary(alerts_by_city[key], start, common_end)
        table_cities[key] = {"periods": periods}

    data["time_of_day_profile"] = {
        "meta": {
            "slot_minutes": SLOT_MINUTES,
            "timezone": "Europe/Kyiv",
            "city_count": len(profile_cities),
            "periods": list(PROFILE_PERIODS),
            "current_day_excluded": True,
            "normalization": "each city/period peak = 100",
        },
        "cities": profile_cities,
    }
    data["all_cities_table"] = {
        "meta": {
            "city_count": len(table_cities),
            "periods": list(table_specs),
            "common_start": common_start.isoformat(),
            "common_end": common_end.isoformat(),
            "comparison_window": "intersection_of_all_23_city_rows",
            "current_day_excluded": True,
        },
        "cities": table_cities,
    }
    meta["rolling_window_periods"] = ["weekly", "rolling30", "rolling90"]
    meta["time_of_day_profile_version"] = "production-v1"
    meta["all_cities_table_version"] = "production-v1"

    DATA_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print("Converted all production rows to rolling 7-day windows:", len(keys))
    for key in keys:
        rows = cities[key].get("weekly", [])
        print(
            key,
            len(rows),
            rows[0]["week_end"] if rows else None,
            "->",
            rows[-1]["week_end"] if rows else None,
        )


if __name__ == "__main__":
    main()
