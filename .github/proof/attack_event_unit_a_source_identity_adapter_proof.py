#!/usr/bin/env python3
"""Offline, read-only source-identity parity proof for frozen Unit A A1/A3.

Only local Git objects are read. No classifier, discovery, network service,
database, or production script is imported or executed.
"""
from __future__ import annotations

import ast
import base64
from collections import Counter, defaultdict
import copy
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

BASE = "d2d3df412393325ba5256daa6d45ee78aeae8b7d"
OUTPUT = Path("research/attack_event_execution_unit_a_source_identity_adapter_proof_2026-10-09.json")
A1_CORPUS_SHA = "9b3a1cb44dcf3ad18230309f4e49c3ad04dbe6837fc12ba4f8930bda1e812073"
INPUTS = {
    "A1": {
        "commit": "f54b0d6dcfcdd7e5b51a5b45b996273d1df72cff",
        "path": "research/attack_event_execution_unit_a_materialized_inputs_2026-10-07.json",
        "blob": "52e89792352513664428da3a7fcb9b43f79f1ba1",
        "sha256": "07148ac498a6f4251e356bbf24be0aa40ebf220dd39c5df7ec99177a6f7214cc",
    },
    "A3": {
        "commit": "1422e8482303ec9262647ca55fef753a9aa2b3ea",
        "path": "research/attack_event_execution_unit_a_classification_replay_2026-10-09.json",
        "blob": "4dfc8aa7132706e2a3a4febd655ffa0a2bd71640",
        "sha256": "bacbc9e0473a9108b380a4c568115303da5cdb27def595acaf5e2691a6163042",
    },
    "A4": {
        "commit": "bc58ab0705699c1686d897f07852c3493b5eec16",
        "path": "research/attack_event_execution_unit_a_shadow_persistence_gap_audit_2026-10-09.json",
        "blob": "f9bfd11577b3c3ce43d0653ee83281dcbb83284e",
        "sha256": "3069e776634ccbb8a80138d42603f706e2547006752c563cca0e5711b11398d4",
    },
    "classifier": {
        "commit": "71cb6f6fbe856cc7b96759310fe9cc9c71cc0453",
        "path": "kyiv-air-alerts-grafana/scripts/monitor_explosion_candidates.py",
        "blob": "778469b74c2aa807d851cf2c2ee35cf4aa785589",
    },
    "canonical_persistence": {
        "commit": "51adc76b715669e46e8c2c936906022d4d96ed44",
        "path": "kyiv-air-alerts-grafana/scripts/attack_event_canonical_persistence.py",
        "blob": "0118ca9e5f1308173e657257f1b49fe91cc19fe1",
    },
}
EXPECTED_DISTRIBUTION = {
    "STRICT_EVENT_POSITIVE": 9,
    "SENSITIVITY_EVENT_POSITIVE": 1,
    "NO_CONFIRMED_EVENT": 1260,
    "NEEDS_REVIEW": 443,
}
SOURCE_FIELDS = (
    "source_url", "resolved_url", "title", "snippet", "matched_text_excerpt",
    "publisher", "publisher_url", "published_at",
)
POSITIVE = {"STRICT_EVENT_POSITIVE", "SENSITIVITY_EVENT_POSITIVE"}


class ProofBlocked(Exception):
    def __init__(self, gate: str, detail: Any = None, partial: dict | None = None):
        super().__init__(gate)
        self.gate, self.detail, self.partial = gate, detail, partial or {}


def fail(gate: str, detail: Any = None, partial: dict | None = None):
    raise ProofBlocked(gate, detail, partial)


def git(*args: str) -> bytes:
    env = dict(os.environ, GIT_NO_LAZY_FETCH="1", GIT_TERMINAL_PROMPT="0")
    result = subprocess.run(("git", *args), check=False, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, env=env)
    if result.returncode:
        fail("UNIT_A_LOCAL_GIT_OBJECT_UNAVAILABLE", {
            "command": list(args)[:3],
            "stderr_tail": result.stderr.decode("utf-8", "replace")[-240:],
        })
    return result.stdout


def gitref(ref: str, path: str) -> str:
    return git("rev-parse", f"{ref}:{path}").decode("ascii").strip()


def gitshow(ref: str, path: str) -> bytes:
    return git("show", f"{ref}:{path}")


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canon(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def a1_canon(value: Any) -> bytes:
    # Exact original A1 materialization serialization (including LF).
    return canon(value) + b"\n"


def verify_inputs():
    checked = {}
    docs = {}
    for name, pin in INPUTS.items():
        original_blob = gitref(pin["commit"], pin["path"])
        if original_blob != pin["blob"]:
            fail("UNIT_A_PINNED_INPUT_BLOB_MISMATCH", {
                "name": name, "expected": pin["blob"], "observed": original_blob,
            })
        raw = gitshow(pin["commit"], pin["path"])
        worktree_blob = gitref("HEAD", pin["path"]) if name in ("A1", "A3", "A4") else None
        if worktree_blob is not None and worktree_blob != pin["blob"]:
            fail("UNIT_A_FROZEN_INPUT_HEAD_DRIFT", {"name": name, "observed": worktree_blob})
        if pin.get("sha256") and sha(raw) != pin["sha256"]:
            fail("UNIT_A_PINNED_INPUT_SHA256_MISMATCH", {"name": name, "observed": sha(raw)})
        checked[name] = {
            "commit": pin["commit"], "path": pin["path"], "blob": original_blob,
            "sha256": sha(raw), "bytes": len(raw),
            "same_blob_in_worktree": worktree_blob == pin["blob"] if worktree_blob else None,
        }
        docs[name] = raw
    a4 = json.loads(docs["A4"])
    if (a4.get("verdict") != "ATTACK-EVENT EXECUTION UNIT A SHADOW PERSISTENCE GAP AUDIT = BLOCKED"
            or a4.get("first_failing_gate") != "UNIT_A_SOURCE_LINK_PROJECTION_NOT_LOSSLESS"):
        fail("UNIT_A_A4_DIAGNOSTIC_VERDICT_DRIFT", a4.get("first_failing_gate"))
    return checked, docs


def production_adapter(source: bytes):
    # Execute ONLY three pure, pinned production helper functions, and ONLY
    # the two assignment expressions that production _source_row executes.
    # Do not import production module: it imports psycopg and owns DB code.
    root = ast.parse(source.decode("utf-8"))
    funcs = {n.name: n for n in root.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    needed = ("canonical_json_bytes", "canonical_sha256", "_normalized_source_content", "_source_row")
    if any(n not in funcs for n in needed):
        fail("UNIT_A_PINNED_ADAPTER_SHAPE_DRIFT", {"missing_functions": [n for n in needed if n not in funcs]})
    source_fn = funcs["_source_row"]
    assignments = {}
    for item in ast.walk(source_fn):
        if isinstance(item, (ast.Assign, ast.AnnAssign)):
            targets = item.targets if isinstance(item, ast.Assign) else [item.target]
            for target in targets:
                if isinstance(target, ast.Name) and target.id in ("observation_id", "content_sha"):
                    assignments.setdefault(target.id, []).append(item)
    if any(len(assignments.get(n, [])) != 1 for n in ("observation_id", "content_sha")):
        fail("UNIT_A_PINNED_ADAPTER_SHAPE_DRIFT", "source_row identity assignments not unique")
    identity_body = [
        copy.deepcopy(assignments["observation_id"][0]),
        copy.deepcopy(assignments["content_sha"][0]),
        ast.Return(ast.Tuple(
            elts=[ast.Name(id="observation_id", ctx=ast.Load()),
                  ast.Name(id="content_sha", ctx=ast.Load())],
            ctx=ast.Load())),
    ]
    args = ast.arguments(posonlyargs=[], args=[ast.arg(arg="row")], vararg=None,
                         kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[])
    derive = ast.FunctionDef(
        name="derive_pinned_identity", args=args, body=identity_body,
        decorator_list=[], returns=None, type_comment=None)
    module = ast.fix_missing_locations(ast.Module(
        body=[copy.deepcopy(funcs[n]) for n in needed[:3]] + [derive], type_ignores=[]))
    env = {"json": json, "hashlib": hashlib, "Any": Any}
    exec(compile(module, INPUTS["canonical_persistence"]["path"], "exec"), env)
    # The assignments were extracted, not reimplemented; confirm pinned
    # formula and normalized-field interface before admitting a proof.
    obs_expr = ast.unparse(assignments["observation_id"][0].value)
    content_expr = ast.unparse(assignments["content_sha"][0].value)
    if obs_expr != "str(row.get('candidate_id') or '').strip()":
        fail("UNIT_A_PINNED_ADAPTER_SHAPE_DRIFT", {"observation_expression": obs_expr})
    if content_expr != "canonical_sha256(_normalized_source_content(row))":
        fail("UNIT_A_PINNED_ADAPTER_SHAPE_DRIFT", {"hash_expression": content_expr})
    if tuple(env["_normalized_source_content"]({}).keys()) != SOURCE_FIELDS:
        fail("UNIT_A_PINNED_ADAPTER_SHAPE_DRIFT", "normalized fields drifted")
    example = {"candidate_id": "0123456789abcdef01234567", "url": "https://example.invalid/a"}
    observation, hashed = env["derive_pinned_identity"](example)
    if observation != example["candidate_id"] or hashed != env["canonical_sha256"](
            env["_normalized_source_content"](example)):
        fail("UNIT_A_PINNED_ADAPTER_RUNTIME_DIVERGENCE", "pure helper smoke check")
    return env


def decode_a1(doc: dict):
    block = doc.get("corpus")
    if not isinstance(block, dict) or block.get("encoding") != "gzip+base64":
        fail("UNIT_A_A1_RECONSTRUCTION_INVALID", "encoding")
    compressed = base64.b64decode(block["payload_base64"].encode("ascii"), validate=True)
    if (sha(compressed) != block.get("compressed_sha256")
            or len(compressed) != int(block["compressed_bytes"])):
        fail("UNIT_A_A1_RECONSTRUCTION_INVALID", "compressed bytes/hash")
    decoded = gzip.decompress(compressed)
    if (sha(decoded) != A1_CORPUS_SHA
            or block.get("uncompressed_sha256") != A1_CORPUS_SHA
            or len(decoded) != int(block["uncompressed_bytes"])):
        fail("UNIT_A_A1_CORPUS_SHA_MISMATCH", {"observed": sha(decoded)})
    corpus = json.loads(decoded)
    if a1_canon(corpus) != decoded:
        fail("UNIT_A_A1_RECONSTRUCTION_INVALID", "decoded corpus noncanonical")
    if (corpus.get("schema_version") != 2
            or corpus.get("kind") != "attack_event_execution_unit_a_materialized_input_corpus"
            or corpus.get("candidate_input_representation") != "FROZEN_LIVE_CANDIDATE_INPUT_BUNDLE"
            or (corpus.get("artifact_serialization") or {}).get("format")
               != "content-addressed-candidate-dedup-v1"):
        fail("UNIT_A_A1_RECONSTRUCTION_INVALID", "unexpected schema")
    store_rows = corpus["candidate_input_store"]
    store = {}
    for record in store_rows:
        ref = record["sha256"]
        candidate = record["candidate_input"]
        if sha(a1_canon(candidate)) != ref:
            fail("UNIT_A_A1_CANDIDATE_STORE_HASH_MISMATCH", {"candidate_input_ref": ref})
        if ref in store:
            fail("UNIT_A_A1_CANDIDATE_STORE_DUPLICATE", {"candidate_input_ref": ref})
        store[ref] = candidate
    if len(store_rows) != 3347:
        fail("UNIT_A_A1_CANDIDATE_STORE_COUNT", {"observed": len(store_rows)})
    episodes = corpus["episodes"]
    if len(episodes) != 1713:
        fail("UNIT_A_A1_EPISODE_COUNT", {"observed": len(episodes)})
    refs_total = 0
    for ep in episodes:
        refs = ep["candidate_input_refs"]
        candidate_inputs = []
        for ref in refs:
            refs_total += 1
            if ref not in store:
                fail("UNIT_A_A1_CANDIDATE_REF_UNRESOLVED", {"ref": ref})
            candidate_inputs.append(store[ref])
        if not refs and (ep.get("evidence_provenance") or {}).get("accepted_empty_candidate_set") is not True:
            fail("UNIT_A_A1_UNACCEPTED_EMPTY_CANDIDATE_SET", ep.get("alert_episode_uid"))
        logical = {
            "alert_episode_uid": ep.get("alert_episode_uid"),
            "canonical_parent_identity": ep.get("canonical_parent_identity"),
            "classifier_episode_input": ep.get("classifier_episode_input"),
            "candidate_input_representation": ep.get("candidate_input_representation"),
            "candidate_inputs": candidate_inputs,
            "evidence_provenance": ep.get("evidence_provenance"),
        }
        if sha(a1_canon(logical)) != ep.get("materialized_input_sha256"):
            fail("UNIT_A_A1_EPISODE_RECONSTRUCTION_DRIFT", ep.get("alert_episode_uid"))
    if refs_total != 99663:
        fail("UNIT_A_A1_CANDIDATE_REF_COUNT", {"observed": refs_total})
    return corpus, episodes, store, refs_total


def verify_a3(doc: dict, episodes: list[dict]):
    a3rows = doc["episode_results"]
    decisions = doc["candidate_decision_store"]
    if len(a3rows) != len(episodes) or len(a3rows) != 1713:
        fail("UNIT_A_A3_TARGET_COUNT_MISMATCH", len(a3rows))
    distribution = dict(Counter(row["verdict"] for row in a3rows))
    if distribution != EXPECTED_DISTRIBUTION:
        fail("UNIT_A_A3_VERDICT_DISTRIBUTION_MISMATCH", distribution)
    by_uid = {x["alert_episode_uid"]: x for x in episodes}
    if len(by_uid) != 1713:
        fail("UNIT_A_A1_UID_DUPLICATE", len(by_uid))
    seen = set()
    positives = 0
    contributors = 0
    for ep in a3rows:
        uid = ep["alert_episode_uid"]
        if uid in seen or uid not in by_uid:
            fail("UNIT_A_A3_A1_TARGET_IDENTITY_MISMATCH", uid)
        seen.add(uid)
        refs = ep["candidate_input_refs"]
        drefs = ep["candidate_decision_refs"]
        if refs != by_uid[uid]["candidate_input_refs"] or len(drefs) != len(refs):
            fail("UNIT_A_A3_A1_CANDIDATE_REF_ALIGNMENT_MISMATCH", uid)
        for dref in drefs:
            if dref not in decisions:
                fail("UNIT_A_A3_DECISION_REF_UNRESOLVED", {"uid": uid, "ref": dref})
        final = ep.get("final_contributor_refs") or []
        if ep["verdict"] in POSITIVE:
            positives += 1
            contributors += len(final)
        elif final:
            fail("UNIT_A_A3_NONPOSITIVE_CONTRIBUTORS", uid)
    if len(seen) != 1713 or positives != 10 or contributors != 18:
        fail("UNIT_A_A3_CONTRIBUTOR_CARDINALITY_MISMATCH", {
            "targets": len(seen), "positive": positives, "contributors": contributors})
    return a3rows, decisions, by_uid


def selected_queue_rows(queue: list[dict], episode_id: str, checked_at: str | None):
    # Exactly the accepted A1 selection function, without discovery/matching.
    by_candidate = {}
    for row in queue:
        if not isinstance(row, dict):
            continue
        matched = str(row.get("matched_episode_id") or "")
        triggers = {str(x) for x in (row.get("trigger_episode_ids") or []) if str(x)}
        if episode_id not in triggers and matched != episode_id:
            continue
        if checked_at:
            discovered = str(row.get("first_discovered_at") or "")
            if discovered and discovered > checked_at:
                continue
        cid = str(row.get("candidate_id") or "")
        if not cid:
            fail("UNIT_A_FROZEN_QUEUE_CANDIDATE_UNRESOLVED", {
                "episode_id": episode_id, "reason": "missing_candidate_id"})
        by_candidate[cid] = row
    return [by_candidate[k] for k in sorted(by_candidate)]


def bounded_difference(left: dict, right: dict):
    return [k for k in SOURCE_FIELDS if left.get(k) != right.get(k)]


def run_proof(run_name: str) -> dict:
    # Deliberately no caches or decoded documents are shared between RUN A/B.
    checked, docs = verify_inputs()
    env = production_adapter(docs["canonical_persistence"])
    a1 = json.loads(docs["A1"])
    a3 = json.loads(docs["A3"])
    corpus, episodes, store, refs_total = decode_a1(a1)
    a3rows, decisions, a1_by_uid = verify_a3(a3, episodes)
    normalized = env["_normalized_source_content"]
    derive = env["derive_pinned_identity"]
    source_identity_by_ref = {}
    for ref, cand in store.items():
        observation_id, content_sha = derive(cand)
        if not observation_id or not content_sha:
            fail("UNIT_A_SOURCE_IDENTITY_DERIVATION_FAILED", {"ref": ref})
        source_identity_by_ref[ref] = {
            "candidate_id": str(cand.get("candidate_id") or ""),
            "observation_id": observation_id, "content_sha256": content_sha,
        }

    queue_cache = {}
    consumed = {}
    matches = 0
    mismatches = 0
    occurrences = 0
    resolved = 0
    equality_ids = 0
    unresolved = 0
    derivation_seen = set()
    candidate_id_matches = set()
    candidate_id_mismatches = set()
    derivation_mismatch_versions = 0
    identity_failures = 0
    first_content_mismatch = None
    all_candidate_ids = set()
    all_pairs = set()
    id_to_hashes = defaultdict(set)
    mapper = hashlib.sha256()
    example_derivation = None

    for ep in sorted(episodes, key=lambda row: row["alert_episode_uid"]):
        uid = ep["alert_episode_uid"]
        refs = ep["candidate_input_refs"]
        if not refs:
            continue
        evidence = ep["evidence_provenance"]
        qi = evidence.get("collection_queue_identity") or {}
        commit, path, blob = (str(qi.get(name) or "") for name in ("commit", "path", "blob"))
        if not (commit and path and blob):
            fail("UNIT_A_FROZEN_QUEUE_CANDIDATE_UNRESOLVED", {"uid": uid, "reason": "queue identity absent"})
        key = (commit, path)
        if key not in queue_cache:
            actual_blob = gitref(commit, path)
            if actual_blob != blob:
                fail("UNIT_A_FROZEN_QUEUE_BLOB_MISMATCH", {
                    "uid": uid, "path": path, "expected_blob": blob, "observed_blob": actual_blob})
            raw = gitshow(commit, path)
            queue = json.loads(raw)
            if not isinstance(queue, list):
                fail("UNIT_A_FROZEN_QUEUE_SCHEMA_INVALID", {"uid": uid, "path": path})
            queue_cache[key] = queue
            consumed[key] = {
                "commit": commit, "path": path, "blob": blob,
                "sha256": sha(raw), "rows": len(queue),
            }
        queue = queue_cache[key]
        cid = str(ep["classifier_episode_input"]["episode_id"])
        checked_at = evidence.get("followup_72h_checked_at")
        chosen = selected_queue_rows(queue, cid, checked_at)
        provenance = evidence.get("candidate_selection_provenance") or []
        if len(chosen) != len(refs) or len(provenance) != len(refs):
            unresolved += abs(len(chosen) - len(refs))
            fail("UNIT_A_FROZEN_QUEUE_CANDIDATE_UNRESOLVED", {
                "uid": uid, "A1_ref_count": len(refs), "selected_queue_count": len(chosen),
                "selection_provenance_count": len(provenance)}, {
                    "candidate_occurrences_checked": occurrences,
                    "candidate_occurrences_resolved": resolved,
                    "queue_resolution_failures": unresolved,
                    "frozen_queue_snapshots_consumed": len(consumed),
                })
        city_key = str(ep["classifier_episode_input"]["city_key"])
        for pos, (ref, raw, prov) in enumerate(zip(refs, chosen, provenance)):
            occurrences += 1
            candidate = store[ref]
            raw_cid = str(raw.get("candidate_id") or "")
            a1_cid = str(candidate.get("candidate_id") or "")
            prov_cid = str(prov.get("candidate_id") or "")
            if (a1_cid != raw_cid or prov_cid != raw_cid or
                    prov.get("candidate_input_sha256") != ref):
                unresolved += 1
                fail("UNIT_A_FROZEN_QUEUE_CANDIDATE_UNRESOLVED", {
                    "uid": uid, "position": pos, "ref": ref,
                    "raw_candidate_id": raw_cid, "a1_candidate_id": a1_cid,
                    "provenance_candidate_id": prov_cid}, {
                        "candidate_occurrences_checked": occurrences,
                        "candidate_occurrences_resolved": resolved,
                        "queue_resolution_failures": unresolved,
                    })
            # Verify original selection provenance exactly (including cutoff).
            for field in ("matched_episode_id", "trigger_episode_ids",
                          "trigger_check_labels", "first_discovered_at"):
                expected = raw.get(field) if field not in ("trigger_episode_ids", "trigger_check_labels") else (raw.get(field) or [])
                if prov.get(field) != expected:
                    fail("UNIT_A_A1_SELECTION_PROVENANCE_MISMATCH", {
                        "uid": uid, "candidate_id": raw_cid, "field": field})
            discovered = str(raw.get("first_discovered_at") or "")
            if checked_at and discovered and discovered > checked_at:
                fail("UNIT_A_A1_FOLLOWUP_BOUNDARY_MISMATCH", {
                    "uid": uid, "candidate_id": raw_cid})
            resolved += 1
            equality_ids += 1

            a1_norm = normalized(candidate)
            raw_norm = normalized(raw)
            a1_observation, a1_hash = derive(candidate)
            raw_observation, raw_hash = derive(raw)
            if (a1_observation != a1_cid or raw_observation != raw_cid
                    or not a1_hash or not raw_hash):
                identity_failures += 1
            if a1_hash == raw_hash:
                matches += 1
            else:
                mismatches += 1
                if first_content_mismatch is None:
                    first_content_mismatch = {
                        "uid": uid, "position": pos, "ref": ref,
                        "candidate_id": raw_cid,
                        "raw_normalized_content_sha256": raw_hash,
                        "a1_normalized_content_sha256": a1_hash,
                        "different_normalized_fields": bounded_difference(a1_norm, raw_norm),
                    }
            # Independently verify the pinned classifier's candidate identity
            # formula, without invoking the classifier or its module.
            raw_city = str(raw.get("city_key") or "")
            raw_url = str(raw.get("url") or "")
            raw_title = str(raw.get("title") or "")
            derivation_key = (raw_cid, raw_city, raw_url, raw_title)
            if derivation_key not in derivation_seen:
                derivation_seen.add(derivation_key)
                derived_cid = sha(f"{raw_city}|{raw_url}|{raw_title}".encode("utf-8"))[:24]
                if derived_cid == raw_cid:
                    candidate_id_matches.add(raw_cid)
                else:
                    candidate_id_mismatches.add(raw_cid)
                    derivation_mismatch_versions += 1
                    if example_derivation is None:
                        example_derivation = {
                            "uid": uid, "candidate_id": raw_cid,
                            "derived_candidate_id": derived_cid,
                            "candidate_input_ref": ref,
                        }
            all_candidate_ids.add(raw_cid)
            all_pairs.add((a1_observation, a1_hash))
            id_to_hashes[raw_cid].add(a1_hash)
            compact_row = [
                uid, pos, ref, raw_cid, a1_observation, a1_hash,
            ]
            mapper.update(canon(compact_row) + b"\n")

    counts = {
        "target_episodes": len(episodes),
        "candidate_store_entries": len(store),
        "candidate_refs": refs_total,
        "frozen_queue_snapshots_consumed": len(consumed),
        "candidate_occurrences_checked": occurrences,
        "candidate_occurrences_resolved": resolved,
        "queue_resolution_failures": unresolved,
        "candidate_id_equality_matches": equality_ids,
        "normalized_source_content_hash_matches": matches,
        "normalized_source_content_hash_mismatches": mismatches,
        "candidate_id_derivation_versions_checked": len(derivation_seen),
        "candidate_id_derivation_matches": len(candidate_id_matches - candidate_id_mismatches),
        "candidate_id_derivation_mismatches": derivation_mismatch_versions,
        "source_identity_derivation_failures": identity_failures,
        "distinct_candidate_ids": len(all_candidate_ids),
        "distinct_observation_content_pairs": len(all_pairs),
        "candidate_ids_with_multiple_content_hashes": len([
            cid for cid, hashes in id_to_hashes.items() if len(hashes) > 1]),
    }
    partial = {
        "counts": counts,
        "frozen_queue_inputs": sorted(consumed.values(), key=lambda x: (x["commit"], x["path"])),
        "first_source_content_mismatch": first_content_mismatch,
        "first_candidate_id_derivation_mismatch": example_derivation,
        "mapping_sha256": mapper.hexdigest(),
    }
    if occurrences != 99663 or resolved != 99663 or equality_ids != 99663 or unresolved:
        fail("UNIT_A_FROZEN_QUEUE_CANDIDATE_UNRESOLVED", counts, partial)
    if mismatches:
        fail("UNIT_A_A1_SOURCE_CONTENT_NOT_LOSSLESS", first_content_mismatch, partial)
    if derivation_mismatch_versions:
        fail("UNIT_A_CANDIDATE_ID_DERIVATION_MISMATCH", example_derivation, partial)
    if identity_failures:
        fail("UNIT_A_SOURCE_IDENTITY_DERIVATION_FAILED", counts, partial)

    contributors = []
    for a3ep in a3rows:
        if a3ep["verdict"] not in POSITIVE:
            continue
        uid = a3ep["alert_episode_uid"]
        refs = a3ep["candidate_input_refs"]
        drefs = a3ep["candidate_decision_refs"]
        for decision_ref in a3ep["final_contributor_refs"]:
            positions = [i for i, dref in enumerate(drefs) if dref == decision_ref]
            if not positions:
                fail("UNIT_A_FINAL_CONTRIBUTOR_SOURCE_IDENTITY_UNRESOLVED", {
                    "uid": uid, "decision_ref": decision_ref}, partial)
            corresponding_refs = {refs[i] for i in positions}
            if len(corresponding_refs) != 1:
                fail("UNIT_A_FINAL_CONTRIBUTOR_SOURCE_IDENTITY_UNRESOLVED", {
                    "uid": uid, "decision_ref": decision_ref,
                    "reason": "ambiguous A3 aligned refs"}, partial)
            candidate_ref = next(iter(corresponding_refs))
            derived = source_identity_by_ref.get(candidate_ref)
            candidate = store.get(candidate_ref) or {}
            if (decision_ref not in decisions or derived is None
                    or not derived["observation_id"] or not derived["content_sha256"]
                    or not str(candidate.get("url") or "").strip()):
                fail("UNIT_A_FINAL_CONTRIBUTOR_SOURCE_IDENTITY_UNRESOLVED", {
                    "uid": uid, "decision_ref": decision_ref, "candidate_input_ref": candidate_ref},
                    partial)
            contributors.append({
                "alert_episode_uid": uid,
                "decision_ref": decision_ref,
                "candidate_input_ref": candidate_ref,
                "candidate_id": derived["candidate_id"],
                "observation_id": derived["observation_id"],
                "content_sha256": derived["content_sha256"],
            })
    if len(contributors) != 18:
        fail("UNIT_A_FINAL_CONTRIBUTOR_SOURCE_IDENTITY_UNRESOLVED", {
            "contributors_found": len(contributors)}, partial)
    contributors.sort(key=lambda x: (x["alert_episode_uid"], x["decision_ref"], x["candidate_input_ref"]))
    multi = {cid: sorted(hashes) for cid, hashes in sorted(id_to_hashes.items()) if len(hashes) > 1}
    counts.update({
        "final_contributor_refs": 18,
        "final_contributors_resolved": len(contributors),
        "final_contributors_with_observation_id": sum(bool(x["observation_id"]) for x in contributors),
        "final_contributors_with_content_sha256": sum(bool(x["content_sha256"]) for x in contributors),
        "unresolved_final_contributors": 18 - len(contributors),
    })
    return {
        "checked_inputs": checked,
        "counts": counts,
        "frozen_queue_inputs": partial["frozen_queue_inputs"],
        "contributor_source_identity_mapping": contributors,
        "multiple_content_hashes_by_candidate_id": multi,
        "mapping_sha256": mapper.hexdigest(),
        "semantic_mismatches": (mismatches + derivation_mismatch_versions +
                                unresolved + identity_failures),
    }


def main() -> int:
    proof = {
        "schema_version": 1,
        "kind": "attack_event_execution_unit_a_source_identity_adapter_proof",
        "base_commit": BASE,
        "branch": "attack-event-unit-a-source-identity-adapter-proof-2026-10-09",
        "pinned_input_refs": INPUTS,
        "source_identity_adapter": {
            "commit": INPUTS["canonical_persistence"]["commit"],
            "blob": INPUTS["canonical_persistence"]["blob"],
            "observation_id": "str(row.get('candidate_id') or '').strip()",
            "normalized_source_content_fields": list(SOURCE_FIELDS),
            "normalized_source_content_code": "PINNED_AST_EXTRACTED_HELPER",
            "canonical_encoding": "json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')",
            "content_sha256": "SHA256(canonical_json_bytes(_normalized_source_content(row)))",
            "content_hash_basis": "NORMALIZED_EVIDENCE",
            "source_link_key_version": "attack-event-source-link-key-v1",
            "source_link_identity_tuple": [
                "attack-event-source-link-key-v1", "classification_key",
                "observation_id", "content_sha256",
            ],
            "candidate_id_verification": "sha256(f'{city_key}|{url}|{title}'.encode('utf-8')).hexdigest()[:24]",
        },
        "safety": {
            "external_evidence_requests": 0,
            "classifier_executions": 0,
            "compose_episode_candidates_executions": 0,
            "discovery_executions": 0,
            "neon_queries": 0,
            "database_connections": 0,
            "database_queries": 0,
            "database_writes": 0,
            "production_mutation": False,
        },
        "source_link_cardinality_decided": False,
        "a4_resumed": False,
        "a5_authorized": False,
    }
    try:
        first = run_proof("A")
        second = run_proof("B")
        if (first["mapping_sha256"] != second["mapping_sha256"] or
                first["counts"] != second["counts"] or
                first["contributor_source_identity_mapping"] != second["contributor_source_identity_mapping"] or
                first["frozen_queue_inputs"] != second["frozen_queue_inputs"] or
                first["multiple_content_hashes_by_candidate_id"] != second["multiple_content_hashes_by_candidate_id"]):
            fail("UNIT_A_SOURCE_IDENTITY_ADAPTER_NONDETERMINISTIC", {
                "run_a_sha256": first["mapping_sha256"],
                "run_b_sha256": second["mapping_sha256"],
            })
        if first["semantic_mismatches"] or second["semantic_mismatches"]:
            fail("UNIT_A_SOURCE_IDENTITY_ADAPTER_SEMANTIC_MISMATCH", {
                "run_a": first["semantic_mismatches"],
                "run_b": second["semantic_mismatches"]})
        proof.update({
            "verdict": "ATTACK-EVENT EXECUTION UNIT A SOURCE IDENTITY ADAPTER = PROVEN",
            "first_failing_gate": None,
            "immutable_input_identities": first["checked_inputs"],
            "counts": first["counts"],
            "frozen_queue_inputs": first["frozen_queue_inputs"],
            "contributor_source_identity_mapping": first["contributor_source_identity_mapping"],
            "multiple_content_hashes_by_candidate_id": first["multiple_content_hashes_by_candidate_id"],
            "run_a_mapping_sha256": first["mapping_sha256"],
            "run_b_mapping_sha256": second["mapping_sha256"],
            "run_a_run_b_semantic_mismatches": 0,
            "deterministic": True,
            "whole_unit_a_candidate_mapping_sha256": first["mapping_sha256"],
            "continuation": "STOP. Source identity proven only; A4 gap audit remains incomplete. No DB access, A5, Unit B or Unit C.",
        })
    except ProofBlocked as exc:
        proof.update({
            "verdict": "ATTACK-EVENT EXECUTION UNIT A SOURCE IDENTITY ADAPTER = BLOCKED",
            "first_failing_gate": exc.gate,
            "first_blocker": exc.detail,
            "partial_diagnostic": exc.partial,
            "run_a_mapping_sha256": exc.partial.get("mapping_sha256"),
            "run_b_mapping_sha256": None,
            "run_a_run_b_semantic_mismatches": None,
            "deterministic": False,
            "continuation": "STOP AT FIRST DEMONSTRATED BLOCKER. Do not repair in this task; no A4, A5, Unit B/C or database access.",
        })
    except Exception as exc:
        proof.update({
            "verdict": "ATTACK-EVENT EXECUTION UNIT A SOURCE IDENTITY ADAPTER = BLOCKED",
            "first_failing_gate": "UNIT_A_SOURCE_IDENTITY_PROOF_EXECUTION_ERROR",
            "first_blocker": {"type": type(exc).__name__, "detail": str(exc)[:300]},
            "run_a_mapping_sha256": None, "run_b_mapping_sha256": None,
            "deterministic": False,
            "continuation": "STOP. Proof execution needs independent diagnosis; no projection claims.",
        })
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes(json.dumps(proof, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n")
    print("VERDICT=" + str(proof["verdict"]))
    print("FIRST_FAILING_GATE=" + str(proof.get("first_failing_gate")))
    print("COUNTS=" + json.dumps(proof.get("counts") or (proof.get("partial_diagnostic") or {}).get("counts") or {}, sort_keys=True))
    print("RUN_A_MAPPING_SHA256=" + str(proof.get("run_a_mapping_sha256")))
    print("RUN_B_MAPPING_SHA256=" + str(proof.get("run_b_mapping_sha256")))
    print("DURABLE_ARTIFACT_PATH=" + str(OUTPUT))
    print("DURABLE_ARTIFACT_SHA256=" + sha(OUTPUT.read_bytes()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
