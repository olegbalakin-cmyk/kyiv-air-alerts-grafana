#!/usr/bin/env python3
"""Work H: rebase *actual* Work F/D generator display onto CURRENT site-prod JSON.

This is an offline, fail-closed, single-month adapter. No invented casualties,
no changes to checked-out branches, live revisions, source queues or publishers.
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
from pathlib import Path

CITY = "zaporizhzhia"
MONTH = "2026-10"
GENERATOR_MINIMUM = 23


def require(condition, message):
    if not condition:
        raise RuntimeError("CURRENT_FRONTEND_BLOCKED:" + message)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stable(obj):
    return hashlib.sha256(json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")).hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser()
    for name in ("historical_dashboard", "current_dashboard", "workd_qualified",
                 "workd_bridge", "workf_probe", "current_generator",
                 "current_revisions", "output", "proof"):
        parser.add_argument("--" + name.replace("_", "-"), required=True, type=Path)
    a = parser.parse_args()
    sources = [getattr(a, x).resolve() for x in (
        "historical_dashboard", "current_dashboard", "workd_qualified",
        "workd_bridge", "workf_probe", "current_generator", "current_revisions")]
    require(all(p.is_file() for p in sources), "MISSING_IMMUTABLE_SOURCE")
    output, proof_file = a.output.resolve(), a.proof.resolve()
    require(output != proof_file and all(
        p not in sources and "/tmp/" in str(p) and not p.exists()
        for p in (output, proof_file)), "OUTPUT_MUST_BE_NEW_SCRATCH_FILE")
    initial_sha = {str(p): digest(p) for p in sources}
    historical, current, qualified = (load(p) for p in sources[:3])
    bridge, probe = (load(p) for p in sources[3:5])
    require(bridge.get("decision") == "REAL_GENERATOR_TO_INCOMPLETE_DATA_PASS"
            and bridge.get("publication_allowed") is False
            and bridge.get("generator_numeric_month") == GENERATOR_MINIMUM,
            "WORKD_NOT_ACTUAL_GENERATOR_PROOF")
    require(bridge.get("source_dashboard_sha256") == digest(sources[0]) and
            bridge.get("generated_dashboard_sha256") == digest(sources[2]),
            "WORKD_SOURCE_HASH_DRIFT")
    require(bridge.get("generator_sha256") == digest(sources[5]) and
            bridge.get("generator_revisions_sha256") == digest(sources[6]),
            "CURRENT_GENERATOR_OR_REVISIONS_DRIFT")
    require(probe.get("status") == "PASS" and
            probe.get("workc_protected_review_promote") is True and
            probe.get("new_delta") == GENERATOR_MINIMUM and
            probe.get("publication_allowed") is False,
            "WORKF_PROMOTED_PROBE_MISSING")
    with sources[6].open(newline="", encoding="utf-8-sig") as inp:
        revisions = list(csv.DictReader(inp))
    require(len(revisions) == 1 and revisions[0]["city_key"] == "sumy"
            and revisions[0]["deaths_delta"] == "1",
            "ORIGINAL_SUMY_PLUS_ONE_LOST")
    require(len(historical.get("cities", {})) == 23 and
            len(current.get("cities", {})) == 23 and
            len(current.get("casualties_by_city", {})) == 23 and
            set(current["cities"]) == set(historical["cities"]),
            "CURRENT_ALERT_CITY_SET_CHANGED")
    require(set(current["casualties_by_city"]) ==
            set(historical["casualties_by_city"]),
            "CURRENT_CASUALTY_CITY_SET_CHANGED")
    require(digest(sources[0]) != digest(sources[1]),
            "CURRENT_DASHBOARD_NOT_NEWER_SNAPSHOT")

    # Work D may have changed ONLY Zaporizhzhia's added October row.
    for key in historical:
        if key != "casualties_by_city":
            require(qualified.get(key) == historical[key],
                    "WORKD_CHANGED_OTHER_TOP_LEVEL_DATA:" + key)
    require(set(qualified["casualties_by_city"]) ==
            set(historical["casualties_by_city"]), "WORKD_CITY_KEYS_DRIFT")
    for city, data in historical["casualties_by_city"].items():
        if city != CITY:
            require(qualified["casualties_by_city"][city] == data,
                    "WORKD_CHANGED_UNRELATED_CITY:" + city)
    old_zap = historical["casualties_by_city"][CITY]
    workd_zap = qualified["casualties_by_city"][CITY]
    current_zap = current["casualties_by_city"][CITY]
    # The real generator adds source metadata to Zaporizhzhia's city object.
    # Work D's bridge already validates that generator and its non-target scope;
    # import ONLY its single October row, never that metadata.
    old_months = old_zap["monthly"]
    workd_months = workd_zap["monthly"]
    newly_qualified = [x for x in workd_months if x.get("month") == MONTH]
    require(len(newly_qualified) == 1 and
            [x for x in workd_months if x.get("month") != MONTH] == old_months,
            "WORKD_ADDED_MORE_THAN_ONE_GENERATED_ROW")
    row = newly_qualified[0]
    require(row.get("deaths") is None and
            row.get("coverage_status") == "INCOMPLETE" and
            row.get("confirmed_minimum") == GENERATOR_MINIMUM and
            row.get("complete_total") is None and
            row.get("revision_delta") == GENERATOR_MINIMUM and
            row.get("baseline_deaths") == 0,
            "LOWER_BOUND_ROW_INVALID")
    require(not any(x.get("month") == MONTH for x in current_zap["monthly"]),
            "CURRENT_ALREADY_CONTAINS_OCTOBER_DO_NOT_OVERWRITE")
    require(all(x.get("month") != MONTH for x in old_months),
            "HISTORICAL_ALREADY_CONTAINS_OCTOBER")
    # Preserve all other months and all metadata from CURRENT JSON.
    merged = copy.deepcopy(current)
    merged["casualties_by_city"][CITY]["monthly"] = sorted(
        [*copy.deepcopy(current_zap["monthly"]), copy.deepcopy(row)],
        key=lambda x: x["month"])
    require(len(merged["cities"]) == 23 and
            merged["cities"] == current["cities"],
            "ALERT_23_CITY_DATA_CHANGED")
    require(all(merged["casualties_by_city"][k] ==
                current["casualties_by_city"][k]
                for k in current["casualties_by_city"] if k != CITY),
            "UNRELATED_CASUALTY_SERIES_CHANGED")
    require({k: v for k, v in merged.items() if k != "casualties_by_city"} ==
            {k: v for k, v in current.items() if k != "casualties_by_city"},
            "CURRENT_DASHBOARD_NON_CASUALTY_KEYS_CHANGED")
    require([r for r in merged["casualties_by_city"][CITY]["monthly"]
             if r["month"] != MONTH] == current_zap["monthly"],
            "OTHER_ZAP_MONTHS_CHANGED")
    output.parent.mkdir(parents=True, exist_ok=True)
    proof_file.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    report = {
        "verdict": "CURRENT_DASHBOARD_REBASE_PASS",
        "source": "Work F original-text to Work C actual scratch PROMOTE, Work D",
        "site_prod_reference": "f0cfcbc862ca3dbf1b853e72de07ffcf6042856f",
        "city_key": CITY, "month": MONTH,
        "coverage_status": "INCOMPLETE", "confirmed_minimum": 23,
        "complete_total": None, "original_revision_count": 1,
        "repeat_promote_increment": 0, "sumy_plus_one_preserved": True,
        "current_alert_cities": 23, "unmodified_casualty_cities": 22,
        "current_alert_series_sha256": stable(current["cities"]),
        "rebase_alert_series_sha256": stable(merged["cities"]),
        "current_other_casualties_sha256": stable(
            {k:v for k,v in current["casualties_by_city"].items() if k != CITY}),
        "rebase_other_casualties_sha256": stable(
            {k:v for k,v in merged["casualties_by_city"].items() if k != CITY}),
        "current_dashboard_sha256": digest(sources[1]),
        "workd_qualified_sha256": digest(sources[2]),
        "rebase_dashboard_sha256": digest(output),
        "sources_sha256": initial_sha,
        "external_publisher_http": 0,
        "publication_allowed": False,
        "production_data_changed": False,
    }
    require(initial_sha == {str(p): digest(p) for p in sources},
            "INPUT_CHANGED_DURING_REBASE")
    proof_file.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True,
                                     indent=2) + "\n", encoding="utf-8")
    print("CURRENT_DASHBOARD_REBASE_PASS current site-prod data preserved, "
          "Work F/D derived October >=23 only; 23 alert cities / 22 other "
          "casualty cities / Sumy +1 intact; NO PUBLISH")


if __name__ == "__main__":
    main()
