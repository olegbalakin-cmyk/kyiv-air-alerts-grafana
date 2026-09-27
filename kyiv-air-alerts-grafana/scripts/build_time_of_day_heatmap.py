#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import io
import json
import math
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

import add_duration_unit_switch as exactmod
import apply_ukrainealarm_bridge as bridge
import expand_multicity_production as base
import extend_remaining_proxies as extended
from update_data import Alert, TZ, http_session

UTC = timezone.utc
SLOT_MINUTES = 15
SLOT_SECONDS = SLOT_MINUTES * 60
PERIODS = {
    "7d": 7,
    "30d": 30,
    "90d": 90,
    "year": 365,
    "all": None,
}


def parse_dt(value: str) -> datetime:
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError(f"Timezone-aware datetime required: {value!r}")
    return dt


def union_alerts(alerts: list[Alert], source: str) -> list[Alert]:
    merged: list[list[datetime]] = []
    for alert in sorted(alerts, key=lambda a: a.start.astimezone(UTC)):
        start = alert.start.astimezone(TZ)
        end = alert.end.astimezone(TZ)
        if end <= start:
            continue
        if not merged or start.astimezone(UTC) > merged[-1][1].astimezone(UTC):
            merged.append([start, end])
        elif end.astimezone(UTC) > merged[-1][1].astimezone(UTC):
            merged[-1][1] = end
    return [Alert(start=s, end=e, source=source) for s, e in merged]


def load_historical_source() -> tuple[dict[str, list[Alert]], dict[str, list[Alert]], dict[str, dict]]:
    proxy_cfg = extended.configure_all_proxies()
    session = http_session()
    response = session.get(exactmod.CITY_SOURCE_URL, timeout=120)
    response.raise_for_status()
    source_text = response.content.decode("utf-8-sig")

    hromada_to_key = {cfg["hromada"]: key for key, cfg in exactmod.CITY_CONFIG.items()}
    exact: dict[str, list[Alert]] = {key: [] for key in exactmod.CITY_CONFIG}
    exact_seen: dict[str, set[tuple[str, str]]] = {key: set() for key in exactmod.CITY_CONFIG}

    oblast_to_key = {cfg["oblast"]: key for key, cfg in proxy_cfg.items()}
    proxy_intervals: dict[str, list[tuple[datetime, datetime]]] = {key: [] for key in proxy_cfg}
    proxy_seen: dict[str, set[tuple[str, str, str]]] = {key: set() for key in proxy_cfg}

    for row in csv.DictReader(io.StringIO(source_text)):
        level = (row.get("level") or "").strip()
        started = (row.get("started_at") or "").strip()
        finished = (row.get("finished_at") or "").strip()
        if not started or not finished:
            continue
        try:
            start = parse_dt(started).astimezone(TZ)
            end = parse_dt(finished).astimezone(TZ)
        except ValueError:
            continue
        if end <= start:
            continue

        if level == "hromada":
            key = hromada_to_key.get((row.get("hromada") or "").strip())
            if key:
                marker = (started, finished)
                valid_from = parse_dt(exactmod.CITY_CONFIG[key]["valid_from"]).astimezone(TZ)
                if marker not in exact_seen[key] and start >= valid_from:
                    exact_seen[key].add(marker)
                    exact[key].append(Alert(start=start, end=end, source="vadimkin_official"))

        oblast = (row.get("oblast") or "").strip()
        proxy_key = oblast_to_key.get(oblast)
        if not proxy_key:
            continue
        cfg = proxy_cfg[proxy_key]
        raion = (row.get("raion") or "").strip()
        if level != "oblast" and not (level == "raion" and raion == cfg["raion"]):
            continue
        marker = (level, started, finished)
        if marker in proxy_seen[proxy_key]:
            continue
        cutoff = datetime.combine(date.fromisoformat(cfg["coverage_start"]), time.min, tzinfo=TZ)
        if end <= cutoff:
            continue
        proxy_seen[proxy_key].add(marker)
        proxy_intervals[proxy_key].append((max(start, cutoff), end))

    for alerts in exact.values():
        alerts.sort(key=lambda a: a.start.astimezone(UTC))
    proxy = {
        key: [Alert(start=a.start, end=a.end, source=a.source) for a in base.union_alerts(intervals)]
        for key, intervals in proxy_intervals.items()
    }
    return exact, proxy, proxy_cfg


def load_kyiv(path: Path) -> list[Alert]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    alerts = []
    for row in rows:
        try:
            start = parse_dt(row["start"]).astimezone(TZ)
            end = parse_dt(row["end"]).astimezone(TZ)
        except (KeyError, ValueError, TypeError):
            continue
        if end > start:
            alerts.append(Alert(start=start, end=end, source=row.get("source", "kyiv_combined")))
    return union_alerts(alerts, "kyiv_production_combined")


def load_sevastopol(path: Path) -> list[Alert]:
    store = json.loads(path.read_text(encoding="utf-8"))
    alerts = []
    for row in store.get("pairs", []):
        try:
            start = parse_dt(row["start"]).astimezone(TZ)
            end = parse_dt(row["end"]).astimezone(TZ)
        except (KeyError, ValueError, TypeError):
            continue
        if end > start:
            alerts.append(Alert(start=start, end=end, source="sevastopol_occupation_admin_telegram"))
    return union_alerts(alerts, "sevastopol_production_combined")


def load_bridge_store(path: Path) -> dict:
    store = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(store.get("events"), list):
        raise RuntimeError("UkraineAlarm bridge store has no events array")
    return store


def bridge_alerts(store: dict, key: str) -> list[Alert]:
    alerts = []
    for row in store.get("events", []):
        if row.get("city_key") != key or row.get("alert_type") not in (None, "AIR"):
            continue
        try:
            start = parse_dt(row["start"]).astimezone(TZ)
            end = parse_dt(row["end"]).astimezone(TZ)
        except (KeyError, ValueError, TypeError):
            continue
        if end > start:
            alerts.append(Alert(start=start, end=end, source="ukrainealarm_bridge"))
    return alerts


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


def format_slot(index: int) -> tuple[str, str]:
    start_minutes = index * SLOT_MINUTES
    end_minutes = (start_minutes + SLOT_MINUTES) % (24 * 60)
    sh, sm = divmod(start_minutes, 60)
    eh, em = divmod(end_minutes, 60)
    start = f"{sh:02d}:{sm:02d}"
    end = f"{eh:02d}:{em:02d}"
    return start, f"{start}–{end}"


def period_heatmap(
    alerts: list[Alert],
    coverage_day: date,
    end_day: date,
    requested_days: int | None,
) -> dict:
    if requested_days is None:
        start_day = coverage_day
    else:
        start_day = max(coverage_day, end_day - timedelta(days=requested_days - 1))
    if start_day > end_day:
        raise RuntimeError(f"Invalid heatmap range: {start_day} > {end_day}")

    start_local = datetime.combine(start_day, time.min, tzinfo=TZ)
    end_local = datetime.combine(end_day + timedelta(days=1), time.min, tzinfo=TZ)
    start_utc = start_local.astimezone(UTC)
    end_utc = end_local.astimezone(UTC)

    possible = [0.0] * 96
    active = [0.0] * 96
    add_interval_seconds(possible, start_utc, end_utc)

    for alert in alerts:
        a0 = max(alert.start.astimezone(UTC), start_utc)
        a1 = min(alert.end.astimezone(UTC), end_utc)
        if a1 > a0:
            add_interval_seconds(active, a0, a1)

    shares = [
        (active[i] / possible[i] * 100.0) if possible[i] > 0 else 0.0
        for i in range(96)
    ]
    peak = max(shares) if shares else 0.0
    peak_index = shares.index(peak) if peak > 0 else None
    slots = []
    for i, share in enumerate(shares):
        start_label, label = format_slot(i)
        slots.append(
            {
                "index": i,
                "start": start_label,
                "label": label,
                "alert_share_pct": round(share, 3),
                "relative_intensity": round((share / peak * 100.0) if peak > 0 else 0.0, 2),
                "alert_minutes": round(active[i] / 60.0, 2),
                "possible_minutes": round(possible[i] / 60.0, 2),
            }
        )

    return {
        "range_start": start_day.isoformat(),
        "range_end": end_day.isoformat(),
        "days": (end_day - start_day).days + 1,
        "requested_days": requested_days,
        "peak_slot": format_slot(peak_index)[1] if peak_index is not None else None,
        "peak_alert_share_pct": round(peak, 3),
        "slots": slots,
    }


def period_summary(alerts: list[Alert], start_day: date, end_day: date) -> dict:
    start_local = datetime.combine(start_day, time.min, tzinfo=TZ)
    end_local = datetime.combine(end_day + timedelta(days=1), time.min, tzinfo=TZ)
    start_utc = start_local.astimezone(UTC)
    end_utc = end_local.astimezone(UTC)

    active_seconds = 0.0
    for alert in alerts:
        a0 = max(alert.start.astimezone(UTC), start_utc)
        a1 = min(alert.end.astimezone(UTC), end_utc)
        if a1 > a0:
            active_seconds += (a1 - a0).total_seconds()

    starts_in_period = [
        alert
        for alert in alerts
        if start_utc <= alert.start.astimezone(UTC) < end_utc
    ]
    durations_min = [
        (alert.end.astimezone(UTC) - alert.start.astimezone(UTC)).total_seconds() / 60.0
        for alert in starts_in_period
        if alert.end.astimezone(UTC) > alert.start.astimezone(UTC)
    ]
    avg_duration = sum(durations_min) / len(durations_min) if durations_min else None

    return {
        "range_start": start_day.isoformat(),
        "range_end": end_day.isoformat(),
        "days": (end_day - start_day).days + 1,
        "alerts_started": len(starts_in_period),
        "alert_hours": round(active_seconds / 3600.0, 3),
        "avg_alert_duration_min": round(avg_duration, 3) if avg_duration is not None else None,
    }


def coverage_start(dashboard: dict, key: str, alerts: list[Alert]) -> date:
    meta = dashboard.get("multicity_meta", {}).get("cities", {}).get(key, {})
    value = meta.get("coverage_start") or dashboard.get("cities", {}).get(key, {}).get("meta", {}).get("coverage_start")
    if value:
        return date.fromisoformat(str(value)[:10])
    return min(a.start.astimezone(TZ).date() for a in alerts)


def analysis_end(dashboard: dict, key: str) -> date:
    city_meta = dashboard.get("cities", {}).get(key, {}).get("meta", {})
    value = city_meta.get("analysis_end") or dashboard.get("meta", {}).get("analysis_end")
    if not value:
        raise RuntimeError(f"No analysis_end for {key}")
    return date.fromisoformat(str(value)[:10])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dashboard", type=Path, required=True)
    parser.add_argument("--kyiv-alerts", type=Path, required=True)
    parser.add_argument("--bridge-store", type=Path, required=True)
    parser.add_argument("--sevastopol-events", type=Path, required=True)
    args = parser.parse_args()

    dashboard = json.loads(args.dashboard.read_text(encoding="utf-8"))
    production_keys = list(dashboard.get("multicity_meta", {}).get("production_city_keys", []))
    if len(production_keys) != 23:
        raise RuntimeError(f"Expected 23 production rows, got {len(production_keys)}")

    exact_base, proxy_base, proxy_cfg = load_historical_source()
    static, _ = bridge.load_static_bridge()
    store = load_bridge_store(args.bridge_store)

    city_alerts: dict[str, list[Alert]] = {
        "kyiv": load_kyiv(args.kyiv_alerts),
        "sevastopol": load_sevastopol(args.sevastopol_events),
    }

    for key in exactmod.CITY_CONFIG:
        city_alerts[key] = union_alerts(
            [*exact_base.get(key, []), *static.get(key, []), *bridge_alerts(store, key)],
            "historical_exact_plus_bridge",
        )

    for key in proxy_cfg:
        city_alerts[key] = union_alerts(
            [*proxy_base.get(key, []), *static.get(key, []), *bridge_alerts(store, key)],
            "historical_proxy_plus_bridge",
        )

    missing = [key for key in production_keys if not city_alerts.get(key)]
    if missing:
        raise RuntimeError(f"Missing alert intervals for heatmap rows: {missing}")

    coverage_days = {
        key: coverage_start(dashboard, key, city_alerts[key])
        for key in production_keys
    }
    analysis_days = {
        key: analysis_end(dashboard, key)
        for key in production_keys
    }
    common_start_day = max(coverage_days.values())
    common_end_day = min(analysis_days.values())
    if common_start_day > common_end_day:
        raise RuntimeError(
            f"No shared all-city window: {common_start_day} > {common_end_day}"
        )

    cities = {}
    table_cities = {}
    table_specs = {
        "7d": 7,
        "30d": 30,
        "90d": 90,
        "year": 365,
        "common": None,
    }

    for key in production_keys:
        alerts = city_alerts[key]
        start_day = coverage_days[key]
        end_day = analysis_days[key]
        periods = {
            period: period_heatmap(alerts, start_day, end_day, days)
            for period, days in PERIODS.items()
        }
        cities[key] = {
            "coverage_start": start_day.isoformat(),
            "analysis_end": end_day.isoformat(),
            "source_type": dashboard.get("multicity_meta", {}).get("cities", {}).get(key, {}).get("source_type"),
            "periods": periods,
        }

        table_periods = {}
        for period, requested_days in table_specs.items():
            if requested_days is None:
                table_start = common_start_day
            else:
                requested_start = common_end_day - timedelta(days=requested_days - 1)
                table_start = max(common_start_day, requested_start)
            table_periods[period] = period_summary(alerts, table_start, common_end_day)
        table_cities[key] = {"periods": table_periods}

    dashboard["all_cities_table_test"] = {
        "meta": {
            "test_only": True,
            "city_count": len(table_cities),
            "periods": list(table_specs),
            "common_start": common_start_day.isoformat(),
            "common_end": common_end_day.isoformat(),
            "comparison_window": "intersection_of_all_23_city_rows",
            "current_day_excluded": True,
        },
        "cities": table_cities,
    }

    dashboard["time_of_day_heatmap_test"] = {
        "meta": {
            "test_only": True,
            "slot_minutes": SLOT_MINUTES,
            "timezone": "Europe/Kyiv",
            "city_count": len(cities),
            "periods": list(PERIODS),
            "current_day_excluded": True,
            "color_scale": "normalized_to_city_period_peak",
            "cell_value": "share_of_real_elapsed_time_in_local_15_minute_slot_spent_under_alert",
            "dst_handling": "actual elapsed seconds are mapped to Europe/Kyiv local slots; repeated or skipped DST time is weighted by real duration",
        },
        "cities": cities,
    }
    args.dashboard.write_text(json.dumps(dashboard, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "ok": True,
        "city_count": len(cities),
        "slot_minutes": SLOT_MINUTES,
        "periods": list(PERIODS),
        "all_cities_table_common_start": common_start_day.isoformat(),
        "all_cities_table_common_end": common_end_day.isoformat(),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
