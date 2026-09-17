#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta
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
