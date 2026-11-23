#!/usr/bin/env python3
"""Issue #246: stdlib-only offline fail-closed incident credit audit. No HTTP or writes."""
import copy
import csv
import hashlib
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
J = ROOT / "kyiv_2026_09_incident_ledger.json"
C = ROOT / "kyiv_2026_09_credit_decisions.csv"
PINS = {
    "site_prod_sha": "f7e0681ca6aa98405638dae7a63c884f4ed55d20",
    "main_sha": "b35ca5c8d189a011c1b7158275f189a195192890",
    "pr243_head": "f8112362beaf6a9a8015c83c86dd8b131df5236c",
    "review_queue_blob": "8ae078bc60f2c27838b61e9aebf90b7286e0dd55",
    "kyiv_baseline_blob": "52238c1e72bdba3b06fc0c0469d699f018d8e353",
    "confirmed_revisions_blob": "8d7a2e2540bf4bf0f8c6227023821390bf82ce13",
    "source_candidates_blob": "0f1b252a458ad69465211f33c422336136de0903",
}
EXPECTED_DATES = {"2026-09-23": 2, "2026-09-24": 2, "2026-09-25": 7,
                  "2026-09-27": 1, "2026-09-28": 2, "2026-09-30": 3}
CATEGORIES = {"SAFE NEW CREDIT", "NEEDS_REVIEW", "EXCLUDED_AS_DUPLICATE_OR_OUT_OF_CITY"}


def validate(j, csv_text):
    assert j["schema"] == "casualty-kyiv-sept2026-reconciled-incidents-v1"
    assert j["issue"] == 246 and j["coordinate_release_issue"] == 245
    assert j["research_only"] is True and j["promotion"] == "OFF"
    assert j["publication_allowed"] is False and j["automatic_credits"] == 0
    assert j["publisher_gets_this_issue"] == 0
    assert all(j["pins"][k] == v for k, v in PINS.items())
    b = j["baseline"]
    assert b["month"] == "2026-09" and b["city"] == "kyiv"
    assert b["original_published_partial"] == 18
    assert b["coverage_through_inclusive"] == "2026-09-15"
    assert b["confirmed_kyiv_revision_rows_at_pin"] == 0
    assert b["exact_month_total"] is None
    src = j["source_cards"]
    assert len(src) >= 20 and len(set(x["url"] for x in src.values())) == len(src)
    for key, x in src.items():
        assert key == "q" + str(x["queue_index"])
        assert x["url"].startswith("https://")
        assert len(x["captured_sha256"]) == 64
        int(x["captured_sha256"], 16)
        assert x["title"] and x["original_excerpt"]
    groups = j["date_groups"]
    assert {x["date"]: x["reported_citywide_final"] for x in groups} == EXPECTED_DATES
    assert sum(g["reported_citywide_final"] for g in groups) == 17
    assert sum(g["safe_new_delta"] for g in groups) == 15
    assert sum(g["held_unresolved"] for g in groups) == 2
    decisions = j["decisions"]
    ids = [d["id"] for d in decisions]
    assert len(ids) == len(set(ids))
    assert len(decisions) == 18
    assert {d["category"] for d in decisions} == CATEGORIES
    rows = list(csv.DictReader(io.StringIO(csv_text)))
    assert len(rows) == len(decisions)
    for d, r in zip(decisions, rows):
        assert d["city"] == r["city"] == "kyiv"
        assert d["attack_date"] == r["attack_date"]
        assert d["id"] == r["id"] and d["category"] == r["category"]
        assert d["category"] in CATEGORIES
        assert d["automatic_credit"] is False
        assert d["source_refs"] == r["source_refs"].split("|") if d["source_refs"] else r["source_refs"] == ""
        assert d["victim_slots"] == (r["victim_slots"].split("|") if r["victim_slots"] else [])
        assert int(r["verified_new_delta"]) == d["verified_new_delta"]
        assert all(ref in src for ref in d["source_refs"])
        assert d["attack_date"] <= "2026-09-30"
        if d["category"] == "SAFE NEW CREDIT":
            assert d["attack_date"] > b["coverage_through_inclusive"]
            assert d["city_boundary"] == "KYIV_CITY_ADMIN"
            assert d["baseline_credited"] == 0
            assert d["baseline_credited_proof"] == b["baseline_proof"]
            assert d["count_kind"] == "DISTINCT_BOUNDED_IDENTITIES"
            assert d["verified_new_delta"] == len(d["victim_slots"]) > 0
            assert len(d["source_refs"]) >= 2
            assert d["civilian_aerial_evidence"].startswith(("Russian UAV", "Night ballistic", "Night missile/UAV", "Morning UAV"))
        else:
            assert d["verified_new_delta"] == 0
            assert not d["victim_slots"]
            assert d["baseline_credited"] is None
        if d["category"] == "NEEDS_REVIEW":
            assert d["unresolved_count"] > 0
            assert d["baseline_credited_proof"] == "UNPROVEN_EVENT_VICTIM_MAPPING"
        if d["category"] == "EXCLUDED_AS_DUPLICATE_OR_OUT_OF_CITY":
            assert d["count_kind"] == "NON_ADDITIVE_WITNESS"
    all_slots = [s for d in decisions for s in d["victim_slots"]]
    assert len(all_slots) == len(set(all_slots)) == 15
    for g in groups:
        d_for_g = [d for d in decisions if d["id"] in g["decision_ids"]]
        assert len(d_for_g) == len(g["decision_ids"])
        assert all(d["attack_date"] == g["date"] for d in d_for_g)
        assert sum(d["verified_new_delta"] for d in d_for_g) == g["safe_new_delta"]
        assert sum(d.get("unresolved_count", 0) for d in d_for_g) == g["held_unresolved"]
        assert g["safe_new_delta"] + g["held_unresolved"] == g["reported_citywide_final"]
        assert g["cumulative_trajectory"][-1] == g["reported_citywide_final"]
    assert j["summary"]["proposed_safe_new_credit"] == 15
    assert j["summary"]["pending_unresolved_within_parent_17"] == 2
    assert j["summary"]["kyiv_proposed_confirmed_partial_minimum_after_separate_owner_review"] == 33
    assert b["original_published_partial"] + sum(d["verified_new_delta"] for d in decisions) == 33
    assert j["summary"]["publication_status"] == "NOT_AUTHORIZED_NO_DATA_CHANGED"
    return {"status": "PASS", "safe_proposed_delta": 15, "held": 2,
            "date_groups": 6, "decisions": len(decisions),
            "source_cards": len(src), "publication": "OFF"}


def negative_cases(j, csv_text):
    cases = []
    def fail_mutation(label, mutate):
        x = copy.deepcopy(j)
        mutate(x)
        try:
            validate(x, csv_text)
        except (AssertionError, ValueError, KeyError):
            cases.append(label)
        else:
            raise AssertionError("Failed to block " + label)
    fail_mutation("PROMOTE_ON", lambda x: x.update(promotion="ON"))
    fail_mutation("publication_allowed", lambda x: x.update(publication_allowed=True))
    fail_mutation("new_http", lambda x: x.update(publisher_gets_this_issue=1))
    fail_mutation("site_prod_drift", lambda x: x["pins"].update(site_prod_sha="0" * 40))
    fail_mutation("original_baseline_drift", lambda x: x["baseline"].update(original_published_partial=17))
    fail_mutation("month_complete", lambda x: x["baseline"].update(exact_month_total=33))
    fail_mutation("citywide_duplicate", lambda x: x["decisions"][0].update(verified_new_delta=3))
    fail_mutation("identity_duplicate", lambda x: x["decisions"][1]["victim_slots"].__setitem__(0, x["decisions"][0]["victim_slots"][0]))
    fail_mutation("out_of_city_credit", lambda x: x["decisions"][11].update(verified_new_delta=2))
    fail_mutation("held_auto_credit", lambda x: x["decisions"][8].update(automatic_credit=True))
    fail_mutation("unknown_as_credit", lambda x: x["decisions"][8].update(verified_new_delta=2))
    fail_mutation("sep25_double_count", lambda x: x["date_groups"][2].update(safe_new_delta=7))
    fail_mutation("late_date_wrong_month", lambda x: x["decisions"][0].update(attack_date="2026-10-01"))
    fail_mutation("missing_source", lambda x: x["decisions"][0]["source_refs"].append("q90000"))
    fail_mutation("unpinned_sha", lambda x: x["source_cards"]["q120"].update(captured_sha256="a"))
    fail_mutation("csv_mismatch", lambda x: x["decisions"][0].update(id="tampered"))
    return cases


if __name__ == "__main__":
    j = json.loads(J.read_text(encoding="utf-8"))
    csv_text = C.read_text(encoding="utf-8")
    outcome = validate(j, csv_text)
    outcomes = negative_cases(j, csv_text)
    outcome["negative_cases_pass"] = len(outcomes)
    outcome["proof_sha256"] = {"ledger": hashlib.sha256(J.read_bytes()).hexdigest(),
                                "decisions_csv": hashlib.sha256(C.read_bytes()).hexdigest()}
    print(json.dumps(outcome, ensure_ascii=False, sort_keys=True))
