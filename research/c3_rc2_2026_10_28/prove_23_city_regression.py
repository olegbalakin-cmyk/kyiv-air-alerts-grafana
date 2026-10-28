#!/usr/bin/env python3
"""C3-RC2: real cached-source 23-city replay, pinned pre-RC1 comparison.

Runs the actual source adapters and process_events from the staged and pinned
operational WIP revisions; no source HTTP, production writes or live Neon.
"""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone
from collections import Counter

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / "kyiv-air-alerts-grafana"
SCRIPTS = PKG / "scripts"
sys.path.insert(0, str(SCRIPTS))
import monitor_explosion_candidates as stage
import live_canonical_queue as journal
import live_parent_ordering as families

WIP = "08c1a0a9cb3d27a73cfd85b48b31a29817c1d20d"
PROD = "a2d593c51830a62516d8907b6f55aae1b05e8948"
DATA = Path(os.environ["C3_RC2_FROZEN_DIR"])

def pinned_pre_monitor():
    path = SCRIPTS / "_c3_rc2_pinned_pre_rc1_temp.py"
    raw = subprocess.check_output([
        "git","show",WIP + ":kyiv-air-alerts-grafana/scripts/monitor_explosion_candidates.py"
    ], cwd=ROOT)
    try:
        path.write_bytes(raw)
        spec = importlib.util.spec_from_file_location("_c3_rc2_pre_rc1", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        path.unlink(missing_ok=True)

def main():
    baseline = pinned_pre_monitor()
    assert len(stage.CITY_CONFIG) == len(baseline.CITY_CONFIG) == 23
    assert set(stage.CITY_CONFIG) == set(baseline.CITY_CONFIG)
    bridge_path = DATA / "ukrainealarm_bridge.json"
    kyiv_path = DATA / "alerts_combined.json"
    sev_path = DATA / "sevastopol_events.json"
    bridge = json.loads(bridge_path.read_text())
    checked = [
        stage.parse_dt(region.get("last_checked_at"))
        for region in (bridge.get("regions") or {}).values()
        if region.get("last_checked_at")
    ]
    assert len(checked) >= 21, "frozen bridge must include actual city polls"
    now = max(checked)
    frozen = {
        "source_ref": PROD,
        "source_sha_manifest": json.loads((DATA/"sha_manifest.json").read_text()),
        "observed_at": stage.iso(now),
        "cities": {},
        "errors": {},
    }
    st_rows, st_errors = stage.poll_cached_bridge(bridge_path, now, kyiv_path, sev_path)
    pre_rows, pre_errors = baseline.poll_cached_bridge(bridge_path, now, kyiv_path, sev_path)
    assert st_errors == pre_errors, (st_errors, pre_errors)
    assert set(st_rows) == set(pre_rows) == set(stage.CITY_CONFIG)
    assert not st_errors, ("incomplete cached source coverage", st_errors)
    assert all(st_rows[c] for c in stage.CITY_CONFIG), "source returned an empty city"

    previous = {"schema_version":1, "cities": {}}
    current = {"schema_version":1, "cities": {}}
    pre_new = baseline.process_events(previous, pre_rows, dict(pre_errors), now)
    stage_new = stage.process_events(current, st_rows, dict(st_errors), now)
    assert pre_new == stage_new, (pre_new, stage_new)
    total_obligations = 0
    source_identities = set()
    for city in sorted(stage.CITY_CONFIG):
        family = families.ingestion_family(city)
        expected_family = ("Kyiv exact-city combined" if city == "kyiv"
                           else "Sevastopol verified exact-city pairs" if city == "sevastopol"
                           else "UkraineAlarm exact-hromada" if city in {"kharkiv", "zaporizhzhia"}
                           else "UkraineAlarm raion-proxy")
        assert family == expected_family, city
        stages = st_rows[city]
        prior = pre_rows[city]
        def keys(rows):
            return [(r["episode_id"], r["alert_start"], r["alert_end"]) for r in rows]
        assert keys(stages) == keys(prior), ("source_regression", city)
        assert keys(current["cities"][city]["episodes"]) == keys(previous["cities"][city]["episodes"]), ("state_regression",city)
        assert len(stages) == len(set(x[0] for x in keys(stages))), city
        assert len(stages) > 0, city
        for ep in stages:
            assert ep["city_key"] == city, ("city leakage", city)
            assert ep["alert_source"] == (
                "kyiv_combined_exact_city" if city == "kyiv" else
                "sevastopol_verified_exact_city_pairs" if city == "sevastopol" else
                "ukrainealarm_bridge_cached" if family == "UkraineAlarm exact-hromada" else
                "ukrainealarm_bridge_cached_union"
            ), (city, ep["alert_source"])
            source_identities.add((city,ep["episode_id"]))
            if family == "UkraineAlarm raion-proxy":
                assert ep.get("logical_grouping") == "apply_ukrainealarm_bridge.union_alerts",city
        cur_due = stage.due_checks({"cities":{city:current["cities"][city]}},now)
        pre_due = baseline.due_checks({"cities":{city:previous["cities"][city]}},now)
        assert len(cur_due.get(city,[])) == len(pre_due.get(city,[])),("due",city)
        obligations = [x for x in journal.store(current).values() if x["city_key"]==city]
        # All post-cutoff alerts must survive initial retention registration.
        source_eligible = [x for x in stages if stage.parse_dt(x["alert_end"]) >= stage._live_cutoff_for_obligation_registration()]
        assert len(obligations)==len(source_eligible), ("journal denominator",city,len(obligations),len(source_eligible))
        total_obligations += len(obligations)
        frozen["cities"][city] = {
            "source_episodes": len(stages),
            "pre_rc1_episodes": len(prior),
            "state_episodes": len(current["cities"][city]["episodes"]),
            "pre_rc1_state_episodes": len(previous["cities"][city]["episodes"]),
            "due_checks": len(cur_due.get(city,[])),
            "canonical_obligations": len(obligations),
            "source": stages[0]["alert_source"],
            "ingestion_family": family,
        }

    assert len(source_identities) == sum(row["source_episodes"] for row in frozen["cities"].values())
    assert set(frozen["cities"]) == set(stage.CITY_CONFIG)
    assert sum(x["ingestion_family"]=="UkraineAlarm raion-proxy" for x in frozen["cities"].values())==19
    assert sum(x["ingestion_family"]=="UkraineAlarm exact-hromada" for x in frozen["cities"].values())==2
    frozen["pre_rc1_new_alerts"] = pre_new
    frozen["staged_new_alerts"] = stage_new
    frozen["source_episodes_total"] = len(source_identities)
    frozen["journal_obligations_total"] = total_obligations
    frozen["result"] = "PASS_23_CITY_SOURCE_AND_STATE_PARITY"
    print("C3_RC2_CITY_MATRIX=" + json.dumps(frozen, sort_keys=True, ensure_ascii=False))

if __name__ == "__main__":
    main()
