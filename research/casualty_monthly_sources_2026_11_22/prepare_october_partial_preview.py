#!/usr/bin/env python3
"""Offline-only October preview from four evidenced civilian incident groups.

Never writes site data, never imports generator, never reaches media, never
schedules or credits casualties. The preview has lower bounds, NOT exact months.
"""
import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from datetime import date

ROOT = Path(__file__).resolve().parent
LEDGER = ROOT / "october_2026_verified_event_candidates.json"
COVERAGE = ROOT / "baseline_23city_2026_10_coverage.csv"
MONTH = "2026-10"
SITES = {
    "lutsk": 6,
    "poltava": 1,
    "ivano-frankivsk": 1,
    "khmelnytskyi": 3,
}
EXPECTED_TOTAL = 11

def build():
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    with COVERAGE.open(encoding="utf-8", newline="") as stream:
        coverage = list(csv.DictReader(stream))
    events = ledger["events"]
    ids = [e["incident_id"] for e in events]
    if len(events) != 4 or len(ids) != len(set(ids)):
        raise AssertionError("Four distinct incident IDs required")
    if len(coverage) != 23 or len({r["city_slug"] for r in coverage}) != 23:
        raise AssertionError("All 23 city slots required")
    if any(r["published_oct2026"] != "NO" or
           r["oct2026_deaths"] or r["oct2026_coverage"] != "UNKNOWN_NOT_ZERO"
           for r in coverage):
        raise AssertionError("No October baseline is published")
    if ledger["promotion"] != "OFF" or ledger["publication_approval"] is not False:
        raise AssertionError("Promotion must remain OFF")
    by_city = Counter()
    for e in events:
        if not e["incident_id"].startswith("incident:"):
            raise AssertionError("Invalid incident")
        if e["weapon_class"] not in {"aerial_uav", "aerial_cruise_missile", "aerial_attack"}:
            raise AssertionError("Incompatible weapon classification")
        if e["victim_scope"] != "civilians_killed_inside_city":
            raise AssertionError("Civilians in city only")
        if e["attack_date"][:7] != MONTH:
            raise AssertionError("Incorrect attack attribution month")
        date.fromisoformat(e["attack_date"])
        count = e["civilian_deaths_cumulative"]
        if type(count) is not int or count < 1:
            raise AssertionError("Invalid cumulative count")
        if not isinstance(e["source_updates"], list) or len(e["source_updates"]) < 2:
            raise AssertionError("Independent evidence required")
        by_city[e["city_slug"]] += count
    if dict(by_city) != SITES or sum(by_city.values()) != EXPECTED_TOTAL:
        raise AssertionError("Candidate subtotal mismatch")
    lutsk = next(x for x in events if x["city_slug"] == "lutsk")
    assert len(lutsk["source_updates"]) >= 2
    assert len([e for e in events if e["city_slug"] == "lutsk"]) == 1
    khm = next(x for x in events if x["city_slug"] == "khmelnytskyi")
    assert khm["initial_reported_deaths"] == 2 and khm["later_additional_deaths"] == 1
    # Kyiv Oct 7/8 has overlapping media updates: excluded until incident
    # chronology can be separated; do not accidentally add as a fifth case.
    if any(e["city_slug"] == "kyiv" for e in events):
        raise AssertionError("Kyiv event chronology not released")
    city_records = []
    for row in coverage:
        city = row["city_slug"]
        known = by_city.get(city)
        city_records.append({
            "city_slug": city,
            "month": MONTH,
            "confirmed_event_lower_bound": known if known is not None else None,
            "event_count_verified": sum(e["city_slug"] == city for e in events),
            "monthly_exact_total": None,
            "published_monthly_total": None,
            "coverage": "PARTIAL_VERIFIED_EVENTS" if known is not None else "NO_VERIFIED_EVENTS_UNKNOWN",
            "is_final": False,
            "ready_for_monthly_data_publishing": False,
        })
    return {
        "schema": "casualty-october-partial-review-v1",
        "month": MONTH,
        "measurement": ledger["measurement"],
        "display_policy": "PREVIEW_ONLY_NO_SITE_MUTATION",
        "promotion": "OFF",
        "is_month_complete": False,
        "no_automatic_credits": True,
        "no_production_changes": True,
        "confirmed_event_groups": 4,
        "known_civilian_fatalities_from_these_events": EXPECTED_TOTAL,
        "NOT_an_October_23city_monthly_total": True,
        "cities": city_records,
        "incident_ids": ids
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--validate", action="store_true")
    p.add_argument("--write-preview", type=Path)
    args=p.parse_args()
    preview=build()
    # A checked-in static preview must match this deterministic generator.
    frozen = ROOT / "october_2026_partial_preview.json"
    if not frozen.is_file():
        raise AssertionError("Missing staged preview")
    actual = json.loads(frozen.read_text(encoding="utf-8"))
    if actual != preview:
        raise AssertionError("Frozen October preview differs from validated ledger")
    raw=json.dumps(preview,sort_keys=True,ensure_ascii=False,indent=2)+"\n"
    if args.write_preview:
        if args.write_preview.resolve().is_relative_to(Path.cwd().resolve()):
            raise SystemExit("STOP: no writes into git repository checkout")
        args.write_preview.write_text(raw,encoding="utf-8")
    print("OCTOBER_FOUR_EVENTS_OFFLINE_PASS 4 11 23 PROMOTE_OFF")
    if not args.write_preview:
        print(raw)
if __name__=="__main__":
    main()
