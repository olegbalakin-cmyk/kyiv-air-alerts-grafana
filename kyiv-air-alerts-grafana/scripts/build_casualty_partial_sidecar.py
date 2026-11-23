#!/usr/bin/env python3
"""Issue #240: deterministic OFF-by-default casualty partial-month sidecar.

Read ONLY pinned local source inputs; no network, revisions, dashboard or deployment writes.
A sidecar is *not* a credited revision or permission to publish.
"""
import argparse
import csv
import hashlib
import io
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "kyiv-air-alerts-grafana/data"
RESEARCH = ROOT / "research/casualty_publisher_240"
OUTPUT = DATA / "casualty_partial_months.json"
PREFIX = "kyiv-air-alerts-grafana/data/casualties/"
INPUT_BLOBS = {
    PREFIX + "master_20cities_monthly_wide.csv": "f3b7fdf6750e12d7b9af05ffd094bb47aa9ed801",
    PREFIX + "master_20cities_manifest.json": "cdff7c9887dba0662bc44435048aa5449f7485cc",
    PREFIX + "baseline_monthly.csv": "52238c1e72bdba3b06fc0c0469d699f018d8e353",
    PREFIX + "revisions.csv": "8d7a2e2540bf4bf0f8c6227023821390bf82ce13",
    **{
        PREFIX + f"cities/{c}/{c}_air_attack_deaths_monthly.csv": h
        for c, h in {
            "kherson": "5520e34c5d0696a167ed0eea378a8648c8836c49",
            "odesa": "b51a2cd204b3a3c977025e7acd9311ba98e3a317",
            "zaporizhzhia": "1b32d8808069b4499fda35b092fd56f51c64583f",
        }.items()
    },
    **{
        PREFIX + f"cities/{c}/manifest.json": h
        for c, h in {
            "kherson": "8f343b2fb01774ed476910d34489e03fbf190cb5",
            "odesa": "bc9e487f63cf4c67c0c9c86757c3ded04537ee24",
            "zaporizhzhia": "4dcfb6a14949820b4934a100063f549e22799e8b",
        }.items()
    },
    "research/casualty_publisher_240/october_2026_verified_events_frozen.json": "444973fba6295c58c3a6423ff4e872774f273d99",
}
EVENTS = {
    "incident:lutsk:2026-10-14:konjakina-wholesale-drone": ("lutsk", "2026-10-14", 6),
    "incident:poltava:2026-10-17:residential-aerial-strike": ("poltava", "2026-10-17", 1),
    "incident:ivano-frankivsk:2026-10-08:reactive-drone-civilian": ("ivano-frankivsk", "2026-10-08", 1),
    "incident:khmelnytskyi:2026-10-19:residential-aerial-strike": ("khmelnytskyi", "2026-10-19", 3),
}
SUMY_ID = "casualty:sumy:2026-09-20:fpv-double-strike-zarichnyi-apartment-entrance"
SUMY_CANDIDATE = "a25952a45587fdc555fbbb43"


def git_blob_sha(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def read_pinned(path):
    if path not in INPUT_BLOBS:
        raise ValueError("Unpinned input: " + path)
    data = (ROOT / path).read_bytes()
    if git_blob_sha(data) != INPUT_BLOBS[path]:
        raise ValueError("Frozen baseline/evidence SHA drift: " + path)
    return data.decode("utf-8-sig")


def read_csv(path):
    return list(csv.DictReader(io.StringIO(read_pinned(path))))


def checked_count(raw, label):
    if not isinstance(raw, str) or not re.fullmatch(r"0|[1-9][0-9]*", raw):
        raise ValueError("Unknown/negative/invalid numeric count at " + label)
    return int(raw)


def baseline_series():
    manifest = json.loads(read_pinned(PREFIX + "master_20cities_manifest.json"))
    master_cities = [r["slug"] for r in manifest["cities"]]
    if len(master_cities) != 20 or len(set(master_cities)) != 20 or "sumy" not in master_cities:
        raise ValueError("Master city roster mismatch")
    series = {slug: {} for slug in master_cities}
    for row in read_csv(PREFIX + "master_20cities_monthly_wide.csv"):
        month = row["month"]
        if month in series[master_cities[0]]:
            raise ValueError("Duplicate baseline month")
        for slug in master_cities:
            series[slug][month] = checked_count(row.get(slug), f"{slug}/{month}")
    if any(sorted(rows)[-1] != "2026-09" for rows in series.values()):
        raise ValueError("Unexpected master cutoff")
    kyiv = read_csv(PREFIX + "baseline_monthly.csv")
    expected_kyiv = {r["month"]: checked_count(r["deaths"], r["month"]) for r in kyiv}
    if len(expected_kyiv) != len(kyiv) or expected_kyiv != series["kyiv"] or kyiv[-1]["coverage_through"] != "2026-09-15":
        raise ValueError("Kyiv audited/master baseline mismatch")
    cutoff = {slug: "2026-09-18" for slug in master_cities}
    cutoff["kyiv"] = "2026-09-15"
    for city in ("kherson", "odesa", "zaporizhzhia"):
        mf = json.loads(read_pinned(PREFIX + f"cities/{city}/manifest.json"))
        if mf["city_slug"] != city or mf.get("current_month_partial") is not True:
            raise ValueError("City manifest mismatch: " + city)
        rows = read_csv(PREFIX + f"cities/{city}/{city}_air_attack_deaths_monthly.csv")
        entry = {}
        for row in rows:
            month = row["month"]
            if month in entry:
                raise ValueError("Duplicate city month")
            entry[month] = checked_count(row["deaths_confirmed"], city + month)
        if sorted(entry) != sorted(series["kyiv"]):
            raise ValueError("Invalid city month coverage")
        if sum(entry.values()) != mf["confirmed_deaths"]:
            raise ValueError("City lifetime total mismatch")
        series[city] = entry
        cutoff[city] = mf["validated_through"]
    if len(series) != 23:
        raise ValueError("23-city roster mismatch")
    # One existing, manually accepted Sumy September row. Reconcile exactly once,
    # and do NOT place this increment in October or add it a second time.
    revisions = read_csv(PREFIX + "revisions.csv")
    if len(revisions) != 1:
        raise ValueError("Unexpected confirmed revision rows")
    row = revisions[0]
    if not (
        row["record_id"] == SUMY_ID and row["city_key"] == "sumy"
        and row["attack_date"] == "2026-09-20" and row["deaths_delta"] == "1"
        and row["status"] == "confirmed" and row["candidate_ids"] == SUMY_CANDIDATE
        and row["observed_at"] == "2026-10-09T11:11:26+03:00"
    ):
        raise ValueError("Pinned Sumy Sep 20 revision drift")
    # Actual existing generator overlays +1; sidecar mirrors the effective
    # historical value instead of introducing any new credit.
    series["sumy"]["2026-09"] += 1
    cutoff["sumy"] = "2026-09-18 + pinned 2026-09-20 confirmed revision"
    return series, cutoff


def reviewed_events():
    obj = json.loads(read_pinned(
        "research/casualty_publisher_240/october_2026_verified_events_frozen.json"
    ))
    events = obj.get("events")
    if not isinstance(events, list) or len(events) != 4:
        raise ValueError("Exact four reviewed events required")
    found = {}
    for event in events:
        incident_id = event.get("incident_id")
        if incident_id in found or incident_id not in EVENTS:
            raise ValueError("New, duplicate or unallowlisted incident identity")
        city, attack_date, count = EVENTS[incident_id]
        if (event.get("city_slug"), event.get("attack_date"), event.get("civilian_deaths_cumulative")) != (city, attack_date, count):
            raise ValueError("Incident count/city/date changed")
        if event.get("victim_scope") != "civilians_killed_inside_city" or not str(event.get("weapon_class", "")).startswith("aerial_"):
            raise ValueError("Military, oblast, ground-fire or unscoped incident")
        sources = event.get("source_updates")
        if not isinstance(sources, list) or len(sources) < 2 or not all(
            isinstance(s.get("url"), str) and s["url"].startswith("https://")
            and s.get("published_date") and s.get("publisher") for s in sources
        ):
            raise ValueError("Missing source provenance")
        found[incident_id] = event
    if set(found) != set(EVENTS):
        raise ValueError("Incident whitelist incomplete")
    return found


def build():
    series, cutoffs = baseline_series()
    found = reviewed_events()
    per_city = {}
    for incident_id, (slug, _, deaths) in EVENTS.items():
        if slug in per_city:
            raise ValueError("Duplicate city lower-bound assignment requires review")
        event = found[incident_id]
        per_city[slug] = {
            "incident_id": incident_id, "count": deaths,
            "sources": [s["url"] for s in event["source_updates"]],
        }
    rows = {}
    for city in sorted(series):
        sep = series[city]["2026-09"]
        evidence = per_city.get(city)
        rows[city] = {
            "2026-09": {
                "status": "partial_baseline", "confirmed_baseline_deaths": sep,
                "confirmed_event_lower_bound": None, "monthly_exact_total": None,
                "is_complete": False, "coverage_through": cutoffs[city],
                "last_verified_at": None,
                "provenance": {
                    "type": "frozen_site_prod_baseline_plus_pinned_suma_revision",
                    "baseline_ref": "site-prod@f7e0681ca6aa98405638dae7a63c884f4ed55d20",
                    "source_git_blob_shas": {p: sha for p, sha in INPUT_BLOBS.items() if p.startswith(PREFIX)},
                },
            },
            "2026-10": {
                "status": "verified_incident_lower_bound" if evidence else "unknown",
                "confirmed_baseline_deaths": None,
                "confirmed_event_lower_bound": evidence["count"] if evidence else None,
                "monthly_exact_total": None, "is_complete": False,
                "last_verified_at": "2026-11-22" if evidence else None,
                "provenance": (
                    {"incident_ids": [evidence["incident_id"]], "source_urls": evidence["sources"],
                     "research_ref": "PR #236@270702ccc4a76d81ee8cc5b9cf73059fd19df025",
                     "research_git_blob_sha": INPUT_BLOBS["research/casualty_publisher_240/october_2026_verified_events_frozen.json"]}
                    if evidence else None
                ),
            },
        }
    assert len(rows) == 23
    assert sum(r["2026-10"]["confirmed_event_lower_bound"] is None for r in rows.values()) == 19
    assert sum(r["2026-10"]["confirmed_event_lower_bound"] or 0 for r in rows.values()) == 11
    return {
        "schema": "casualty-partial-months-v1",
        "source": "canonical site-prod Git JSON companion; no Netlify deploy per data update",
        "canonical_data_url": "https://raw.githubusercontent.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/site-prod/kyiv-air-alerts-grafana/data/casualty_partial_months.json",
        "baseline_ref": "site-prod@f7e0681ca6aa98405638dae7a63c884f4ed55d20",
        "baseline_sha": INPUT_BLOBS[PREFIX + "master_20cities_monthly_wide.csv"],
        "source_frozen_git_blob_shas": INPUT_BLOBS,
        "publication_allowed": False,
        "promotion": "OFF", "is_complete": False,
        "contains_exact_monthly_totals": False,
        "last_verified_at": "2026-11-22",
        "latest_exact_month": "2026-08",
        "year_2026_policy": "Preserve existing year-to-date exact-series semantics; do not add October lower bounds; label January-September as provisional",
        "published_monthly_overwrite": False,
        "cities": rows,
    }


def render(payload):
    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--check", action="store_true", help="Check frozen artifact without writing")
    args = parser.parse_args()
    # No publication toggle exists. All modes remain OFF and no HTTP is used.
    raw = render(build())
    if args.check:
        if args.output.read_bytes() != raw:
            raise SystemExit("SIDECAR_DRIFT: frozen data mismatch")
        print("CASUALTY_240_SIDECAR_CHECK_PASS 23 cities Sep partial Oct 4/19 OFF")
    else:
        args.output.write_bytes(raw)
        print("CASUALTY_240_SIDECAR_BUILT_OFFLINE_NO_PUBLICATION")


if __name__ == "__main__":
    main()
