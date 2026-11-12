#!/usr/bin/env python3
"""Qualify a REAL pinned generator output with an explicit evidence decision.

This adapter never constructs a casualty count or reruns a synthetic fixture.
Input generator_probe.json MUST come from Work A's actual site-prod
reconcile_confirmed_revisions -> apply_city_revision_overlay path in this run.
Writes only outside the repository. No external HTTP, no publication.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path

EXPECTED_CITY = "zaporizhzhia"
EXPECTED_MONTH = "2026-10"
EXPECTED_ATTACK = "2026-10-10"
EXPECTED_CANDIDATE = "e0fba98b19473874e9a1d8f1"
EXPECTED_TEXT_SHA = "011894b7c4bd906dcfd0c5d2f7cef07a932976ca313220fa9089999264feb259"

def require(ok, message):
    if not ok:
        raise RuntimeError("GENERATOR_DISPLAY_BLOCKED:" + message)

def sha(body):
    return hashlib.sha256(body).hexdigest()

def stable_sha(obj):
    return sha(json.dumps(obj, sort_keys=True, ensure_ascii=False,
                          separators=(",", ":")).encode("utf-8"))

def input_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def adapt(base, probe, proposals, decision, generator_hash, revisions_hash):
    require(decision.get("scope") == "SHADOW_ONLY" and decision.get("publication_allowed") is False,
            "COVERAGE_DECISION_NOT_SHADOW")
    require((decision.get("city_key"), decision.get("month"), decision.get("coverage_status")) ==
            (EXPECTED_CITY, EXPECTED_MONTH, "INCOMPLETE"), "UNEXPECTED_COVERAGE_SCOPE")
    require(type(decision.get("confirmed_minimum")) is int and
            decision["confirmed_minimum"] == 23 and decision.get("complete_total") is None,
            "UNVERIFIED_COVERAGE_MINIMUM")
    require(decision.get("evidence_candidate_id") == EXPECTED_CANDIDATE and
            decision.get("source_text_sha256") == EXPECTED_TEXT_SHA,
            "EVIDENCE_SOURCE_NOT_PINNED")
    require(type(proposals) is list and len(proposals) == 1, "EXPECTED_ONE_REAL_PROPOSAL")
    p = proposals[0]
    require((p.get("city_key"), p.get("attack_date"), p.get("status"),
             p.get("count_kind"), p.get("baseline_credited"), p.get("candidate_ids")) ==
            (EXPECTED_CITY, EXPECTED_ATTACK, "confirmed", "cumulative", "0",
             EXPECTED_CANDIDATE), "PROPOSAL_IDENTITY_OR_DEDUP_DRIFT")
    require(int(p.get("deaths_delta", "-1")) == 23 and
            str(p.get("incident_id") or "").startswith("incident:") and
            str(p.get("identity_proof") or "").startswith("sha256:") and
            str(p.get("credited_proof") or "").startswith("sha256:") and
            str(p.get("source_url") or "").startswith("https://"),
            "PROPOSAL_NOT_STRICT_GENERATOR_COMPATIBLE")
    require(probe.get("status") == "PASS" and probe.get("publication_allowed") is False,
            "REAL_GENERATOR_PROOF_NOT_PASS")
    require((probe.get("month"), probe.get("before_month"), probe.get("shadow_month"),
             probe.get("new_delta")) == (EXPECTED_MONTH, 0, 23, 23),
            "REAL_GENERATOR_COUNT_DRIFT")
    require(probe.get("production_generator_sha256") == generator_hash and
            probe.get("production_revisions_sha256") == revisions_hash,
            "REAL_GENERATOR_OR_LEDGER_SHA_MISMATCH")
    cities = base.get("casualties_by_city")
    require(isinstance(cities, dict) and len(cities) == 23 and EXPECTED_CITY in cities,
            "EXPECTED_23_CITIES")
    others = {k:v for k,v in cities.items() if k != EXPECTED_CITY}
    require(stable_sha(others) == probe.get("unchanged_22_other_cities_sha256"),
            "OTHER_CITY_PROOF_MISMATCH")
    patch = probe.get("isolated_dashboard_patch")
    require(type(patch) is dict and list(patch) == ["casualties_by_city"] and
            type(patch["casualties_by_city"]) is dict and
            set(patch["casualties_by_city"]) == {EXPECTED_CITY},
            "GENERATOR_PATCH_HAS_UNRELATED_DATA")
    generated = patch["casualties_by_city"][EXPECTED_CITY]
    require(isinstance(generated.get("monthly"), list), "GENERATOR_MONTHLY_ABSENT")
    original = cities[EXPECTED_CITY]["monthly"]
    original_by_month = {r["month"]:r for r in original}
    generated_by_month = {r["month"]:r for r in generated["monthly"]}
    require(len(original_by_month) == len(original) and
            len(generated_by_month) == len(generated["monthly"]) and
            EXPECTED_MONTH not in original_by_month and
            set(generated_by_month) == set(original_by_month) | {EXPECTED_MONTH},
            "GENERATOR_CHANGED_BASELINE_MONTHS")
    require(all(generated_by_month[m] == row for m,row in original_by_month.items()),
            "GENERATOR_MODIFIED_OTHER_MONTH")
    actual = generated_by_month[EXPECTED_MONTH]
    require(type(actual.get("deaths")) is int and actual["deaths"] == 23 and
            actual.get("revision_delta") == 23 and actual.get("baseline_deaths") == 0,
            "GENERATOR_ROW_NOT_23")
    require("coverage_status" not in actual and "confirmed_minimum" not in actual,
            "GENERATOR_ALREADY_QUALIFIED_UNEXPECTEDLY")
    qualified = copy.deepcopy(base)
    qualified["casualties_by_city"][EXPECTED_CITY] = copy.deepcopy(generated)
    row = next(r for r in qualified["casualties_by_city"][EXPECTED_CITY]["monthly"]
               if r["month"] == EXPECTED_MONTH)
    row.update(deaths=None, coverage_status="INCOMPLETE",
               confirmed_minimum=actual["deaths"], complete_total=None)
    require(stable_sha({k:v for k,v in qualified["casualties_by_city"].items()
                        if k != EXPECTED_CITY}) == stable_sha(others),
            "OTHER_CASUALTY_CITIES_CHANGED")
    require(qualified["cities"] == base["cities"] and
            len(qualified["cities"]) == 23, "ALERT_SERIES_CHANGED")
    require(all(row.get("coverage_status") != "COMPLETE"
                for row in qualified["casualties_by_city"][EXPECTED_CITY]["monthly"]
                if row["month"] == EXPECTED_MONTH), "FALSE_COMPLETE")
    require(all(key == "casualties_by_city" or qualified[key] == value
                for key,value in base.items()), "UNRELATED_DASHBOARD_KEYS_CHANGED")
    return qualified, {
        "decision": "REAL_GENERATOR_TO_INCOMPLETE_DATA_PASS",
        "scope": "SHADOW_ONLY", "publication_allowed": False,
        "city_key": EXPECTED_CITY, "month": EXPECTED_MONTH,
        "generator_numeric_month": actual["deaths"],
        "chart_row": row, "generator_sha256": generator_hash,
        "generator_revisions_sha256": revisions_hash,
        "other_22_cities_sha256": stable_sha(others),
        "original_alert_cities_sha256": stable_sha(base["cities"]),
        "coverage_evidence": decision["evidence"],
        "complete_total_asserted": False, "outside_repo_only": True
    }

def main():
    parser = argparse.ArgumentParser()
    for arg in ("dashboard", "generator_probe", "proposals", "decision",
                "generator", "revisions", "output", "proof"):
        parser.add_argument("--" + arg.replace("_","-"), required=True)
    args = parser.parse_args()
    here = Path(__file__).resolve().parents[2]
    files = [Path(getattr(args, x)).resolve() for x in
             ("dashboard","generator_probe","proposals","decision","generator","revisions")]
    require(all(p.is_file() for p in files), "INPUT_MISSING")
    paths = [Path(args.output).resolve(), Path(args.proof).resolve()]
    require(len(set(paths)) == 2 and all(here not in p.parents and p != here for p in paths),
            "WRITES_MUST_BE_OUTSIDE_REPO")
    require(all(p not in files for p in paths), "OUTPUT_OVERWRITES_INPUT")
    base, probe, proposals, decision = map(input_json, files[:4])
    qualified, report = adapt(base,probe,proposals,decision,
                              sha(files[4].read_bytes()),sha(files[5].read_bytes()))
    inputs_before = {str(p):sha(p.read_bytes()) for p in files}
    for output in paths:
        output.parent.mkdir(parents=True, exist_ok=True)
        require(not output.exists(), "OUTPUT_ALREADY_EXISTS")
    paths[0].write_text(json.dumps(qualified,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    report["generated_dashboard_sha256"] = sha(paths[0].read_bytes())
    report["source_dashboard_sha256"] = inputs_before[str(files[0])]
    report["input_sha256"] = inputs_before
    paths[1].write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    require(inputs_before == {str(p):sha(p.read_bytes()) for p in files},
            "INPUT_MUTATED")
    print("GENERATOR_DISPLAY_BRIDGE_PASS " + json.dumps({
        "city": EXPECTED_CITY,"month":EXPECTED_MONTH,
        "coverage_status":"INCOMPLETE","confirmed_minimum":23,
        "dashboard_sha256":report["generated_dashboard_sha256"],
        "publication_allowed":False}))

if __name__ == "__main__":
    main()
