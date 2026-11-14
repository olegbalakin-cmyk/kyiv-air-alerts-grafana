#!/usr/bin/env python3
"""WORK F: a narrow *isolated* adapter from an actual Work E/A proposal through
Work C's guarded REVIEW/PROMOTE to the unchanged production generator.

Never operate on a production path. The only operator calls here use newly
created, private scratch files and the previously verified Work C test pattern.
The protected GitHub operator workflow is NEVER invoked.
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import importlib.util
import json
import shutil
import sys
from pathlib import Path

CID = "e0fba98b19473874e9a1d8f1"
TEXT_SHA = "011894b7c4bd906dcfd0c5d2f7cef07a932976ca313220fa9089999264feb259"
EVIDENCE_FIELDS = ("incident_id", "count_kind", "baseline_credited",
                   "identity_proof", "credited_proof")
BASE_SHA = "d0a7d22de2828c93236562cccc9d2e68c6a66e3d"
CURRENT_SHA = "f0cfcbc862ca3dbf1b853e72de07ffcf6042856f"


def require(ok, msg):
    if not ok:
        raise RuntimeError("WORKF_BLOCKED:" + msg)


def sha(body):
    return hashlib.sha256(body).hexdigest()


def stable_sha(obj):
    return sha(json.dumps(obj, sort_keys=True, ensure_ascii=False,
                          separators=(",", ":")).encode("utf-8"))


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    Path(path).write_text(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    indent=2) + "\n", encoding="utf-8")


def read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def module_from_file(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    require(spec.loader is not None, "MODULE_LOADER_ABSENT")
    spec.loader.exec_module(module)
    return module


def run(a):
    files = [Path(getattr(a, name)).resolve() for name in
             ("proposals", "fact_cards", "candidate_decisions", "summary",
              "wip_queue", "site_root", "current_root", "workc_root",
              "city_manifest", "city_csv")]
    out = Path(a.output).resolve()
    require(all(p.exists() for p in files), "INPUT_MISSING")
    require(out.is_absolute() and not out.exists(), "OUTPUT_MUST_BE_NEW")
    require(not any(out == p or p in out.parents or out in p.parents
                    for p in files), "OUTPUT_OVERLAPS_INPUT")
    base = Path(a.site_root).resolve()
    current = Path(a.current_root).resolve()
    workc = Path(a.workc_root).resolve()
    base_ledger = base / "data/casualties/revisions.csv"
    current_ledger = current / "data/casualties/revisions.csv"
    base_generator = base / "scripts/update_casualties.py"
    current_generator = current / "scripts/update_casualties.py"
    base_dashboard_path = base / "data/dashboard_data.json"
    current_dashboard_path = current / "data/dashboard_data.json"
    all_inputs = [p for p in files if p.is_file()] + [
        base_ledger, current_ledger, base_generator, current_generator,
        base_dashboard_path, current_dashboard_path]
    require(all(p.is_file() for p in all_inputs), "SOURCE_FILE_MISSING")
    input_shas = {str(p): sha(p.read_bytes()) for p in all_inputs}
    require(input_shas[str(base_generator)] == input_shas[str(current_generator)],
            "CURRENT_GENERATOR_CHANGED_SEPARATE_COMPATIBILITY_REQUIRED")
    require(input_shas[str(base_ledger)] == input_shas[str(current_ledger)],
            "CURRENT_LEDGER_CHANGED_SEPARATE_BASELINE_REQUIRED")

    proposals = read_json(a.proposals)
    cards = read_json(a.fact_cards)
    decisions = read_json(a.candidate_decisions)
    summary = read_json(a.summary)
    require(isinstance(proposals, list) and len(proposals) == 1,
            "NOT_ONE_REAL_WORKA_PROPOSAL")
    p = proposals[0]
    require(p["candidate_ids"] == CID and p["city_key"] == "zaporizhzhia"
            and p["attack_date"] == "2026-10-10"
            and p["status"] == "confirmed" and p["count_kind"] == "cumulative"
            and p["baseline_credited"] == "0"
            and int(p["deaths_delta"]) == 23, "PROPOSAL_NOT_SOURCE_BACKED_CUMULATIVE")
    require(all(p.get(f) for f in EVIDENCE_FIELDS), "PROPOSAL_PROOF_FIELD_MISSING")
    source_card = [c for c in cards if c.get("candidate_id") == CID]
    require(len(source_card) == 1, "NO_UNIQUE_WORKE_CARD")
    card = source_card[0]
    require(card["original_text_sha256"] == TEXT_SHA
            and sorted(card["reported_totals"]) == [18, 20, 23]
            and card["confirmed_total"] == 23
            and card["incident"]["attack_date"] == p["attack_date"]
            and card["incident"]["city_key"] == p["city_key"]
            and card["attributed_official_origin_id"] == "dsns"
            and card["publication_allowed"] is False,
            "WORKE_FACT_CARD_UNVERIFIED")
    require(sum(d["candidate_id"] == CID and d["status"] == "AUTO_READY"
                for d in decisions) == 1, "WORKA_DECISION_MISMATCH")
    require(summary["candidates_seen"] == 1682
            and summary["shadow_proposals"] == 1
            and summary["needs_review_candidates"] == 1681
            and summary["publication_allowed"] is False, "WORKA_SUMMARY_MISMATCH")
    # Use Work C's unchanged production functions, never the workflow, against
    # scratch files. The queue entry is derived from the actual frozen WIP and
    # its "needs_review" state represents an unapproved human review.
    sys.path.insert(0, str(workc / "scripts"))
    import casualty_review_operator as operator
    import review_casualty_candidates as reviewer
    original_queue = reviewer.load_queue(Path(a.wip_queue))
    found = [c for c in original_queue if c.get("candidate_id") == CID]
    require(len(original_queue) == 1682 and len(found) == 1,
            "FROZEN_WIP_CANDIDATE_MISMATCH")
    require(found[0]["city_key"] == p["city_key"], "WIP_CITY_MISMATCH")
    require(found[0].get("status") in (None, "needs_review", "pending"),
            "WIP_ALREADY_REVIEWED")
    require(not found[0].get("review_disposition"), "EXISTING_REVIEW_DISPOSITION")
    review_entry = copy.deepcopy(found[0])
    review_entry["status"] = "needs_review"
    out.mkdir(parents=True)
    scratch = out / "scratch"
    scratch.mkdir()
    queue = scratch / "queue.json"
    ledger = scratch / "revisions.csv"
    initial_queue = (json.dumps([review_entry], ensure_ascii=False) + "\n").encode("utf-8")
    queue.write_bytes(initial_queue)
    shutil.copyfile(base_ledger, ledger)
    initial_ledger = ledger.read_bytes()
    old_rows = read_csv(base_ledger)
    require(len(old_rows) == 1 and old_rows[0]["city_key"] == "sumy"
            and old_rows[0]["deaths_delta"] == "1", "SUMY_BASELINE_DRIFT")

    def state():
        return {"wip_head": "frozen-offline-43b580491d54",
                "site_prod_head": BASE_SHA,
                "queue_blob_sha": operator.git_blob_sha(queue),
                "revisions_blob_sha": operator.git_blob_sha(ledger)}

    payload = {key: p[key] for key in
               ("record_id", "city_key", "attack_date", "deaths_delta",
                "source_name", "source_url", *EVIDENCE_FIELDS)}
    payload["deaths_delta"] = int(payload["deaths_delta"])
    payload["note"] = "OFFLINE SHADOW: linked retained source and prior credit proof"
    # This reuses precisely the isolated test arrangement proven in Work C.
    st = state()
    review = operator.build_preview(
        mode="REVIEW", candidate_id=CID, decision="CONFIRM", payload=payload,
        queue_path=queue, revisions_path=ledger, state=st)
    require(review["effect"]["projected_revision_increment"] == 23,
            "REVIEW_EXPECTED_23")
    outcome = operator.apply_preview(
        review, queue_path=queue, revisions_path=ledger, current_state=st,
        reviewed_by="human-researcher", workflow_run_id="offline-workf-test")
    require(outcome["revisions_changed"] is False
            and ledger.read_bytes() == initial_ledger, "REVIEW_CHANGED_LEDGER")
    disposition = reviewer.load_queue(queue)[0]["review_disposition"]
    require(all(disposition[field] == p[field] for field in EVIDENCE_FIELDS),
            "REVIEW_STRIPPED_DEDUP_FIELDS")

    st = state()
    promote = operator.build_preview(
        mode="PROMOTE", candidate_id=CID, decision="", payload={},
        queue_path=queue, revisions_path=ledger, state=st)
    require(promote["effect"]["projected_revision_increment"] == 23,
            "PROMOTE_PREVIEW_NOT_23")
    promoted = operator.apply_preview(
        promote, queue_path=queue, revisions_path=ledger, current_state=st,
        reviewed_by="human-researcher", workflow_run_id="offline-workf-test")
    require(promoted["ledger_changed"] and promoted["canonical_records_added"] == 1,
            "PROMOTE_DID_NOT_ADD_ONE")
    after_rows = read_csv(ledger)
    require(len(after_rows) == 2, "LEDGER_NOT_TWO_ROWS")
    require(all(after_rows[0][k] == v for k, v in old_rows[0].items()),
            "SUMY_EXISTING_ROW_CHANGED")
    require(all(after_rows[1][key] == str(p[key]) for key in EVIDENCE_FIELDS)
            and after_rows[1]["candidate_ids"] == CID,
            "PROMOTED_FIVE_FIELDS_NOT_PRESERVED")
    copied_promoted = out / "promoted_revisions.csv"
    shutil.copyfile(ledger, copied_promoted)
    promoted_sha = sha(copied_promoted.read_bytes())

    # A second actual guarded PROMOTE, with the post-PROMOTE ledger present.
    st = state()
    replay_preview = operator.build_preview(
        mode="PROMOTE", candidate_id=CID, decision="", payload={},
        queue_path=queue, revisions_path=ledger, state=st)
    require(replay_preview["effect"]["projected_revision_increment"] == 0,
            "REPLAY_INCREMENT_NONZERO")
    replay = operator.apply_preview(
        replay_preview, queue_path=queue, revisions_path=ledger,
        current_state=st, reviewed_by="human-researcher",
        workflow_run_id="offline-workf-replay")
    require(not replay["ledger_changed"] and
            sha(ledger.read_bytes()) == promoted_sha, "REPLAY_CHANGED_LEDGER")

    # Recompute the generator result FROM THE PROMOTED SCRATCH LEDGER, rather
    # than passing through Work A's pre-PROMOTE generator probe.
    gen = module_from_file(base_generator, "workf_site_prod_generator")
    gen.REVISIONS_FILE = ledger
    effective = gen.reconcile_confirmed_revisions(gen.load_revisions())
    zap = [row for row in effective if row["city_key"] == "zaporizhzhia"]
    require(len(zap) == 1 and zap[0]["deaths_delta"] == 23,
            "REAL_GENERATOR_DEDUP_NOT_23")
    require(len([row for row in effective if row["city_key"] == "sumy"]) == 1,
            "SUMY_LOST_IN_GENERATOR")
    manifest = read_json(a.city_manifest)
    source_monthly = read_csv(a.city_csv)
    before = {"meta": manifest,
              "monthly": [{"month": row["month"],
                           "time": gen.month_timestamp(row["month"]),
                           "deaths": int(row["deaths_confirmed"])}
                          for row in source_monthly]}
    generated = gen.apply_city_revision_overlay(before, effective, "zaporizhzhia")
    prior_count = sum(int(r["deaths"]) for r in before["monthly"]
                      if r["month"] == "2026-10")
    new_count = sum(int(r["deaths"]) for r in generated["monthly"]
                    if r["month"] == "2026-10")
    require((prior_count, new_count) == (0, 23), "GENERATOR_BASELINE_MISMATCH")
    base_data = read_json(base_dashboard_path)
    require(len(base_data["cities"]) == 23
            and len(base_data["casualties_by_city"]) == 23,
            "ORIGINAL_23_CITY_DATA_MISSING")
    old_months = base_data["casualties_by_city"]["zaporizhzhia"]["monthly"]
    require({(r["month"], int(r["deaths"])) for r in old_months} ==
            {(r["month"], int(r["deaths"])) for r in before["monthly"]},
            "HISTORICAL_DASHBOARD_CSV_MISMATCH")
    others = {k: v for k, v in base_data["casualties_by_city"].items()
              if k != "zaporizhzhia"}
    probe = {
        "status": "PASS", "month": "2026-10", "before_month": prior_count,
        "shadow_month": new_count, "new_delta": new_count - prior_count,
        "production_generator_sha256": sha(base_generator.read_bytes()),
        "production_revisions_sha256": sha(base_ledger.read_bytes()),
        "promoted_scratch_revisions_sha256": promoted_sha,
        "workc_protected_review_promote": True,
        "unchanged_22_other_cities_sha256": stable_sha(others),
        "isolated_dashboard_patch": {
            "casualties_by_city": {"zaporizhzhia": generated}},
        "publication_allowed": False,
    }
    write_json(out / "generator_probe_after_promote.json", probe)
    # Read-only current site-prod compatibility: generator + ledger bytes are
    # equal to baseline; its actual dashboard and frontend may have drifted.
    current_gen = module_from_file(current_generator, "workf_current_generator")
    current_gen.REVISIONS_FILE = ledger
    current_eff = current_gen.reconcile_confirmed_revisions(
        current_gen.load_revisions())
    current_zap = [x for x in current_eff if x["city_key"] == "zaporizhzhia"]
    require(len(current_zap) == 1 and current_zap[0]["deaths_delta"] == 23,
            "CURRENT_GENERATOR_NO_LONGER_COMPATIBLE")
    current_data = read_json(current_dashboard_path)
    require(len(current_data["cities"]) == 23
            and len(current_data["casualties_by_city"]) == 23,
            "CURRENT_CITY_COUNT_CHANGED")
    current_preview_app = current / "pages-preview/app.js"
    base_preview_app = base / "pages-preview/app.js"
    current_preview_index = current / "pages-preview/index.html"
    base_preview_index = base / "pages-preview/index.html"
    require(all(x.is_file() for x in
                (current_preview_app, base_preview_app,
                 current_preview_index, base_preview_index)),
            "FRONTEND_SNAPSHOT_MISSING")
    current_contract = {
        "frozen_historical_site_prod": BASE_SHA,
        "observed_current_site_prod": CURRENT_SHA,
        "generator_sha256_same": sha(current_generator.read_bytes()) ==
                                 sha(base_generator.read_bytes()),
        "revisions_sha256_same": sha(current_ledger.read_bytes()) ==
                                 sha(base_ledger.read_bytes()),
        "current_generator_scratch_delta": current_zap[0]["deaths_delta"],
        "current_city_count": len(current_data["cities"]),
        "current_dashboard_sha256": sha(current_dashboard_path.read_bytes()),
        "baseline_dashboard_sha256": sha(base_dashboard_path.read_bytes()),
        "current_dashboard_same": sha(current_dashboard_path.read_bytes()) ==
                                  sha(base_dashboard_path.read_bytes()),
        "current_frontend_app_sha256": sha(current_preview_app.read_bytes()),
        "baseline_frontend_app_sha256": sha(base_preview_app.read_bytes()),
        "current_frontend_app_same": sha(current_preview_app.read_bytes()) ==
                                     sha(base_preview_app.read_bytes()),
        "current_frontend_index_same": sha(current_preview_index.read_bytes()) ==
                                      sha(base_preview_index.read_bytes()),
        "current_frontend_browser_pass_claimed": False,
        "current_dashboard_generator_visualization_certified": False,
    }
    write_json(out / "current_siteprod_readonly_comparison.json",
               current_contract)
    promotion_report = {
        "status": "REVIEW_PROMOTE_REAL_GENERATOR_PASS",
        "source": "Work E archived original -> Work A proposal",
        "candidate_id": CID,
        "original_text_sha256": TEXT_SHA,
        "reported_totals": card["reported_totals"],
        "reconciled_incident_total": new_count,
        "net_new": new_count - prior_count,
        "repeat_promote_net_new": 0,
        "proof_fields_preserved": list(EVIDENCE_FIELDS),
        "scratch_ledger_sha256": promoted_sha,
        "baseline_ledger_sha256": sha(initial_ledger),
        "sumy_plus_one_preserved": True,
        "all_23_alert_cities_unchanged": True,
        "other_22_casualty_cities_unchanged": True,
        "reviewed_by": "human-researcher (isolated simulation, not live approval)",
        "operator": "unchanged Work C build_preview/apply_preview",
        "real_operator_workflow_invoked": False,
        "production_paths_written": False,
        "publisher_http_requests": 0,
        "publication_allowed": False,
    }
    write_json(out / "promotion_report.json", promotion_report)
    # Explicit scratch rollback and immutable input byte comparison.
    ledger.write_bytes(initial_ledger)
    queue.write_bytes(initial_queue)
    require(sha(ledger.read_bytes()) == sha(base_ledger.read_bytes())
            and queue.read_bytes() == initial_queue, "SCRATCH_ROLLBACK_FAILED")
    require(input_shas == {str(path): sha(path.read_bytes())
                           for path in all_inputs}, "SOURCE_CHANGED")
    write_json(out / "rollback_and_integrity.json", {
        "status": "SCRATCH_ROLLBACK_PASS",
        "ledger_restored_to_baseline": True,
        "queue_restored_to_pre_review": True,
        "input_sha256": input_shas,
        "source_inputs_unchanged": True,
        "production_data_changed": False,
        "publication_allowed": False,
    })
    print("WORKF_PROMOTED_GENERATOR_PASS "
          "original=18->20->23; guarded REVIEW/PROMOTE +23; replay +0; "
          "5 evidence fields; Sumy +1; scratch rollback PASS; "
          "current site-prod generator compatible; NO PUBLISH")


def main():
    parser = argparse.ArgumentParser()
    for key in ("proposals", "fact_cards", "candidate_decisions", "summary",
                "wip_queue", "site_root", "current_root", "workc_root",
                "city_manifest", "city_csv", "output"):
        parser.add_argument("--" + key.replace("_", "-"), required=True)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
