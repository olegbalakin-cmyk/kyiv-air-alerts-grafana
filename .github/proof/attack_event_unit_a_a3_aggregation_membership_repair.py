#!/usr/bin/env python3
"""Bounded offline repair of frozen Unit A A3 episode aggregation membership.

No classifier, matching, composition, discovery, database, or production module
is imported. Reads only previously frozen repository artifacts and pinned code.
"""
from __future__ import annotations

import ast
import base64
import copy
from collections import Counter, defaultdict
import gzip
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from typing import Any

BASE = "87152684e694f8c0faed6e575c9f99c6d073423b"
BRANCH = "attack-event-unit-a-a3-aggregation-membership-repair-2026-10-09"
OUTPUT = Path("research/attack_event_execution_unit_a_classification_aggregation_repair_2026-10-09.json")
A3_PATH = "research/attack_event_execution_unit_a_classification_replay_2026-10-09.json"
A1_PATH = "research/attack_event_execution_unit_a_materialized_inputs_2026-10-07.json"
DIAG_PATH = "research/attack_event_execution_unit_a_membership_semantics_diagnostic_2026-10-09.json"
A3_COMMIT = "1422e8482303ec9262647ca55fef753a9aa2b3ea"
A3_BLOB = "4dfc8aa7132706e2a3a4febd655ffa0a2bd71640"
A3_SHA = "bacbc9e0473a9108b380a4c568115303da5cdb27def595acaf5e2691a6163042"
A1_BLOB = "52e89792352513664428da3a7fcb9b43f79f1ba1"
A1_SHA = "07148ac498a6f4251e356bbf24be0aa40ebf220dd39c5df7ec99177a6f7214cc"
A1_CORPUS_SHA = "9b3a1cb44dcf3ad18230309f4e49c3ad04dbe6837fc12ba4f8930bda1e812073"
DIAG_BLOB = "a381a057e84a981707948d0b4cbce250b6304634"
DIAG_SHA = "abe006c6f498239ac94ec4029afb55eec6259170053d6590ae34c748f3957ebf"
A3_HARNESS_COMMIT = "1422e8482303ec9262647ca55fef753a9aa2b3ea"
A3_HARNESS_PATH = ".github/proof/attack_event_unit_a_bounded_classification_replay.py"
A3_HARNESS_BLOB = "f72f08336f1ebebcc766841f7baf73d196ed092a"
HIST_COMMIT = "71cb6f6fbe856cc7b96759310fe9cc9c71cc0453"
HIST_PATH = "kyiv-air-alerts-grafana/scripts/run_historical_attack_event_backfill_batch.py"
HIST_BLOB = "cb2791bd309abacf4c3aae8fee0d1a8f038220b2"
PROD_COMMIT = "51adc76b715669e46e8c2c936906022d4d96ed44"
PROD_PATH = "kyiv-air-alerts-grafana/scripts/attack_event_canonical_persistence.py"
PROD_BLOB = "0118ca9e5f1308173e657257f1b49fe91cc19fe1"
CLASS_PATH = "kyiv-air-alerts-grafana/scripts/monitor_explosion_candidates.py"
CLASS_BLOB = "778469b74c2aa807d851cf2c2ee35cf4aa785589"
METHOD = "historical-attack-event-air-defense-action-v2"
NORM = "historical-attack-event-observation-v2"
MEMBERSHIP_RULE = "HISTORICAL_PRODUCTION_EPISODE_REFS_V1"
VERDICTS = ("STRICT_EVENT_POSITIVE", "SENSITIVITY_EVENT_POSITIVE",
            "NEEDS_REVIEW", "NO_CONFIRMED_EVENT")
ORIGINAL = {"STRICT_EVENT_POSITIVE":9, "SENSITIVITY_EVENT_POSITIVE":1,
            "NEEDS_REVIEW":443, "NO_CONFIRMED_EVENT":1260}
REPAIRED = {"STRICT_EVENT_POSITIVE":9, "SENSITIVITY_EVENT_POSITIVE":1,
            "NEEDS_REVIEW":356, "NO_CONFIRMED_EVENT":1347}
POSITIVE = set(VERDICTS[:2])
ALLOWED_QA = {"TEMPORAL_AMBIGUITY", "CITY_AMBIGUITY",
              "MULTI_INCIDENT_CONTEXT_RISK", "SOURCE_REFERENCE_INCOMPLETE",
              "PROVENANCE_REQUIRED"}


class RepairBlocked(RuntimeError):
    def __init__(self, gate: str, detail: Any = None):
        super().__init__(gate)
        self.gate, self.detail = gate, detail


def require(condition: bool, gate: str, detail: Any = None):
    if not condition:
        raise RepairBlocked(gate, detail)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canon(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def hobj(value: Any) -> str:
    return sha(canon(value))


def git(*args: str) -> bytes:
    p = subprocess.run(("git", *args), stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, check=False,
                       env=dict(os.environ, GIT_NO_LAZY_FETCH="1",
                                GIT_TERMINAL_PROMPT="0"))
    require(p.returncode == 0, "UNIT_A_PINNED_GIT_OBJECT_UNAVAILABLE",
            {"args":list(args)[:2], "stderr":p.stderr.decode("utf-8", "replace")[-180:]})
    return p.stdout


def gref(ref: str, path: str) -> str:
    return git("rev-parse", f"{ref}:{path}").decode("ascii").strip()


def pinned(ref: str, path: str, blob: str) -> bytes:
    require(gref(ref, path) == blob, "UNIT_A_PINNED_INPUT_BLOB_MISMATCH", path)
    return git("show", f"{ref}:{path}")


def verify_head_file(path: str, blob: str, file_sha: str) -> bytes:
    require(gref("HEAD", path) == blob, "UNIT_A_PINNED_INPUT_BLOB_MISMATCH", path)
    raw = Path(path).read_bytes()
    require(sha(raw) == file_sha, "UNIT_A_PINNED_INPUT_SHA256_MISMATCH", path)
    return raw


def only_functions(source: bytes, names: list[str], label: str, globals_: dict):
    tree = ast.parse(source.decode("utf-8"))
    defs = {item.name:item for item in tree.body if isinstance(item, ast.FunctionDef)}
    require(all(n in defs for n in names), "UNIT_A_PINNED_FUNCTION_MISSING", label)
    module = ast.fix_missing_locations(ast.Module(
        body=[copy.deepcopy(defs[n]) for n in names], type_ignores=[]))
    env = {"__builtins__":__builtins__, "Any":Any}
    env.update(globals_)
    exec(compile(module, label, "exec"), env)
    return env


def narrow_related(dec: dict, eid: str) -> bool:
    matching = dec.get("matching") or {}
    if str(dec.get("proposed_matched_episode_id") or "") == eid:
        return True
    if str(matching.get("matched_episode_id") or "") == eid:
        return True
    return eid in {str(x) for x in matching.get("matched_episode_ids") or [] if x}


def disabled_network():
    def forbidden(*_args, **_kwargs):
        raise RuntimeError("EXTERNAL_NETWORK_DISABLED")
    socket.socket.connect = forbidden
    socket.create_connection = forbidden
    socket.getaddrinfo = forbidden


def read_inputs():
    require(git("merge-base", "HEAD", BASE).decode().strip() == BASE,
            "UNIT_A_REPAIR_BASE_ANCESTRY_DRIFT")
    require(os.environ.get("GITHUB_REF_NAME") == BRANCH,
            "UNIT_A_REPAIR_UNEXPECTED_BRANCH")
    a3_raw = verify_head_file(A3_PATH, A3_BLOB, A3_SHA)
    a1_raw = verify_head_file(A1_PATH, A1_BLOB, A1_SHA)
    diag_raw = verify_head_file(DIAG_PATH, DIAG_BLOB, DIAG_SHA)
    require(gref(A3_COMMIT, A3_PATH) == A3_BLOB,
            "UNIT_A_ORIGINAL_A3_IDENTITY_DRIFT")
    harness = pinned(A3_HARNESS_COMMIT, A3_HARNESS_PATH, A3_HARNESS_BLOB)
    historical = pinned(HIST_COMMIT, HIST_PATH, HIST_BLOB)
    production = pinned(PROD_COMMIT, PROD_PATH, PROD_BLOB)
    pinned(HIST_COMMIT, CLASS_PATH, CLASS_BLOB)
    diag = json.loads(diag_raw)
    require(diag.get("verdict") ==
            "ATTACK-EVENT EXECUTION UNIT A MEMBERSHIP SEMANTICS DIAGNOSTIC = PROVEN"
            and diag.get("diagnostic_conclusion") == "A3_AGGREGATION_MEMBERSHIP_DRIFT = PROVEN",
            "UNIT_A_A3_REPAIR_DIAGNOSTIC_PARITY_MISMATCH", "diagnostic verdict")
    require(diag.get("frozen_authorities",{}).get("a3",{}).get("sha256") == A3_SHA,
            "UNIT_A_A3_REPAIR_DIAGNOSTIC_PARITY_MISMATCH", "original A3 authority")
    expected_old = only_functions(harness, ["related", "qa_for"],
                                  "frozen_A3_aggregation", {})
    expected_new = only_functions(harness, ["qa_for"],
                                  "frozen_A3_qa_with_narrow_membership",
                                  {"related":narrow_related})
    hist_ref = only_functions(historical, ["observation_episode_refs"],
                              "historical_episode_refs", {})["observation_episode_refs"]
    prod_ref = only_functions(production, ["_episode_refs"],
                              "production_episode_refs", {})["_episode_refs"]
    # Executable control: exactly three membership channels, no temporal/review channels.
    for field in ("matched_episode_id", "matched_episode_ids",
                  "proposed_matched_episode_id", "temporal_episode_id",
                  "temporal_supported_episode_ids", "review_target_episode_id"):
        d = {"matching":{"matched_episode_id":None, "matched_episode_ids":[]},
             "proposed_matched_episode_id":None,
             "temporal_binding":{"episode_id":None,"supported_episode_ids":[]},
             "review_provenance_adapter":{"target_episode_id":None}}
        if field == "matched_episode_id":
            d["matching"]["matched_episode_id"] = "target"
        elif field == "matched_episode_ids":
            d["matching"]["matched_episode_ids"] = ["target"]
        elif field == "proposed_matched_episode_id":
            d["proposed_matched_episode_id"] = "target"
        elif field == "temporal_episode_id":
            d["temporal_binding"]["episode_id"] = "target"
        elif field == "temporal_supported_episode_ids":
            d["temporal_binding"]["supported_episode_ids"] = ["target"]
        else:
            d["review_provenance_adapter"]["target_episode_id"] = "target"
        obs = {"classification_episode_id":d["proposed_matched_episode_id"],
               "candidate_matching":d["matching"]}
        item = {"classification_evidence":{
                   "classification_episode_id":d["proposed_matched_episode_id"]},
                "matched_episode_id":d["matching"]["matched_episode_id"],
                "matched_episode_ids":d["matching"]["matched_episode_ids"]}
        expected = field in ("matched_episode_id", "matched_episode_ids",
                             "proposed_matched_episode_id")
        require(narrow_related(d, "target") == expected
                and ("target" in hist_ref(obs)) == expected
                and ("target" in prod_ref(item)) == expected
                and expected_old["related"](d, "target"),
                "UNIT_A_A3_MEMBERSHIP_RULE_IDENTITY_DRIFT", field)
    return a3_raw, a1_raw, diag, expected_old, expected_new


def decode_a1(raw: bytes):
    doc = json.loads(raw)
    block = doc.get("corpus") or {}
    require(block.get("encoding") == "gzip+base64",
            "UNIT_A_A3_DECISION_ALIGNMENT_DRIFT", "A1 encoding")
    compressed = base64.b64decode(block["payload_base64"], validate=True)
    require(sha(compressed) == block.get("compressed_sha256")
            and len(compressed) == block.get("compressed_bytes"),
            "UNIT_A_A3_DECISION_ALIGNMENT_DRIFT", "compressed A1")
    expanded = gzip.decompress(compressed)
    require(sha(expanded) == A1_CORPUS_SHA
            and block.get("uncompressed_sha256") == A1_CORPUS_SHA,
            "UNIT_A_A3_DECISION_ALIGNMENT_DRIFT", "A1 decoded hash")
    corpus = json.loads(expanded)
    require(canon(corpus) + b"\n" == expanded,
            "UNIT_A_A3_DECISION_ALIGNMENT_DRIFT", "A1 serialization")
    store = {}
    for record in corpus["candidate_input_store"]:
        ref, row = record["sha256"], record["candidate_input"]
        require(sha(canon(row) + b"\n") == ref and ref not in store,
                "UNIT_A_A3_DECISION_ALIGNMENT_DRIFT", "A1 candidate store")
        store[ref] = row
    eps = corpus["episodes"]
    require(len(eps) == 1713 and len(store) == 3347,
            "UNIT_A_A3_DECISION_ALIGNMENT_DRIFT", "A1 cardinality")
    by_uid = {}
    occurrences = 0
    for e in eps:
        uid = e["alert_episode_uid"]
        require(uid not in by_uid, "UNIT_A_A3_DECISION_ALIGNMENT_DRIFT", "duplicate A1 uid")
        by_uid[uid] = e
        refs = e["candidate_input_refs"]
        occurrences += len(refs)
        require(all(r in store for r in refs),
                "UNIT_A_A3_DECISION_ALIGNMENT_DRIFT", "unresolved A1 ref")
        if not refs:
            require((e.get("evidence_provenance") or {}).get("accepted_empty_candidate_set") is True,
                    "UNIT_A_A3_DECISION_ALIGNMENT_DRIFT", "unaccepted empty candidates")
        logical = {"alert_episode_uid":uid,
                   "canonical_parent_identity":e.get("canonical_parent_identity"),
                   "classifier_episode_input":e.get("classifier_episode_input"),
                   "candidate_input_representation":e.get("candidate_input_representation"),
                   "candidate_inputs":[store[r] for r in refs],
                   "evidence_provenance":e.get("evidence_provenance")}
        require(sha(canon(logical) + b"\n") == e["materialized_input_sha256"],
                "UNIT_A_A3_DECISION_ALIGNMENT_DRIFT", "A1 episode materialization")
    require(occurrences == 99663, "UNIT_A_A3_DECISION_ALIGNMENT_DRIFT",
            {"candidate_occurrences":occurrences})
    return store, by_uid


def repair_once(a3_raw: bytes, a1_raw: bytes, old: dict, new: dict):
    # Fresh objects and independent references on every invocation.
    a3 = json.loads(a3_raw)
    store, a1_by = decode_a1(a1_raw)
    episodes = a3.get("episode_results") or []
    decisions = a3.get("candidate_decision_store") or {}
    require(a3.get("verdict") ==
            "ATTACK-EVENT EXECUTION UNIT A BOUNDED CLASSIFICATION REPLAY = FROZEN"
            and len(episodes) == 1713 and len(a1_by) == 1713,
            "UNIT_A_A3_DECISION_ALIGNMENT_DRIFT", "A3 target count/verdict")
    require(a3.get("distribution") == ORIGINAL
            and a3.get("authoritative_classifier",{}).get("blob") == CLASS_BLOB
            and a3.get("historical_builder",{}).get("blob") == HIST_BLOB
            and a3.get("methodology_version") == METHOD
            and a3.get("normalization_version") == NORM,
            "UNIT_A_A3_DECISION_ALIGNMENT_DRIFT", "frozen classification identity")
    before_corpus_sha = hobj(decisions)
    seen_uids = set()
    checked_pairs = set()
    original_dist, repaired_dist = Counter(), Counter()
    transitions = {a:{b:0 for b in VERDICTS} for a in VERDICTS}
    a3_members = narrow_members = removed_members = new_members = 0
    affected = qa_affected = temporal_removed = qa_added = 0
    review_affected = verdict_affected = event_diffs = composition_diffs = 0
    positive_intersect = positive_changed = positive_tier_changed = 0
    comp_intersect = strict_count = composed_count = sensitivity_count = 0
    positive_ref_before = positive_ref_after = 0
    qa_effect_codes = defaultdict(Counter)
    qa_distribution, event_distribution, city_distribution = Counter(), Counter(), defaultdict(Counter)
    results = []
    for ep in episodes:
        uid, eid, city = ep["alert_episode_uid"], str(ep["episode_id"]), str(ep["city_key"])
        require(uid not in seen_uids and uid in a1_by and eid,
                "UNIT_A_A3_DECISION_ALIGNMENT_DRIFT", "episode uid")
        seen_uids.add(uid)
        a1_episode = a1_by[uid]
        episode_input = a1_episode.get("classifier_episode_input") or {}
        for key in ("episode_id", "city_key", "alert_start", "alert_end"):
            require(ep[key] == episode_input.get(key),
                    "UNIT_A_A3_DECISION_ALIGNMENT_DRIFT", {"uid":uid,"field":key})
        refs, drefs = ep["candidate_input_refs"], ep["candidate_decision_refs"]
        require(refs == a1_episode["candidate_input_refs"] and len(refs) == len(drefs),
                "UNIT_A_A3_DECISION_ALIGNMENT_DRIFT", "ordered refs:"+uid)
        old_result = {k:v for k,v in ep.items() if k != "result_sha256"}
        require(hobj(old_result) == ep.get("result_sha256"),
                "UNIT_A_A3_DECISION_ALIGNMENT_DRIFT", "frozen result SHA:"+uid)
        resolved = []
        for candidate_ref, decision_ref in zip(refs, drefs):
            require(candidate_ref in store and decision_ref in decisions,
                    "UNIT_A_A3_DECISION_ALIGNMENT_DRIFT", "decision resolution:"+uid)
            pair = (candidate_ref,decision_ref)
            if pair not in checked_pairs:
                require(hobj({"candidate_ref":candidate_ref,
                              "decision":decisions[decision_ref]}) == decision_ref,
                        "UNIT_A_A3_DECISION_ALIGNMENT_DRIFT", "decision hash:"+decision_ref)
                checked_pairs.add(pair)
            resolved.append((store[candidate_ref], decisions[decision_ref]))
        broad_positions = [i for i,(_candidate,d) in enumerate(resolved)
                           if old["related"](d,eid)]
        narrow_positions = [i for i,(_candidate,d) in enumerate(resolved)
                            if narrow_related(d,eid)]
        broad = set(broad_positions)
        narrow = set(narrow_positions)
        missing = sorted(broad - narrow)
        added = sorted(narrow - broad)
        require(not added, "UNIT_A_A3_MEMBERSHIP_REPAIR_COUNT_MISMATCH", uid)
        require([drefs[i] for i in broad_positions] ==
                ep["target_related_candidate_decision_refs"],
                "UNIT_A_A3_DECISION_ALIGNMENT_DRIFT", "frozen broad membership:"+uid)
        original_qa = sorted({q for i in broad_positions
                              for q in old["qa_for"](resolved[i][1],eid,resolved[i][0])})
        qa = sorted({q for i in narrow_positions
                     for q in new["qa_for"](resolved[i][1],eid,resolved[i][0])})
        require(original_qa == ep["qa_reasons"] and set(qa).issubset(ALLOWED_QA),
                "UNIT_A_A3_DECISION_ALIGNMENT_DRIFT", "frozen QA:"+uid)
        old_strict = [drefs[i] for i in broad_positions
                      if resolved[i][1].get("proposed_outcome") == "approved_strict"
                      and str(resolved[i][1].get("proposed_matched_episode_id") or "") == eid]
        old_sens = [drefs[i] for i in broad_positions
                    if resolved[i][1].get("proposed_outcome") == "approved_sensitivity"
                    and str(resolved[i][1].get("proposed_matched_episode_id") or "") == eid]
        old_review = [drefs[i] for i in broad_positions
                      if resolved[i][1].get("proposed_outcome") == "needs_review"]
        require(old_strict == ep["direct_strict_contributor_refs"]
                and old_sens == ep["sensitivity_contributor_refs"]
                and old_review == ep["review_contributor_refs"],
                "UNIT_A_A3_DECISION_ALIGNMENT_DRIFT", "frozen contributors:"+uid)
        strict_positions = [i for i in narrow_positions
                            if resolved[i][1].get("proposed_outcome") == "approved_strict"
                            and str(resolved[i][1].get("proposed_matched_episode_id") or "") == eid]
        sens_positions = [i for i in narrow_positions
                          if resolved[i][1].get("proposed_outcome") == "approved_sensitivity"
                          and str(resolved[i][1].get("proposed_matched_episode_id") or "") == eid]
        review_positions = [i for i in narrow_positions
                            if resolved[i][1].get("proposed_outcome") == "needs_review"]
        strict = [drefs[i] for i in strict_positions]
        sensitivity = [drefs[i] for i in sens_positions]
        review = [drefs[i] for i in review_positions]
        comp = ep.get("composition_provenance")
        comp_ok = (isinstance(comp,dict)
                   and comp.get("final_composed_verdict") == "approved_strict"
                   and str(comp.get("target_episode_id") or "") == eid)
        if comp is not None:
            require(comp_ok and ep["verdict"] == "STRICT_EVENT_POSITIVE"
                    and not old_strict and not strict,
                    "UNIT_A_A3_AGGREGATION_REPAIR_REQUIRES_COMPOSITION_RERUN",uid)
            anchors = [i for i,(candidate,_decision) in enumerate(resolved)
                       if str(candidate.get("candidate_id") or "") ==
                       str(comp.get("anchor_candidate_id") or "")]
            composition_ids = {str(cid) for cid in comp.get("contributing_candidate_ids") or []}
            require(len(anchors) == 1 and bool(comp.get("anchor_candidate_id"))
                    and composition_ids
                    and composition_ids.issubset({str(c.get("candidate_id") or "")
                                                  for c,_d in resolved}),
                    "UNIT_A_A3_AGGREGATION_REPAIR_REQUIRES_COMPOSITION_RERUN",uid)
            comp_intersect += sum(str(resolved[i][0].get("candidate_id") or "")
                                  in composition_ids for i in missing)
            if any(str(resolved[i][0].get("candidate_id") or "")
                   in composition_ids for i in missing):
                raise RepairBlocked("UNIT_A_A3_AGGREGATION_REPAIR_REQUIRES_COMPOSITION_RERUN",uid)
            composed_count += 1
        if strict or comp_ok:
            verdict = "STRICT_EVENT_POSITIVE"
            if strict:
                strict_count += 1
                contrib = strict
                ev = list(dict.fromkeys(et for i in strict_positions
                                        for et in resolved[i][1].get("event_types") or []))
            else:
                contrib = list(ep["final_contributor_refs"])
                ev = list(ep["event_types"])
        elif sensitivity:
            verdict = "SENSITIVITY_EVENT_POSITIVE"
            sensitivity_count += 1
            contrib = sensitivity
            ev = list(dict.fromkeys(et for i in sens_positions
                                    for et in resolved[i][1].get("event_types") or []))
        elif review or qa:
            verdict, contrib, ev = "NEEDS_REVIEW", [], []
        else:
            verdict, contrib, ev = "NO_CONFIRMED_EVENT", [], []
        for i in missing:
            decision = resolved[i][1]
            temporal = decision.get("temporal_binding") or {}
            matching = decision.get("matching") or {}
            require(decision.get("proposed_outcome") == "needs_review"
                    and temporal.get("code") == "TEMPORAL_EXPLICIT_ALERT_RELATION_AMBIGUOUS_DATE"
                    and eid in {str(x) for x in temporal.get("supported_episode_ids") or [] if x}
                    and not (str(temporal.get("episode_id") or "") == eid)
                    and not (str((decision.get("review_provenance_adapter") or {}).get("target_episode_id") or "") == eid)
                    and not narrow_related(decision,eid),
                    "UNIT_A_A3_MEMBERSHIP_REPAIR_COUNT_MISMATCH", "unexplained removal:"+uid)
        a3_members += len(broad_positions)
        narrow_members += len(narrow_positions)
        removed_members += len(missing)
        new_members += len(added)
        if missing or added:
            affected += 1
            for code in set(original_qa) | set(qa):
                if code in original_qa and code in qa:
                    qa_effect_codes[code]["preserved"] += 1
                elif code in original_qa:
                    qa_effect_codes[code]["removed"] += 1
                else:
                    qa_effect_codes[code]["newly_added"] += 1
        if original_qa != qa:
            qa_affected += 1
            temporal_removed += int("TEMPORAL_AMBIGUITY" in original_qa
                                    and "TEMPORAL_AMBIGUITY" not in qa)
            qa_added += len(set(qa) - set(original_qa))
        if Counter(review) != Counter(old_review):
            review_affected += 1
        if verdict != ep["verdict"]:
            verdict_affected += 1
        if ev != ep["event_types"]:
            event_diffs += 1
        if comp != ep.get("composition_provenance"):
            composition_diffs += 1
        if any(drefs[i] in ep["final_contributor_refs"] for i in missing):
            positive_intersect += sum(drefs[i] in ep["final_contributor_refs"] for i in missing)
        if Counter(contrib) != Counter(ep["final_contributor_refs"]):
            positive_changed += 1
        if ep["verdict"] in POSITIVE and verdict in POSITIVE and verdict != ep["verdict"]:
            positive_tier_changed += 1
        positive_ref_before += len(ep["final_contributor_refs"])
        positive_ref_after += len(contrib)
        original_dist[ep["verdict"]] += 1
        repaired_dist[verdict] += 1
        transitions[ep["verdict"]][verdict] += 1
        city_distribution[city][verdict] += 1
        qa_distribution.update(qa)
        event_distribution.update(ev)
        repaired = copy.deepcopy(ep)
        repaired.update({
            "verdict":verdict,
            "event_types":ev,
            "qa_reasons":qa,
            "target_related_candidate_decision_refs":[drefs[i] for i in narrow_positions],
            "target_related_candidate_input_refs":[refs[i] for i in narrow_positions],
            "target_related_candidate_positions":narrow_positions,
            "direct_strict_contributor_refs":strict,
            "sensitivity_contributor_refs":sensitivity,
            "review_contributor_refs":review,
            "final_contributor_refs":contrib,
        })
        for field in ("alert_episode_uid", "episode_id", "city_key", "alert_start",
                      "alert_end", "candidate_input_refs", "candidate_decision_refs",
                      "composition_provenance", "classifier_blob",
                      "methodology_version", "normalization_version"):
            require(repaired[field] == ep[field],
                    "UNIT_A_A3_DECISION_ALIGNMENT_DRIFT", "frozen field:"+uid+":"+field)
        require(repaired["classifier_blob"] == CLASS_BLOB
                and repaired["methodology_version"] == METHOD
                and repaired["normalization_version"] == NORM,
                "UNIT_A_A3_DECISION_ALIGNMENT_DRIFT", "frozen episode version")
        repaired["related_membership_sha256"] = hobj([
            [i, refs[i], drefs[i]] for i in narrow_positions])
        repaired["result_sha256"] = hobj({k:v for k,v in repaired.items()
                                          if k != "result_sha256"})
        results.append(repaired)
    require(len(seen_uids) == 1713 and len(results) == 1713,
            "UNIT_A_A3_DECISION_ALIGNMENT_DRIFT", "episode alignment total")
    require(dict(original_dist) == ORIGINAL, "UNIT_A_A3_DECISION_ALIGNMENT_DRIFT",
            "original verdict distribution")
    require((a3_members,narrow_members,removed_members,new_members,affected) ==
            (1741,1559,182,0,130),
            "UNIT_A_A3_MEMBERSHIP_REPAIR_COUNT_MISMATCH",
            [a3_members,narrow_members,removed_members,new_members,affected])
    require(dict(repaired_dist) == REPAIRED,
            "UNIT_A_A3_REPAIR_DIAGNOSTIC_PARITY_MISMATCH",
            "repaired distribution")
    require((qa_affected,temporal_removed,qa_added,review_affected,
             verdict_affected) == (117,117,0,130,87),
            "UNIT_A_A3_REPAIR_DIAGNOSTIC_PARITY_MISMATCH",
            "QA/review/verdict effects")
    require((positive_intersect,positive_changed,positive_tier_changed,
             comp_intersect,event_diffs,composition_diffs,
             positive_ref_before,positive_ref_after,
             composed_count) == (0,0,0,0,0,0,18,18,3),
            "UNIT_A_A3_POSITIVE_DISPOSITION_CHANGED",
            "positive/composition guards")
    require(strict_count + composed_count == 9 and sensitivity_count == 1,
            "UNIT_A_A3_POSITIVE_DISPOSITION_CHANGED", "positive tier counts")
    after_corpus_sha = hobj(decisions)
    require(before_corpus_sha == after_corpus_sha,
            "UNIT_A_A3_DECISION_ALIGNMENT_DRIFT", "candidate corpus mutated")
    require(all(ep["result_sha256"] ==
                hobj({k:v for k,v in ep.items() if k != "result_sha256"})
                for ep in results),
            "UNIT_A_A3_REPAIR_NONDETERMINISTIC", "result hash validation")
    results.sort(key=lambda x:x["alert_episode_uid"])
    return {
        "episode_results":results,
        "distribution":{k:repaired_dist[k] for k in VERDICTS},
        "original_distribution":{k:original_dist[k] for k in VERDICTS},
        "transition_matrix":transitions,
        "counts":{
            "unit_a_targets":1713, "original_a3_membership_occurrences":a3_members,
            "repaired_membership_occurrences":narrow_members,
            "removed_memberships":removed_members, "added_memberships":new_members,
            "affected_episodes":affected, "qa_impacted_episodes":qa_affected,
            "temporal_ambiguity_removed_episodes":temporal_removed,
            "new_qa_reasons":qa_added,"review_contributor_impacted_episodes":review_affected,
            "verdict_impacted_episodes":verdict_affected,
            "positive_contributor_intersections":positive_intersect,
            "positive_contributor_changes":positive_changed,
            "positive_tier_changes":positive_tier_changed,
            "positive_contributor_refs_before":positive_ref_before,
            "positive_contributor_refs_after":positive_ref_after,
            "direct_strict":strict_count,"composed_strict":composed_count,
            "sensitivity":sensitivity_count,"event_type_differences":event_diffs,
            "composition_differences":composition_diffs,
            "composed_contributor_removed_intersections":comp_intersect,
            "evidence_membership_impacted_episodes":affected
        },
        "qa_impact_by_code":{k:dict(qa_effect_codes[k]) for k in sorted(qa_effect_codes)},
        "qa_reason_distribution":dict(sorted(qa_distribution.items())),
        "event_type_distribution":dict(sorted(event_distribution.items())),
        "per_city_distribution":{k:{v:city_distribution[k][v] for v in VERDICTS}
                                 for k in sorted(city_distribution)},
        "candidate_decision_corpus_sha256_before":before_corpus_sha,
        "candidate_decision_corpus_sha256_after":after_corpus_sha
    }


def enforce_diagnostic_parity(result: dict, diag: dict):
    c = result["counts"]
    dc, de = diag["counts"], diag["effects"]
    cf, qi = diag["diagnostic_counterfactual"], diag["qa_impact"]
    expected = {
        "unit_a_targets":dc["unit_a_targets"],
        "original_a3_membership_occurrences":dc["a3_membership_occurrences"],
        "repaired_membership_occurrences":dc["historical_production_membership_occurrences"],
        "removed_memberships":dc["a3_only_occurrences"],
        "added_memberships":dc["production_only_occurrences"],
        "affected_episodes":dc["affected_episodes"],
        "qa_impacted_episodes":qi["affected_episode_count"],
        "review_contributor_impacted_episodes":de["REVIEW_EFFECT"],
        "verdict_impacted_episodes":de["FINAL_VERDICT_EFFECT"],
        "positive_contributor_intersections":dc["positive_contributor_intersecting_occurrences"],
        "positive_contributor_refs_before":dc["positive_contributor_refs_total"],
        "event_type_differences":de["EVENT_TYPE_EFFECT"],
        "composition_differences":de["COMPOSITION_EFFECT"]
    }
    for key,value in expected.items():
        require(c[key] == value, "UNIT_A_A3_REPAIR_DIAGNOSTIC_PARITY_MISMATCH",
                {"field":key,"got":c[key],"diagnostic":value})
    require(result["original_distribution"] == cf["frozen_a3_distribution"]
            and result["distribution"] == cf["narrowed_membership_distribution"]
            and result["transition_matrix"] == cf["full_transition_matrix"]
            and result["qa_impact_by_code"] == qi["per_code"]
            and sum(x.get("newly_added",0)
                    for x in result["qa_impact_by_code"].values()) == qi["newly_added_total"]
            and c["temporal_ambiguity_removed_episodes"] ==
                qi["per_code"]["TEMPORAL_AMBIGUITY"]["removed"]
            and c["positive_tier_changes"] == cf["positive_tier_differences"]
            and c["positive_contributor_changes"] == de["POSITIVE_CONTRIBUTOR_EFFECT"]
            and c["composed_contributor_removed_intersections"] ==
                de["frozen_composed_contributor_occurrences_intersecting_mismatches"],
            "UNIT_A_A3_REPAIR_DIAGNOSTIC_PARITY_MISMATCH", "full diagnostic parity")


def safety():
    return {
        "classifier_executions":0,"matching_executions":0,
        "composition_executions":0,"discovery_executions":0,
        "external_evidence_requests":0,"neon_queries":0,
        "db_connections":0,"db_queries":0,"db_writes":0,
        "historical_builder_modifications":0,
        "production_persistence_modifications":0,
        "original_a3_artifact_modifications":0,
        "production_mutation":"NO","a4_executions":0,"a5_executions":0,
        "unit_b_executions":0,"unit_c_executions":0
    }


def execute():
    disabled_network()
    a3_raw,a1_raw,diag,old,new = read_inputs()
    # Deliberately repeat all parsing, decoding, and episode reconstruction.
    first = repair_once(a3_raw,a1_raw,old,new)
    enforce_diagnostic_parity(first,diag)
    second = repair_once(a3_raw,a1_raw,old,new)
    enforce_diagnostic_parity(second,diag)
    semantic_mismatches = sum(x != y for x,y in
                              zip(first["episode_results"],second["episode_results"]))
    semantic_mismatches += abs(len(first["episode_results"])-len(second["episode_results"]))
    agg_a = hobj({"membership_rule":MEMBERSHIP_RULE,
                  "candidate_corpus_sha":first["candidate_decision_corpus_sha256_after"],
                  "episodes":first["episode_results"]})
    agg_b = hobj({"membership_rule":MEMBERSHIP_RULE,
                  "candidate_corpus_sha":second["candidate_decision_corpus_sha256_after"],
                  "episodes":second["episode_results"]})
    require(first == second and semantic_mismatches == 0 and agg_a == agg_b,
            "UNIT_A_A3_REPAIR_NONDETERMINISTIC")
    require(first["candidate_decision_corpus_sha256_before"] ==
            second["candidate_decision_corpus_sha256_after"],
            "UNIT_A_A3_DECISION_ALIGNMENT_DRIFT", "RUN A/B decision identity")
    artifact = {
        "schema_version":1,
        "kind":"attack_event_execution_unit_a_classification_aggregation_repair",
        "verdict":"ATTACK-EVENT EXECUTION UNIT A A3 AGGREGATION REPAIR = FROZEN",
        "base_commit":BASE,"branch":BRANCH,
        "actions_run_id":os.environ.get("GITHUB_RUN_ID"),
        "original_a3":{"commit":A3_COMMIT,"path":A3_PATH,"blob":A3_BLOB,"sha256":A3_SHA},
        "diagnostic":{"path":DIAG_PATH,"blob":DIAG_BLOB,"sha256":DIAG_SHA,
                      "deterministic_diagnostic_sha256":
                      diag["determinism"]["run_a_diagnostic_sha256"]},
        "a1_materialized_input":{"path":A1_PATH,"blob":A1_BLOB,
                                  "file_sha256":A1_SHA,"decoded_corpus_sha256":A1_CORPUS_SHA},
        "authoritative_classifier":{"commit":HIST_COMMIT,"path":CLASS_PATH,"blob":CLASS_BLOB},
        "historical_builder":{"commit":HIST_COMMIT,"path":HIST_PATH,"blob":HIST_BLOB},
        "production_membership":{"commit":PROD_COMMIT,"path":PROD_PATH,"blob":PROD_BLOB},
        "membership_rule":{
            "id":MEMBERSHIP_RULE,
            "independent_channels":["proposed_matched_episode_id",
                                    "matching.matched_episode_id",
                                    "matching.matched_episode_ids"],
            "forbidden_independent_channels":["temporal_binding.supported_episode_ids",
                                               "temporal_binding.episode_id",
                                               "review_provenance_adapter.target_episode_id"]
        },
        "authority_relationship":{
            "candidate_decisions_authority":"original frozen A3",
            "episode_aggregation_authority_for_unit_a_persistence":"this repaired A3 aggregation artifact",
            "superseded_semantic":"original A3 related() membership expansion through temporal/review channels",
            "candidate_decision_retrieval":{"artifact":A3_PATH,
                                            "dictionary":"candidate_decision_store",
                                            "key":"candidate_decision_refs"},
            "evidence_membership_reconstruction":{
                "artifact":A1_PATH,
                "method":"For each repaired episode, ordered target_related_candidate_positions indexes into immutable original candidate_input_refs and candidate_decision_refs; do not re-evaluate the original A3 related()",
                "source_row_identity":"Use the frozen A4 source-identity adapter with these narrowed membership positions"
            }
        },
        "methodology_version":METHOD,"normalization_version":NORM,
        "diagnostic_parity":"YES",
        "determinism":{"run_a_repaired_aggregation_sha256":agg_a,
                       "run_b_repaired_aggregation_sha256":agg_b,
                       "semantic_mismatches":semantic_mismatches},
        "safety":safety(),
        **first
    }
    return artifact


def write_artifact(artifact):
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(artifact,ensure_ascii=False,sort_keys=True,
                         separators=(",", ":")) + "\n"
    OUTPUT.write_text(payload,encoding="utf-8")
    print("VERDICT="+artifact["verdict"])
    if artifact["verdict"].endswith("FROZEN"):
        print("COUNTS="+json.dumps(artifact["counts"],sort_keys=True))
        print("ORIGINAL_DISTRIBUTION="+json.dumps(artifact["original_distribution"],sort_keys=True))
        print("REPAIRED_DISTRIBUTION="+json.dumps(artifact["distribution"],sort_keys=True))
        print("TRANSITIONS="+json.dumps(artifact["transition_matrix"],sort_keys=True))
        print("QA_BY_CODE="+json.dumps(artifact["qa_impact_by_code"],sort_keys=True))
        print("CANDIDATE_CORPUS_SHA_BEFORE="+artifact["candidate_decision_corpus_sha256_before"])
        print("CANDIDATE_CORPUS_SHA_AFTER="+artifact["candidate_decision_corpus_sha256_after"])
        print("DIAGNOSTIC_PARITY="+artifact["diagnostic_parity"])
        print("RUN_A_REPAIRED_SHA256="+artifact["determinism"]["run_a_repaired_aggregation_sha256"])
        print("RUN_B_REPAIRED_SHA256="+artifact["determinism"]["run_b_repaired_aggregation_sha256"])
        print("SEMANTIC_MISMATCHES="+str(artifact["determinism"]["semantic_mismatches"]))
    else:
        print("FIRST_FAILING_GATE="+artifact["first_failing_gate"])
        print("FAILURE_DETAIL="+json.dumps(artifact.get("failure_detail"),sort_keys=True))
    print("SAFETY="+json.dumps(artifact["safety"],sort_keys=True))
    print("ARTIFACT_SHA256="+sha(payload.encode("utf-8")))


def main():
    try:
        artifact = execute()
        write_artifact(artifact)
        return 0
    except RepairBlocked as exc:
        artifact = {"schema_version":1,"kind":"attack_event_execution_unit_a_classification_aggregation_repair",
                    "verdict":"ATTACK-EVENT EXECUTION UNIT A A3 AGGREGATION REPAIR = BLOCKED",
                    "base_commit":BASE,"branch":BRANCH,
                    "actions_run_id":os.environ.get("GITHUB_RUN_ID"),
                    "original_a3":{"path":A3_PATH,"blob":A3_BLOB,"sha256":A3_SHA},
                    "diagnostic":{"path":DIAG_PATH,"blob":DIAG_BLOB,"sha256":DIAG_SHA},
                    "first_failing_gate":exc.gate,"failure_detail":exc.detail,
                    "safety":safety()}
        write_artifact(artifact)
        return 2
    except Exception as exc:
        artifact = {"schema_version":1,"kind":"attack_event_execution_unit_a_classification_aggregation_repair",
                    "verdict":"ATTACK-EVENT EXECUTION UNIT A A3 AGGREGATION REPAIR = BLOCKED",
                    "base_commit":BASE,"branch":BRANCH,
                    "actions_run_id":os.environ.get("GITHUB_RUN_ID"),
                    "first_failing_gate":"UNIT_A_A3_REPAIR_UNEXPECTED_RUNTIME",
                    "failure_detail":type(exc).__name__+":"+str(exc)[:280],
                    "safety":safety()}
        write_artifact(artifact)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
