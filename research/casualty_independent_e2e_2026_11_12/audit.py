#!/usr/bin/env python3
"""Independent, read-only evaluation of frozen Work A using separate event gold.

Only GitHub-pinned inputs and runner-temp files are read/written.
NO publisher HTTP, no WIP mutation, no real revision or dashboard publication.
The Work A code is the subject under test, not copied or modified here.
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKA = ROOT / "_worka"
SITE = ROOT / "_site" / "kyiv-air-alerts-grafana"
MATRIX = ROOT / "_matrix" / "research/casualty_zaporizhzhia_additional_events_2026_11_12/verification_matrix.json"
DISPLAY = ROOT / "_display" / "research/casualty_incomplete_month_preview_2026_11_12"
WIP = ROOT / "_wip" / "kyiv-air-alerts-grafana/data/casualties/multicity_review_queue.json"
GENERATOR_PATH = SITE / "scripts/update_casualties.py"
REVIEWER_PATH = WORKA / "kyiv-air-alerts-grafana/scripts/review_casualty_candidates.py"
REQUIRED_CONTRACT = ("incident_id", "count_kind", "baseline_credited", "identity_proof", "credited_proof")

# This is a separately defined case-level gold from PRs #85 and #102.
# Gold does NOT derive its labels from Work A candidate decisions.
# 5 October is an unverified possible later death, NOT a positive.
GOLD = {
    "oct_10_guided_bomb": dict(attack_date="2026-10-10", fatalities=23,
                               truth="CONFIRMED_RETAINED_PRIMARY", prior_credit="0_PROVEN"),
    "oct_18_drone": dict(attack_date="2026-10-18", fatalities=1,
                          truth="CONFIRMED_PR102_PRIOR_SOURCE_ASSESSMENT", prior_credit="UNRECONCILED"),
    "oct_22_23_two_vs_three": dict(attack_date="2026-10-22", fatalities=3,
                                   truth="CONFIRMED_PR102_ONE_INCIDENT", prior_credit="UNRECONCILED"),
    "sep_25_26_possible_attacks": dict(attack_date="2026-09-26", fatalities=2,
                                       truth="CONFIRMED_PR102_ONE_INCIDENT", prior_credit="UNALLOCATED_SEPTEMBER"),
    "sep_27_shahed": dict(attack_date="2026-09-27", fatalities=1,
                          truth="CONFIRMED_PR102_ONE_INCIDENT", prior_credit="UNALLOCATED_SEPTEMBER"),
    "oct_26_apartment": dict(attack_date="2026-10-05", fatalities=None,
                             truth="AMBIGUOUS_POSSIBLE_LATE_DEATH", prior_credit="UNKNOWN"),
}
SHA = {
    "evidence": "84ffea1315d41b8ec67b55a07273d6bbd7d6e8e14191801402168f7fddf4e5df",
    "receipts": "4c21321b8a75d57f60efc97f581e89604eaa03289bb64bfba26e491ac83a203b",
}


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def file_sha(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stable_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode()).hexdigest()


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def ensure(condition, name: str):
    if not condition:
        raise AssertionError(name)


def run_worka(out: Path, evidence: Path, receipts: Path):
    # A real rerun, using Work A's unchanged implementation and exact production generator.
    # Paths and prior proposal reservation are intentionally explicit.
    common = [
        "--queue", str(WIP),
        "--evidence", str(evidence),
        "--receipts", str(receipts),
        "--matrix", str(MATRIX),
        "--revisions", str(SITE / "data/casualties/revisions.csv"),
        "--baseline", str(WORKA / "research/casualty_automated_review_2026_11_10/baseline_coverage.json"),
        "--city-manifest", str(SITE / "data/casualties/cities/zaporizhzhia/manifest.json"),
        "--city-csv", str(SITE / "data/casualties/cities/zaporizhzhia/zaporizhzhia_air_attack_deaths_monthly.csv"),
        "--generator", str(GENERATOR_PATH),
        "--dashboard", str(SITE / "data/dashboard_data.json"),
    ]
    script = WORKA / "research/casualty_e2e_shadow_2026_11_12/pipeline.py"
    first, second = out / "first", out / "replay"
    subprocess.run([sys.executable, str(script), *common, "--output", str(first)],
                   check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    subprocess.run([sys.executable, str(script), *common, "--previous-proposals",
                    str(first / "proposals.json"), "--output", str(second)],
                   check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return first, second


def test_synthetic_guards(gen, proposal):
    # All manufactured rows below are SOFTWARE TEST FIXTURES, not real attacks.
    checks = []
    def case(name, f):
        f()
        checks.append(name)

    def row(suffix, total, when, **override):
        r = copy.deepcopy(proposal)
        r["record_id"] = "synthetic-e2e-" + suffix
        r["deaths_delta"] = total
        r["observed_at"] = when
        r["attack_date"] = date.fromisoformat(proposal["attack_date"])
        r.update(override)
        return r

    t18 = row("18", 18, "2026-10-10T11:00:00+03:00")
    t20 = row("20", 20, "2026-10-10T12:00:00+03:00")
    t23 = row("23", 23, "2026-10-10T13:00:00+03:00")
    case("18_20_23_cumulative_equals_23_not_61", lambda:
         ensure(sum(r["deaths_delta"] for r in gen.reconcile_confirmed_revisions(
             [t18, t20, t23])) == 23, "cumulative incorrectly added"))
    case("repeat_23_never_adds_again", lambda:
         ensure(sum(r["deaths_delta"] for r in gen.reconcile_confirmed_revisions(
             [t18, t20, t23, row("23-repeat", 23, "2026-10-10T15:00:00+03:00")])) == 23,
             "repeat duplicated"))
    already18 = [row("credited18", 23, "2026-10-10T15:00:00+03:00",
                     baseline_credited="18")]
    case("existing_credit_18_to_23_is_plus_5", lambda:
         ensure(sum(r["deaths_delta"] for r in gen.reconcile_confirmed_revisions(
             already18)) == 5, "credited delta is not +5"))

    def separate_attack():
        independent = row(
            "other-attack", 7, "2026-10-10T19:00:00+03:00",
            incident_id="incident:synthetic-distinct-attack",
            identity_proof="sha256:" + "a"*64,
            source_url="https://example.org/synthetic-unpublished-other-attack",
            candidate_ids="synthetic-another-candidate")
        values = gen.reconcile_confirmed_revisions([t23, independent])
        ensure(sorted(r["deaths_delta"] for r in values) == [7,23],
               "distinct same-day incidents collapsed")
    case("distinct_same_day_incident_is_not_collapsed", separate_attack)

    def reject_reuse():
        independent = row("reused", 7, "2026-10-10T19:00:00+03:00",
            incident_id="incident:synthetic-distinct-attack",
            identity_proof="sha256:" + "a"*64,
            source_url="https://example.org/synthetic-unpublished-other-attack")
        try:
            gen.reconcile_confirmed_revisions([t23, independent])
        except RuntimeError as exc:
            ensure("Ambiguous candidate_id" in str(exc), "wrong reuse failure")
            return
        raise AssertionError("cross-incident candidate reuse accepted")
    case("duplicate_candidate_cross_incident_rejected", reject_reuse)

    def downward():
        try:
            gen.reconcile_confirmed_revisions(
                [t23, row("decrease", 18, "2026-10-10T20:00:00+03:00")])
        except RuntimeError as exc:
            ensure("Downward/ambiguous" in str(exc), "unexpected conflict handling")
            return
        raise AssertionError("contradictory downward total accepted")
    case("contradictory_total_fails_closed", downward)

    def no_proof():
        invalid = row("missing-proof", 23, "2026-10-10T13:00:00+03:00",
                      identity_proof="", credited_proof="")
        try:
            gen.reconcile_confirmed_revisions([invalid])
        except RuntimeError as exc:
            ensure("missing immutable" in str(exc), "wrong missing-proof check")
            return
        raise AssertionError("unproved confirmed row accepted")
    case("missing_primary_identity_proof_rejected", no_proof)
    return checks


def reviewer_compatibility(gen, proposal, temp: Path):
    # Do not post/modify any real candidate: exercise old promote on an isolated
    # single-candidate queue made from the REAL valid Work A proposal.
    reviewer = load_module("legacy_reviewer_audit", REVIEWER_PATH)
    disposition = dict(proposal)
    disposition.update(candidate_id=proposal["candidate_ids"],
                       reviewed_at=proposal["observed_at"],
                       deaths_delta=int(proposal["deaths_delta"]),
                       status="confirmed")
    queue = [{"candidate_id": proposal["candidate_ids"], "city_key": proposal["city_key"],
              "status": "confirmed", "review_disposition": disposition}]
    q, ledger = temp / "private_review_queue.json", temp / "private_revisions.csv"
    q.write_text(json.dumps(queue), encoding="utf-8")
    result = reviewer.promote_reviewed(q, ledger, allowed_city_keys={"zaporizhzhia"})
    with ledger.open(newline="", encoding="utf-8") as f:
        saved = list(csv.DictReader(f))
    ensure(result["canonical_records_added"] == 1, "legacy reviewer promotion absent")
    ensure(len(saved) == 1, "legacy reviewed ledger count")
    lost = [k for k in REQUIRED_CONTRACT if k not in saved[0] or not saved[0][k]]
    ensure(lost == list(REQUIRED_CONTRACT), "unexpected legacy reviewer contract")
    old_path = gen.REVISIONS_FILE
    gen.REVISIONS_FILE = ledger
    try:
        parsed = gen.load_revisions()
    finally:
        gen.REVISIONS_FILE = old_path
    error = None
    try:
        gen.reconcile_confirmed_revisions(parsed)
    except RuntimeError as exc:
        error = str(exc)
    ensure(error and "missing documented incident" in error,
           "legacy-reviewed output unexpectedly passed strict dedup")
    return {"legacy_promotion_status": "WRITES_INCOMPATIBLE_CONFIRMED_ROW",
            "lost_fields": lost, "generator_rejection": error,
            "worka_direct_adapter_status": "PASS_ISOLATED_ONLY"}


def display_and_rollback(probe, out: Path):
    original = read(SITE / "data/dashboard_data.json")
    overlay = probe["isolated_dashboard_patch"]["casualties_by_city"]["zaporizhzhia"]
    patched = copy.deepcopy(original)
    patched["casualties_by_city"]["zaporizhzhia"] = overlay
    noncasualty = {k: v for k, v in original.items() if k != "casualties_by_city"}
    ensure(stable_sha({k:v for k,v in patched.items() if k != "casualties_by_city"}) ==
           stable_sha(noncasualty), "alert/noncasualty mutated")
    other = {k:v for k,v in original["casualties_by_city"].items() if k != "zaporizhzhia"}
    ensure(stable_sha({k:v for k,v in patched["casualties_by_city"].items()
                       if k != "zaporizhzhia"}) == stable_sha(other),
           "other-city casualty values changed")
    october = [r for r in overlay["monthly"] if r["month"] == "2026-10"]
    ensure(len(october) == 1 and october[0]["deaths"] == 23,
           "incorrect generator month/delta")
    # Real graph metadata is absent: WITHOUT the separate PR99 local-only overlay
    # this is an unqualified integer, not a verified lower bound.
    ensure("coverage_status" not in october[0] and "confirmed_minimum" not in october[0],
           "graph contract unexpectedly changed; independent re-review needed")
    month_file = out / "actual_generator_month.json"
    month_file.write_text(json.dumps(october[0], ensure_ascii=False), encoding="utf-8")
    script = ("const fs=require('fs');"
              "const m=require(process.argv[1]);"
              "const raw=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));"
              "console.log(JSON.stringify(m.normalize(raw)));")
    proc = subprocess.run(["node", "-e", script, str(DISPLAY / "coverage-preview.js"),
                           str(month_file)], check=True, text=True, capture_output=True)
    normalized = json.loads(proc.stdout)
    ensure(normalized["status"] == "LEGACY_UNVERIFIED",
           "worka generator already produces classified complete/incomplete data")
    fixture = read(DISPLAY / "fixture.json")
    ensure(fixture["coverage_status"] == "INCOMPLETE" and
           fixture["confirmed_minimum"] == 23 and fixture["deaths"] is None,
           "PR99 incomplete fixture mismatch")
    patched["casualties_by_city"]["zaporizhzhia"] = original["casualties_by_city"]["zaporizhzhia"]
    ensure(stable_sha(original) == stable_sha(patched), "Git JSON rollback hash differs")
    return {"isolated_generator_month": october[0],
            "pr99_normalizes_real_generator_row_as": normalized["status"],
            "pr99_separate_fixture_status": fixture["coverage_status"],
            "actual_incomplete_month_display": "NOT_CONNECTED",
            "live_export_csv_png_embed": "NOT_E2E_PROVEN",
            "noncasualty_fields_unchanged": True,
            "other_22_city_casualties_unchanged": True,
            "reversible_git_json_patch": True}


def main(output: Path, evidence: Path, receipts: Path):
    output.mkdir(parents=True, exist_ok=True)
    ensure(file_sha(evidence) == SHA["evidence"], "original evidence SHA mismatch")
    ensure(file_sha(receipts) == SHA["receipts"], "approved PR102 receipt SHA mismatch")
    ensure(GENERATOR_PATH.is_file() and REVIEWER_PATH.is_file(), "pinned code absent")
    matrix = read(MATRIX)
    ensure({g["cluster_id"] for g in matrix["groups"]} == set(GOLD) - {"oct_10_guided_bomb"},
           "independent gold group mismatch")

    # No publisher connection is performed by audit.py or Work A pipeline.
    first, again = run_worka(output, evidence, receipts)
    summary, repeat = read(first / "summary.json"), read(again / "summary.json")
    cases, proposals = read(first / "attack_decisions.json"), read(first / "proposals.json")
    probe = read(first / "generator_probe.json")
    decisions = read(first / "candidate_decisions.json")
    ensure(summary["candidates_seen"] == len(decisions) == 1682, "candidate accounting")
    ensure(summary["auto_ready_candidates"] == 1, "first-run auto count")
    ensure(summary["needs_review_candidates"] == 1681, "first-run review count")
    ensure(summary["rejected_candidates"] == 0, "first-run rejection count")
    ensure(len(cases) == len(GOLD) == 6, "case count")
    ensure(len(proposals) == 1 and proposals[0]["deaths_delta"] == "23", "proposals mismatch")
    ensure(probe["status"] == "PASS" and probe["new_delta"] == 23, "generator proof mismatch")
    ensure(repeat["shadow_proposals"] == 0 and
           repeat["generator_probe"] == "SKIPPED_ALREADY_RESERVED", "replay not idempotent")
    ensure(read(first / "manifest.json")["input_unchanged"] and
           read(again / "manifest.json")["input_unchanged"], "inputs changed")
    ensure(not summary["publication_allowed"], "publication flag unsafe")

    case_rows = []
    for case in cases:
        name = case["cluster_id"]
        truth = GOLD[name]
        observed = case["status"]
        expected = "AUTO_READY" if name == "oct_10_guided_bomb" else "NEEDS_REVIEW"
        ensure(observed == expected, "unexpected decision " + name)
        if name != "oct_10_guided_bomb":
            ensure("BLOCKED_SOURCE_CONTENT" in case["reasons"], "missing fail-closed reason")
            ensure(case.get("new_increment") is None, "unverified deaths credited")
        case_rows.append({"cluster_id": name, **truth, "worka_decision": observed,
                          "worka_increment": case.get("new_increment"),
                          "incident_is_confirmed_by_independent_gold": truth["fatalities"] is not None,
                          "is_auto_advanced": observed == "AUTO_READY"})
    good = [r for r in case_rows if r["incident_is_confirmed_by_independent_gold"]]
    unadvanced = [r for r in good if not r["is_auto_advanced"]]
    ambiguous = [r for r in case_rows if not r["incident_is_confirmed_by_independent_gold"]]
    ensure(len(good) == 5 and len(unadvanced) == 4 and len(ambiguous) == 1,
           "independent case gold totals differ")
    ensure(ambiguous[0]["worka_decision"] == "NEEDS_REVIEW",
           "unconfirmed late death incorrectly auto-promoted")

    sys.path.insert(0, str(SITE / "scripts"))
    gen = load_module("independent_production_generator", GENERATOR_PATH)
    synthetic = test_synthetic_guards(gen, proposals[0])
    with tempfile.TemporaryDirectory(prefix="independent-revision-contract-") as td:
        compatibility = reviewer_compatibility(gen, proposals[0], Path(td))
    front = display_and_rollback(probe, output)
    metrics = {
        "status": "PARTIAL",
        "gold_source": "PR85+PR102; not Work A decisions",
        "frozen_candidates_processed": 1682,
        "selected_independent_real_incidents": 6,
        "independently_confirmed_incidents_in_selected_set": 5,
        "correct_automatic_confirmations_selected": 1,
        "false_automatic_confirmations_selected": 0,
        "confirmed_incidents_not_automatically_advanced_selected": 4,
        "correctly_blocked_ambiguous_selected": 1,
        "new_revision_proposals_first": 1,
        "new_revision_proposals_replay": 0,
        "selected_incidents_automatic_fraction": "1/6",
        "all_wip_candidates_automatic_fraction": "1/1682",
        "case_level_advance_rate_on_confirmed_selected": "1/5",
        "overall_recall": None,
        "overall_precision": None,
        "overall_false_positive_rate": None,
        "end_to_end_coverage_proven": False,
        "real_2026_october_coverage": "COVERAGE_INCOMPLETE",
        "shadow_generator_delta_for_oct_10": 23,
        "publisher_http_requested": False,
        "neon_c2_netlify_invoked": False,
        "production_mutated": False,
        "generator_direct_adapter": "PASS",
        "legacy_review_to_generator_contract": "FAIL",
        "generator_to_incomplete_month_graph": "FAIL",
        "publication_allowed": False,
    }
    ensure(len(synthetic) == 7, "negative/safety coverage")
    ensure(compatibility["worka_direct_adapter_status"] == "PASS_ISOLATED_ONLY",
           "compatibility probe")
    report = {"metrics": metrics, "cases": case_rows,
              "synthetic_safety_checks": synthetic,
              "reviewer_compatibility": compatibility,
              "graph_rollback": front,
              "proof": {"worka_exact_head": "6a0100b0937218c62c5c079fd46e80e5071783cb",
                        "production_generator_exact_ref": "d0a7d22de2828c93236562cccc9d2e68c6a66e3d",
                        "evidence_sha256": file_sha(evidence),
                        "receipts_sha256": file_sha(receipts),
                        "first_inputs_unchanged": True, "replay_inputs_unchanged": True}}
    (output / "independent_results.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    print(json.dumps(metrics, ensure_ascii=False, sort_keys=True))
    print("INDEPENDENT_AUDIT_PARTIAL_COMPLETE: real cases 6; safety guards 7; no writes")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--receipts", type=Path, required=True)
    args = parser.parse_args()
    main(args.output.resolve(), args.evidence.resolve(), args.receipts.resolve())
