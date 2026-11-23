#!/usr/bin/env python3
"""Fail-closed stdlib-only offline tests for Issue #238. No network or writes."""
import csv
import io
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
COVERAGE = HERE / "september_2026_23city_coverage.csv"
LEDGER = HERE / "september_2026_incident_candidates.json"
WITNESS = HERE / "september_2026_source_witness.json"
EXPECTED_SHA = "f7e0681ca6aa98405638dae7a63c884f4ed55d20"
EXPECTED_SUMY_ID = "casualty:sumy:2026-09-20:fpv-double-strike-zarichnyi-apartment-entrance"


def validate(coverage: str, ledger: dict, witness: dict) -> dict:
    rows = list(csv.DictReader(io.StringIO(coverage)))
    assert len(rows) == 23, "must cover exactly 23 cities"
    assert len({r["city_slug"] for r in rows}) == 23, "duplicate city row"
    assert all(r["month"] == "2026-09" for r in rows)
    assert all(r["baseline_status"] == "PARTIAL" for r in rows)
    assert all(r["month_exact_total"] == "" for r in rows)
    assert all(r["can_publish_new_value"] == "false" for r in rows)
    assert all(r["geographic_scope"] == "CITY_ONLY_CIVILIAN_AERIAL" for r in rows)
    assert all(r["coverage_unknown"] in ("true", "false") for r in rows)
    assert all(r["coverage_unknown"] == ("false" if r["validated_through"] else "true") for r in rows)
    assert sum(bool(r["validated_through"]) for r in rows) == 4
    expected_dates = {"kyiv": "2026-09-15", "kherson": "2026-09-17",
                      "odesa": "2026-09-18", "zaporizhzhia": "2026-09-18"}
    for r in rows:
        assert r["validated_through"] == expected_dates.get(r["city_slug"], ""), r["city_slug"]
    assert all(r["confirmed_known_minimum"] == "" for r in rows if int(r["published_sep2026_baseline"]) == 0)
    assert all(r["confirmed_minimum_basis"] == "UNKNOWN_NOT_ZERO"
               for r in rows if int(r["published_sep2026_baseline"]) == 0)
    assert sum(int(r["published_sep2026_baseline"]) for r in rows) == 55
    by_city = {r["city_slug"]: r for r in rows}
    assert int(by_city["kyiv"]["published_sep2026_baseline"]) == 18
    assert int(by_city["sumy"]["published_sep2026_baseline"]) == 3
    assert int(by_city["sumy"]["confirmed_known_minimum"]) == 4
    assert int(by_city["kherson"]["published_sep2026_baseline"]) == 12
    assert int(by_city["odesa"]["published_sep2026_baseline"]) == 3
    assert int(by_city["zaporizhzhia"]["published_sep2026_baseline"]) == 4
    assert int(by_city["kyiv"]["needs_review_count"]) == 53
    assert int(by_city["kyiv"]["post_cutoff_source_cards"]) == 48
    assert int(by_city["kyiv"]["held_uncredited_candidate_minimum"]) == 17
    assert all(r["post_cutoff_source_cards"] == "" for r in rows if r["city_slug"] != "kyiv")
    assert all(r["needs_review_count"] == "" for r in rows
               if r["city_slug"] not in ("kyiv", "kherson", "odesa", "zaporizhzhia"))
    assert witness["site_prod_sha"] == EXPECTED_SHA == ledger["site_prod_sha"]
    assert witness["promotion"] == ledger["promotion"] == "OFF"
    assert ledger["publication_approval"] is False and ledger["no_new_publisher_gets"] is True
    assert witness["revision_ledger"]["sumy_record_id"] == EXPECTED_SUMY_ID
    assert witness["revision_ledger"]["rows"] == 1
    assert ledger["published_partial_baseline"]["previously_published_confirmed_minimum"] == 56
    assert ledger["published_partial_baseline"]["exact_monthly_total"] is None
    assert ledger["published_partial_baseline"]["all_23_partial"] is True
    assert ledger["summary"]["automatic_credits"] == 0
    assert ledger["summary"]["new_events_publication_ready"] == 0
    assert ledger["summary"]["all_cities_month_exact_total_unknown"] is True
    assert witness["prior_run"]["approved_get_budget_consumed"] == 27
    assert witness["prior_run"]["artifact_id"] == 14773425588
    assert witness["october_offline_run"]["status"] == "success"
    confirmed = ledger["already_credited"]
    assert len(confirmed) == 1 and confirmed[0]["incident_id"] == EXPECTED_SUMY_ID
    assert confirmed[0]["credited_delta"] == 1 and confirmed[0]["new_delta_allowed"] == 0
    assert any(e["reason"] == "SUMY_ALREADY_CREDITED" for e in ledger["exclusions"])
    assert any(e["reason"] == "GLEVAKHA_FASTIV_OUTSIDE_KYIV_CITY" for e in ledger["exclusions"])
    assert any(e["reason"] == "VYSHHOROD_OUTSIDE_KYIV_CITY" for e in ledger["exclusions"])
    events = ledger["candidates"]
    assert len(events) == 6 and len({e["incident_id"] for e in events}) == 6
    assert sum(e["reported_cumulative_deaths"] for e in events) == 17
    assert set(e["attack_date"] for e in events) == {
        "2026-09-23", "2026-09-24", "2026-09-25",
        "2026-09-27", "2026-09-28", "2026-09-30"}
    for e in events:
        assert e["city_slug"] == "kyiv" and e["location_boundary"] == "KYIV_CITY_ADMIN"
        assert e["attack_date"] > expected_dates["kyiv"]
        assert e["count_kind"] == "cumulative"
        assert e["civilian_scope"] == "civilian_only" and e["weapon_scope"].startswith("aerial_")
        assert e["proposed_delta"] is None and e["needs_review"] is True
        assert e["automatic_credit"] is False
        assert e["publication_ready"] is False
        assert e["baseline_credit_check"]["site_prod_sha"] == EXPECTED_SHA
        assert e["baseline_credit_check"]["already_credited_kyiv_revision_count"] == 0
        assert e["identity_proof_status"] == "PENDING"
        assert len(e["source_evidence"]) >= 2
        assert all(x["url"].startswith("https://") and len(x["captured_sha256"]) == 64
                   for x in e["source_evidence"])
    assert ledger["publication_decision"].startswith("EXISTING_PARTIAL_BASELINE_ONLY")
    return {"status": "PASS", "cities": len(rows), "partial": 23,
            "known_cutoffs": 4, "unknown_cutoffs": 19,
            "baseline": 55, "already_credited_sumy": 1,
            "candidate_groups_review_only": 6, "candidate_reported_counts_not_credited": 17,
            "new_credits": 0, "publisher_gets": 0}


def self_test(coverage: str, ledger: dict, witness: dict) -> None:
    import copy
    validate(coverage, ledger, witness)
    bad = coverage.replace("PARTIAL", "COMPLETE", 1)
    try:
        validate(bad, ledger, witness)
    except AssertionError:
        pass
    else:
        raise AssertionError("Must reject completed September")
    bad_ledger = copy.deepcopy(ledger)
    bad_ledger["already_credited"][0]["new_delta_allowed"] = 1
    try:
        validate(coverage, bad_ledger, witness)
    except AssertionError:
        pass
    else:
        raise AssertionError("Must reject Sumy duplicate credit")
    bad_ledger = copy.deepcopy(ledger)
    bad_ledger["candidates"][0]["publication_ready"] = True
    try:
        validate(coverage, bad_ledger, witness)
    except AssertionError:
        pass
    else:
        raise AssertionError("Must reject accidental promotion")
    bad_ledger = copy.deepcopy(ledger)
    bad_ledger["candidates"][0]["count_kind"] = "delta"
    try:
        validate(coverage, bad_ledger, witness)
    except AssertionError:
        pass
    else:
        raise AssertionError("Must reject cumulative->delta confusion")
    bad_coverage = coverage.replace("UNKNOWN_NOT_ZERO", "0", 1)
    try:
        validate(bad_coverage, ledger, witness)
    except AssertionError:
        pass
    else:
        raise AssertionError("Must reject unknown interpreted as zero")


if __name__ == "__main__":
    coverage = COVERAGE.read_text(encoding="utf-8")
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    witness = json.loads(WITNESS.read_text(encoding="utf-8"))
    outcome = validate(coverage, ledger, witness)
    self_test(coverage, ledger, witness)
    print(json.dumps(outcome, ensure_ascii=False, sort_keys=True))
