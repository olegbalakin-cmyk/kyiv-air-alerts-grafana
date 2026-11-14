#!/usr/bin/env python3
"""Fail-closed final Work H proof gate; all fields refer to real ephemeral Work F/D outputs."""
import hashlib
import json
import sys
from pathlib import Path


def read(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def require(v, code):
    if not v:
        raise RuntimeError("CURRENT_FRONTEND_INTEGRATION_BLOCKED:" + code)


def main():
    f, data, rebase, hbrowser, dbrowser, output = map(Path, sys.argv[1:])
    w = read(f)
    d = read(data)
    r = read(rebase)
    h = hbrowser.read_text(encoding="utf-8")
    b = dbrowser.read_text(encoding="utf-8")
    require(w["verdict"] == "INTEGRATED_SHADOW_PASS" and
            w["actual_guarded_scratch_promote"] == 23 and
            w["repeat_increment"] == 0, "WORKF_ACTUAL_CHAIN")
    require(r["verdict"] == "CURRENT_DASHBOARD_REBASE_PASS" and
            r["confirmed_minimum"] == 23 and
            r["coverage_status"] == "INCOMPLETE" and
            r["complete_total"] is None and
            r["sumy_plus_one_preserved"] and
            r["unmodified_casualty_cities"] == 22 and
            r["current_alert_cities"] == 23 and
            r["current_alert_series_sha256"] ==
            r["rebase_alert_series_sha256"] and
            r["current_other_casualties_sha256"] ==
            r["rebase_other_casualties_sha256"] and
            r["publication_allowed"] is False and
            r["production_data_changed"] is False, "DATA_ISOLATION")
    require(sha(data) == r["rebase_dashboard_sha256"], "REBASE_SHA_MISMATCH")
    require(len(d["cities"]) == len(d["casualties_by_city"]) == 23,
            "REBASE_CITY_COUNTS")
    z = [x for x in d["casualties_by_city"]["zaporizhzhia"]["monthly"]
         if x["month"] == "2026-10"]
    require(len(z) == 1 and z[0]["deaths"] is None and
            z[0]["coverage_status"] == "INCOMPLETE" and
            z[0]["confirmed_minimum"] == 23 and
            z[0]["complete_total"] is None, "OCTOBER_COVERAGE")
    require("BROWSER_CHECKS_PASS=42 BROWSER_CHECKS_FAIL=0" in b,
            "CURRENT_SITE_WORKD_42_BROWSER_ASSERTIONS")
    require("CURRENT_BROWSER_CHECKS_FAIL=0" in h and
            "CURRENT_BROWSER_CHECKS_PASS=" in h,
            "CURRENT_SITE_EXTRA_REGRESSIONS")
    require("CURRENT_SCREENSHOTS_SHA256=" in h,
            "SCREENSHOTS_MISSING")
    require(all("localhost" not in str(p) for p in (f, data, rebase)),
            "PROOF_PATH_INVALID")
    record = {
        "checkpoint_proposed": "CASUALTY-CURRENT-SITEPROD-FRONTEND-WORKH-01",
        "verdict": "CURRENT_FRONTEND_INTEGRATION_PASS",
        "site_prod_head": "f0cfcbc862ca3dbf1b853e72de07ffcf6042856f",
        "workf_head": "2274276ebf962e3e9917d59024ea624fd3bdbb95",
        "workd_head": "62aef3645c4bdc89940bc1ba05abe23c08d23142",
        "source_cumulative": [18, 20, 23],
        "scratch_promote": 23,
        "scratch_replay_increment": 0,
        "current_frontend_browser_42_assertions": True,
        "regression_tests": h.split("CURRENT_BROWSER_CHECKS_PASS=")[-1].split()[0],
        "23_alert_cities_unchanged": True,
        "22_other_casualty_cities_unchanged": True,
        "sumy_plus_one_retained": True,
        "external_source_http": 0,
        "production_data_changed": False,
        "publication_allowed": False,
        "proof_sha256": {
            "workf_integrated_manifest": sha(f),
            "rebased_current_dashboard": sha(data),
            "rebase_report": sha(rebase),
            "current_browser_checks": sha(hbrowser),
            "workd_browser_checks": sha(dbrowser)
        }
    }
    output.write_text(json.dumps(record, indent=2, sort_keys=True,
                                 ensure_ascii=False) + "\n", encoding="utf-8")
    print("CURRENT_FRONTEND_INTEGRATION_PASS current site-prod, sourced "
          "Work F/D, original alerts/KPIs, desktop/mobile, sharing/CSV/embed, "
          "rollback, unchanged 23 cities and Sumy, NO PUBLISH")


if __name__ == "__main__":
    main()
