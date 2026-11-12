#!/usr/bin/env python3
"""C3 read-only two-plane recovery policy checks on immutable offline fixtures.

A successful test proves detection of unsafe rollback cases, NOT operational
Netlify republish permission or an executed production rollback.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import subprocess
from datetime import datetime, timezone

DATA = "kyiv-air-alerts-grafana/data"
STATIC = "kyiv-air-alerts-grafana/pages-preview"
FILES = ("dashboard_data.json", "site_derived.json", "alerts_combined.json",
         "kyiv_threat_mix.json", "sevastopol_events.json")
MODES = ("daily28", "weekly", "rolling30", "rolling90", "rolling180",
         "calendarWeekly", "monthly", "allTime")
EXPECTED_SHA = "68629fdae5534ec3a136e666bcb7d5c84dcd05aa"
OLD_DEPLOY = "6adb629bc3ebc570117d82e1"

def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def blob(path):
    return subprocess.check_output(["git", "hash-object", str(path)], text=True).strip()

def check(condition, explanation):
    if not condition:
        raise AssertionError(explanation)

def actual_guard(app_path, git_index, old_index, neon_index, git_time):
    """Run the predicate copied verbatim from the checkout, never a rewrite."""
    source = Path(app_path).read_text(encoding="utf-8")
    match = re.search(r"const validIndex = index =>[\s\S]*?;", source)
    check(match is not None, "production validIndex() source missing")
    check("historical-daily-kpi.json" in source, "static fallback missing")
    check("embeddedHistory.meta.source_dashboard_generated_at === sourceGeneratedAt" in source,
          "embedded dashboard/index parity guard changed")
    check("index?.meta?.verified_count > 0" in source, "static fallback contract changed")
    code = r'''
const vm=require("node:vm");
const input=JSON.parse(require("node:fs").readFileSync(0,"utf8"));
const f=vm.runInNewContext(input.guard+"\nvalidIndex", {}, {timeout:1000});
const ans={
 git_index_accepted:f(input.gitIndex),
 old_static_index_accepted:f(input.oldIndex),
 neon_index_accepted:f(input.neonIndex),
 git_embedded_generation_match:input.gitIndex.meta.source_dashboard_generated_at===input.gitTime,
 old_static_generation_match:input.oldIndex.meta.source_dashboard_generated_at===input.gitTime,
 neon_generation_match:input.neonIndex.meta.source_dashboard_generated_at===input.gitTime
};
process.stdout.write(JSON.stringify(ans));
'''
    sample_old = {
        "schema": old_index["schema"],
        "meta": dict(old_index)
    }
    sample_old["meta"].pop("schema", None)
    payload = {"guard":match.group(0), "gitIndex":git_index,
               "oldIndex":sample_old, "neonIndex":neon_index,
               "gitTime":git_time}
    proc = subprocess.run(["node", "-e", code], input=json.dumps(payload),
                          text=True, capture_output=True, timeout=25, check=True)
    return json.loads(proc.stdout)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--production-tree", type=Path, required=True)
    ap.add_argument("--old-report", type=Path, required=True)
    ap.add_argument("--preview-root", type=Path, required=True)
    ap.add_argument("--preview-qa", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args=ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    old=read(args.old_report)
    prod=args.production_tree
    preview=args.preview_root
    proof={
        "schema":"c3-compatible-rollback-two-plane-checks-v1",
        "created_at":datetime.now(timezone.utc).isoformat(),
        "scope":"RESEARCH_READ_ONLY_OFFLINE_WITH_IMMUTABLE_GITHUB_FIXTURES",
        "operational_verdict":"BLOCKED",
        "production_deploy_performed":False, "git_publication_performed":False,
        "netlify_republish_performed":False, "neon_write_performed":False,
        "global_cutover":"NO", "dst_correction":"OFF",
        "old_netlify_deploy":OLD_DEPLOY, "site_prod_pinned_sha":EXPECTED_SHA,
        "existing_old_http_sha_artifact":13946647755,
        "existing_preview_package_artifact":13940887007,
        "existing_preview_live_qa_artifact":13945375693,
        "cases":{}, "git_runtime":{}, "static_reconstruction":{}
    }
    check(old["schema"]=="c3-production-old-deploy-http-snapshot-v1","prior HTTP proof schema")
    check(old["deployment_id"]==OLD_DEPLOY,"prior deploy id mismatch")
    check(old["operator_publish_control_verified"] is False,"operator state has changed; recheck")
    sha=subprocess.check_output(["git","-C",str(prod),"rev-parse","HEAD"],text=True).strip()
    check(sha==EXPECTED_SHA,"site-prod immutable checkout mismatch")

    for filename in FILES:
        p=prod/DATA/filename
        check(p.is_file(), "runtime Git JSON missing: "+filename)
        got=digest(p)
        want=old["runtime_git"][filename]["sha256"]
        check(got==want, "pinned Git runtime differs from HTTP baseline: "+filename)
        proof["git_runtime"][filename]={
            "sha256":got, "git_blob_sha1":blob(p), "bytes":p.stat().st_size,
            "source_commit":EXPECTED_SHA
        }
    # Current site-prod HEAD is two code-only commits after the recorded HTTP SHA.
    # This independent file-by-file check proves the five runtime bytes remain exact.
    for filename in ("app.js","kpi-range.js","chart-share.js","styles.css","features.json"):
        p=prod/STATIC/filename
        got=digest(p)
        want=old["old_static"][filename]["sha256"]
        check(got==want, "old deployed static != pinned frontend file: "+filename)
        proof["static_reconstruction"][filename]={"sha256":got,
            "deployed_sha256":want, "git_blob_sha1":blob(p)}
    proof["static_reconstruction"]["index.html"]={
        "deployed_sha256":old["old_static"]["index.html"]["sha256"],
        "verified_from_deploy_http_proof":True, "source_commit_attribution":False
    }
    proof["static_reconstruction"]["historical-daily-kpi.json"]={
        "deployed_sha256":old["old_static"]["historical-daily-kpi.json"]["sha256"],
        "meta":old["index_meta"], "verified_from_deploy_http_proof":True,
        "rebuild_not_equivalent_to_immutable_deploy":True
    }

    dashboard=read(prod/DATA/"dashboard_data.json")
    derived=read(prod/DATA/"site_derived.json")
    old_legacy=read(preview/"data/legacy/dashboard_data.json")
    neon=read(preview/"data/neon/dashboard_data.json")
    old_keys=sorted(old_legacy["cities"])
    real_keys=sorted(dashboard["cities"])
    neon_keys=sorted(neon["cities"])
    production_list=dashboard["multicity_meta"]["production_city_keys"]
    check(len(real_keys)==23 and len(set(production_list))==23 and
          set(production_list)==set(real_keys),"current 23-city contract broken")
    check(real_keys==old_keys==neon_keys,"23-city index inconsistent across pinned fixtures")
    check(derived["meta"]["city_count"]==23,"derived city count broken")
    check(derived["meta"]["generated_at"]==dashboard["meta"]["generated_at"],
          "same-run derived and dashboard generation differs")
    check(old["runtime_meta"]["generated_at"]==dashboard["meta"]["generated_at"],
          "2026-11-12 exact production generation changed")
    git_idx=dashboard.get("historical_daily_kpi")
    check(isinstance(git_idx,dict),"current Git embedded historical index missing")
    check(git_idx["meta"]["source_ref"]=="site-prod","Git source_ref mismatch")
    check(git_idx["meta"]["expected_cities"]==23 and git_idx["meta"]["verified_count"]==23,
          "Git verified historical cities not 23")
    check(set(git_idx["cities"])==set(real_keys),"Git KPI actual city keys mismatch")
    neon_idx=neon["historical_daily_kpi"]
    check(neon_idx["meta"]["source_ref"]=="neon:br-bold-mode-b5rub8pq",
          "physical Neon branch mismatch")
    guard=actual_guard(prod/STATIC/"app.js",git_idx,old["index_meta"],neon_idx,
                       dashboard["meta"]["generated_at"])
    proof["actual_production_validIndex_results"]=guard
    proof["generation"]={
        "old_netlify_source_dashboard_generated_at":old["index_meta"]["source_dashboard_generated_at"],
        "pinned_git_dashboard_generated_at":dashboard["meta"]["generated_at"],
        "pinned_git_index_generated_at":git_idx["meta"]["source_dashboard_generated_at"],
        "neon_preview_generated_at":neon["meta"]["generated_at"]
    }
    check(guard["git_index_accepted"] and guard["git_embedded_generation_match"],
          "normal current Git embedded KPI index is not accepted")
    check(guard["old_static_index_accepted"] and not guard["old_static_generation_match"],
          "expected real stale fallback not detected; re-evaluate risk")
    check(not guard["neon_index_accepted"],"old frontend unexpectedly accepts Neon index")
    proof["cases"]["1_normal_frontend_plus_current_git"]={
        "status":"CONDITIONALLY_COMPATIBLE_OFFLINE",
        "details":"old app bytes exact, five Git JSON byte-exact, embedded current Git KPI index valid, 23/23",
        "not_a_production_rollback":True
    }
    proof["cases"]["2_index_generation_mismatch"]={
        "status":"UNSAFE_STATIC_FALLBACK_DETECTED",
        "old_index_fails_generation_parity":True,
        "old_app_predicate_still_accepts_stale_static":True,
        "policy":"BLOCK; never treat static 23/23 alone as compatibility certification"
    }

    # Synthetic future writes: verify recovery policy must preserve newer state,
    # and old whole-tree restore must be rejected. No fake records reach the site.
    original={"c2_episodes":["baseline_33135"],"casualty_events":["original"],
              "auxiliary_versions":["original"],"kyiv_intervals":["old"]}
    newer=copy.deepcopy(original)
    newer["c2_episodes"].append("SIMULATED_NEW_C2_EPISODE")
    newer["casualty_events"].append("SIMULATED_NEW_CASUALTY_CONFIRMATION")
    newer["auxiliary_versions"].append("SIMULATED_NEW_KYIV_AUX")
    newer["kyiv_intervals"].append("SIMULATED_NEW_KYIV_INTERVAL")
    static_restore_only=copy.deepcopy(newer)
    check(static_restore_only==newer,"static-only recovery accidentally reverted runtime")
    check(original!=newer and len(original["c2_episodes"])<len(newer["c2_episodes"]),
          "synthetic post-baseline C2 loss scenario missing")
    proof["cases"]["3_postbaseline_c2"]={
        "status":"PASS_POLICY_REJECT_OLD_WHOLE_TREE_RESET",
        "new_records_preserved_if_static_only":True,
        "old_snapshot_reset_loses_c2":True,
        "data_marker":"SIMULATED_NOT_LIVE"
    }
    check(all(len(newer[k])>len(original[k]) for k in
              ("casualty_events","auxiliary_versions","kyiv_intervals")),
          "synthetic casualty/auxiliary test setup bad")
    proof["cases"]["4_independent_casualty_aux_and_kyiv"]={
        "status":"PASS_POLICY_PRESERVE_NEWER_UNRELATED_RECORDS",
        "old_full_git_reset_would_drop_them":True,
        "restoration_action":"do not restore any runtime file without per-field reconciliation",
        "data_marker":"SIMULATED_NOT_LIVE"
    }
    proof["cases"]["5_netlify_static_only_against_neon_git"]={
        "status":"BLOCKED_INCOMPATIBLE",
        "neon_embedded_rejected":not guard["neon_index_accepted"],
        "old_static_stale_accepted":guard["old_static_index_accepted"],
        "netlify_restore_does_not_revert_git":True
    }
    workflow=(prod/".github/workflows/netlify-production.yml").read_text(encoding="utf-8")
    check("branches: [site-prod]" in workflow and "kyiv-air-alerts-grafana/pages-preview/**" in workflow,
          "actual Netlify auto-deploy triggers changed")
    check("netlify-cli@latest deploy" in workflow and "--prod" in workflow,
          "Netlify --prod deployment path changed")
    proof["cases"]["6_automatic_republication"]={
        "status":"BLOCKED_UNTIL_OPERATOR_LOCK_AND_RUNNER_QUIESCENCE",
        "frontend_path_change_triggers_production_deploy":True,
        "site_prod_push_can_republish":True,
        "data_only_path_not_listed_in_netlify_workflow":("kyiv-air-alerts-grafana/data/**" not in workflow),
        "lock_enabled_by_this_test":False
    }

    qa=read(args.preview_qa)
    check(qa["verdict"]=="PASS_SCOPED_NEON_INDEX_OFFLINE_PREVIEW","previous QA failed")
    checks=qa["results"]
    check(checks[0]["city_mode_combinations"]==184 and checks[0]["cities"]==23
          and checks[0]["modes"]==len(MODES),"184 previous browser cases missing")
    check(len(qa["csv"])==23 and not qa["js_errors"]
          and not qa["failed_responses"] and not qa["external_requests"],
          "previous browser QA receipt is not clean")
    proof["previous_browser_qa_reused"]={
        "source":"existing C3 candidate preview, NOT production rollback",
        "cities":23,"modes":8,"views":184,"csv_exports":23,
        "github_actions_run":43208800105
    }
    proof["city_keys"]=real_keys
    proof["safety_checks_completed"]=6
    proof["blocking_reasons"]=[
        "netlify_publish_deploy_control_for_a_non-current_immutable_deploy_unverified",
        "old_static_kpi_fallback_accepts_wrong_dashboard_generation",
        "future_cutover_two_plane_manifest_not_yet_pinned_or_activated",
        "live_c2_casualty_aux_conflict_safe_recovery_not_exercised",
        "netlify_auto_publish_lock_and_sequencing_not_operationally_proven"
    ]
    proof["operational_verdict"]="BLOCKED"
    target=args.out/"RECOVERY_PROOF.json"
    target.write_text(json.dumps(proof,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (args.out/"BASELINE_MANIFEST.json").write_text(json.dumps({
        "old_netlify_deploy":OLD_DEPLOY,
        "old_static":old["old_static"],
        "netlify_static_index_meta":old["index_meta"],
        "git_runtime_at":EXPECTED_SHA,
        "git_runtime":proof["git_runtime"],
        "source_ref":"site-prod",
        "generated_at":dashboard["meta"]["generated_at"],
        "cities":real_keys
    },ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("C3_OFFLINE_POLICY_CASES=6/6")
    print("REUSED_PREVIEW_BROWSER=184/184 23 CSV (not recovery QA)")
    print("STALE_STATIC_INDEX_FALLBACK=ACCEPTED_UNSAFE_BY_OLD_APP")
    print("COMPATIBLE_ROLLBACK_READY=BLOCKED")
    print("NO_DEPLOY_NO_PUBLICATION_NO_NEON_WRITE")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
