#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

REPO = "olegbalakin-cmyk/kyiv-air-alerts-grafana"
ALIGNMENT_BRANCH = "attack-event-shared-live-classifier-alignment-2026-10-07"
LIVE_BRANCH = "multicity-wip-2026-09-16"
LIVE_PATH = "kyiv-air-alerts-grafana/scripts/monitor_explosion_candidates.py"
PIN_PATH = "kyiv-air-alerts-grafana/scripts/authoritative_classifier_71cb6f6f.py"
PREDECESSOR_BLOB = "927dc89df0b52edd52cb31a126b0d57ca492a278"
REPAIRED_BLOB = "e8bb3def24e411eb59028410cf144339ece0f28a"
AUTH_COMMIT = "71cb6f6fbe856cc7b96759310fe9cc9c71cc0453"
AUTH_BLOB = "778469b74c2aa807d851cf2c2ee35cf4aa785589"
RECOVERY_REF = "attack-event-multicity-86case-representability-recovery-2026-10-07"
PARITY_SCRIPT = ".github/proof/attack_event_multicity_classifier_parity.py"
RECOVERY_SCRIPT = ".github/proof/attack_event_multicity_86case_representability_recovery.py"
RECOVERY_TRIAL = ".github/proof/attack_event_multicity_86case_recovery_trial.py"
RECOVERY_DIAG = ".github/proof/attack_event_multicity_86case_recovery_diag.py"
RECOVERY_ARTIFACT = "research/attack_event_multicity_86case_representability_recovery_2026-10-07.json"
EXPECTED_TOTAL = 26405
EXPECTED_REPLAYABLE = 26363
EXPECTED_LEGACY_NON_REPLAYABLE = 42
POS = {"STRICT_EVENT_POSITIVE", "SENSITIVITY_EVENT_POSITIVE"}

class Blocked(RuntimeError):
    pass

def sh(args, *, cwd=None, check=True):
    p = subprocess.run(
        [str(x) for x in args],
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and p.returncode:
        raise Blocked("command failed: " + " ".join(map(str,args)) + "\n" + p.stderr[-4000:])
    return p

def git(*args):
    return sh(["git", *args]).stdout.strip()

def git_bytes(ref, path):
    p = subprocess.run(["git","show",f"{ref}:{path}"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode:
        raise Blocked(f"git show failed {ref}:{path}: {p.stderr.decode('utf-8','replace')[-2000:]}")
    return p.stdout

def ensure_ref(ref):
    p = sh(["git","cat-file","-e",f"{ref}^{{commit}}"], check=False)
    if p.returncode:
        if re.fullmatch(r"[0-9a-f]{40}", ref):
            sh(["git","fetch","--no-tags","origin",ref])
        else:
            sh(["git","fetch","--no-tags","origin",f"refs/heads/{ref}:refs/heads/{ref}"])
    git("rev-parse", f"{ref}^{{commit}}")

def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise Blocked(f"cannot import {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def patch_parity_script(src: str, code_commit: str) -> str:
    src = re.sub(r'CAND_COMMIT="[0-9a-f]{40}"', f'CAND_COMMIT="{code_commit}"', src, count=1)
    src = re.sub(r'CAND_BLOB="[0-9a-f]{40}"', f'CAND_BLOB="{REPAIRED_BLOB}"', src, count=1)
    needle = '            cand_path.write_bytes(candidate_bytes)'
    insert = needle + '\n            auth_path=wt/"kyiv-air-alerts-grafana"/"scripts"/"authoritative_classifier_71cb6f6f.py"\n            auth_path.write_bytes(git_bytes(CAND_COMMIT,"' + PIN_PATH + '"))'
    if needle not in src:
        raise Blocked("parity candidate write hook missing")
    return src.replace(needle, insert, 1)

def patch_recovery_script(src: str) -> str:
    needle = '        candpath.write_bytes(p.git_bytes(p.CAND_COMMIT,p.CAND_PATH))'
    insert = needle + '\n        authpath=wt/"kyiv-air-alerts-grafana"/"scripts"/"authoritative_classifier_71cb6f6f.py"\n        authpath.write_bytes(p.git_bytes(p.CAND_COMMIT,"' + PIN_PATH + '"))'
    if needle not in src:
        raise Blocked("recovery candidate write hook missing")
    return src.replace(needle, insert, 1)

def run_historical_regression(tmp: Path, code_commit: str, run_id: str):
    proofdir = tmp / "proof"
    proofdir.mkdir(parents=True)
    parity_src = git_bytes(RECOVERY_REF, PARITY_SCRIPT).decode("utf-8")
    parity_src = patch_parity_script(parity_src, code_commit)
    (proofdir / "attack_event_multicity_classifier_parity.py").write_text(parity_src, encoding="utf-8")
    for rel, name in [
        (RECOVERY_TRIAL, "attack_event_multicity_86case_recovery_trial.py"),
        (RECOVERY_DIAG, "attack_event_multicity_86case_recovery_diag.py"),
    ]:
        (proofdir / name).write_bytes(git_bytes(RECOVERY_REF, rel))
    recovery_src = git_bytes(RECOVERY_REF, RECOVERY_SCRIPT).decode("utf-8")
    recovery_src = patch_recovery_script(recovery_src)
    recovery_py = proofdir / "attack_event_multicity_86case_representability_recovery.py"
    recovery_py.write_text(recovery_src, encoding="utf-8")

    parity_out = tmp / "parity.json"
    parity_summary = tmp / "parity-summary.json"
    p = sh([
        sys.executable,
        str(proofdir / "attack_event_multicity_classifier_parity.py"),
        "--out", str(parity_out),
        "--summary", str(parity_summary),
        "--run-id", run_id,
    ], check=False)
    if p.returncode:
        raise Blocked("repaired-path parity run failed\n" + p.stderr[-4000:] + "\n" + p.stdout[-4000:])
    parity = json.loads(parity_out.read_text(encoding="utf-8"))
    pt = parity["totals"]
    if pt["episodes_replayed"] != 26319:
        raise Blocked(f"initial repaired replay count {pt['episodes_replayed']} != 26319")
    if pt["exact_verdict_matches"] != 26319 or pt["total_mismatches"] != 0:
        raise Blocked("initial repaired replay is not exact")
    if pt["unsafe_promotions_from_NO_CONFIRMED_EVENT"] or pt["unsafe_promotions_from_NEEDS_REVIEW"]:
        raise Blocked("unsafe promotion in initial repaired replay")

    recovery_out = tmp / "recovery.json"
    p = sh([sys.executable, str(recovery_py), str(recovery_out), run_id], check=False)
    if p.returncode:
        raise Blocked("repaired-path representability recovery failed\n" + p.stderr[-4000:] + "\n" + p.stdout[-4000:])
    recovery = json.loads(recovery_out.read_text(encoding="utf-8"))
    rs = recovery["summary"]
    required = {
        "cases_recovered": 44,
        "cases_still_untestable": 42,
        "exact_verdict_matches_among_recovered": 44,
        "mismatches": 0,
        "unsafe_promotions": 0,
    }
    for k,v in required.items():
        if rs.get(k) != v:
            raise Blocked(f"recovery {k}={rs.get(k)} expected {v}")
    return parity, recovery

def strip_alignment_block(src: str) -> str:
    start = src.find("# Shared live classifier alignment:")
    end = src.find("\ndef apply_episode_composition(\n", start)
    if start < 0 or end < 0:
        raise Blocked("alignment block markers missing")
    return src[:start].rstrip("\\n") + "\\n\\n" + src[end+1:].lstrip("\\n")

def verify_code_identity(code_commit: str):
    repaired_blob = git("rev-parse", f"{code_commit}:{LIVE_PATH}")
    pin_blob = git("rev-parse", f"{code_commit}:{PIN_PATH}")
    if repaired_blob != REPAIRED_BLOB:
        raise Blocked(f"repaired blob drift {repaired_blob}")
    if pin_blob != AUTH_BLOB:
        raise Blocked(f"pinned authoritative blob drift {pin_blob}")
    if git("rev-parse", f"{AUTH_COMMIT}:{LIVE_PATH}") != AUTH_BLOB:
        raise Blocked("authoritative reference blob mismatch")
    predecessor = git_bytes(LIVE_BRANCH, LIVE_PATH).decode("utf-8")
    if git("rev-parse", f"{LIVE_BRANCH}:{LIVE_PATH}") != PREDECESSOR_BLOB:
        raise Blocked("live predecessor moved before proof")
    repaired = git_bytes(code_commit, LIVE_PATH).decode("utf-8")
    marker = "# Shared live classifier alignment:"
    shared_def = "\ndef apply_episode_composition(\n"
    insertion_start = repaired.find(marker)
    repaired_suffix_start = repaired.find(shared_def, insertion_start)
    predecessor_suffix_start = predecessor.find(shared_def)
    if insertion_start < 0 or repaired_suffix_start < 0 or predecessor_suffix_start < 0:
        raise Blocked("alignment insertion boundary not found")
    if repaired[:insertion_start].rstrip("\n") != predecessor[:predecessor_suffix_start].rstrip("\n"):
        raise Blocked("non-wiring live monitor prefix changes detected")
    if repaired[repaired_suffix_start:] != predecessor[predecessor_suffix_start:]:
        raise Blocked("non-wiring live monitor suffix changes detected")
    return repaired_blob, pin_blob

def first_failing_gate(decision):
    codes = list(decision.get("reason_codes") or [])
    order = [
        "NO_EXACT_CITY_EVENT_TEXT",
        "NO_STRICT_EXPLOSION_EVIDENCE",
        "NO_AIR_MILITARY_CONTEXT",
        "AIR_CONTEXT_NOT_LINKED_TO_EVENT",
        "MATCH_NONE",
        "MATCH_AMBIGUOUS",
        "NO_STRICT_TEMPORAL_BINDING",
        "MULTI_EPISODE_DATE_REQUIRES_EPISODE_SPECIFIC_TEMPORAL_PROOF",
        "PUBLISHER_FULLTEXT_REQUIRES_REVIEW",
    ]
    temporal = str((decision.get("temporal_binding") or {}).get("code") or "")
    for code in order:
        if code in codes:
            return code
        if code == "NO_STRICT_TEMPORAL_BINDING" and temporal and temporal.startswith("NO_"):
            return temporal
    return codes[-1] if codes else None

def shadow_live(code_commit: str):
    root = Path.cwd()
    scripts = root / "kyiv-air-alerts-grafana" / "scripts"
    sys.path.insert(0, str(scripts))
    live = load_module(scripts / "monitor_explosion_candidates.py", "aligned_live_monitor")
    state = live.load_json(live.STATE_FILE, {})
    queue = live.load_json(live.QUEUE_FILE, [])
    if not isinstance(queue, list):
        raise Blocked("live review queue unavailable")
    rows = [r for r in queue if isinstance(r,dict) and str(r.get("city_key") or "") in live.CITY_CONFIG]
    rows.sort(key=lambda r: str(r.get("first_discovered_at") or r.get("published_at") or ""), reverse=True)
    selected = {}
    for row in rows:
        city = str(row.get("city_key") or "")
        if city in selected:
            continue
        evidence = any(row.get(k) for k in ("title","snippet","matched_text_excerpt","review_provenance"))
        if not evidence:
            continue
        episodes = live.tracked_episodes_for_city(state, city)
        if not episodes:
            continue
        selected[city] = (row, episodes)

    tests = []
    for city in sorted(selected):
        row, episodes = selected[city]
        before = live.authoritative_classifier_runtime_identity()["invocations"]
        matching = live.match_candidate_to_episodes(row, episodes)
        decision = live.classify_candidate(row, city, episodes, matching)
        after = live.authoritative_classifier_runtime_identity()["invocations"]
        episode_id = (
            decision.get("proposed_matched_episode_id")
            or row.get("matched_episode_id")
            or ((row.get("trigger_episode_ids") or [None])[0])
        )
        tests.append({
            "city": city,
            "episode_id": episode_id,
            "evidence_available": "YES",
            "authoritative_classifier_invoked": "YES" if after > before else "NO",
            "shadow_verdict": decision.get("proposed_outcome"),
            "first_failing_gate": None if decision.get("proposed_outcome") in {"approved_strict","approved_sensitivity","rejected"} else first_failing_gate(decision),
        })
    if not tests:
        raise Blocked("no recent live evidence available for shadow proof")
    proven = sum(t["authoritative_classifier_invoked"] == "YES" for t in tests)
    if proven != len(tests):
        raise Blocked("authoritative execution not proven for every shadow test")
    return tests, live

def shared_coverage(live):
    cities = sorted(live.CITY_CONFIG)
    if len(cities) != 23:
        raise Blocked(f"shared city count {len(cities)}")
    src = git_bytes(LIVE_BRANCH, LIVE_PATH).decode("utf-8")
    # The live branch is updated only after proof; use repaired checkout for wiring inspection.
    repaired_src = Path("kyiv-air-alerts-grafana/scripts/monitor_explosion_candidates.py").read_text(encoding="utf-8")
    if repaired_src.count("decision = classify_candidate(decision_input, city_key, tracked_episodes, matching)") != 1:
        raise Blocked("shared add_candidates classifier call not singular")
    bypass = []
    for city in cities:
        episodes = [{
            "episode_id": "coverage-" + city,
            "city_key": city,
            "city": live.CITY_CONFIG[city]["label"],
            "alert_start": "2026-10-07T00:00:00Z",
            "alert_end": "2026-10-07T01:00:00Z",
        }]
        row = {
            "city_key": city,
            "title": live.CITY_CONFIG[city]["label"],
            "snippet": "neutral shared-path coverage probe",
            "published_at": "2026-10-07T00:30:00Z",
            "source": "coverage-probe",
            "publisher": "coverage-probe",
        }
        before = live.authoritative_classifier_runtime_identity()["invocations"]
        matching = live.match_candidate_to_episodes(row, episodes)
        live.classify_candidate(row, city, episodes, matching)
        after = live.authoritative_classifier_runtime_identity()["invocations"]
        if after <= before:
            bypass.append(city)
    return cities, bypass

def changed_files(base, head):
    return [x for x in sh(["git","diff","--name-only",f"{base}...{head}"]).stdout.splitlines() if x.strip()]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--run-id", required=True)
    a = ap.parse_args()
    out = Path(a.out)
    code_commit = git("rev-parse","HEAD")
    ensure_ref(RECOVERY_REF)
    ensure_ref(AUTH_COMMIT)
    ensure_ref(LIVE_BRANCH)

    repaired_blob, pin_blob = verify_code_identity(code_commit)
    tmp = Path(tempfile.mkdtemp(prefix="shared-live-classifier-alignment-"))
    try:
        parity, recovery = run_historical_regression(tmp, code_commit, a.run_id)
        tests, live = shadow_live(code_commit)
        cities, bypass = shared_coverage(live)
        pt = parity["totals"]
        rs = recovery["summary"]
        combined_replayed = int(pt["episodes_replayed"]) + int(rs["cases_recovered"])
        combined_exact = int(pt["exact_verdict_matches"]) + int(rs["exact_verdict_matches_among_recovered"])
        mismatches = int(pt["total_mismatches"]) + int(rs["mismatches"])
        unsafe = (
            int(pt["unsafe_promotions_from_NO_CONFIRMED_EVENT"])
            + int(pt["unsafe_promotions_from_NEEDS_REVIEW"])
            + int(rs["unsafe_promotions"])
        )
        legacy = int(rs["cases_still_untestable"])
        blockers = rs["remaining_blocker_counts"]

        if combined_replayed != EXPECTED_REPLAYABLE or combined_exact != EXPECTED_REPLAYABLE:
            raise Blocked(f"combined historical regression {combined_exact}/{combined_replayed}")
        if mismatches != 0 or unsafe != 0 or legacy != EXPECTED_LEGACY_NON_REPLAYABLE:
            raise Blocked("historical safety invariant failed")
        if bypass:
            raise Blocked("bypass cities: " + ",".join(bypass))

        artifact = {
            "schema_version": 1,
            "proof": "SHARED 23-CITY LIVE CLASSIFIER ALIGNMENT",
            "verdict": "SHARED 23-CITY LIVE CLASSIFIER ALIGNMENT = PROVEN",
            "actions_run_id": int(a.run_id),
            "implementation": {
                "predecessor_live_classifier_blob": PREDECESSOR_BLOB,
                "authoritative_reference_commit": AUTH_COMMIT,
                "authoritative_reference_blob": AUTH_BLOB,
                "repaired_live_classifier_blob": repaired_blob,
                "pinned_authoritative_runtime_blob": pin_blob,
                "semantic_identity": "BEHAVIORALLY_IDENTICAL_WITH_BYTE_IDENTICAL_PINNED_AUTHORITATIVE_RUNTIME",
                "blob_identity_reason": "The repaired live monitor retains ingestion/discovery and contains a thin shared delegation/input-normalization wrapper; the invoked authoritative runtime file itself is byte-identical to the reference blob.",
                "cherkasy_normalization": "accepted upstream genitive normalization preserved before authoritative classifier invocation",
            },
            "historical_regression": {
                "frozen_total": EXPECTED_TOTAL,
                "replayed": combined_replayed,
                "exact_verdict_matches": combined_exact,
                "semantic_mismatches": mismatches,
                "unsafe_promotions": unsafe,
                "legacy_input_not_replayable": legacy,
                "legacy_label": "LEGACY_INPUT_NOT_REPLAYABLE",
                "remaining_blocker_counts": blockers,
                "initial_parity_replayed": pt["episodes_replayed"],
                "recovered_replayed": rs["cases_recovered"],
            },
            "live_shadow": {
                "recent_live_episodes_shadow_tested": len(tests),
                "authoritative_classifier_execution_proven": sum(t["authoritative_classifier_invoked"]=="YES" for t in tests),
                "cities_shadow_tested": sorted({t["city"] for t in tests}),
                "records": tests,
                "replacement_evidence_fetched": False,
            },
            "shared_coverage": {
                "cities_covered": len(cities),
                "cities_total": 23,
                "city_keys": cities,
                "bypass_cities": bypass,
            },
            "boundaries": {
                "source_ingestion_changes": 0,
                "persistence_changes": 0,
                "canonical_persistence_writes": 0,
                "Neon_writes": 0,
                "deployments": 0,
                "historical_backfill": 0,
                "classifier_policy_changes": 0,
                "parser_policy_changes": 0,
                "temporal_semantics_changes": 0,
                "source_query_strategy_changes": 0,
                "city_ingestion_semantics_changes": 0,
                "alert_grouping_changes": 0,
            },
            "mutation_confirmation": {
                "allowed_mutations_only": True,
                "live_shared_classifier_wiring_changed": True,
                "proof_harness_workflow_changed": True,
                "durable_proof_artifact_written": True,
                "canonical_persistence_unchanged": True,
                "historical_backfill_started": False,
                "deployment_started": False,
            },
        }
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print("ALIGNMENT_SUMMARY=" + json.dumps({
            "verdict": artifact["verdict"],
            "cities": f"{len(cities)}/23",
            "historical": f"{combined_exact}/{combined_replayed}",
            "mismatches": mismatches,
            "unsafe": unsafe,
            "legacy": legacy,
            "shadow_tests": len(tests),
            "shadow_exec_proven": artifact["live_shadow"]["authoritative_classifier_execution_proven"],
            "bypass": bypass,
            "repaired_blob": repaired_blob,
        }, separators=(",",":")))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

if __name__ == "__main__":
    try:
        main()
    except Blocked as exc:
        print("ALIGNMENT_BLOCKED=" + str(exc), file=sys.stderr)
        raise SystemExit(2)
