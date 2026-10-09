#!/usr/bin/env python3
"""Offline shape and source-identity preflight only; strictly no database access."""
import base64
import collections
import gzip
import hashlib
import json
import subprocess
from pathlib import Path

A3 = "research/attack_event_execution_unit_a_classification_replay_2026-10-09.json"
A1 = "research/attack_event_execution_unit_a_materialized_inputs_2026-10-07.json"
def sha(raw):
    return hashlib.sha256(raw).hexdigest()
def blob(path):
    return subprocess.check_output(["git", "rev-parse", "HEAD:" + path], text=True).strip()
def verify(path, expected_blob, expected_file_sha):
    assert blob(path) == expected_blob, (path, "BLOB_MISMATCH")
    b = Path(path).read_bytes()
    assert sha(b) == expected_file_sha, (path, "FILE_SHA_MISMATCH")
    return json.loads(b)
a3 = verify(A3, "4dfc8aa7132706e2a3a4febd655ffa0a2bd71640", "bacbc9e0473a9108b380a4c568115303da5cdb27def595acaf5e2691a6163042")
a1 = verify(A1, "52e89792352513664428da3a7fcb9b43f79f1ba1", "07148ac498a6f4251e356bbf24be0aa40ebf220dd39c5df7ec99177a6f7214cc")
compressed = base64.b64decode(a1["corpus"]["payload_base64"], validate=True)
decoded = gzip.decompress(compressed)
assert sha(decoded) == "9b3a1cb44dcf3ad18230309f4e49c3ad04dbe6837fc12ba4f8930bda1e812073"
corpus = json.loads(decoded)
a3_episodes = a3["episode_results"]
a1_episodes = corpus["episodes"]
store = {item["sha256"]: item["candidate_input"] for item in corpus["candidate_input_store"]}
dist = collections.Counter(x["verdict"] for x in a3_episodes)
assert len(a3_episodes) == len(a1_episodes) == 1713
assert dist == {"STRICT_EVENT_POSITIVE": 9, "SENSITIVITY_EVENT_POSITIVE": 1,
                "NO_CONFIRMED_EVENT":1260, "NEEDS_REVIEW":443}, dist
a1_by_uid = {x["alert_episode_uid"]: x for x in a1_episodes}
all_candidate_keys = collections.Counter()
all_candidate_primitive_fields = collections.Counter()
positive_candidate_keys = collections.Counter()
contrib_fields = collections.Counter()
contributor_refs = 0
positive_episodes = 0
missing_decisions = 0
orphan_contributors = 0
positive_per_episode = []
for ep in a3_episodes:
    refs = ep.get("candidate_input_refs") or []
    drefs = ep.get("candidate_decision_refs") or []
    assert len(refs) == len(drefs), "decision/ref cardinality"
    assert refs == a1_by_uid[ep["alert_episode_uid"]]["candidate_input_refs"], "ref mismatch"
    for ref in refs:
        if ref not in store: raise RuntimeError("MISSING_CANDIDATE")
        all_candidate_keys.update(store[ref].keys())
        for field, value in store[ref].items():
            if isinstance(value, (str, int, float, bool)) and value is not None:
                all_candidate_primitive_fields[field] += 1
    if ep["verdict"] not in ("STRICT_EVENT_POSITIVE", "SENSITIVITY_EVENT_POSITIVE"):
        continue
    positive_episodes += 1
    needed = ep.get("final_contributor_refs") or []
    positive_per_episode.append(len(needed))
    for dr in needed:
        contributor_refs += 1
        if dr not in a3["candidate_decision_store"]:
            missing_decisions += 1
        if dr not in drefs:
            orphan_contributors += 1
            continue
        candidate = store[refs[drefs.index(dr)]]
        contrib_fields.update(k for k, v in candidate.items() if v is not None)
        positive_candidate_keys.update(candidate.keys())
print("OFFLINE_PROBE=" + json.dumps({
    "a3_episodes":len(a3_episodes),"a1_episodes":len(a1_episodes),
    "a3_episode_keys":sorted(a3_episodes[0].keys()),
    "a1_episode_keys":sorted(a1_episodes[0].keys()),
    "a1_parent_identity_keys": sorted((a1_episodes[0].get("canonical_parent_identity") or {}).keys()),
    "a1_evidence_provenance_keys":sorted((a1_episodes[0].get("evidence_provenance") or {}).keys()),
    "candidate_store_size":len(store),
    "candidate_store_field_counts":dict(all_candidate_keys),
    "candidate_primitive_field_counts":dict(all_candidate_primitive_fields),
    "a3_candidate_decision_keys":sorted(next(iter(a3["candidate_decision_store"].values())).keys()),
    "positive_episodes":positive_episodes,
    "contributors_total":contributor_refs,
    "contributors_per_positive":positive_per_episode,
    "contributors_missing_decisions":missing_decisions,
    "contributors_not_in_decision_refs":orphan_contributors,
    "positive_candidate_keys":dict(positive_candidate_keys),
    "contributor_nonnull_fields":dict(contrib_fields),
    "distribution":dict(dist)
}, sort_keys=True, ensure_ascii=True, separators=(",",":")))
