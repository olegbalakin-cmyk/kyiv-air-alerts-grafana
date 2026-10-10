#!/usr/bin/env python3
"""Independent, offline-only Unit A A4 re-acceptance over frozen Git objects.
The producer manifest is NOT decoded until independent projections and partitions exist.
No database library, database URL, network client, classifier or discovery is used.
"""
from __future__ import annotations
import ast
import copy
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from urllib.parse import urlparse

BASE = "3268213ef1d59db8069a588ba1d6d115a98ea825"
BRANCH = "attack-event-unit-a-a4-independent-reacceptance-v5-2026-10-10"
OUT = Path("research/attack_event_execution_unit_a_a4_independent_reacceptance_v5_2026-10-10.json")
EXPECTED_PROJECTION = "7978087ad00f37d0d1eb9f4326a478d5760e79cd7f7a68ae2be39fc5211bffa3"
EXPECTED_DELTA = "6070b6dbfc03e16b5236aed5b3cb090fa066100857a9c4f7bed502d6bb294aa3"
MONITOR_BLOB = "778469b74c2aa807d851cf2c2ee35cf4aa785589"
PROJECT, NEON_BRANCH = "green-cake-44216048", "br-bold-mode-b5rub8pq"
POSITIVE = {"STRICT_EVENT_POSITIVE", "SENSITIVITY_EVENT_POSITIVE"}
DIST = {"STRICT_EVENT_POSITIVE": 9, "SENSITIVITY_EVENT_POSITIVE": 1,
        "NEEDS_REVIEW": 356, "NO_CONFIRMED_EVENT": 1347}
SIX = {"air_defense_context", "candidate_evidence", "controlled_blast_event_segments",
       "sensitivity_basis", "single_episode_day_inference", "strict_explosion_evidence"}
REQUIRED = {"exact_city", "strict_explosion", "event_types", "air_defense_context",
            "air_defense_action", "interception_claim", "air_military_context",
            "same_attack_context", "temporal_binding", "single_episode_day_inference",
            "controlled_blast_event_segments", "sensitivity_basis",
            "classification_episode_id", "candidate_evidence", "review_provenance_adapter"}
KEY_SHA = "ddf73127fa96c10b4882293cf8970a561d403d2b48a488c5a139ee5e8ae91a74"
REC_MAP_SHA = "3dd4706afb5b48b874d9fd47b9d8e88e61b3de6f8574a57629b9c51b57cb5f35"
SOURCE_MAP_SHA = "557bd96a2d5d0f8f337852965cb9ca9ead7c2d947f556c476d04aeffb13d7703"
PINS = {
 "producer": ("36a5989229ed5c1ad1cd07fbb61df5033af22681", "research/attack_event_execution_unit_a_shadow_persistence_gap_audit_resume3_2026-10-09.json", "d9bd54a946c3bb88faa0e351d18883eed7c44e60", "2e6a3b0b8ab0dec2ac5d38c996a71325cabd257d5b80864e32b6c47756667e55"),
 "snapshot": ("e41a704e9ebb0ff673d5d46510f805d668598df1", "research/attack_event_unit_a_independent_shadow_gap_state_evidence_2026-10-10.json", "ce31f699935a21dc3b6ab3213668fd324d7a3183", "8f6166a5cf2b79b669952b15beaa6f0b1bcc482d6fa0082284c2f4f201ab26cc"),
 "repaired": ("d8fe91fdbfdcf8d1b851a52358d7eb441308e0ee", "research/attack_event_execution_unit_a_classification_aggregation_repair_2026-10-09.json", "a53f665c4f4da26f0b0699939c3b165f376da047", "a61dfcb222c2973195de0d2929f76745935553f40eda8c0eb35e648e71921302"),
 "original": ("1422e8482303ec9262647ca55fef753a9aa2b3ea", "research/attack_event_execution_unit_a_classification_replay_2026-10-09.json", "4dfc8aa7132706e2a3a4febd655ffa0a2bd71640", "bacbc9e0473a9108b380a4c568115303da5cdb27def595acaf5e2691a6163042"),
 "a1": ("2d07c81147932d39cb3a9d9934830f6eb707ee37", "research/attack_event_execution_unit_a_materialized_inputs_2026-10-07.json", "52e89792352513664428da3a7fcb9b43f79f1ba1", "07148ac498a6f4251e356bbf24be0aa40ebf220dd39c5df7ec99177a6f7214cc"),
 "adapter": ("a0eb594dd4240d1d923ca5262725fc42f4807338", "research/attack_event_execution_unit_a_source_identity_adapter_proof_2026-10-09.json", "a7e6b992180bfef3dd640fcd9ef8eec8a6436af7", "568f98bafb7601fbceaaa5a576c5255c65324a00b94911500e85ec5dc2884891"),
 "cross": ("6a891372d4d59f9f2454123afcac2a21ef042d68", "research/attack_event_unit_a_crossbranch_authority_overlap_audit_2026-10-09.json", "4c228f800350ed74363747a9a93bdcae312a5c36", "3d63f49a118dcac3a2ef75db45e945cbc6f00a041b4f25ff8529c82cd95d9647"),
 "replay": ("41bec58604420333dc71910ec38f4a785f6b108e", "research/attack_event_unit_a_bounded_persistence_payload_replay_schema_repair_2026-10-09.json", "cb0192e6776cce44b056bb88bf5618541f1c9339", "d28d80e15251fed8aad7367748cda7ea3a75b37f45dcb9cd3b656a11db619317"),
 "persist": ("51adc76b715669e46e8c2c936906022d4d96ed44", "kyiv-air-alerts-grafana/scripts/attack_event_canonical_persistence.py", "0118ca9e5f1308173e657257f1b49fe91cc19fe1", None),
 "monitor": ("71cb6f6fbe856cc7b96759310fe9cc9c71cc0453", "kyiv-air-alerts-grafana/scripts/monitor_explosion_candidates.py", MONITOR_BLOB, None),
 "adapter_helper": ("a0eb594dd4240d1d923ca5262725fc42f4807338", ".github/proof/attack_event_unit_a_source_identity_adapter_proof.py", "83dd5279f4aeb17c8e06fe5bfaf143c07059efc2", None),
 "recovery_helper": ("41ee8d160c34145b9d9a51b9da095084cf342824", ".github/proof/attack_event_unit_a_frozen_persistence_payload_recovery.py", "1d0541bef22ced23c0028eda516cc6d13c55b869", None)
}
RAW = {}
QUEUE_BYTES = {}
class Gate(Exception):
 def __init__(self, code, example=None):
  super().__init__(code)
  self.code, self.example = code, example

def check(test, code, example=None):
 if not test: raise Gate(code, example)

def git(*args):
 p = subprocess.run(["git", *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    env=dict(os.environ, GIT_NO_LAZY_FETCH="1", GIT_TERMINAL_PROMPT="0"))
 check(p.returncode == 0, "FROZEN_GIT_OBJECT_UNAVAILABLE",
       {"command": list(args)[:2], "error": p.stderr.decode(errors="replace")[-200:]})
 return p.stdout

def digest(b): return hashlib.sha256(b).hexdigest()
def canonical(x): return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
def hashed(x): return digest(canonical(x))
def normal(x):
 if isinstance(x, datetime):
  check(x.tzinfo is not None, "NAIVE_TEMPORAL_VALUE")
  return x.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
 if isinstance(x, dict): return {k: normal(v) for k, v in x.items()}
 if isinstance(x, (list, tuple)): return [normal(v) for v in x]
 return x
def parse(k): return json.loads(RAW[k].decode("utf-8"))

def pure_functions(source, names, variables):
 tree = ast.parse(source.decode("utf-8"))
 functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
 check(set(names) <= set(functions), "PINNED_PURE_METHOD_MISSING", sorted(set(names)-set(functions))[:1])
 module = ast.fix_missing_locations(ast.Module(body=[copy.deepcopy(functions[n]) for n in names], type_ignores=[]))
 exec(compile(module, "pinned_semantic_primitive", "exec"), variables)
 return variables

def historical_module(name):
 with tempfile.TemporaryDirectory(prefix="unit_a_v5_") as directory:
  path = Path(directory)/(name+".py")
  path.write_bytes(RAW[name])
  spec = importlib.util.spec_from_file_location("frozen_"+name, path)
  mod = importlib.util.module_from_spec(spec)
  spec.loader.exec_module(mod)
  return mod

def report_new():
 return {"schema_version": 1, "kind": "unit_a_a4_independent_offline_reacceptance_v5",
   "branch": BRANCH, "execution_base_main": BASE, "run_id": os.getenv("GITHUB_RUN_ID"),
   "verdict": "ATTACK-EVENT EXECUTION UNIT A A4 CHECKPOINT ACCEPTANCE = BLOCKED",
   "A4_ACCEPTANCE_GATE": "FAIL", "A5_MANIFEST_ACCEPTED": "NO", "A5_REQUIRED": "UNKNOWN",
   "A5_AUTHORIZED": "NO", "first_failing_gate": None, "first_bounded_example": None,
   "phase_reached": "INIT", "immutable_inputs": {}, "primitive_evidence": {},
   "projection": {}, "parent_partition": {}, "classification_partition": {},
   "source_partition": {}, "event_partition": {}, "independent_mutations": {},
   "producer_comparison": {}, "delta": {}, "preconditions": {},
   "safety": {"neon_connections": 0, "sql_queries": 0, "db_writes": 0,
      "classifier_executions": 0, "matching_executions": 0,
      "composition_executions": 0, "discovery_executions": 0,
      "a5_executions": 0, "production_mutation": "NO"}}

def save(report):
 OUT.parent.mkdir(parents=True, exist_ok=True)
 OUT.write_bytes(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False).encode()+b"\n")

def verify_frozen(report):
 check(os.getenv("GITHUB_REF_NAME") == BRANCH, "WRONG_PROOF_BRANCH")
 check(git("merge-base", "HEAD", BASE).decode().strip() == BASE, "EXECUTION_BASE_ANCESTRY_CHANGED")
 for name, (commit, path, blob, sha) in PINS.items():
  actual_blob = git("rev-parse", commit+":"+path).decode().strip()
  check(actual_blob == blob, "FROZEN_BLOB_IDENTITY_MISMATCH", {"name": name, "expected": blob, "got": actual_blob})
  b = git("show", commit+":"+path)
  actual_sha = digest(b)
  if sha: check(actual_sha == sha, "FROZEN_BYTES_SHA256_MISMATCH",
                {"name": name, "expected": sha, "got": actual_sha})
  RAW[name] = b
  report["immutable_inputs"][name] = {"commit": commit, "path": path, "blob": blob, "sha256": actual_sha}
 rec = parse("replay")
 check(rec.get("verdict") == "ATTACK-EVENT UNIT A BOUNDED PERSISTENCE PAYLOAD REPLAY = PROVEN"
       and rec.get("A4_PAYLOAD_REPLAY_GATE") == "PASS", "RECOVERED_REPLAY_NOT_ACCEPTED")
 check(rec.get("determinism", {}).get("run_a_recovered_payload_sha256") == REC_MAP_SHA
       and rec.get("determinism", {}).get("run_b_recovered_payload_sha256") == REC_MAP_SHA,
       "RECOVERED_REPLAY_HASH_MISMATCH")
 check(rec.get("persistence_evidence", {}).get("payloads_sha256") == KEY_SHA
       and len(rec.get("recovered_decision_map", {})) == 1418, "RECOVERED_REPLAY_CARDINALITY_DRIFT")
 check(parse("cross").get("A5_CROSSBRANCH_GATE") == "PASS", "UNIT_A_CROSSBRANCH_AUTHORITY_DRIFT")
 adapter = parse("adapter")
 check(adapter.get("run_a_mapping_sha256") == SOURCE_MAP_SHA
       and adapter.get("run_b_mapping_sha256") == SOURCE_MAP_SHA, "FROZEN_SOURCE_IDENTITY_DRIFT")
 report["phase_reached"] = "A_FROZEN_BYTES_PASS"
 return rec, adapter

def primitive(report):
 data_a = parse("snapshot")
 check(data_a.get("OBJECT_STATE_EVIDENCE_GATE") == "PASS"
       and data_a.get("A4_ACCEPTANCE_GATE") == "NOT_RUN", "FROZEN_PRIMITIVE_SNAPSHOT_GATE")
 e = data_a["semantic_evidence"]["evidence"]
 expected = {"parents": 1713, "classifications": 1713, "sources": 1559, "events": 1713}
 sizes = {k: len(e.get(k, [])) for k in expected}
 check(sizes == expected and sum(sizes.values()) == 6698, "PRIMITIVE_COVERAGE_MISMATCH", sizes)
 identifiers = {
    "parents": lambda x: (x["classification_key"], x["episode_id"]),
    "classifications": lambda x: (x["classification_key"], x["episode_id"]),
    "sources": lambda x: x["source_link_key"],
    "events": lambda x: x["episode_id"]}
 for name in expected:
  ids = [identifiers[name](v) for v in e[name]]
  check(len(set(ids)) == len(ids), "DUPLICATE_PRIMITIVE_EVIDENCE_IDENTITY", {"type": name})
  check(len({canonical(v) for v in e[name]}) == len(e[name]), "DUPLICATE_PRIMITIVE_RECORD", {"type": name})
 hashes_a = {k: hashed(e[k]) for k in expected}
 data_b = parse("snapshot")
 e2 = data_b["semantic_evidence"]["evidence"]
 hashes_b = {k: hashed(e2[k]) for k in expected}
 combined_a = hashed(data_a["semantic_evidence"])
 combined_b = hashed(data_b["semantic_evidence"])
 check(hashes_a == hashes_b and combined_a == combined_b
       and combined_a == data_a["hashes"]["combined_run_a"]
       and combined_b == data_a["hashes"]["combined_run_b"], "PRIMITIVE_A_B_NONDETERMINISM",
       {"run_a": combined_a, "run_b": combined_b})
 report["primitive_evidence"] = {"counts": sizes, "total": 6698,
     "omissions": 0, "duplicate_evidence_identities": 0, "run_a_hashes": hashes_a,
     "run_b_hashes": hashes_b, "run_a_combined_sha256": combined_a,
     "run_b_combined_sha256": combined_b, "a_b_equality": "PASS"}
 report["phase_reached"] = "B_PRIMITIVE_EVIDENCE_PASS"
 return e

def projected_fresh(rec, adapter):
 # Never use the producer's projection, mutation list or A4 builder as derivation inputs.
 helper = historical_module("adapter_helper")
 recovery = historical_module("recovery_helper")
 a1, original, repaired = parse("a1"), parse("original"), parse("repaired")
 _, a1_episodes, candidate_store, refs = helper.decode_a1(a1)
 original_episodes, decisions, provenance = helper.verify_a3(original, a1_episodes)
 episodes = repaired["episode_results"]
 check(len(episodes) == 1713 and refs == 99663, "PROJECTED_A1_UNIVERSE_GAP")
 old_episodes = {v["alert_episode_uid"]: v for v in original_episodes}
 count = 0
 for ep in episodes:
  old = old_episodes.get(ep["alert_episode_uid"])
  check(old is not None, "REPAIRED_A3_UNKNOWN_EPISODE", ep["alert_episode_uid"])
  for f in ("episode_id", "city_key", "alert_start", "alert_end",
            "candidate_input_refs", "candidate_decision_refs", "composition_provenance"):
   check(ep.get(f) == old.get(f), "REPAIRED_A3_FROZEN_FIELD_CHANGE", {"id": ep["episode_id"], "field": f})
  positions = ep.get("target_related_candidate_positions") or []
  check([ep["candidate_decision_refs"][i] for i in positions]
        == ep["target_related_candidate_decision_refs"], "REPAIRED_A3_MEMBERSHIP_DRIFT", ep["episode_id"])
  count += len(positions)
 check(count == 1559, "REPAIRED_A3_CARDINALITY", count)
 byref = {k: v.get("candidate_id") for k, v in candidate_store.items()}
 scratch = {"recovery_target_counts": {}, "persistence_payload_construction": {},
            "smallest_deterministic_blocker_example": None}
 occurrences, bydecision, frozen_decisions = recovery.targets_build(scratch, repaired, original, byref)
 check(len(occurrences) == 1559 and len(bydecision) == 1418
       and len({v["alert_episode_uid"] for v in occurrences}) == 370,
       "RECOVERED_OCCURRENCE_CARDINALITY")
 check(frozen_decisions == {k: decisions[k] for k in frozen_decisions},
       "RECOVERED_DECISION_REF_DRIFT")
 recovered = rec["recovered_decision_map"]
 check(set(recovered) == set(bydecision), "RECOVERED_DECISION_REF_SET_DRIFT")
 monitor = pure_functions(RAW["monitor"],
    ["apply_matching_result", "classification_evidence_payload", "apply_classification_decision"], {})
 persist = pure_functions(RAW["persist"],
    ["canonical_json_bytes", "canonical_sha256", "_tuple_sha256", "_parse_dt",
     "utc_microseconds", "_normalized_source_content", "_source_timestamp",
     "_telegram_identity", "_event_time_from_evidence", "_source_row",
     "_review_provenance"],
    {"hashlib": hashlib, "json": json, "datetime": datetime, "timezone": timezone,
     "urlparse": urlparse, "SOURCE_LINK_KEY_VERSION": "attack-event-source-link-key-v1",
     "MONITOR_RELATIVE_PATH": PINS["monitor"][1], "PersistenceContractError": ValueError,
     "Any": object})
 payloads = {}
 hashrows = []
 for occurrence in occurrences:
  dr = occurrence["decision_ref"]
  found, v = recovered[dr], bydecision[dr]
  check(found.get("candidate_input_ref") == v["candidate_input_ref"]
        and found.get("candidate_id") == v["candidate_id"]
        and found.get("frozen_a3_parity_status") == "EXACT_MATCH",
        "RECOVERED_IDENTITY_MISMATCH", dr)
  six = found.get("recovered_fields") or {}
  check(set(six) == SIX, "RECOVERED_SIX_FIELD_SCHEMA_MISMATCH", dr)
  decision = {**copy.deepcopy(frozen_decisions[dr]), **copy.deepcopy(six)}
  payload = monitor["classification_evidence_payload"](decision)
  check(set(payload) == REQUIRED, "CANONICAL_EVIDENCE_PAYLOAD_SCHEMA_MISMATCH", dr)
  payloads[dr] = payload
  hashrows.append({"occurrence": occurrence, "evidence_sha256": hashed(payload)})
 check(len(hashrows) == 1559 and hashed(hashrows) == KEY_SHA,
       "RECOVERED_EVIDENCE_PAYLOAD_HASH_MISMATCH", {"got": hashed(hashrows)})
 frozen_queues = {(v["commit"], v["path"]): v for v in adapter["frozen_queue_inputs"]}
 check(len(frozen_queues) == 89, "SOURCE_QUEUE_AUTHORITY_MISSING")
 output = {"classifications": [], "events": [], "sources": []}
 composition_count = 0
 for ep in episodes:
  uid, eid, city = ep["alert_episode_uid"], ep["episode_id"], ep["city_key"]
  ref_ids, decision_ids = ep["candidate_input_refs"], ep["candidate_decision_refs"]
  related = []
  positions = sorted(ep.get("target_related_candidate_positions") or [])
  if positions:
   metadata = provenance[uid]["evidence_provenance"]
   qi = metadata.get("collection_queue_identity") or {}
   pair = (str(qi.get("commit") or ""), str(qi.get("path") or ""))
   expected = frozen_queues.get(pair)
   check(expected is not None, "QUEUE_IDENTITY_NOT_FROZEN", {"episode": eid, "queue": pair})
   if pair not in QUEUE_BYTES:
    q = git("show", pair[0]+":"+pair[1])
    check(git("rev-parse", pair[0]+":"+pair[1]).decode().strip() == expected["blob"]
          and digest(q) == expected["sha256"], "QUEUE_BYTES_DRIFT", {"queue": pair})
    QUEUE_BYTES[pair] = q
   selected = helper.selected_queue_rows(json.loads(QUEUE_BYTES[pair]), eid,
                                         metadata.get("followup_72h_checked_at"))
   check(len(selected) == len(ref_ids), "QUEUE_SELECTION_CARDINALITY_DRIFT", {"episode": eid})
   for i in positions:
    dr, cref = decision_ids[i], ref_ids[i]
    cand, source = candidate_store[cref], selected[i]
    check(cand["candidate_id"] == source.get("candidate_id") == bydecision[dr]["candidate_id"]
          and persist["_normalized_source_content"](cand) ==
              persist["_normalized_source_content"](source),
          "SOURCE_CONTENT_IDENTITY_DRIFT", {"episode": eid, "decision_ref": dr})
    row = copy.deepcopy(source)
    decision = {**copy.deepcopy(decisions[dr]), **copy.deepcopy(recovered[dr]["recovered_fields"])}
    monitor["apply_classification_decision"](row, decision, copy.deepcopy(decisions[dr]["matching"]))
    check(row["classification_evidence"] == payloads[dr], "DECISION_PAYLOAD_LOSS", dr)
    related.append((row, dr, cref))
  composition = ep.get("composition_provenance")
  if composition is not None:
   composition_count += 1
   anchor = str(composition.get("anchor_candidate_id") or "")
   matches = [x[0] for x in related if x[0].get("candidate_id") == anchor]
   check(len(matches) == 1 and ep["verdict"] == "STRICT_EVENT_POSITIVE"
         and composition.get("final_composed_verdict") == "approved_strict"
         and not ep.get("direct_strict_contributor_refs"),
         "FROZEN_COMPOSITION_PROVENANCE_DRIFT", {"episode": eid})
   row = matches[0]
   row["status"] = "approved_strict"
   row["matched_episode_id"] = eid
   row["composition_provenance"] = copy.deepcopy(composition)
   codes = list(row.get("classification_reason_codes") or [])
   for code in composition.get("reason_codes") or []:
    if code not in codes: codes.append(code)
   row["classification_reason_codes"] = codes
   row["review_note"] = "episode-level composed strict classification"
  rows = [x[0] for x in related]
  start = persist["utc_microseconds"](ep["alert_start"])
  end = persist["utc_microseconds"](ep["alert_end"])
  check(start < end, "PROJECTED_INTERVAL_INVALID", eid)
  identities = []
  for row in sorted(rows, key=lambda r: (str(r.get("candidate_id") or ""),
                                         str(r.get("url") or ""), str(r.get("title") or ""))):
   observation = str(row.get("candidate_id") or "").strip()
   check(bool(observation), "PROJECTED_OBSERVATION_ID_MISSING", eid)
   identities.append([observation, persist["canonical_sha256"](
      persist["_normalized_source_content"](row))])
  identities.sort(key=lambda x: (x[0], x[1]))
  evidence_hash = persist["_tuple_sha256"](identities)
  review = persist["_review_provenance"](rows)
  review_hash = persist["canonical_sha256"](review) if review else None
  reason_codes = sorted({str(code) for row in rows for code in row.get("classification_reason_codes") or []
                         if str(code).strip()})
  event_types = sorted({str(t) for t in ep["event_types"] if str(t).strip()})
  qa_reasons = sorted({str(t) for t in ep["qa_reasons"] if str(t).strip()})
  verdict = ep["verdict"]
  tup = ["attack-event-classification-key-v2", city, eid, start, end, verdict,
      json.dumps(event_types, ensure_ascii=False, separators=(",", ":")), "MATERIALIZED",
      json.dumps(qa_reasons, ensure_ascii=False, separators=(",", ":")), MONITOR_BLOB,
      "historical-attack-event-air-defense-action-v2",
      "historical-attack-event-observation-v2", evidence_hash, review_hash]
  key = persist["_tuple_sha256"](tup)
  event_key = persist["_tuple_sha256"](
      ["attack-event-key-v1", "HISTORICAL_ALERT_EPISODE", city, eid, start, end])
  is_positive = verdict in POSITIVE
  tier = ("STRICT" if verdict == "STRICT_EVENT_POSITIVE" else
          "SENSITIVITY" if verdict == "SENSITIVITY_EVENT_POSITIVE" else None)
  sem = {"classification_key_version": "attack-event-classification-key-v2",
       "classification_key": key, "historical_episode_id": eid, "city_key": city,
       "alert_type": "AIR", "alert_start_at": start, "alert_end_at": end,
       "verdict": verdict, "is_event": is_positive, "positive_tier": tier,
       "event_types": event_types, "qa_reasons_state": "MATERIALIZED",
       "qa_reasons": qa_reasons, "classifier_reason_codes": reason_codes,
       "classifier_blob_sha": MONITOR_BLOB,
       "classifier_methodology_version": "historical-attack-event-air-defense-action-v2",
       "normalization_version": "historical-attack-event-observation-v2",
       "evidence_set_sha256": evidence_hash, "review_provenance_sha256": review_hash,
       "human_review_state": ("NEEDS_REVIEW" if verdict == "NEEDS_REVIEW" else
                              "REVIEWED_EVIDENCE" if review else "NONE"),
       "review_provenance": review, "composition_provenance": composition,
       "attack_event_key": event_key,
       "parent_identity": {"legacy_episode_id": eid, "city_key": city,
           "alert_type": "AIR", "episode_state": "closed",
           "canonicalization_version": "alert-canonicalization-v1",
           "start_at": start, "end_at": end}}
  output["classifications"].append(sem)
  if is_positive:
   output["events"].append({"attack_event_key": event_key,
      "attack_event_key_version": "attack-event-key-v1",
      "event_grain": "HISTORICAL_ALERT_EPISODE",
      "historical_episode_id": eid, "city_key": city, "alert_start_at": start,
      "alert_end_at": end, "desired_status": "ACTIVE",
      "desired_classification_key": key})
  origin = {"ref": "OFFLINE_AUDIT_NON_SEMANTIC_PLACEHOLDER",
      "commit": PINS["monitor"][0], "run_id": None, "monitor_blob": MONITOR_BLOB,
      "origin_provenance": {"kind": "offline_unit_a_projection_non_persisted",
        "repository": "olegbalakin-cmyk/kyiv-air-alerts-grafana",
        "ref": "OFFLINE_AUDIT_NON_SEMANTIC_PLACEHOLDER",
        "commit": PINS["monitor"][0], "monitor_path": PINS["monitor"][1],
        "monitor_blob": MONITOR_BLOB, "classifier_blob": MONITOR_BLOB,
        "classifier_methodology_version": "historical-attack-event-air-defense-action-v2",
        "normalization_version": "historical-attack-event-observation-v2"}}
  for row, dr, cref in related:
   made = persist["_source_row"](row, classification_key=key, origin=origin)
   source = {k: normal(v) for k, v in made.items() if k not in {
       "origin_git_ref", "origin_git_blob_sha", "origin_provenance",
       "origin_provenance_sha256", "origin_artifact_path", "raw_object_path"}}
   source["classification_key"] = key
   source["decision_ref"] = dr
   source["candidate_input_ref"] = cref
   output["sources"].append(source)
 check(composition_count == 3 and len(output["sources"]) == 1559,
       "FROZEN_MEMBERSHIP_OR_COMPOSITION_GAP", {"composition": composition_count,
                                               "source": len(output["sources"])})
 for name, field in (("classifications", "classification_key"),
                     ("sources", "source_link_key"), ("events", "attack_event_key")):
  output[name].sort(key=lambda x: x[field])
  ids = [row[field] for row in output[name]]
  check(len(set(ids)) == len(ids), "PROJECTED_DUPLICATE_IDENTITY", {"type": name})
 check(len(output["classifications"]) == 1713 and len(output["events"]) == 10
       and Counter(c["verdict"] for c in output["classifications"]) == DIST,
       "PROJECTED_VERDICT_DISTRIBUTION")
 return output

def check_projection(report, projected_a, projected_b, primitive_rows):
 ha = {k: hashed(projected_a[k]) for k in ("classifications", "sources", "events")}
 hb = {k: hashed(projected_b[k]) for k in ("classifications", "sources", "events")}
 ha["complete"], hb["complete"] = hashed(projected_a), hashed(projected_b)
 report["projection"] = {"counts": {k: len(v) for k, v in projected_a.items()},
                         "positive": 10, "nonpositive": 1703,
                         "verdict_distribution": dict(Counter(v["verdict"] for v in projected_a["classifications"])),
                         "run_a_sha256": ha, "run_b_sha256": hb,
                         "producer_declared_sha256": EXPECTED_PROJECTION}
 check(ha == hb, "PROJECTION_A_B_NONDETERMINISM", {"A": ha["complete"], "B": hb["complete"]})
 check(ha["complete"] == EXPECTED_PROJECTION, "PROJECTION_PRODUCER_HASH_MISMATCH",
       {"computed": ha["complete"], "expected": EXPECTED_PROJECTION})
 for category, proj_key, snap_key in [
      ("classifications", "classification_key", "classification_key"),
      ("sources", "source_link_key", "source_link_key"),
      ("events", "historical_episode_id", "episode_id")]:
  actual = {x[snap_key] for x in primitive_rows[category]}
  required = {x[proj_key] for x in projected_a[category]} if category != "events" else {
      x["historical_episode_id"] for x in projected_a["classifications"]}
  check(actual == required, "PRIMITIVE_EVIDENCE_OMISSION_OR_EXTRA",
        {"type": category, "missing_count": len(required-actual), "extra_count": len(actual-required)})
 report["phase_reached"] = "C_PROJECTION_PASS"

def persisted_match(want, got, fields):
 return [f for f in fields if normal(want.get(f)) != normal(got.get(f))]

CLASS_FIELDS = ("classification_key_version classification_key historical_episode_id city_key "
 "alert_start_at alert_end_at verdict is_event positive_tier event_types qa_reasons_state "
 "qa_reasons classifier_reason_codes classifier_blob_sha classifier_methodology_version "
 "normalization_version evidence_set_sha256 review_provenance_sha256").split()
SOURCE_FIELDS = ("source_link_key_version source_link_key observation_id source_family source_type "
 "source_type_state source_url telegram_channel telegram_message_id source_timestamp "
 "source_timestamp_state source_timestamp_raw event_timestamp_if_stated excerpt "
 "content_sha256 content_hash_basis observation_classification_outcome classification_episode_id "
 "evidence_payload retrieval_provenance").split()

def partition_from_frozen(projection, evidence):
 classes = projection["classifications"]
 sources = projection["sources"]
 desired_events = {x["historical_episode_id"]: x for x in projection["events"]}
 pidx = {x["classification_key"]: x for x in evidence["parents"]}
 cidx = {x["classification_key"]: x for x in evidence["classifications"]}
 sidx = {x["source_link_key"]: x for x in evidence["sources"]}
 eidx = {x["episode_id"]: x for x in evidence["events"]}
 parent_binding, part = {}, Counter()
 first = {"parents": None, "classifications": None, "sources": None, "events": None}
 for expected in classes:
  key, eid = expected["classification_key"], expected["historical_episode_id"]
  row = pidx[key]
  matches = [r for r in row["all_legacy_id_rows"] if all(
      normal(r.get(k)) == normal(v) for k, v in expected["parent_identity"].items())]
  check(canonical(matches) == canonical(row["matching_rows"]),
        "PRIMITIVE_PARENT_MATCH_SELECTION_MISMATCH", {"episode": eid})
  state = "exactly_one_parent" if len(matches) == 1 else "missing_parent" if not matches else "ambiguous_parent"
  part[state] += 1
  if state != "exactly_one_parent" and first["parents"] is None:
   first["parents"] = {"episode": eid, "state": state, "matches": len(matches)}
  else:
   if len(matches) == 1: parent_binding[key] = str(matches[0]["episode_uid"])
 check(part["missing_parent"] == 0 and part["ambiguous_parent"] == 0,
       "PARENT_BINDING_GAP", first["parents"])
 actions = {"classification_actions": [], "source_actions": [], "event_actions": []}
 classification_counts = Counter()
 tips = {}
 for want in classes:
  key, eid = want["classification_key"], want["historical_episode_id"]
  sample = cidx[key]
  exact = sample["exact_key_rows"]
  prior = sample["all_episode_rows"]
  if len(exact) > 1:
   classification_counts["SEMANTIC_CONFLICT"] += 1
   first["classifications"] = first["classifications"] or {"episode": eid, "reason": "duplicate exact classification key"}
   continue
  if exact:
   bad = persisted_match(want, exact[0], CLASS_FIELDS)
   bad_parent = str(exact[0]["alert_episode_uid"]) != parent_binding[key]
   if bad or bad_parent:
    classification_counts["SEMANTIC_CONFLICT"] += 1
    first["classifications"] = first["classifications"] or {"episode": eid, "fields": bad[:3], "parent": bad_parent}
    continue
   classification_counts["EXACT_PRESENT"] += 1
   tips[key] = str(exact[0]["classification_uid"])
   continue
  superseded = {str(x["supersedes_classification_uid"]) for x in prior
                if x["supersedes_classification_uid"] is not None}
  open_tips = [x for x in prior if str(x["classification_uid"]) not in superseded]
  if len(open_tips) > 1:
   classification_counts["MULTIPLE_CURRENT_TIPS"] += 1
   first["classifications"] = first["classifications"] or {"episode": eid, "reason": "multiple tips", "n": len(open_tips)}
   continue
  tip = open_tips[0] if open_tips else None
  state = "MISSING_WITH_PRIOR_REVISION" if tip else "MISSING_NO_PRIOR_REVISION"
  classification_counts[state] += 1
  actions["classification_actions"].append({
      "action": "INSERT_REVISION" if tip else "INSERT_INITIAL",
      "classification_key": key, "historical_episode_id": eid,
      "city_key": want["city_key"], "alert_episode_uid": parent_binding[key],
      "semantic_row_sha256": hashed(want), "semantic_row": want,
      "expected_tip_uid": str(tip["classification_uid"]) if tip else None,
      "expected_tip_key": tip["classification_key"] if tip else None,
      "expected_prior_verdict": tip["verdict"] if tip else None})
 check(classification_counts["SEMANTIC_CONFLICT"] == 0,
       "CLASSIFICATION_SEMANTIC_CONFLICT", first["classifications"])
 check(classification_counts["MULTIPLE_CURRENT_TIPS"] == 0,
       "MULTIPLE_CURRENT_CLASSIFICATION_TIPS", first["classifications"])
 check(sum(classification_counts.values()) == 1713, "CLASSIFICATION_PARTITION_NOT_EXHAUSTIVE")
 source_counts = Counter()
 for want in sources:
  key = want["source_link_key"]
  observed = sidx[key]["observed_rows"]
  if observed:
   changed = persisted_match(want, observed[0], SOURCE_FIELDS)
   foreign = str(observed[0]["parent_classification_key"]) != want["classification_key"]
   if len(observed) > 1 or changed or foreign:
    source_counts["CONFLICT"] += 1
    first["sources"] = first["sources"] or {"source_link_key": key, "fields": changed[:3], "wrong_parent": foreign}
    continue
   source_counts["EXACT"] += 1
  else:
   source_counts["MISSING"] += 1
   actions["source_actions"].append({
      "action": "INSERT_SOURCE_LINK", "source_link_key": key,
      "target_classification_key": want["classification_key"],
      "observation_id": want["observation_id"],
      "content_sha256": want["content_sha256"],
      "semantic_source_row_sha256": hashed(want), "semantic_source_row": want})
 check(source_counts["CONFLICT"] == 0, "SOURCE_SEMANTIC_CONFLICT", first["sources"])
 check(sum(source_counts.values()) == 1559, "SOURCE_PARTITION_NOT_EXHAUSTIVE")
 event_counts = Counter()
 for want in classes:
  eid, key = want["historical_episode_id"], want["classification_key"]
  rows = [x for x in eidx[eid]["observed_rows"] if x["city_key"] == want["city_key"]]
  if len(rows) > 1:
   event_counts["CONFLICT"] += 1
   first["events"] = first["events"] or {"episode": eid, "reason": "multiple events"}
   continue
  desired = desired_events.get(eid)
  event = rows[0] if rows else None
  if event:
   bad = (event["attack_event_key"] != want["attack_event_key"]
      or normal(event["alert_start_at"]) != want["alert_start_at"]
      or normal(event["alert_end_at"]) != want["alert_end_at"]
      or str(event["alert_episode_uid"]) != parent_binding[key])
   if bad:
    event_counts["CONFLICT"] += 1
    first["events"] = first["events"] or {"episode": eid, "reason": "stable event identity"}
    continue
  if not event:
   if desired:
    event_counts["INSERT_EVENT"] += 1
    actions["event_actions"].append({
       "action": "INSERT_EVENT", "attack_event_key": desired["attack_event_key"],
       "historical_episode_id": eid, "city_key": want["city_key"],
       "desired_classification_key": key,
       "semantic_precondition_hash": hashed({"absent": True, "episode": eid})})
   else: event_counts["NOOP_ABSENT_NONPOSITIVE"] += 1
   continue
  current = str(event["current_classification_uid"]) if event["current_classification_uid"] else None
  uid = tips.get(key)
  right_status = event["event_status"] == ("ACTIVE" if desired else "WITHDRAWN")
  right_pointer = uid is not None and current == uid
  if right_status and right_pointer:
   event_counts["NOOP_EXACT"] += 1
   continue
  action = "WITHDRAW_EVENT" if not desired and not right_status else "UPDATE_CURRENT_CLASSIFICATION_POINTER"
  event_counts[action] += 1
  actions["event_actions"].append({
     "action": action, "attack_event_key": want["attack_event_key"],
     "historical_episode_id": eid, "city_key": want["city_key"],
     "expected_current_db_state": {"event_uid": str(event["attack_event_uid"]),
          "event_status": event["event_status"], "current_classification_uid": current},
     "desired_classification_key": key,
     "semantic_precondition_hash": hashed({"event_key": event["attack_event_key"],
          "event_status": event["event_status"], "current_uid": current})})
 check(event_counts["CONFLICT"] == 0, "EVENT_SEMANTIC_CONFLICT", first["events"])
 check(sum(event_counts.values()) == 1713, "EVENT_PARTITION_NOT_EXHAUSTIVE")
 return parent_binding, dict(part), dict(classification_counts), dict(source_counts), dict(event_counts), actions

def action_id(action, category):
 key = {"classification_actions": "classification_key",
        "source_actions": "source_link_key",
        "event_actions": "attack_event_key"}[category]
 return (category, action["action"], action[key])

def flat(actions):
 return [(kind, action) for kind in ("classification_actions", "source_actions", "event_actions")
         for action in actions[kind]]

def compare_to_producer(independent, producer):
 missing = extra = duplicate_prod = duplicate_ind = mismatch = 0
 example = None
 for cat in ("classification_actions", "source_actions", "event_actions"):
  want, got = independent[cat], producer[cat]
  iw = {action_id(v, cat): v for v in want}
  pg = {action_id(v, cat): v for v in got}
  duplicate_ind += len(want)-len(iw)
  duplicate_prod += len(got)-len(pg)
  missing += len(set(iw)-set(pg))
  extra += len(set(pg)-set(iw))
  for key in sorted(set(iw)&set(pg)):
   if canonical(iw[key]) != canonical(pg[key]):
    mismatch += 1
    if example is None: example = {"identity": key, "independent_sha": hashed(iw[key]), "producer_sha": hashed(pg[key])}
  if example is None and set(iw) != set(pg):
   example = {"category": cat, "missing": sorted(set(iw)-set(pg))[:1],
              "extra": sorted(set(pg)-set(iw))[:1]}
 return {"missing_producer_actions": missing, "extra_producer_actions": extra,
         "producer_duplicates": duplicate_prod, "independent_duplicates": duplicate_ind,
         "semantic_mismatches": mismatch, "example": example}

def make_delta(projection, binding, actions):
 counts = Counter(v["action"] for kind, v in flat(actions))
 return {"schema_version": 1, "project": PROJECT, "branch": NEON_BRANCH,
      "parent_binding_sha256": hashed(sorted(binding.items())),
      "projection_sha256": hashed(projection),
      "classification_actions": actions["classification_actions"],
      "source_actions": actions["source_actions"],
      "event_actions": actions["event_actions"],
      "action_counts": dict(sorted(counts.items()))}

def precondition_check(projection, evidence, bindings, actions):
 class_e = {x["classification_key"]: x for x in evidence["classifications"]}
 source_e = {x["source_link_key"]: x for x in evidence["sources"]}
 event_e = {x["episode_id"]: x for x in evidence["events"]}
 class_k = {x["classification_key"] for x in projection["classifications"]}
 verified, errors, example = 0, 0, None
 for typ, item in flat(actions):
  okay = False
  if typ == "classification_actions":
   sample = class_e[item["classification_key"]]
   rows = sample["all_episode_rows"]
   superseded = {str(v["supersedes_classification_uid"]) for v in rows
                 if v["supersedes_classification_uid"] is not None}
   tips = [x for x in rows if str(x["classification_uid"]) not in superseded]
   t = tips[0] if len(tips) == 1 else None
   okay = (not sample["exact_key_rows"] and item["alert_episode_uid"] == bindings[item["classification_key"]]
       and item["semantic_row_sha256"] == hashed(item["semantic_row"])
       and (t is None) == (item["action"] == "INSERT_INITIAL")
       and item["expected_tip_uid"] == (str(t["classification_uid"]) if t else None)
       and item["expected_tip_key"] == (t["classification_key"] if t else None)
       and item["expected_prior_verdict"] == (t["verdict"] if t else None))
  elif typ == "source_actions":
   okay = (item["action"] == "INSERT_SOURCE_LINK"
      and not source_e[item["source_link_key"]]["observed_rows"]
      and item["target_classification_key"] in class_k
      and item["semantic_source_row_sha256"] == hashed(item["semantic_source_row"]))
  elif typ == "event_actions":
   sample = event_e[item["historical_episode_id"]]
   observed = sample["observed_rows"]
   if item["action"] == "INSERT_EVENT":
    okay = (not observed and item["semantic_precondition_hash"] ==
            hashed({"absent": True, "episode": item["historical_episode_id"]}))
   elif len(observed) == 1:
    e = observed[0]
    current = str(e["current_classification_uid"]) if e["current_classification_uid"] else None
    okay = (item["expected_current_db_state"] == {
       "event_uid": str(e["attack_event_uid"]), "event_status": e["event_status"],
       "current_classification_uid": current}
       and item["semantic_precondition_hash"] == hashed({
       "event_key": e["attack_event_key"], "event_status": e["event_status"],
       "current_uid": current}))
  verified += int(okay)
  if not okay:
   errors += 1
   if example is None: example = {"action": item["action"], "category": typ,
                                   "identity": action_id(item, typ)[2]}
 return {"checked": len(flat(actions)), "complete": verified, "incomplete": errors,
         "first_incomplete_example": example}

def main():
 r = report_new()
 try:
  rec, adapter = verify_frozen(r)
  evidence = primitive(r)
  a = projected_fresh(rec, adapter)
  b = projected_fresh(rec, adapter)
  check_projection(r, a, b, evidence)
  bindings_a, parents_a, classes_a, sources_a, events_a, actions_a = partition_from_frozen(a, evidence)
  r["parent_partition"] = parents_a
  r["classification_partition"] = classes_a
  r["source_partition"] = sources_a
  r["event_partition"] = events_a
  r["phase_reached"] = "D_G_INDEPENDENT_PARTITIONS_PASS"
  # The producer remains unread by this process until after every partition is complete.
  independent_dist = Counter(v["action"] for _, v in flat(actions_a))
  r["independent_mutations"] = {"counts": dict(sorted(independent_dist.items())),
                                "total": sum(independent_dist.values())}
  b_evidence = parse("snapshot")["semantic_evidence"]["evidence"]
  bindings_b, pb, cb, sb, eb, actions_b = partition_from_frozen(b, b_evidence)
  check((bindings_a, parents_a, classes_a, sources_a, events_a) ==
        (bindings_b, pb, cb, sb, eb)
        and canonical(actions_a) == canonical(actions_b), "MUTATION_A_B_NONDETERMINISM")
  r["phase_reached"] = "H_INDEPENDENT_MUTATION_SET_PASS"
  producer = parse("producer")
  manifest = producer.get("A5_frozen_delta_manifest")
  check(isinstance(manifest, dict), "PRODUCER_DELTA_MANIFEST_MISSING")
  for field in ("classification_actions", "source_actions", "event_actions"):
   check(isinstance(manifest.get(field), list), "PRODUCER_MANIFEST_ACTIONS_INVALID", field)
  diff = compare_to_producer(actions_a, manifest)
  r["producer_comparison"] = {**diff, "producer_total":
        sum(len(manifest[v]) for v in ("classification_actions", "source_actions", "event_actions"))}
  check(all(diff[k] == 0 for k in ("missing_producer_actions", "extra_producer_actions",
       "producer_duplicates", "independent_duplicates", "semantic_mismatches")),
       "PRODUCER_MANIFEST_DISAGREEMENT", diff["example"])
  r["phase_reached"] = "I_PRODUCER_COMPARISON_PASS"
  delta_a, delta_b = make_delta(a, bindings_a, actions_a), make_delta(b, bindings_b, actions_b)
  hash_a, hash_b = hashed(delta_a), hashed(delta_b)
  r["delta"] = {"run_a_sha256": hash_a, "run_b_sha256": hash_b,
      "producer_declared_sha256": EXPECTED_DELTA,
      "producer_artifact_sha256": producer.get("A5_DELTA_SHA256")}
  check(hash_a == hash_b, "DELTA_A_B_NONDETERMINISM",
       {"A": hash_a, "B": hash_b})
  check(hash_a == EXPECTED_DELTA == producer.get("A5_DELTA_SHA256"),
       "DELTA_PRODUCER_HASH_MISMATCH",
       {"A": hash_a, "producer": producer.get("A5_DELTA_SHA256")})
  r["phase_reached"] = "J_DELTA_SHA256_PASS"
  pre = precondition_check(a, evidence, bindings_a, actions_a)
  r["preconditions"] = pre
  check(pre["incomplete"] == 0 and pre["checked"] == pre["complete"] ==
        r["independent_mutations"]["total"], "STALE_STATE_PRECONDITION_INCOMPLETE",
        pre["first_incomplete_example"])
  r["phase_reached"] = "K_STALE_STATE_PRECONDITIONS_PASS"
  r["A4_ACCEPTANCE_GATE"] = "PASS"
  r["A5_MANIFEST_ACCEPTED"] = "YES"
  r["A5_REQUIRED"] = "YES" if pre["checked"] else "NO"
  r["verdict"] = "ATTACK-EVENT EXECUTION UNIT A A4 CHECKPOINT ACCEPTANCE = PROVEN"
  r["first_failing_gate"] = None
 except Gate as ex:
  r["first_failing_gate"] = ex.code
  r["first_bounded_example"] = normal(ex.example)
 except Exception as ex:
  r["first_failing_gate"] = "A4_HARNESS_EXECUTION_ERROR"
  r["first_bounded_example"] = {"type": type(ex).__name__, "message": str(ex)[:240]}
 finally:
  save(r)
  print("VERDICT="+r["verdict"])
  print("FIRST_FAILING_GATE="+str(r["first_failing_gate"]))
  print("PHASE_REACHED="+r["phase_reached"])
  print("A4_ACCEPTANCE_GATE="+r["A4_ACCEPTANCE_GATE"])
  print("A5_MANIFEST_ACCEPTED="+r["A5_MANIFEST_ACCEPTED"])
  print("A5_REQUIRED="+r["A5_REQUIRED"])
  print("A5_AUTHORIZED=NO")
  print("INDEPENDENT_ACTIONS="+str(r["independent_mutations"].get("total")))
  print("PRIMITIVE_COUNTS="+str(r["primitive_evidence"].get("counts")))
  print("PROJECTION_SHA_A="+str(r["projection"].get("run_a_sha256", {}).get("complete")))
  print("PROJECTION_SHA_B="+str(r["projection"].get("run_b_sha256", {}).get("complete")))
  print("DELTA_SHA_A="+str(r["delta"].get("run_a_sha256")))
  print("DELTA_SHA_B="+str(r["delta"].get("run_b_sha256")))
  print("NEON_CONNECTIONS=0 SQL_QUERIES=0 DB_WRITES=0 A5_EXECUTIONS=0")
  print("ARTIFACT_SHA256="+digest(OUT.read_bytes()))

if __name__ == "__main__":
 main()
