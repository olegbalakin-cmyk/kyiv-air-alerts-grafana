#!/usr/bin/env python3
"""Offline proof metadata only: inspect pinned repo sources, no network calls."""
import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SITE = ROOT / "_site/kyiv-air-alerts-grafana/data/casualties"
PR102 = ROOT / "_pr102/research/casualty_zaporizhzhia_http_capture_2026_11_12/capture_once.py"

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    plan_path = HERE / "capture_plan.json"
    authorization_path = HERE / "authorization_template.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    a = json.loads(authorization_path.read_text(encoding="utf-8"))
    manifest_path = SITE / "cities/zaporizhzhia/manifest.json"
    monthly_path = SITE / "cities/zaporizhzhia/zaporizhzhia_air_attack_deaths_monthly.csv"
    revisions_path = SITE / "revisions.csv"
    assert plan["work_e_head"] == "6b44b9766fdbe2cd2d65a20413d08f4f5ca91916"
    assert a["authorization_id"] is None
    assert a["status"] == "NOT_AUTHORIZED"
    assert a["targets"] == [{"url":t["url"],"role":t["role"],
                             "candidate_ids":t["candidate_ids"],
                             "approved_redirect_urls":[]} for t in plan["targets"]]
    assert a["redirect_policy"] == "EXACT_PER_INITIAL_TARGET_DEFAULT_DENY"
    manifest = json.loads(manifest_path.read_text())
    with monthly_path.open() as fh:
        months = list(csv.DictReader(fh))
    assert manifest["validated_through"] == "2026-09-18"
    assert not any(x["month"] == "2026-10" for x in months)
    assert len(plan["targets"]) == 10
    assert len(set(x["url"] for x in plan["targets"])) == 10
    assert not plan["automatic_credit_allowed"]
    assert plan["cases"]["late05"]["credit_gate"] == "LATER_OFFICIAL_CONFIRMATION_MISSING"
    result = {
        "checkpoint":"CASUALTY-CONTROLLED-CAPTURE-PREFLIGHT-OFFLINE-01",
        "decision":"CONTROLLED_CAPTURE_PREFLIGHT_PASS",
        "execution":"OFFLINE_ONLY",
        "authorization_status":"NOT_AUTHORIZED",
        "initial_target_count":len(plan["targets"]),
        "allowed_hosts":plan["allowed_hosts"],
        "max_requests_total":plan["limits"]["max_requests_total"],
        "media_http_requests":0,
        "publisher_bodies_saved":0,
        "official_death_claims_newly_verified":0,
        "automatic_death_credits":0,
        "publication_allowed":False,
        "site_prod_manifest_validated_through":manifest["validated_through"],
        "september_credit":"BLOCKED_UNALLOCATED_BASELINE",
        "late_death":"BLOCKED_MISSING_OFFICIAL_CONFIRMATION",
        "input_sha256":{
            "capture_plan.json":sha(plan_path),
            "authorization_template.json":sha(authorization_path),
            "pr102_capture_once.py":sha(PR102),
            "site_prod_manifest.json":sha(manifest_path),
            "site_prod_monthly.csv":sha(monthly_path),
            "site_prod_revisions.csv":sha(revisions_path),
        },
        "limitations":[
            "No live publisher HTTP, body capture or fact-level proof in this preflight",
            "Work I blocks unapproved redirect paths before the next GET; live HTTP still NOT_AUTHORIZED",
            "Official articles are retained separately but not automatically incident-linked",
            "Work E controlled mode should not be used as a casualty-crediting or production pipeline",
            "Authorization template is intentionally invalid and default OFF",
        ],
    }
    output = Path(sys.argv[1])
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n")
    print("CONTROLLED_CAPTURE_PREFLIGHT_PASS: offline checks; 10 exact sources; 0 publisher HTTP; authorization NOT_AUTHORIZED")
if __name__ == "__main__":
    main()
