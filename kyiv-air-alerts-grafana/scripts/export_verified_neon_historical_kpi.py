#!/usr/bin/env python3
"""Export only the already-verified 23-city Neon→Git historical KPI.

The production reader built this index in the same run as dashboard_data.json.
Do not reconstruct it from overlapping upstream feeds (DST would diverge).
No HTTP, Neon query, publication, source fetch, or fallback.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


class IndexRejected(ValueError):
    pass


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise IndexRejected("NEON_HISTORICAL_INDEX_" + reason)


def verified_index(source: dict) -> dict:
    keys = source.get("multicity_meta", {}).get("production_city_keys")
    index = source.get("historical_daily_kpi")
    require(isinstance(keys, list) and len(keys) == 23 and len(set(keys)) == 23,
            "CITY_KEYS")
    require(isinstance(index, dict) and index.get("schema") ==
            "verified-historical-daily-start-counts-v1", "SCHEMA")
    meta = index.get("meta", {})
    require(meta.get("expected_cities") == 23 and meta.get("verified_count") == 23,
            "COUNT")
    require(meta.get("timezone") == "Europe/Kyiv", "TIMEZONE")
    require(str(meta.get("source_ref", "")).startswith("neon:"), "SOURCE_REF")
    generation = source.get("meta", {}).get("generated_at")
    require(isinstance(generation, str) and generation and
            generation == meta.get("source_dashboard_generated_at") ==
            meta.get("generated_at"), "GENERATION")
    cities = index.get("cities", {})
    require(isinstance(cities, dict) and set(cities) == set(keys) ==
            set(source.get("cities", {})), "CITY_MEMBERSHIP")
    require(set(meta.get("verified_cities", [])) == set(keys), "VERIFIED_SET")
    for key in keys:
        city = cities[key]
        require(city.get("status") == "verified" and
                isinstance(city.get("counts"), list) and
                len(city["counts"]) > 0 and
                city.get("checked_complete_months", 0) > 0 and
                city.get("checked_recent_days", 0) > 0,
                "CITY_NOT_VERIFIED:" + key)
        require(all(type(v) is int and v >= 0 for v in city["counts"]),
                "INVALID_DAILY_COUNT:" + key)
    return index


def export(source: Path, output: Path) -> None:
    require(not output.exists(), "OUTPUT_ALREADY_EXISTS")
    dashboard = json.loads(source.read_text(encoding="utf-8"))
    index = verified_index(dashboard)
    output.write_text(json.dumps(index, ensure_ascii=False,
                                 separators=(",", ":")) + "\n", encoding="utf-8")
    readback = json.loads(output.read_text(encoding="utf-8"))
    require(readback == index, "OUTPUT_DRIFT")
    print("VERIFIED_SAME_GENERATION_NEON_HISTORICAL_INDEX_23_OF_23")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--dashboard", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    export(args.dashboard, args.output)


if __name__ == "__main__":
    main()
