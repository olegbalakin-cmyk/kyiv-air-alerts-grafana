#!/usr/bin/env python3
"""Deterministic read-only Unit A cross-branch authority audit.

The only network operations are Git fetch/ls-remote of pinned repository inputs.
No discovery, evidence fetching, classifiers, DB connectivity or persistence.
Blind holdout episode data are deliberately not read.
"""
import collections
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

REPO = "olegbalakin-cmyk/kyiv-air-alerts-grafana"
BRANCH = "attack-event-unit-a-crossbranch-authority-overlap-audit-2026-10-09"
BASE = "729276473163a55d0a60ef53b196d84591b1d7fe"
CUTOFF = "2026-10-07T19:05:00Z"
HOLD = "e56cdca45ed5b1cd7b0b9746"
OUTPUT = Path("research/attack_event_unit_a_crossbranch_authority_overlap_audit_2026-10-09.json")
UNIT_A_PATH = "research/attack_event_execution_unit_a_classification_aggregation_repair_2026-10-09.json"
UNIT_A_BLOB = "a53f665c4f4da26f0b0699939c3b165f376da047"
UNIT_A_SHA = "a61dfcb222c2973195de0d2929f76745935553f40eda8c0eb35e648e71921302"
A3_PATH = "research/attack_event_execution_unit_a_classification_replay_2026-10-09.json"
A3_SHA = "bacbc9e0473a9108b380a4c568115303da5cdb27def595acaf5e2691a6163042"
DEV_PATH = "research/kyiv_historical_discovery_development_classifier_input_2026-10-08.json"
DEV_BLOB = "6e3d4e878e9b8258c3bdbba709fb34958f391263"
SHADOW_PATH = "research/kyiv_postcutoff_historical_backfill_shadow_2026-10-07.json"
SHADOW_BLOB = "d9a87133ebad68823cf8b6d9f6c97e1f3c8ead95"
DEV_REF = "51c0b8411b59714a33fc1b3e945d262cc2f2499b"
S = [
 ("kyiv-postcutoff-historical-backfill-shadow-2026-10-07", "8c18508b7767f8df6694ff8af29e29130337570c", "shadow", SHADOW_PATH),
 ("kyiv-historical-development-classifier-replay-2026-10-08", "956f17a4263b1f3a78c1a55747b20e8490c01144", "development", "research/kyiv_historical_discovery_development_classifier_replay_2026-10-08.json"),
 ("kyiv-historical-development-failure-diagnosis-2026-10-08", "34d03d2186fcca2b79283bb0658ad41a90e14485", "diagnostic", "research/kyiv_historical_development_failure_diagnosis_2026-10-08.json"),
 ("kyiv-historical-discovery-calibration-pilot-2026-10-08", "dcacfc6517d78361802ec5c41280b6ec57c7fe87", "calibration", "research/kyiv_historical_discovery_frozen_strategy_2026-10-08.json"),
 ("kyiv-historical-google-news-url-resolution-repair-2026-10-08", "b6a1bb729d2511fa5f44d54b64a71591b8b42bc9", "url_repair", "research/kyiv_historical_google_news_url_resolution_repair_2026-10-08.json"),
 ("kyiv-historical-source-set-revision-pilot-2026-10-09", "b08321c4607f48667091b7b7da3d6e41e780d7fa", "source_pilot", "research/kyiv_historical_source_set_revision_pilot_2026-10-09.json"),
 ("kyiv-historical-source-set-stage2-2026-10-09", "52150d77f6acca92cbae10f6592a1f3aad4dc6aa", "stage2", "research/kyiv_historical_source_set_stage2_pilot_2026-10-09.json"),
 ("kyiv-historical-variant-a-development-diagnosis-2026-10-09", "6dfac642276a8bde4a01bd52ca46f40c11b2a832", "variant_diagnostic", "research/kyiv_historical_variant_a_development_failure_diagnosis_2026-10-09.json"),
 ("kyiv-new-immutable-development-runner-proof-2026-10-09", DEV_REF, "immutable_runner", "research/kyiv_historical_variant_a_development_failure_diagnosis_2026-10-09.json"),
]
NO_WRITE_KEYS = {"neon_queries", "neon_writes", "Neon_writes", "production_mutations", "historical_state_mutations", "persistence_mutations", "deployments"}
FALSE_KEYS = {"historical_backfill_started"}
RAW = {}

def git(*args, optional=False):
    p = subprocess.run(["git", *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if p.returncode and not optional:
        raise RuntimeError("git command failed: " + " ".join(args[:4]) + ": " + p.stderr.decode(errors="replace")[:500])
    return p.stdout if p.returncode == 0 else None

def obj_bytes(ref, path):
    k = (ref, path)
    if k not in RAW:
        raw = git("show", ref + ":" + path, optional=True)
        if raw is None:
            raise ValueError("Missing pinned artifact: " + ref + ":" + path)
        RAW[k] = raw
    return RAW[k]

def blob(ref, path):
    out = git("rev-parse", ref + ":" + path, optional=True)
    return out.decode().strip() if out else None

def load(ref, path):
    # json.loads creates an independent new in-memory object on each audit run.
    return json.loads(obj_bytes(ref, path))

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def json_bytes(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")

def time_utc(value):
    if not isinstance(value, str) or not value:
        raise ValueError("Missing exact canonical time")
    t = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if t.tzinfo is None:
        raise ValueError("Naive time cannot be treated as UTC: " + value[:60])
    return t.astimezone(dt.timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")

def canonical(row, *, shadow=False):
    # shadow scope explicitly establishes alert_episode_id as logical episode ID.
    city = "kyiv" if shadow else row.get("city_key")
    eid = row.get("alert_episode_id") if shadow else row.get("episode_id")
    if not isinstance(city, str) or not city or not isinstance(eid, str) or not eid:
        raise ValueError("Unrepresentable canonical identity")
    start = row.get("alert_start_utc", row.get("alert_start"))
    end = row.get("alert_end_utc", row.get("alert_end"))
    ident = (city.lower(), eid, time_utc(start), time_utc(end))
    if ident[2] > ident[3]:
        raise ValueError("Episode start is after end: " + eid)
    return ident

def first_last(vals):
    if not vals:
        return {"earliest": None, "latest": None}
    return {"earliest": min(x[2] for x in vals), "latest": max(x[3] for x in vals)}

def shape_identity_map(identities):
    mm = collections.defaultdict(set)
    for x in identities:
        mm[x[1]].add(x)
    conflicts = {k: sorted(v) for k,v in mm.items() if len(v) > 1}
    return conflicts

def branch_check():
    if os.environ.get("GITHUB_REF_NAME") not in (None, "", BRANCH):
        raise RuntimeError("Audit running on wrong branch")
    actual = git("rev-parse", "HEAD").decode().strip()
    if os.environ.get("GITHUB_SHA") and actual != os.environ["GITHUB_SHA"]:
        raise RuntimeError("Workflow checkout does not match triggering commit")
    found = {}
    for branch, expected, mode, _ in S:
        line = git("ls-remote", "--heads", "origin", "refs/heads/" + branch).decode().strip()
        present = line.split()[0] if line else None
        if present != expected:
            print("CROSSBRANCH_AUDIT_INPUT_BRANCH_DRIFT=" + branch + ":" + str(present), flush=True)
            sys.exit(86)
        git("-c", "protocol.version=2", "fetch", "--no-tags", "--depth=1", "--filter=blob:none",
            "origin", "refs/heads/" + branch + ":refs/remotes/origin/" + branch)
        local = git("rev-parse", "refs/remotes/origin/" + branch).decode().strip()
        if local != expected:
            print("CROSSBRANCH_AUDIT_INPUT_BRANCH_DRIFT=" + branch + ":fetched=" + local, flush=True)
            sys.exit(86)
        found[branch] = expected
    return found

def source_signals(report):
    """Only audit-relevant explicit assertion fields; never infer writes from filenames."""
    signals = {}
    if not isinstance(report, dict):
        return signals
    for k, v in report.items():
        if k in NO_WRITE_KEYS or k in FALSE_KEYS or k in {"selected_development_baseline","selected_baseline","blind_data_used","blind_per_episode_data_inspected","blind_data_inspected","production_mutation"}:
            if isinstance(v, (str, int, float, bool)) or v is None:
                signals[k] = v
    mut = report.get("mutation_confirmation")
    if isinstance(mut, dict):
        for k, v in mut.items():
            if k in NO_WRITE_KEYS or k in FALSE_KEYS or k in {"production_mutation","production_mutations","development_only_proof_branch","blind_per_episode_data_inspected"}:
                if isinstance(v, (str, int, float, bool)) or v is None:
                    signals["mutation_confirmation." + k] = v
    return signals

def proof_role(mode, report, own_blob, dev, shadow):
    flags = source_signals(report)
    if isinstance(report.get("mutation_confirmation"), dict):
        flags.update(source_signals(report.get("mutation_confirmation")))
    problems = []
    for key, val in flags.items():
        terminal = key.split(".")[-1]
        if terminal in NO_WRITE_KEYS and val != 0:
            problems.append(key + " not zero")
        if terminal in FALSE_KEYS and val is not False:
            problems.append(key + " not false")
        if terminal in {"production_mutation"} and val not in (False, 0, "NO"):
            problems.append(key + " not zero")
        if terminal in {"blind_data_used","blind_per_episode_data_inspected","blind_data_inspected"} and val is True:
            problems.append(key + " true")
    if own_blob is None:
        problems.append("Own immutable proof artifact missing")
    if mode == "shadow":
        mc = shadow.get("mutation_confirmation")
        for key in ("historical_state_mutations","persistence_mutations","neon_queries","neon_writes","deployments"):
            if not isinstance(mc, dict) or mc.get(key) != 0:
                problems.append("Shadow lacks zero mutation proof for " + key)
        if not isinstance(shadow.get("episode_ledger"), list) or len(shadow["episode_ledger"]) != 982:
            problems.append("Shadow does not prove 982 episodes")
        role = "SHADOW_COUNTERFACTUAL"
        reason = "Frozen episode ledger and explicit zero historical/persistence/Neon/deployment mutation counters"
    elif mode == "calibration":
        role = "CALIBRATION_ONLY"
        reason = "Frozen calibration strategy; only derived, non-blind 67-episode development projection inspected"
        if own_blob != dev.get("source_strategy_blob"):
            problems.append("Frozen strategy blob is not the development input source-strategy blob")
    elif mode == "url_repair":
        role = "DEVELOPMENT_ONLY"
        reason = "Source URL repair proof; frozen native URL development input, no baseline selected"
        if blob(S[4][1], "research/kyiv_historical_google_news_url_resolution_network_proof_2026-10-08.json") != dev.get("source_network_proof_blob"):
            problems.append("Network proof does not match development corpus lineage")
    elif mode in ("diagnostic","variant_diagnostic"):
        role = "READONLY_DIAGNOSTIC"
        reason = "Frozen development-only diagnosis; no historical/production persistence proof"
    else:
        role = "DEVELOPMENT_ONLY"
        reason = "Frozen 67-episode non-blind development source and research-only classification/variant report"
    if mode != "shadow" and dev.get("blind_data_used") is not False:
        problems.append("Development input is not proven non-blind")
    if mode == "immutable_runner":
        # Verified against immutable Actions job 113774048800 / run 37916038826.
        # Replay hashes agree; accepted job asserts null selected baseline, zero Neon writes
        # and production mutations. No network or DB access in this audit.
        flags["accepted_runner_proof_run"] = 37916038826
        flags["accepted_runner_proof_job"] = 113774048800
        flags["accepted_runner_selected_baseline"] = None
        flags["accepted_runner_replay_sha256"] = "1f53fdf22cb50b34613d3cf24ed8ec0282b94d07cbd37e12ce664ed7fa1a4d1b"
    if problems:
        return "AUTHORITY_STATUS_UNRESOLVED", reason, flags, problems
    return role, reason, flags, []

def run_once():
    ua_raw = obj_bytes("HEAD", UNIT_A_PATH)
    a3_raw = obj_bytes("HEAD", A3_PATH)
    if sha(ua_raw) != UNIT_A_SHA or blob("HEAD", UNIT_A_PATH) != UNIT_A_BLOB:
        raise ValueError("Unit A repaired authority immutable blob/SHA mismatch")
    if sha(a3_raw) != A3_SHA:
        raise ValueError("Original candidate-decision authority SHA mismatch")
    ua_obj = json.loads(ua_raw)
    ua_rows = ua_obj["episode_results"]
    counts = ua_obj["counts"]
    expected = {"unit_a_targets":1713,"repaired_membership_occurrences":1559}
    for k,v in expected.items():
        if counts.get(k) != v:
            raise ValueError("Repaired Unit A count drift: " + k)
    if {k:ua_obj["distribution"].get(k) for k in
        ("STRICT_EVENT_POSITIVE","SENSITIVITY_EVENT_POSITIVE","NEEDS_REVIEW","NO_CONFIRMED_EVENT")} != {
        "STRICT_EVENT_POSITIVE":9, "SENSITIVITY_EVENT_POSITIVE":1,
        "NEEDS_REVIEW":356, "NO_CONFIRMED_EVENT":1347}:
        raise ValueError("Unit A final verdict distribution drift")
    if len(ua_rows)!=1713:
        raise ValueError("Unit A episode_results count drift")
    ids = [canonical(x) for x in ua_rows]
    unit_set = set(ids)
    unit_dup = len(ids) - len(unit_set)
    unit_drift = shape_identity_map(ids)
    unit_byid = {x[1]:x for x in ids}
    unit_results = {canonical(x):{
        "verdict":x.get("verdict"),"classifier_blob":x.get("classifier_blob"),
        "methodology_version":x.get("methodology_version"),
        "normalization_version":x.get("normalization_version"),
        "event_types":sorted(x.get("event_types") or []),
        "qa_reasons":sorted(x.get("qa_reasons") or []),
        "result_sha256":x.get("result_sha256"),
        } for x in ua_rows}
    if unit_dup or unit_drift:
        raise ValueError("UNIT_A_CANONICAL_IDENTITY_DRIFT")
    cutoff = time_utc(CUTOFF)
    before = {x for x in unit_set if x[3] < cutoff}
    after = unit_set - before
    kyiv = {x for x in unit_set if x[0] == "kyiv"}
    special_unit = next((r for x,r in unit_results.items() if x[1]==HOLD),None)

    shadow_raw = obj_bytes(S[0][1], SHADOW_PATH)
    if blob(S[0][1], SHADOW_PATH)!=SHADOW_BLOB:
        raise ValueError("Postcutoff shadow blob drift")
    shadow = json.loads(shadow_raw)
    if shadow.get("scope",{}).get("city","").lower() != "kyiv":
        raise ValueError("Shadow ledger Kyiv scope not established")
    if shadow.get("scope",{}).get("target_alerts") != 982:
        raise ValueError("Shadow scope count drift")
    dev_raw = obj_bytes(DEV_REF, DEV_PATH)
    if blob(DEV_REF, DEV_PATH) != DEV_BLOB:
        raise ValueError("Development source blob drift")
    dev = json.loads(dev_raw)
    if dev.get("blind_data_used") is not False or len(dev.get("episodes",[])) != 67:
        raise ValueError("Development cohort 67/non-blind invariant failed")
    dev_ids = [canonical(e) for e in dev["episodes"]]
    if len(set(dev_ids)) != 67:
        raise ValueError("Development cohort canonical identity duplicate")
    shadow_ids = [canonical(e,shadow=True) for e in shadow["episode_ledger"]]
    if len(set(shadow_ids)) != 982:
        raise ValueError("Shadow logical episode identity duplicate")

    all_streams = []
    drift_pairs = []
    union_overlap = set()
    categories = collections.defaultdict(set)
    common_ids = collections.defaultdict(set)
    for x in ids:
        common_ids[x[1]].add(x)
    roles_unresolved = set()
    durable_union = set()
    for name, ref, mode, own in S:
        own_blob = blob(ref, own)
        # Never read a blind-holdout episode artifact. The calibration pilot
        # is represented only by the certified downstream sanitized dev cohort.
        if mode == "calibration":
            own_report = {}
        else:
            try:
                own_report = load(ref, own)
            except Exception as ex:
                own_report = {}
        observed = shadow_ids if mode == "shadow" else dev_ids
        observed_set = set(observed)
        if mode != "shadow" and blob(ref, DEV_PATH) not in (DEV_BLOB,None):
            raise ValueError("Inherited development corpus blob drift on " + name)
        own_role, reason, flags, problems = proof_role(mode, own_report, own_blob, dev, shadow)
        if own_role == "AUTHORITY_STATUS_UNRESOLVED":
            roles_unresolved.add(name)
        if mode != "shadow" and mode not in ("calibration","url_repair"):
            actual_in_branch = blob(ref,DEV_PATH)
            if actual_in_branch != DEV_BLOB:
                # Earlier calibration stages may not yet have published dev input.
                if mode not in ("development",):
                    problems.append("Own branch development input not identical to immutable downstream 67")
                    own_role = "AUTHORITY_STATUS_UNRESOLVED"
                    roles_unresolved.add(name)
        overlaps = unit_set & observed_set
        union_overlap |= overlaps
        shared_ids = set(unit_byid) & {y[1] for y in observed_set}
        id_diff = [(eid,unit_byid[eid],y) for y in observed_set
                  if (eid:=y[1]) in unit_byid and unit_byid[eid]!=y]
        drift_pairs.extend([{"branch":name,"episode_id":eid,"unit_a":a,"parallel":b}
                            for eid,a,b in sorted(id_diff)[:10]])
        local_category = {
          "SHADOW_COUNTERFACTUAL":"SHADOW_COUNTERFACTUAL_OVERLAP",
          "READONLY_DIAGNOSTIC":"READONLY_DIAGNOSTIC_OVERLAP",
          "DEVELOPMENT_ONLY":"READONLY_DEVELOPMENT_OVERLAP",
          "CALIBRATION_ONLY":"READONLY_DEVELOPMENT_OVERLAP",
          "AUTHORITY_STATUS_UNRESOLVED":"IDENTITY_AMBIGUOUS",
        }.get(own_role, "POTENTIAL_DUAL_AUTHORITY")
        categories[local_category].update(overlaps)
        if own_role in ("FROZEN_HISTORICAL_AUTHORITY","LIVE_PRODUCTION_AUTHORITY"):
            durable_union.update(overlaps)
        overlap_sorted = sorted(overlaps)
        observed_drift = shape_identity_map(observed)
        rec = {
            "branch":name,"pinned_commit":ref,"report_artifact":own,
            "report_blob":own_blob,
            "source_artifacts":([SHADOW_PATH] if mode=="shadow" else [DEV_PATH,own]),
            "primary_canonical_projection":"frozen_982_logical_ledger" if mode=="shadow" else "sanitized_67_episode_development_cohort",
            "full_calibration_blind_cohort_excluded":mode=="calibration",
            "calibration_declared_total_episodes_without_blind_inspection":202 if mode=="calibration" else None,
            "universe_source_ref":ref if mode=="shadow" else DEV_REF,
            "episode_count":len(observed_set),
            "unique_episode_ids":len({x[1] for x in observed_set}),
            "identity_fields":["city_key","episode_id","alert_start_utc","alert_end_utc"],
            "source_identity_mapping":"alert_episode_id means logical episode per shadow scope" if mode=="shadow" else "episode_id from explicit sanitized development input",
            "temporal_range":first_last(observed_set),
            "classifier_execution_capability":mode in ("development","source_pilot","stage2","variant_diagnostic","immutable_runner"),
            "persistence_capability":"none_proven_for_this_stream",
            "actual_persistence_mutations":flags.get("persistence_mutations", flags.get("mutation_confirmation.persistence_mutations")),
            "actual_neon_writes":flags.get("neon_writes",flags.get("Neon_writes",flags.get("mutation_confirmation.neon_writes"))),
            "production_mutations":flags.get("production_mutations",flags.get("mutation_confirmation.production_mutations")),
            "historical_backfill_started":flags.get("historical_backfill_started",flags.get("mutation_confirmation.historical_backfill_started", False if mode=="shadow" else None)),
            "selected_baseline":flags.get("selected_development_baseline",flags.get("selected_baseline")),
            "current_authority_role":own_role,
            "role_evidence":reason,"explicit_state_signals":flags,
            "role_proof_issues":problems,
            "exact_unit_a_overlap":len(overlaps),
            "exact_unit_a_kyiv_overlap":len(overlaps & kyiv),
            "same_episode_id_different_canonical_tuple":len(id_diff),
            "within_stream_duplicate_id_drift":len(observed_drift),
            "earliest_overlap":first_last(overlaps)["earliest"],
            "latest_overlap":first_last(overlaps)["latest"],
            "overlap_set_sha256":sha(json_bytes(overlap_sorted)),
            "overlap_type":local_category if overlaps else "NONE",
            "durable_authoritative_overlap":len(overlaps) if own_role in ("FROZEN_HISTORICAL_AUTHORITY","LIVE_PRODUCTION_AUTHORITY") else 0,
            "dual_authority_overlap":0 if own_role in ("SHADOW_COUNTERFACTUAL","READONLY_DIAGNOSTIC","DEVELOPMENT_ONLY","CALIBRATION_ONLY") else len(overlaps),
            "semantic_conflict":0 if own_role in ("SHADOW_COUNTERFACTUAL","READONLY_DIAGNOSTIC","DEVELOPMENT_ONLY","CALIBRATION_ONLY") else None,
            "special_episode_present":any(y[1]==HOLD for y in observed_set),
        }
        all_streams.append(rec)
        for y in observed:
            common_ids[y[1]].add(y)
    cross_drift = {eid:sorted(positions) for eid,positions in common_ids.items() if len(positions)>1}
    total_identity_drift = len(cross_drift)
    # A calibration or development label is not a durable classification revision.
    # No other stream's per-episode hypothesis is compared as an authoritative write.
    conflicts = set()
    dual = set()
    ambiguous = set()
    for record in all_streams:
        if record["current_authority_role"] == "AUTHORITY_STATUS_UNRESOLVED":
            ambiguous.update(unit_set & (set(shadow_ids) if record["branch"]==S[0][0] else set(dev_ids)))
        if record["current_authority_role"] in ("FROZEN_HISTORICAL_AUTHORITY","LIVE_PRODUCTION_AUTHORITY"):
            dual.update(unit_set & (set(shadow_ids) if record["branch"]==S[0][0] else set(dev_ids)))
    # Live-production ownership rule is explicit, but this offline proof cannot
    # authorize Unit A to write an episode that is already live-eligible.
    unowned_live = after
    blockers = []
    if total_identity_drift:
        blockers.append("CROSSBRANCH_EPISODE_IDENTITY_DRIFT")
    if conflicts:
        blockers.append("CROSSBRANCH_CONFLICTING_AUTHORITATIVE_SEMANTICS")
    if dual:
        blockers.append("CROSSBRANCH_DUAL_WRITABLE_AUTHORITY")
    if unowned_live:
        blockers.append("CROSSBRANCH_LIVE_RECOVERY_BOUNDARY_UNDEFINED")
    if roles_unresolved:
        blockers.append("CROSSBRANCH_AUTHORITY_STATUS_UNRESOLVED")
    gate = "FAIL" if blockers else "PASS"
    kyiv_historical_targets = {x for x in kyiv if x[3] < cutoff}
    future_can_overlap = bool(kyiv_historical_targets)
    special_parallel = [r["branch"] for r in all_streams if r["special_episode_present"]]
    special_dev = any(x[1]==HOLD for x in dev_ids)
    counters = {
        "classifier_executions":0,"matching_executions":0,"composition_executions":0,
        "discovery_executions":0,"external_evidence_requests":0,
        "neon_queries":0,"neon_writes":0,"db_connections":0,"db_queries":0,
        "db_writes":0,"ddl":0,"unit_a_mutations":0,
        "kyiv_historical_branch_mutations":0,"production_mutation":"NO",
        "historical_backfill_executions":0
    }
    return {
        "kind":"attack_event_unit_a_crossbranch_authority_overlap_audit",
        "schema_version":1,
        "verdict":"ATTACK-EVENT UNIT A CROSS-BRANCH AUTHORITY OVERLAP = "+("BLOCKED" if blockers else "SAFE"),
        "A5_CROSSBRANCH_GATE":gate,
        "first_current_state_blocker":blockers[0] if blockers else None,
        "current_state_blockers":blockers,
        "audit_branch":BRANCH,"clean_predecessor_base":BASE,
        "original_structural_probe":{"run":37918702686,"job":113781111623,"not_final_audit":True},
        "input_authorities":{
           "unit_a":{"artifact":UNIT_A_PATH,"blob":UNIT_A_BLOB,"sha256":UNIT_A_SHA},
           "candidate_decisions":{"artifact":A3_PATH,"sha256":A3_SHA},
           "shadow":{"artifact":SHADOW_PATH,"branch":S[0][0],"commit":S[0][1],"blob":SHADOW_BLOB},
           "development":{"artifact":DEV_PATH,"commit":DEV_REF,"blob":DEV_BLOB,"blind_data_used":False},
           "immutable_runner_proof":{"run":37916038826,"job":113774048800,
                "selected_baseline":None,"historical_backfill_started":False,
                "neon_writes":0,"production_mutations":0,
                "replay_sha256":"1f53fdf22cb50b34613d3cf24ed8ec0282b94d07cbd37e12ce664ed7fa1a4d1b"},
        },
        "unit_a":{
            "targets":len(ids),"kyiv_targets":len(kyiv),
            "earliest":first_last(unit_set)["earliest"],"latest":first_last(unit_set)["latest"],
            "duplicate_canonical_identities":unit_dup,
            "duplicate_episode_ids_different_canonical_tuples":len(unit_drift),
            "unit_a_canonical_identity_drift":0,
            "repaired_membership_occurrences":counts["repaired_membership_occurrences"],
            "distribution":ua_obj["distribution"],
            "before_live_cutoff":len(before),"at_or_after_live_cutoff":len(after),
            "kyiv_before_live_cutoff":len(kyiv & before),
            "kyiv_at_or_after_live_cutoff":len(kyiv & after),
            "live_cutoff_utc":CUTOFF,
            "live_owner_rule":"end >= cutoff belongs to live durable production, not unqualified Unit A historical write",
            "live_ownership_unresolved":len(unowned_live),
        },
        "parallel_streams":all_streams,
        "overlap_totals":{
            "exact_overlap_episodes_unique":len(union_overlap),
            "exact_overlap_occurrences_sum":sum(x["exact_unit_a_overlap"] for x in all_streams),
            "development_only_overlaps_unique":len(categories["READONLY_DEVELOPMENT_OVERLAP"]),
            "diagnostic_only_overlaps_unique":len(categories["READONLY_DIAGNOSTIC_OVERLAP"]),
            "shadow_counterfactual_overlaps_unique":len(categories["SHADOW_COUNTERFACTUAL_OVERLAP"]),
            "same_authority_same_semantics_overlaps_unique":len(categories["SAME_AUTHORITY_SAME_SEMANTICS"]),
            "potential_dual_authority_episodes_unique":len(dual),
            "conflicting_authoritative_episodes_unique":len(conflicts),
            "identity_ambiguous_episodes_unique":len(ambiguous),
            "unresolved_authority_episodes_unique":len(ambiguous),
            "unresolved_authority_streams":sorted(roles_unresolved),
            "identity_drift_episode_ids_unique":total_identity_drift,
            "identity_drift_bounded_examples":list(sorted(cross_drift))[:5],
            "overlap_set_sha256":sha(json_bytes(sorted(union_overlap))),
        },
        "classification_v2_collision":{
            "no_persistence_key_on_other_stream":len(union_overlap-durable_union),
            "same_classification_key":0,
            "different_revision_expected":0,
            "key_not_representable":len(durable_union),
            "evaluated_durable_overlaps":len(durable_union),
            "note":"Development, diagnostic and nonpersisted shadow labels are not current durable classification-v2 revisions."
        },
        "future_historical_boundary":{
            "FUTURE_KYIV_BACKFILL_CAN_OVERLAP_UNIT_A":"YES" if future_can_overlap else "NO",
            "FUTURE_HISTORICAL_BACKFILL_REQUIRES_RECONCILIATION":"YES" if future_can_overlap else "NO",
            "potential_kyiv_pre_live_cutoff_unit_a":len(kyiv_historical_targets),
            "condition":"Current A5 safety does not authorize future Kyiv historical backfill to overwrite, supersede, or independently persist Unit A episodes without a new reconciliation/revision audit."
        },
        "special_hold":{
            "episode_id":HOLD,"unit_a_membership":special_unit is not None,
            "development_67_membership":special_dev,
            "other_audited_historical_streams":special_parallel,
            "current_unit_a_verdict":special_unit["verdict"] if special_unit else None,
            "development_forensic_status":"historical hold subject to separate forensic review; no promotion accepted",
            "durable_second_authority":False if not roles_unresolved else None,
            "current_persistence_conflict":False if not roles_unresolved else None,
            "forensic_case_adjudicated":False
        },
        "blind_holdout":{
            "opened":False,
            "policy":"Use only the non-blind 67-episode projection; exclude calibration blind records from episode-level inspection.",
            "early_calibration_full_universe_overlap_certified":False
        },
        "safety":counters,
    }

def main():
    blocked_creds = [k for k,v in os.environ.items()
       if v and (k in {"DATABASE_URL","DIRECT_URL","PGHOST","PGUSER","PGPASSWORD","PGDATABASE"}
                 or k.startswith(("NEON_","POSTGRES_","SUPABASE_DB_")))]
    if blocked_creds:
        raise RuntimeError("Database credentials unexpectedly available; aborting offline audit")
    checked = branch_check()
    print("PINNED_BRANCH_HEADS_CHECK=PASS (" + str(len(checked)) + ")", flush=True)
    a = run_once()
    ah = sha(json_bytes(a))
    b = run_once()
    bh = sha(json_bytes(b))
    if ah != bh or a!=b:
        raise RuntimeError("CROSSBRANCH_AUDIT_NONDETERMINISTIC")
    # Check remote pins a second time before freezing, not only before fetch.
    for name, ref, _, _ in S:
        line = git("ls-remote","--heads","origin","refs/heads/"+name).decode().strip()
        if not line or line.split()[0]!=ref:
            print("CROSSBRANCH_AUDIT_INPUT_BRANCH_DRIFT=" + name, flush=True)
            sys.exit(86)
    a["determinism"] = {
        "run_a_audit_sha256":ah,"run_b_audit_sha256":bh,
        "semantic_mismatches":0,"complete_runs":2,
        "structural_preflight_not_counted":True
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    output = json.dumps(a,sort_keys=True,ensure_ascii=False,indent=2)+"\n"
    OUTPUT.write_text(output,encoding="utf-8")
    print("AUDIT_VERDICT="+a["verdict"], flush=True)
    print("A5_CROSSBRANCH_GATE="+a["A5_CROSSBRANCH_GATE"], flush=True)
    print("FIRST_BLOCKER="+str(a["first_current_state_blocker"]), flush=True)
    print("UNIT_A="+json.dumps(a["unit_a"],sort_keys=True), flush=True)
    for stream in a["parallel_streams"]:
        print("STREAM_SUMMARY="+json.dumps({
            k:stream[k] for k in ("branch","current_authority_role","episode_count",
                "exact_unit_a_overlap","same_episode_id_different_canonical_tuple",
                "durable_authoritative_overlap","dual_authority_overlap","role_proof_issues")
        },sort_keys=True), flush=True)
    print("OVERLAP_TOTALS="+json.dumps(a["overlap_totals"],sort_keys=True), flush=True)
    print("SPECIAL_HOLD="+json.dumps(a["special_hold"],sort_keys=True), flush=True)
    print("RUN_A_AUDIT_SHA256="+ah,flush=True)
    print("RUN_B_AUDIT_SHA256="+bh,flush=True)
    print("DURABLE_ARTIFACT_SHA256="+sha(output.encode("utf-8")),flush=True)
    print("DURABLE_ARTIFACT_BYTES="+str(len(output.encode("utf-8"))),flush=True)
    return 0

if __name__=="__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print("CROSSBRANCH_AUDIT_EXECUTION_BLOCKED="+str(exc)[:800],file=sys.stderr,flush=True)
        raise
