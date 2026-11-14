#!/usr/bin/env python3
"""Independent compact Work F assertions and reproducibility hash ledger."""
import hashlib
import json
import sys
from pathlib import Path


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def require(ok, reason):
    if not ok:
        raise RuntimeError("INTEGRATED_SHADOW_BLOCKED:" + reason)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    ing, worka, integrated, display, bridge, browser, regressions, output = map(
        Path, sys.argv[1:])
    cards = load(ing / "fact_cards.json")
    proposals = load(worka / "proposals.json")
    summary = load(worka / "summary.json")
    blocked = load(ing / "blocked_clusters.json")
    promoted = load(integrated / "promotion_report.json")
    probe = load(integrated / "generator_probe_after_promote.json")
    current = load(integrated / "current_siteprod_readonly_comparison.json")
    rollback = load(integrated / "rollback_and_integrity.json")
    qualified = load(display)
    bridge_proof = load(bridge)
    regres = load(regressions / "checks.json")
    browser_text = browser.read_text(encoding="utf-8")
    positive = [x for x in cards if x["candidate_id"] ==
                "e0fba98b19473874e9a1d8f1"]
    require(len(positive) == 1 and
            sorted(positive[0]["reported_totals"]) == [18, 20, 23],
            "ORIGINAL_TO_FACT_CARD")
    require(len(proposals) == 1 and
            int(proposals[0]["deaths_delta"]) == 23 and
            all(proposals[0].get(k) for k in
                ("incident_id", "count_kind", "baseline_credited",
                 "identity_proof", "credited_proof")),
            "WORK_A_TO_REVIEWER")
    require(summary["candidates_seen"] == 1682 and
            summary["auto_ready_candidates"] == 1 and
            summary["needs_review_candidates"] == 1681 and
            summary["publication_allowed"] is False,
            "MONITOR_SOURCE_COVERAGE")
    require(len(blocked) == 5 and sum(len(x["candidate_ids"])
                                      for x in blocked) == 11 and
            all(x["status"] == "NEEDS_REVIEW" for x in blocked),
            "MISSING_ORIGINALS_FAIL_CLOSED")
    require(promoted["status"] == "REVIEW_PROMOTE_REAL_GENERATOR_PASS" and
            promoted["net_new"] == 23 and
            promoted["repeat_promote_net_new"] == 0 and
            promoted["sumy_plus_one_preserved"] and
            promoted["real_operator_workflow_invoked"] is False and
            promoted["publication_allowed"] is False, "REVIEW_PROMOTE")
    require(probe["status"] == "PASS" and
            probe["workc_protected_review_promote"] and
            probe["new_delta"] == 23 and
            probe["promoted_scratch_revisions_sha256"] ==
            promoted["scratch_ledger_sha256"], "PROMOTED_LEDGER_NOT_PROBE_SOURCE")
    require(rollback["status"] == "SCRATCH_ROLLBACK_PASS" and
            rollback["source_inputs_unchanged"] and
            rollback["ledger_restored_to_baseline"], "ROLLBACK")
    require(current["generator_sha256_same"] and
            current["revisions_sha256_same"] and
            current["current_generator_scratch_delta"] == 23 and
            current["current_city_count"] == 23,
            "CURRENT_GENERATOR_COMPATIBILITY")
    require(regres["status"] == "REVIEWER_CONTRACT_PASS" and
            regres["test_count"] == 11 and
            not regres["failures"] and not regres["errors"],
            "WORK_C_REGRESSION")
    require(bridge_proof["decision"] ==
            "REAL_GENERATOR_TO_INCOMPLETE_DATA_PASS" and
            bridge_proof["publication_allowed"] is False and
            bridge_proof["generator_numeric_month"] == 23,
            "PROMOTED_GENERATOR_TO_WORK_D")
    oct_rows = [r for r in qualified["casualties_by_city"]["zaporizhzhia"]["monthly"]
                if r["month"] == "2026-10"]
    require(len(oct_rows) == 1 and
            oct_rows[0]["coverage_status"] == "INCOMPLETE" and
            oct_rows[0]["confirmed_minimum"] == 23 and
            oct_rows[0]["complete_total"] is None and
            oct_rows[0]["deaths"] is None, "INCOMPLETE_23_NOT_EXACT")
    require(len(qualified["cities"]) == 23 and
            len(qualified["casualties_by_city"]) == 23,
            "23_CITY_ISOLATION")
    require("BROWSER_CHECKS_FAIL=0" in browser_text and
            "BROWSER_CHECKS_PASS=42" in browser_text, "DESKTOP_MOBILE_EXPORT_QA")
    require(not current["current_frontend_browser_pass_claimed"] and
            not current["current_dashboard_generator_visualization_certified"],
            "CURRENT_BROWSER_CLAIM_NOT_SUPPORTED")
    evidence_files = [
        ing / "summary.json", ing / "fact_cards.json",
        ing / "blocked_clusters.json", worka / "summary.json",
        worka / "proposals.json", worka / "generator_probe.json",
        integrated / "promotion_report.json",
        integrated / "generator_probe_after_promote.json",
        integrated / "promoted_revisions.csv",
        integrated / "rollback_and_integrity.json",
        integrated / "current_siteprod_readonly_comparison.json",
        display, bridge, browser, regressions / "checks.json"]
    result = {
        "checkpoint_proposal": "CASUALTY-INTEGRATED-E2E-SHADOW-WORKF-01",
        "verdict": "INTEGRATED_SHADOW_PASS",
        "scope": "one previously stored Zaporizhzhia 2026-10-10 case; frozen historical baseline",
        "reported_cumulative_totals": [18, 20, 23],
        "actual_guarded_scratch_promote": 23,
        "repeat_increment": 0,
        "missing_original_clusters_blocked": 5,
        "reviewer_regression_tests": 11,
        "browser_regression_tests": 42,
        "current_generator_compatible": True,
        "current_frontend_browser_tested": False,
        "regular_autonomous_coverage_proven": False,
        "external_publisher_http": 0,
        "production_data_changed": False,
        "publication_allowed": False,
        "evidence_sha256": {str(p): sha(p) for p in evidence_files},
    }
    output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True,
                                 indent=2) + "\n", encoding="utf-8")
    print("INTEGRATED_SHADOW_PASS: 18->20->23 -> Work E/A -> guarded "
          "scratch Work C REVIEW/PROMOTE -> actual generator -> "
          "Work D INCOMPLETE >=23 -> 42 browser checks; NO PUBLISH")


if __name__ == "__main__":
    main()
