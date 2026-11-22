#!/usr/bin/env python3
"""Offline quality gates for 23-city October casualty research: no HTTP or writes.

Covers data shape and anti-duplication invariants; NOT a verification that
candidate fatality numbers or final incident identity are correct.
"""
import csv
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ALLOWED = {
    "kyiv", "kharkiv", "sevastopol", "cherkasy", "zhytomyr",
    "dnipro", "khmelnytskyi", "poltava", "rivne", "sumy",
    "vinnytsia", "kropyvnytskyi", "lviv", "chernihiv", "mykolaiv",
    "lutsk", "uzhhorod", "ivano-frankivsk", "ternopil", "chernivtsi",
    "kherson", "odesa", "zaporizhzhia",
}


def read_file(name):
    with (HERE / name).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def verify():
    base = read_file("baseline_23city_2026_10_coverage.csv")
    cases = read_file("incident_reconciliation_2026_10.csv")
    assert len(base) == 23 and {a["city_slug"] for a in base} == ALLOWED
    assert len(cases) == 13
    assert len({c["incident_key"] for c in cases}) == len(cases)
    assert all(c["city_slug"] in ALLOWED for c in cases)
    assert all(c["attack_date_candidate"].startswith("2026-10-") for c in cases)
    assert all(c["decision"] == "NEEDS_REVIEW" for c in cases)
    assert all(c["automatic_credit"] == "0" for c in cases)
    assert all(c["baseline_monthly_status"] == "OCTOBER_NOT_PUBLISHED_IN_SITE_PROD" for c in cases)
    assert all(c["blocking_reason"] for c in cases)
    assert all(c["published_last_month"] == "2026-09" and
               c["sep2026_coverage_status"] == "PARTIAL_SEPTEMBER" for c in base)
    assert all(c["published_oct2026"] == "NO" and c["oct2026_deaths"] == ""
               and c["oct2026_coverage"] == "UNKNOWN_NOT_ZERO" for c in base)
    assert all(c["oct2026_get_evidence"] in
               {"SOME_SOURCES_NOT_COMPLETE", "NO_SUCCESSFUL_SOURCE"} for c in base)
    assert sum(c["oct2026_get_evidence"] == "SOME_SOURCES_NOT_COMPLETE" for c in base) == 11
    assert sum(c["oct2026_get_evidence"] == "NO_SUCCESSFUL_SOURCE" for c in base) == 12
    assert all(int(c["published_sep2026_deaths"]) >= 0 for c in base)
    assert {c["city_slug"] for c in cases} <= {
        c["city_slug"] for c in base
        if c["oct2026_get_evidence"] == "SOME_SOURCES_NOT_COMPLETE"}
    for c in cases:
        refs = c["capture_source_ids"].split(";") if c["capture_source_ids"] else []
        assert all(ref.startswith("s") and len(ref) == 3 and ref[1:].isdigit()
                   for ref in refs)
        if c["cumulative_deaths_candidate"]:
            assert int(c["cumulative_deaths_candidate"]) >= 0
        # Two source reports for one incident still count as one candidate.
        assert len(refs) == len(set(refs))
    groups = {c["incident_key"]: c for c in cases}
    lutsk = groups["LUTSK-2026-10-14-UAV"]
    assert lutsk["cumulative_deaths_candidate"] == "6"
    assert lutsk["capture_source_ids"] == "s21;s22"
    assert groups["ZAPORIZHZHIA-2026-10-22-AERIAL"]["capture_source_ids"] == "s25;s26"
    kyiv = groups["KYIV-2026-10-08-MORNING-UAV"]
    assert kyiv["cumulative_deaths_candidate"] == "4"
    assert kyiv["capture_source_ids"] == "s10"
    assert "supersedes 3" in kyiv["evidence_summary"]
    # We refuse to produce sums or an exportable final October casualty table.
    counts = Counter(c["decision"] for c in cases)
    return {"city_rows": len(base), "retrieved_city_leads": 11,
            "candidate_incident_groups": len(cases),
            "review_required": counts["NEEDS_REVIEW"],
            "confirmed_for_publishing": 0,
            "automatic_credits": 0, "promotion": "OFF",
            "published_october_values": 0}


if __name__ == "__main__":
    import json
    print("CASUALTY_OCTOBER_OFFLINE_RECONCILIATION_PASS",
          json.dumps(verify(), sort_keys=True))
