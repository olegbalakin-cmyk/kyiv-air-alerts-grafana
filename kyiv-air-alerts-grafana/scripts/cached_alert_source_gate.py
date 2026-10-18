#!/usr/bin/env python3
"""Strict offline gate for one pinned production UkraineAlarm/23-city snapshot.

This module performs only local reads. In the monitor it MUST run before
ensure_state(), review/publisher discovery, Neon, or persistence.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

UTC = timezone.utc
MAX_SOURCE_AGE = timedelta(hours=12)
SUPPORTED_SCHEMA = 3
REQUIRED_REGIONS = frozenset((
    "cherkasy", "chernihiv", "chernivtsi", "dnipro", "ivano_frankivsk",
    "kharkiv", "kherson", "khmelnytskyi", "kropyvnytskyi", "lutsk",
    "lviv", "mykolaiv", "odesa", "poltava", "rivne", "sumy",
    "ternopil", "uzhhorod", "vinnytsia", "zaporizhzhia", "zhytomyr",
))
SPECIAL_CITIES = frozenset(("kyiv", "sevastopol"))
EXPECTED_CITIES = REQUIRED_REGIONS | SPECIAL_CITIES


class SourceGateError(RuntimeError):
    """The production source is not safe to consume. No fallback is permitted."""


def demand(condition: bool, reason: str) -> None:
    if not condition:
        raise SourceGateError(reason)


def require_json(path: Path, label: str):
    demand(path.is_file(), f"{label}:missing_file:{path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SourceGateError(f"{label}:invalid_json:{type(exc).__name__}") from exc


def timestamp(value, label: str, *, utc_only: bool) -> datetime:
    demand(isinstance(value, str) and bool(value.strip()), f"{label}:missing_or_invalid_timestamp")
    txt = value.strip()
    # Accept real timezone offsets for Kyiv and Sevastopol historical records,
    # but require explicit UTC for the authoritative API freshness checkpoint.
    try:
        dt = datetime.fromisoformat(txt.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SourceGateError(f"{label}:malformed_timestamp") from exc
    demand(dt.tzinfo is not None and dt.utcoffset() is not None,
           f"{label}:timezone_required")
    if utc_only:
        demand(txt.endswith("Z") or txt.endswith("+00:00"),
               f"{label}:explicit_utc_required")
        demand(dt.utcoffset() == timedelta(0), f"{label}:utc_required")
    return dt.astimezone(UTC)


def fresh(value, label: str, now: datetime) -> datetime:
    dt = timestamp(value, label, utc_only=True)
    demand(dt <= now, f"{label}:future_timestamp")
    demand(now - dt <= MAX_SOURCE_AGE, f"{label}:older_than_12_hours")
    return dt


def valid_intervals(rows, label: str, *, allowed_cities: frozenset[str] | None = None) -> int:
    demand(isinstance(rows, list) and bool(rows), f"{label}:missing_or_empty_collection")
    for idx, row in enumerate(rows):
        prefix = f"{label}[{idx}]"
        demand(isinstance(row, dict), f"{prefix}:not_an_object")
        if allowed_cities is not None:
            demand(row.get("city_key") in allowed_cities,
                   f"{prefix}:unexpected_city_key")
            demand(row.get("alert_type", "AIR") == "AIR",
                   f"{prefix}:unexpected_alert_type")
        start = timestamp(row.get("start"), prefix + ".start", utc_only=False)
        end = timestamp(row.get("end"), prefix + ".end", utc_only=False)
        demand(start < end, f"{prefix}:invalid_interval")
    return len(rows)


def validate_cached_source_files(
    *, bridge_path: Path, dashboard_path: Path, kyiv_alerts_path: Path,
    sevastopol_events_path: Path, qa_path: Path, now: datetime,
    monitor_city_keys=None,
) -> dict:
    """Validate five immutable-site-prod-file inputs at an injected clock.

    Returns a small read-only receipt; raises SourceGateError on any defect.
    No network, writes, or fallback calls are performed.
    """
    demand(isinstance(now, datetime) and now.tzinfo is not None
           and now.utcoffset() is not None, "reference_clock:timezone_required")
    now = now.astimezone(UTC)

    bridge = require_json(bridge_path, "bridge")
    dashboard = require_json(dashboard_path, "dashboard")
    kyiv = require_json(kyiv_alerts_path, "kyiv")
    sevastopol = require_json(sevastopol_events_path, "sevastopol")
    qa = require_json(qa_path, "qa")

    demand(isinstance(bridge, dict), "bridge:not_an_object")
    demand(type(bridge.get("schema_version")) is int
           and bridge["schema_version"] == SUPPORTED_SCHEMA,
           "bridge:unsupported_schema")
    demand(bridge.get("last_fetch_error") is None, "bridge:top_level_fetch_error")
    checkpoint = fresh(bridge.get("last_successful_fetch_at"),
                       "bridge.last_successful_fetch_at", now)

    regions = bridge.get("regions")
    demand(isinstance(regions, dict), "bridge:regions_not_an_object")
    demand(set(regions) == REQUIRED_REGIONS,
           "bridge:missing_or_extra_required_region")
    for city in sorted(REQUIRED_REGIONS):
        row = regions[city]
        demand(isinstance(row, dict), f"region.{city}:not_an_object")
        demand(row.get("city_key") == city, f"region.{city}:city_key_mismatch")
        demand(isinstance(row.get("region_id"), str) and bool(row["region_id"]),
               f"region.{city}:missing_region_id")
        demand(row.get("continuous") is True, f"region.{city}:not_continuous")
        demand(row.get("poll_overlap_verified") is True,
               f"region.{city}:overlap_not_verified")
        demand(row.get("last_error") is None, f"region.{city}:unresolved_error")
        fresh(row.get("last_checked_at"), f"region.{city}.last_checked_at", now)

    events = bridge.get("events")
    demand(isinstance(events, list), "bridge:invalid_events_collection")
    count = bridge.get("event_count")
    demand(type(count) is int and count == len(events), "bridge:event_count_mismatch")
    # Empty events are not evidence of a usable historical source.
    valid_intervals(events, "bridge.events", allowed_cities=REQUIRED_REGIONS)

    demand(isinstance(dashboard, dict) and isinstance(dashboard.get("cities"), dict),
           "dashboard:invalid_cities")
    demand(set(dashboard["cities"]) == EXPECTED_CITIES,
           "dashboard:missing_or_extra_23_city_input")

    valid_intervals(kyiv, "kyiv")
    demand(isinstance(sevastopol, dict), "sevastopol:not_an_object")
    valid_intervals(sevastopol.get("pairs"), "sevastopol.pairs")

    demand(isinstance(qa, dict), "qa:not_an_object")
    demand(qa.get("ok") is True, "qa:not_ok")
    demand(qa.get("errors") == [], "qa:errors")
    demand(type(qa.get("production_rows")) is int and qa["production_rows"] == 23,
           "qa:production_city_count")
    demand(type(qa.get("exact_city_rows")) is int and qa["exact_city_rows"] == 4,
           "qa:exact_city_count")
    demand(type(qa.get("raion_proxy_rows")) is int and qa["raion_proxy_rows"] == 19,
           "qa:raion_proxy_count")
    ef = qa.get("effective_freshness")
    demand(isinstance(ef, dict), "qa:missing_effective_freshness")
    demand(ef.get("source") == "official UkraineAlarm API regionHistory bridge",
           "qa:not_official_bridge")
    demand(ef.get("fully_continuous") is True, "qa:not_continuous")
    demand(ef.get("fresh") is True and ef.get("warning") is False,
           "qa:incomplete_source_freshness")
    demand(ef.get("status") == "official_api_bridge_fresh",
           "qa:incorrect_source_status")
    demand(set(ef.get("required_rows") or []) == REQUIRED_REGIONS,
           "qa:required_regions_mismatch")
    demand(set(ef.get("covered_rows") or []) == REQUIRED_REGIONS,
           "qa:covered_regions_mismatch")
    demand(ef.get("uncovered_rows") == [], "qa:uncovered_regions")
    qa_checkpoint = timestamp(ef.get("last_successful_fetch_at"),
                              "qa.last_successful_fetch_at", utc_only=True)
    demand(qa_checkpoint == checkpoint, "qa:checkpoint_mismatch")

    if monitor_city_keys is not None:
        demand(set(monitor_city_keys) == EXPECTED_CITIES,
               "monitor:city_config_not_23_cities")

    return {
        "ok": True,
        "schema_version": SUPPORTED_SCHEMA,
        "required_region_count": len(REQUIRED_REGIONS),
        "production_city_count": len(dashboard["cities"]),
        "event_count": len(events),
        "kyiv_count": len(kyiv),
        "sevastopol_count": len(sevastopol["pairs"]),
        "source_checkpoint_utc": checkpoint.isoformat().replace("+00:00", "Z"),
        "reference_clock_utc": now.isoformat().replace("+00:00", "Z"),
        "mode": "cached_bridge",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only fail-closed production source gate")
    parser.add_argument("--bridge-file", type=Path, required=True)
    parser.add_argument("--dashboard-data-file", type=Path, required=True)
    parser.add_argument("--kyiv-alerts-file", type=Path, required=True)
    parser.add_argument("--sevastopol-events-file", type=Path, required=True)
    parser.add_argument("--production-qa-file", type=Path, required=True)
    args = parser.parse_args()
    receipt = validate_cached_source_files(
        bridge_path=args.bridge_file, dashboard_path=args.dashboard_data_file,
        kyiv_alerts_path=args.kyiv_alerts_file,
        sevastopol_events_path=args.sevastopol_events_file,
        qa_path=args.production_qa_file, now=datetime.now(UTC),
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
