#!/usr/bin/env python3
"""C3-RC4 source-locked, fail-closed real 23-city staged adapter regression.

Offline. Every datum is copied using git show from a pinned production commit.
The expected SHA-256 file values must be fixed *before* certifying this run.
"""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "kyiv-air-alerts-grafana" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import live_canonical_queue as journal
import live_parent_ordering as families
import monitor_explosion_candidates as stage

HERE = Path(__file__).resolve().parent
FROZEN = Path(os.environ["C3_RC2_FROZEN_DIR"])
OUT = Path(os.environ.get("C3_RC4_REPORT_DIR", "/tmp/c3-rc3-proof"))
OUT.mkdir(parents=True, exist_ok=True)
SOURCE_COMMIT = "c0e3cef6bb4437492cb5933fad5f2f6d5b23e3be"
PRE_IMPL = "08c1a0a9cb3d27a73cfd85b48b31a29817c1d20d"
CUTOFF = datetime.fromisoformat("2026-10-07T19:05:00+00:00")
INPUT_BLOBS = {
    "ukrainealarm_bridge.json": "8b9dad34912fc83b54b5f966435a837d71731e69",
    "alerts_combined.json": "3a50f76fe12b2ef769eb9f104fdfb6d75bd0b37a",
    "sevastopol_events.json": "4aa7359da706d06a3e570c6ef75947817bede385",
}
MANIFEST = HERE / "sha_manifest.json"

def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()

def iso(t):
    return stage.iso(t) if t else None

def run():
    expected = json.loads(MANIFEST.read_text())
    report = {
        "gate": "C3-RC4", "source_commit": SOURCE_COMMIT,
        "pinned_pre_rc1": PRE_IMPL, "activation_cutoff": iso(CUTOFF),
        "inputs": {}, "cities": [], "errors": [], "totals": {},
        "source_hash_lock": "PENDING", "baseline_harness": "NOT_EXECUTED",
        "result": "PARTIAL"
    }
    try:
        if expected.get("source_commit") != SOURCE_COMMIT:
            report["errors"].append("SOURCE_COMMIT_MANIFEST_MISMATCH")
        sha_locks = True
        for name, blob in INPUT_BLOBS.items():
            path = FROZEN / name
            raw = path.read_bytes()
            sha = hashlib.sha256(raw).hexdigest()
            source_path = "kyiv-air-alerts-grafana/data/" + name
            observed_blob = git("hash-object", str(path))
            commit_blob = git("rev-parse", SOURCE_COMMIT + ":" + source_path)
            fixed = (expected.get("files") or {}).get(name) or {}
            fixed_sha = fixed.get("sha256")
            valid = bool(fixed_sha and fixed_sha == sha and
                         observed_blob == commit_blob == blob and
                         fixed.get("blob_sha") == blob)
            sha_locks = sha_locks and valid
            report["inputs"][name] = {
                "source_commit": SOURCE_COMMIT,
                "source_path": source_path, "blob_sha_expected": blob,
                "blob_sha_actual": observed_blob, "commit_blob": commit_blob,
                "file_sha256": sha, "expected_sha256": fixed_sha,
                "bytes": len(raw), "sha256_locked": valid
            }
            if not valid:
                report["errors"].append("FROZEN_INPUT_INTEGRITY_NOT_CERTIFIED:" + name)
        report["source_hash_lock"] = "PASS" if sha_locks else "NOT_PROVEN"
        if git("rev-parse", "HEAD:kyiv-air-alerts-grafana/scripts/live_canonical_queue.py") != "68c31cec6316d236c6839a4f5bb29adec89ab0c9":
            report["errors"].append("STAGED_QUEUE_BLOB_DRIFT")
        if git("rev-parse", "HEAD:kyiv-air-alerts-grafana/scripts/attack_event_canonical_persistence.py") != "d3ad61f9807c4dec2c6e3bf97a29d78af60500be":
            report["errors"].append("STAGED_PERSISTENCE_BLOB_DRIFT")
        if git("rev-parse", "HEAD:kyiv-air-alerts-grafana/scripts/monitor_explosion_candidates.py") != "bc8a63ff52273e14f89dece4681abca4dedb8c53":
            report["errors"].append("STAGED_MONITOR_BLOB_DRIFT")
        if git("rev-parse", "HEAD:kyiv-air-alerts-grafana/config/live_persistence_activation.json") != "62d3d49a8da1a92afc1004ca939980aed0d039f7":
            report["errors"].append("ACTIVATION_BLOB_DRIFT")
        if stage._live_cutoff_for_obligation_registration() != CUTOFF:
            report["errors"].append("ACTIVATION_CUTOFF_SEMANTICS_DRIFT")

        bridge = json.loads((FROZEN / "ukrainealarm_bridge.json").read_text())
        checked = [
            stage.parse_dt(row.get("last_checked_at"))
            for row in (bridge.get("regions") or {}).values()
            if isinstance(row, dict) and row.get("last_checked_at")
        ]
        checked = [x for x in checked if x is not None]
        now = max(checked) if checked else CUTOFF
        report["coverage"] = {
            "oldest_region_last_checked_at": iso(min(checked)) if checked else None,
            "newest_region_last_checked_at": iso(now),
            "checked_region_rows": len(checked),
            "bridge_events": len(bridge.get("events") or []),
            "temporal_source_fresh": len(checked) >= 21 and min(checked) >= CUTOFF if checked else False,
        }
        if not report["coverage"]["temporal_source_fresh"]:
            report["errors"].append("POST_CUTOFF_REGION_COVERAGE_NOT_PROVEN")
        staged, staged_errors = stage.poll_cached_bridge(
            FROZEN / "ukrainealarm_bridge.json", now,
            FROZEN / "alerts_combined.json", FROZEN / "sevastopol_events.json"
        )
        source_coverage = {}
        for city in sorted(stage.CITY_CONFIG):
            eps = staged.get(city) or []
            eligible = [ep for ep in eps if stage.parse_dt(ep.get("alert_end")) and stage.parse_dt(ep["alert_end"]) >= CUTOFF]
            source_coverage[city] = {
                "episodes": len(eps), "eligible": len(eligible),
                "earliest_end": min((ep["alert_end"] for ep in eps), default=None),
                "latest_end": max((ep["alert_end"] for ep in eps), default=None)
            }
        report["source_coverage"] = source_coverage
        for name in INPUT_BLOBS:
            report["inputs"][name]["coverage"] = report["coverage"] if name == "ukrainealarm_bridge.json" else {
                "special_source_rows": len(json.loads((FROZEN / name).read_text()))
                if name == "alerts_combined.json" else
                len(json.loads((FROZEN / name).read_text()).get("pairs") or [])
            }
        report["post_cutoff_eligible_total"] = sum(x["eligible"] for x in source_coverage.values())
        if report["post_cutoff_eligible_total"] == 0:
            report["errors"].append("EMPTY_POST_CUTOFF_ELIGIBLE_COHORT")

        rc2_path = ROOT / "research/c3_rc2_2026_10_28/prove_23_city_regression.py"
        spec = importlib.util.spec_from_file_location("c3rc2baseline", rc2_path)
        rc2 = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(rc2)
        baseline = rc2.pinned_pre_monitor()
        previous, pre_errors = baseline.poll_cached_bridge(
            FROZEN / "ukrainealarm_bridge.json", now,
            FROZEN / "alerts_combined.json", FROZEN / "sevastopol_events.json")
        state, old = {"schema_version":1,"cities":{}},{"schema_version":1,"cities":{}}
        current_new = stage.process_events(state, staged, dict(staged_errors), now)
        prior_new = baseline.process_events(old, previous, dict(pre_errors), now)
        if current_new != prior_new:
            report["errors"].append("NEW_EPISODE_COUNT_DIFFERS")
        all_codes = {"PASS":0,"FAIL":0,"NOT_PROVEN":0}
        for city in sorted(stage.CITY_CONFIG):
            rows, before = staged.get(city) or [], previous.get(city) or []
            family = families.ingestion_family(city)
            family_expected = (
                "Kyiv exact-city combined" if city == "kyiv"
                else "Sevastopol verified exact-city pairs" if city == "sevastopol"
                else "UkraineAlarm exact-hromada" if city in {"kharkiv","zaporizhzhia"}
                else "UkraineAlarm raion-proxy"
            )
            s_ids = [(e["episode_id"],e["alert_start"],e["alert_end"]) for e in rows]
            b_ids = [(e["episode_id"],e["alert_start"],e["alert_end"]) for e in before]
            eligible = source_coverage[city]["eligible"]
            due = stage.due_checks({"cities":{city:(state.get("cities") or {}).get(city,{})}},now)
            j = [v for v in journal.store(state).values() if v["city_key"] == city]
            pending = sum(v["status"] not in {"committed","quarantined"} for v in j)
            acknowledged = sum(v["status"] == "committed" for v in j)
            mismatches = []
            if family != family_expected: mismatches.append("INGESTION_FAMILY")
            if s_ids != b_ids: mismatches.append("SOURCE_IDENTITY_OR_INTERVAL")
            if len(s_ids) != len(set(s_ids)): mismatches.append("DUPLICATE_EPISODE")
            if len(j) != eligible: mismatches.append("ELIGIBLE_JOURNAL_DENOMINATOR")
            if len(rows) != len(before): mismatches.append("PINNED_PRE_RC1_DENOMINATOR")
            if staged_errors.get(city) != pre_errors.get(city): mismatches.append("SOURCE_ERROR_PARITY")
            for ep in rows:
                if ep.get("city_key") != city: mismatches.append("CITY_LEAKAGE")
                if family == "UkraineAlarm raion-proxy" and ep.get("logical_grouping") != "apply_ukrainealarm_bridge.union_alerts":
                    mismatches.append("RAION_PROXY_UNION")
            err = staged_errors.get(city) or pre_errors.get(city)
            if err: mismatches.append("SOURCE_ERROR:" + str(err))
            if mismatches:
                status="FAIL"
            elif not rows or not eligible or not report["coverage"]["temporal_source_fresh"] or not sha_locks:
                status="NOT_PROVEN"
            else: status="PASS"
            all_codes[status] += 1
            report["cities"].append({
                "city": city,"ingestion_family":family,"status":status,
                "source_episodes":len(rows),"pinned_pre_rc1_episodes":len(before),
                "post_cutoff_eligible":eligible,"due":len(due.get(city,[])),
                "journal_obligations":len(j),"pending":pending,"acknowledged":acknowledged,
                "source_errors":err,"mismatches":sorted(set(mismatches)),
                "coverage_end":source_coverage[city]["latest_end"]
            })
        report["totals"] = {
            "city_status":all_codes,
            "cities":len(report["cities"]),
            "source_episodes":sum(r["source_episodes"] for r in report["cities"]),
            "eligible":sum(r["post_cutoff_eligible"] for r in report["cities"]),
            "journal_obligations":sum(r["journal_obligations"] for r in report["cities"]),
            "pending":sum(r["pending"] for r in report["cities"]),
            "acknowledged":sum(r["acknowledged"] for r in report["cities"])
        }
        if report["totals"]["cities"] != 23:
            report["errors"].append("CITY_MATRIX_NOT_23_ROWS")
        if report["totals"]["journal_obligations"] == 0:
            report["errors"].append("EMPTY_POST_CUTOFF_JOURNAL")
        if all_codes["FAIL"] or all_codes["NOT_PROVEN"]:
            report["errors"].append("CITY_MATRIX_NOT_ALL_PASS")
        if not report["errors"]:
            try:
                with contextlib.redirect_stdout(io.StringIO()) as buff:
                    rc2.main()
                report["baseline_harness"] = "PASS"
                report["baseline_harness_output_sha256"] = hashlib.sha256(buff.getvalue().encode()).hexdigest()
            except Exception as exc:
                report["baseline_harness"] = "FAIL:" + repr(exc)
                report["errors"].append("RC2_BASELINE_HARNESS_FAILED")
        report["result"] = "PASS" if not report["errors"] else "PARTIAL"
    except Exception as exc:
        report["errors"].append("EXECUTION_EXCEPTION:" + type(exc).__name__ + ":" + str(exc))
    finally:
        output = OUT / "c3_rc4_23_city_results.json"
        output.write_text(json.dumps(report,indent=2,ensure_ascii=False,sort_keys=True)+"\n")
        print("C3_RC4_23_CITY_RESULT="+json.dumps({
            "result":report["result"],"totals":report.get("totals"),
            "errors":report["errors"],"source_hash_lock":report["source_hash_lock"]
        },ensure_ascii=False,sort_keys=True))
        print("C3_RC4_SHA256_PROBE="+json.dumps({k:v.get("file_sha256") for k,v in report["inputs"].items()},sort_keys=True))
    return 0 if report["result"] == "PASS" else 1

if __name__ == "__main__":
    sys.exit(run())
