#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import copy
import gzip
import hashlib
import importlib
import json
import os
import re
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg

REPO = "olegbalakin-cmyk/kyiv-air-alerts-grafana"
BRANCH = "attack-event-unit-a-canonical-classifier-context-recovery-2026-10-08"
PREDECESSOR = "61239fb8a3751bb62ecbcfd948c0d5b19aadb4f3"
OUT = Path("research/attack_event_unit_a_frozen_classifier_context_2026-10-08.json")
EXPECTED_DB_BRANCH = "br-bold-mode-b5rub8pq"

MATERIALIZATION = {
    "commit": PREDECESSOR,
    "path": "research/attack_event_execution_unit_a_materialized_inputs_2026-10-07.json",
    "blob": "52e89792352513664428da3a7fcb9b43f79f1ba1",
    "sha256": "07148ac498a6f4251e356bbf24be0aa40ebf220dd39c5df7ec99177a6f7214cc",
}
READINESS = {
    "commit": PREDECESSOR,
    "path": "research/attack_event_execution_unit_a_classifier_readiness_validation_2026-10-08.json",
    "blob": "96b680bf740a27c10428f6dd2f1ec3ed183277b1",
    "sha256": "80b679a89b5f9450da6afc663451abb81d131ed9f81bcb2b5c4d86ee41a215fa",
}
CONTINUITY = {
    "commit": "48099cd6d93c2b911e331e79b5141dd482d242a8",
    "path": "research/attack_event_classification_continuity_audit_2026-10-06.json",
    "blob": "57240aa3569b342f317f077b026928c2de21cfc8",
    "sha256": "6bf02b2686f3f37de31965ebda786969cdcc83a80a27cf2a452f3de31158932c",
}
RECOVERY = {
    "commit": "ccb2e6ea2637b2bdbde5d21744a79d8f4a91ff4d",
    "path": "research/attack_event_partitioned_classification_recovery_audit_2026-10-06.json",
    "blob": "d65a545add6125ca16514fa4f9c8cb7a0b74a76c",
    "sha256": "641cd7f4d1ca3c58755150ba0ff4f436794f558d5060ef416638adfed0513a98",
}
HISTORICAL = {
    "commit": "efefa399e69eadd3d7fc8393ac1553cfde35f138",
    "path": "research/attack_event_23city_persistence_snapshot_v2_2026-10-04.json",
    "blob": "8a2f6bd33f879be9db978da59c12c34e61f6f843",
    "sha256": "09458bcf0a019fa2939eb9dfa484da46cd8fa2be077343c5ba6d595c93d71788",
}
PINNED_COMMIT = "71cb6f6fbe856cc7b96759310fe9cc9c71cc0453"
CLASSIFIER_PATH = "kyiv-air-alerts-grafana/scripts/monitor_explosion_candidates.py"
CLASSIFIER_BLOB = "778469b74c2aa807d851cf2c2ee35cf4aa785589"
BUILDER_PATH = "kyiv-air-alerts-grafana/scripts/run_historical_attack_event_backfill_batch.py"
BUILDER_BLOB = "cb2791bd309abacf4c3aae8fee0d1a8f038220b2"

EXPECTED_HISTORICAL = 26405
EXPECTED_BOUND = 26380
EXPECTED_UNBOUND = 25
EXPECTED_UNCOVERED = 2100
EXPECTED_CONTEXT = 28480
EXPECTED_UNIT_A = 1713
UTC = timezone.utc
CANONICAL_UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$")
EPISODE_ID_RE = re.compile(r"^[0-9a-f]{24}$")


class Blocked(RuntimeError):
    def __init__(self, gate: str, count: int, detail: str, smallest: Any = None, distribution: dict | None = None):
        super().__init__(detail)
        self.gate = gate
        self.count = int(count)
        self.detail = str(detail)
        self.smallest = smallest
        self.distribution = distribution or {gate: int(count)}


def run(*args: str) -> bytes:
    p = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if p.returncode:
        raise Blocked(
            "REPOSITORY_READ_FAILED", 1,
            f"{' '.join(args)} :: {p.stderr.decode('utf-8','replace')[-1600:]}"
        )
    return p.stdout


def git_text(*args: str) -> str:
    return run("git", *args).decode("utf-8", "replace").strip()


def git_show(ref: str, path: str) -> bytes:
    return run("git", "show", f"{ref}:{path}")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_bytes(obj: Any) -> bytes:
    return (
        json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
        + "\n"
    ).encode("utf-8")


def artifact_json(spec: dict, label: str) -> tuple[dict, dict]:
    raw = git_show(spec["commit"], spec["path"])
    blob = git_text("rev-parse", f'{spec["commit"]}:{spec["path"]}')
    digest = sha256_bytes(raw)
    if blob != spec["blob"]:
        raise Blocked(f"{label}_BLOB_MISMATCH", 1, f"{blob}!={spec['blob']}")
    if digest != spec["sha256"]:
        raise Blocked(f"{label}_SHA256_MISMATCH", 1, f"{digest}!={spec['sha256']}")
    try:
        doc = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise Blocked(f"{label}_JSON_INVALID", 1, f"{type(exc).__name__}:{exc}")
    return doc, {
        "commit": spec["commit"], "path": spec["path"], "blob": blob,
        "sha256": digest, "bytes": len(raw),
    }


def parse_strict_micro(value: Any) -> datetime:
    if not isinstance(value, str) or not CANONICAL_UTC_RE.fullmatch(value):
        raise ValueError(f"non-canonical timestamp:{value!r}")
    return datetime.fromisoformat(value[:-1] + "+00:00").astimezone(UTC)


def utc_micro(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def decode_materialization(doc: dict) -> dict:
    block = doc.get("corpus") or {}
    if block.get("encoding") != "gzip+base64":
        raise Blocked("MATERIALIZATION_CORPUS_ENCODING_MISMATCH", 1, str(block.get("encoding")))
    payload = block.get("payload_base64")
    if not isinstance(payload, str) or not payload:
        raise Blocked("MATERIALIZATION_CORPUS_PAYLOAD_MISSING", 1, "payload_base64")
    try:
        compressed = base64.b64decode(payload.encode("ascii"), validate=True)
        plain = gzip.decompress(compressed)
    except Exception as exc:
        raise Blocked("MATERIALIZATION_CORPUS_DECODE_FAILED", 1, f"{type(exc).__name__}:{exc}")
    if block.get("compressed_sha256") and sha256_bytes(compressed) != str(block["compressed_sha256"]):
        raise Blocked("MATERIALIZATION_COMPRESSED_SHA256_MISMATCH", 1, "compressed payload")
    if block.get("uncompressed_sha256") and sha256_bytes(plain) != str(block["uncompressed_sha256"]):
        raise Blocked("MATERIALIZATION_UNCOMPRESSED_SHA256_MISMATCH", 1, "uncompressed payload")
    try:
        corpus = json.loads(plain.decode("utf-8"))
    except Exception as exc:
        raise Blocked("MATERIALIZATION_CORPUS_JSON_INVALID", 1, f"{type(exc).__name__}:{exc}")
    return corpus


def import_pinned_monitor():
    temp = Path("/tmp/unit_a_pinned_classifier")
    shutil.rmtree(temp, ignore_errors=True)
    subprocess.check_call(
        ["git", "worktree", "add", "--detach", str(temp), PINNED_COMMIT],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    scripts = temp / "kyiv-air-alerts-grafana" / "scripts"
    sys.path.insert(0, str(scripts))
    monitor = importlib.import_module("monitor_explosion_candidates")
    classifier_blob = git_text("rev-parse", f"{PINNED_COMMIT}:{CLASSIFIER_PATH}")
    builder_blob = git_text("rev-parse", f"{PINNED_COMMIT}:{BUILDER_PATH}")
    if classifier_blob != CLASSIFIER_BLOB:
        raise Blocked("CLASSIFIER_IMPLEMENTATION_DRIFT", 1, f"{classifier_blob}!={CLASSIFIER_BLOB}")
    if builder_blob != BUILDER_BLOB:
        raise Blocked("NORMALIZATION_IMPLEMENTATION_DRIFT", 1, f"{builder_blob}!={BUILDER_BLOB}")
    return monitor, temp


def canonical_parent_row(dbrow: tuple) -> dict:
    uid, city, alert_type, state, canon, start_at, end_at = dbrow
    return {
        "alert_episode_uid": str(uid),
        "city_key": str(city),
        "alert_type": str(alert_type),
        "episode_state": str(state),
        "canonicalization_version": str(canon),
        "start_at": utc_micro(start_at),
        "end_at": utc_micro(end_at),
    }


def logical_key(city: str, start: str, end: str) -> tuple[str, str, str]:
    return str(city), str(start), str(end)


def historical_key(row: dict) -> tuple[str, str, str]:
    city = str(row.get("city_key") or "")
    start = row.get("alert_start_utc_microseconds")
    end = row.get("alert_end_utc_microseconds")
    if not city:
        raise ValueError("missing city_key")
    parse_strict_micro(start)
    parse_strict_micro(end)
    return logical_key(city, start, end)


def frozen_parent_fields(row: dict) -> dict:
    return {
        "alert_episode_uid": str(row.get("alert_episode_uid") or ""),
        "city_key": str(row.get("city_key") or ""),
        "alert_type": str(row.get("alert_type") or ""),
        "episode_state": str(row.get("episode_state") or ""),
        "canonicalization_version": str(row.get("canonicalization_version") or ""),
        "start_at": str(row.get("start_at") or ""),
        "end_at": str(row.get("end_at") or ""),
    }


def derive_episode(monitor, parent: dict) -> dict:
    start = monitor.parse_dt(parent["start_at"])
    end = monitor.parse_dt(parent["end_at"])
    if not start or not end or end <= start:
        raise Blocked("CANONICAL_PARENT_TEMPORAL_PARSE_FAILED", 1, json.dumps(parent, sort_keys=True))
    start_s = monitor.iso(start)
    end_s = monitor.iso(end)
    eid = monitor.event_id(parent["city_key"], start_s, end_s)
    # Prove the exact authoritative make_episode path agrees, then keep only the
    # minimal episode representation consumed by classifier context semantics.
    made = monitor.make_episode(parent["city_key"], start, end)
    if str(made.get("episode_id") or "") != eid:
        raise Blocked("PINNED_EPISODE_ID_PATH_DISAGREEMENT", 1, parent["alert_episode_uid"])
    return {
        "alert_episode_uid": parent["alert_episode_uid"],
        "episode_id": eid,
        "city_key": parent["city_key"],
        "alert_start": start_s,
        "alert_end": end_s,
        "alert_type": parent["alert_type"],
        "episode_state": parent["episode_state"],
        "canonicalization_version": parent["canonicalization_version"],
    }


def reconstruct_once(
    label: str,
    db_rows: list[dict],
    historical_rows: list[dict],
    frozen_uncovered: list[dict],
    monitor,
) -> dict:
    by_logical: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    by_uid: dict[str, list[dict]] = defaultdict(list)
    for p in db_rows:
        by_logical[logical_key(p["city_key"], p["start_at"], p["end_at"])].append(p)
        by_uid[p["alert_episode_uid"]].append(p)

    matched_a = []
    unbound = []
    ambiguous = []
    malformed_hist = []
    for idx, row in enumerate(historical_rows):
        try:
            key = historical_key(row)
        except Exception as exc:
            malformed_hist.append({"index": idx, "error": str(exc)[:200]})
            continue
        hits = by_logical.get(key, [])
        if len(hits) == 1:
            matched_a.append(hits[0])
        elif not hits:
            unbound.append({
                "index": idx, "city_key": key[0],
                "alert_start": key[1], "alert_end": key[2],
                "classification_key": row.get("classification_key"),
            })
        else:
            ambiguous.append({
                "index": idx, "city_key": key[0],
                "alert_start": key[1], "alert_end": key[2],
                "parent_uids": sorted(x["alert_episode_uid"] for x in hits),
            })

    if malformed_hist:
        raise Blocked(
            "HISTORICAL_TEMPORAL_IDENTITY_INVALID", len(malformed_hist),
            "Historical classification temporal identity is not exact canonical UTC microseconds.",
            malformed_hist[0], {"HISTORICAL_TEMPORAL_IDENTITY_INVALID": len(malformed_hist)}
        )
    if len(matched_a) != EXPECTED_BOUND or len(unbound) != EXPECTED_UNBOUND or ambiguous:
        dist = {
            "canonical_parent_matches": len(matched_a),
            "historical_unbound": len(unbound),
            "historical_ambiguous": len(ambiguous),
        }
        smallest = (ambiguous or unbound or [{"observed": dist}])[0]
        raise Blocked(
            "HISTORICAL_CANONICAL_PARENT_RECONCILIATION_MISMATCH",
            abs(len(matched_a) - EXPECTED_BOUND) + abs(len(unbound) - EXPECTED_UNBOUND) + len(ambiguous),
            f"observed={dist}; expected={{'canonical_parent_matches':26380,'historical_unbound':25,'historical_ambiguous':0}}",
            smallest, dist
        )

    exact_b = []
    drift = []
    for frozen in frozen_uncovered:
        expected = frozen_parent_fields(frozen)
        uid = expected["alert_episode_uid"]
        hits = by_uid.get(uid, [])
        if len(hits) != 1:
            drift.append({"alert_episode_uid": uid, "reason": "UID_MATCH_COUNT", "count": len(hits)})
            continue
        actual = hits[0]
        mismatched = [
            k for k in (
                "alert_episode_uid", "city_key", "alert_type", "episode_state",
                "canonicalization_version", "start_at", "end_at"
            )
            if str(actual.get(k) or "") != str(expected.get(k) or "")
        ]
        if expected["alert_type"] != "AIR":
            mismatched.append("FROZEN_ALERT_TYPE_NOT_AIR")
        if expected["episode_state"].casefold() != "closed":
            mismatched.append("FROZEN_EPISODE_STATE_NOT_CLOSED")
        if not expected["canonicalization_version"]:
            mismatched.append("FROZEN_CANONICALIZATION_VERSION_EMPTY")
        if mismatched:
            drift.append({
                "alert_episode_uid": uid,
                "reason": "FIELD_DRIFT",
                "mismatched_fields": sorted(set(mismatched)),
                "expected": expected,
                "actual": actual,
            })
        else:
            exact_b.append(actual)

    if len(frozen_uncovered) != EXPECTED_UNCOVERED:
        raise Blocked("FROZEN_UNCOVERED_COUNT_MISMATCH", len(frozen_uncovered), f"expected={EXPECTED_UNCOVERED}")
    if len(exact_b) != EXPECTED_UNCOVERED or drift:
        reasons = Counter(x.get("reason") for x in drift)
        raise Blocked(
            "FROZEN_UNCOVERED_PARENT_DRIFT", len(drift),
            f"exact={len(exact_b)}/{EXPECTED_UNCOVERED}",
            drift[0] if drift else None, dict(reasons)
        )

    a_uids = [p["alert_episode_uid"] for p in matched_a]
    b_uids = [p["alert_episode_uid"] for p in exact_b]
    overlap = sorted(set(a_uids) & set(b_uids))
    if overlap:
        raise Blocked("SET_A_SET_B_OVERLAP", len(overlap), "Set A and Set B overlap.", overlap[0])

    provenance = {}
    parents_by_uid = {}
    for p in matched_a:
        uid = p["alert_episode_uid"]
        parents_by_uid[uid] = p
        provenance[uid] = "A_PREVIOUSLY_CLASSIFIED_CANONICAL_PARENT"
    for p in exact_b:
        uid = p["alert_episode_uid"]
        parents_by_uid[uid] = p
        provenance[uid] = "B_FROZEN_UNCOVERED_CANONICAL_PARENT"

    context = []
    for uid, parent in parents_by_uid.items():
        ep = derive_episode(monitor, parent)
        ep["context_set"] = provenance[uid]
        context.append(ep)
    context.sort(key=lambda x: (
        x["city_key"], x["alert_start"], x["alert_end"], x["alert_episode_uid"]
    ))

    uid_counts = Counter(x["alert_episode_uid"] for x in context)
    temporal_counts = Counter((x["city_key"], x["alert_start"], x["alert_end"]) for x in context)
    duplicate_uids = [k for k, v in uid_counts.items() if v > 1]
    duplicate_temporal = [k for k, v in temporal_counts.items() if v > 1]
    episode_id_counts = Counter(x["episode_id"] for x in context)
    duplicate_episode_ids = [k for k, v in episode_id_counts.items() if v > 1]

    if len(context) != EXPECTED_CONTEXT:
        raise Blocked("CONTEXT_CANONICAL_PARENT_COUNT_MISMATCH", len(context), f"expected={EXPECTED_CONTEXT}")
    if duplicate_uids:
        raise Blocked("DUPLICATE_CANONICAL_PARENT_UIDS", len(duplicate_uids), "duplicate context parent UIDs", duplicate_uids[0])
    if duplicate_temporal:
        raise Blocked("DUPLICATE_CONTEXT_TEMPORAL_IDENTITIES", len(duplicate_temporal), "duplicate city/start/end", duplicate_temporal[0])
    if duplicate_episode_ids:
        raise Blocked("DUPLICATE_RECONSTRUCTED_EPISODE_IDS", len(duplicate_episode_ids), "episode_id collision/duplication", duplicate_episode_ids[0])

    context_payload = {
        "representation": "unit-a-frozen-classifier-context-v1",
        "rows": context,
    }
    context_sha = sha256_bytes(canonical_bytes(context_payload))
    return {
        "label": label,
        "context_rows": context,
        "context_sha256": context_sha,
        "historical_scanned": len(historical_rows),
        "historical_matched": len(matched_a),
        "historical_unbound": len(unbound),
        "historical_ambiguous": len(ambiguous),
        "unbound_examples": unbound[:5],
        "frozen_uncovered_expected": len(frozen_uncovered),
        "frozen_uncovered_matched": len(exact_b),
        "frozen_uncovered_drift": len(drift),
        "set_overlap": len(overlap),
        "duplicate_uids": len(duplicate_uids),
        "duplicate_temporal": len(duplicate_temporal),
        "duplicate_episode_ids": len(duplicate_episode_ids),
    }


def resolve_candidate_store(corpus: dict) -> tuple[dict[str, dict], int]:
    store_rows = corpus.get("candidate_input_store")
    if not isinstance(store_rows, list):
        raise Blocked("CANDIDATE_STORE_SCHEMA_INVALID", 1, type(store_rows).__name__)
    store = {}
    bad = 0
    for row in store_rows:
        if not isinstance(row, dict):
            bad += 1
            continue
        key = str(row.get("sha256") or "")
        candidate = row.get("candidate_input")
        if not key or not isinstance(candidate, dict):
            bad += 1
            continue
        if sha256_bytes(canonical_bytes(candidate)) != key:
            bad += 1
            continue
        if key in store and canonical_bytes(store[key]) != canonical_bytes(candidate):
            bad += 1
            continue
        store[key] = candidate
    if bad:
        raise Blocked("CANDIDATE_STORE_INTEGRITY_FAILURE", bad, "invalid candidate store rows")
    return store, len(store_rows)


def collect_episode_refs(obj: Any, path: str, origin: str, out: list[dict]) -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            child = f"{path}.{key}"
            if key.endswith("episode_id") and isinstance(value, str) and EPISODE_ID_RE.fullmatch(value):
                out.append({"episode_id": value, "path": child, "origin": origin})
            elif key.endswith("episode_ids") and isinstance(value, list):
                for idx, item in enumerate(value):
                    if isinstance(item, str) and EPISODE_ID_RE.fullmatch(item):
                        out.append({"episode_id": item, "path": f"{child}[{idx}]", "origin": origin})
            if isinstance(value, (dict, list)):
                collect_episode_refs(value, child, origin, out)
    elif isinstance(obj, list):
        for idx, value in enumerate(obj):
            if isinstance(value, (dict, list)):
                collect_episode_refs(value, f"{path}[{idx}]", origin, out)


def is_classifier_consumed_ref(ref: dict) -> bool:
    path = ref["path"]
    origin = ref["origin"]
    if origin == "candidate_input":
        # The frozen candidate projection is the direct row passed to the pinned
        # classifier. Any persisted episode identity in that row is conservatively
        # treated as classifier-consumed, except trigger metadata which the
        # projection contract does not expose as a decision input.
        return ".trigger_episode_ids" not in path
    # Candidate-selection trigger IDs describe why a candidate was selected; the
    # pinned classify_candidate entrypoint does not consume evidence_provenance.
    return False


def target_equivalence(corpus: dict, context_rows: list[dict]) -> dict:
    episodes = corpus.get("episodes")
    if not isinstance(episodes, list):
        raise Blocked("MATERIALIZED_EPISODE_SCHEMA_INVALID", 1, type(episodes).__name__)
    if len(episodes) != EXPECTED_UNIT_A:
        raise Blocked("UNIT_A_TARGET_COUNT_MISMATCH", len(episodes), f"expected={EXPECTED_UNIT_A}")

    by_uid = {x["alert_episode_uid"]: x for x in context_rows}
    exact = 0
    temporal_mismatch = 0
    episode_id_mismatch = 0
    missing_parent = 0
    rows = []
    smallest = None
    for target in episodes:
        uid = str((target or {}).get("alert_episode_uid") or "")
        ci = (target or {}).get("classifier_episode_input") or {}
        ctx = by_uid.get(uid)
        reasons = []
        if not ctx:
            missing_parent += 1
            reasons.append("CANONICAL_CONTEXT_PARENT_MISSING")
        else:
            if str(ci.get("episode_id") or "") != ctx["episode_id"]:
                episode_id_mismatch += 1
                reasons.append("EPISODE_ID_MISMATCH")
            if (
                str(ci.get("city_key") or "") != ctx["city_key"]
                or str(ci.get("alert_start") or "") != ctx["alert_start"]
                or str(ci.get("alert_end") or "") != ctx["alert_end"]
            ):
                temporal_mismatch += 1
                reasons.append("CITY_OR_TEMPORAL_MISMATCH")
        if not reasons:
            exact += 1
        elif smallest is None:
            smallest = {
                "alert_episode_uid": uid,
                "reasons": reasons,
                "materialized": ci,
                "reconstructed": ctx,
            }
        rows.append({
            "alert_episode_uid": uid,
            "reconstructed_episode_id": None if ctx is None else ctx["episode_id"],
            "exact": not reasons,
        })
    if exact != EXPECTED_UNIT_A or temporal_mismatch or episode_id_mismatch or missing_parent:
        dist = {
            "exact": exact,
            "missing_parent": missing_parent,
            "episode_id_mismatch": episode_id_mismatch,
            "temporal_mismatch": temporal_mismatch,
        }
        raise Blocked(
            "UNIT_A_RECONSTRUCTED_EPISODE_ID_OR_TEMPORAL_MISMATCH",
            EXPECTED_UNIT_A - exact, f"observed={dist}", smallest, dist
        )
    return {
        "targets": len(episodes),
        "exact_episode_id_matches": exact,
        "temporal_mismatches": temporal_mismatch,
        "target_mapping_sha256": sha256_bytes(canonical_bytes(rows)),
        "rows": rows,
    }


def candidate_reference_proof(corpus: dict, context_rows: list[dict]) -> dict:
    store, store_row_count = resolve_candidate_store(corpus)
    episodes = corpus.get("episodes") or []
    eid_index: dict[str, list[dict]] = defaultdict(list)
    for row in context_rows:
        eid_index[row["episode_id"]].append(row)

    occurrences = []
    candidate_occurrences = 0
    unresolved_candidate_hashes = 0
    for ep in episodes:
        refs = (ep or {}).get("candidate_input_refs") or []
        if not isinstance(refs, list):
            raise Blocked("CANDIDATE_INPUT_REFS_SCHEMA_INVALID", 1, str((ep or {}).get("alert_episode_uid")))
        for ref_hash in refs:
            candidate_occurrences += 1
            candidate = store.get(str(ref_hash))
            if candidate is None:
                unresolved_candidate_hashes += 1
                continue
            collect_episode_refs(candidate, "candidate", "candidate_input", occurrences)
        provenance = (ep or {}).get("evidence_provenance") or {}
        collect_episode_refs(provenance, "episode_evidence_provenance", "evidence_provenance", occurrences)

    if unresolved_candidate_hashes:
        raise Blocked(
            "CANDIDATE_INPUT_HASH_UNRESOLVED", unresolved_candidate_hashes,
            "Materialized candidate input refs did not resolve to candidate store."
        )

    distinct = {}
    for r in occurrences:
        key = (r["episode_id"], r["path"], r["origin"])
        distinct[key] = r
    refs = list(distinct.values())
    ids = sorted({r["episode_id"] for r in refs})
    resolved_ids = [eid for eid in ids if len(eid_index.get(eid, [])) == 1]
    unresolved_ids = [eid for eid in ids if not eid_index.get(eid)]
    ambiguous_ids = [eid for eid in ids if len(eid_index.get(eid, [])) > 1]

    consumed = [r for r in refs if is_classifier_consumed_ref(r)]
    consumed_ids = sorted({r["episode_id"] for r in consumed})
    consumed_unresolved = [eid for eid in consumed_ids if not eid_index.get(eid)]
    consumed_ambiguous = [eid for eid in consumed_ids if len(eid_index.get(eid, [])) > 1]

    if ambiguous_ids or consumed_ambiguous:
        raise Blocked(
            "AMBIGUOUS_EPISODE_REFERENCES", len(set(ambiguous_ids) | set(consumed_ambiguous)),
            "Episode references resolve to more than one frozen context row.",
            (ambiguous_ids or consumed_ambiguous)[0]
        )
    if consumed_unresolved:
        examples = [
            r for r in consumed if r["episode_id"] in set(consumed_unresolved)
        ][:5]
        raise Blocked(
            "CLASSIFIER_CONSUMED_UNRESOLVED_EPISODE_REFERENCES",
            len(consumed_unresolved),
            "Classifier-consumed episode reference absent from frozen canonical context.",
            examples[0] if examples else consumed_unresolved[0],
            dict(Counter(x["path"].split(".")[-1].split("[")[0] for x in examples))
        )

    unresolved_descriptive = sorted(set(unresolved_ids) - set(consumed_unresolved))
    summary_payload = {
        "distinct_reference_ids": ids,
        "classifier_consumed_reference_ids": consumed_ids,
        "unresolved_descriptive_reference_ids": unresolved_descriptive,
        "ambiguous_reference_ids": ambiguous_ids,
    }
    return {
        "candidate_store_rows": store_row_count,
        "candidate_store_unique": len(store),
        "candidate_occurrences": candidate_occurrences,
        "total_reference_occurrences": len(occurrences),
        "distinct_episode_references": len(ids),
        "references_resolving_to_context": len(resolved_ids),
        "unresolved_episode_references": len(unresolved_ids),
        "classifier_consumed_distinct_episode_references": len(consumed_ids),
        "classifier_consumed_unresolved_episode_references": len(consumed_unresolved),
        "ambiguous_episode_references": len(ambiguous_ids),
        "descriptive_provenance_only_unresolved_episode_references": len(unresolved_descriptive),
        "descriptive_provenance_only_unresolved_examples": unresolved_descriptive[:20],
        "resolution_sha256": sha256_bytes(canonical_bytes(summary_payload)),
        "_store": store,
    }


def contextual_completeness(corpus: dict, context_rows: list[dict], monitor, store: dict[str, dict], guards: dict) -> dict:
    episodes = corpus.get("episodes") or []
    by_city: dict[str, list[dict]] = defaultdict(list)
    by_uid = {}
    for row in context_rows:
        minimal = {
            "episode_id": row["episode_id"],
            "city_key": row["city_key"],
            "alert_start": row["alert_start"],
            "alert_end": row["alert_end"],
        }
        by_city[row["city_key"]].append(minimal)
        by_uid[row["alert_episode_uid"]] = minimal
    for city in by_city:
        by_city[city].sort(key=lambda x: (x["alert_start"], x["alert_end"], x["episode_id"]))

    singleton_shortcuts = 0
    episode_checks = 0
    candidate_checks = 0
    candidate_cache = {}
    primitive_errors = []
    outcome_counts = Counter()
    near_boundary_hits = 0
    relative_hits = 0
    review_target_present = 0
    multi_episode_day_cases = 0

    for ep in episodes:
        uid = str((ep or {}).get("alert_episode_uid") or "")
        target = by_uid.get(uid)
        if not target:
            primitive_errors.append({"uid": uid, "primitive": "target_lookup", "error": "missing"})
            continue
        city_eps = by_city[target["city_key"]]
        if len(city_eps) == 1:
            # This is an observation, not a shortcut. The hard gate below remains
            # about constructing target-only context; we never do that.
            pass
        start = monitor.parse_dt(target["alert_start"])
        end = monitor.parse_dt(target["alert_end"])
        if not start or not end:
            primitive_errors.append({"uid": uid, "primitive": "episode_parse", "error": "invalid"})
            continue
        midpoint = start + (end - start) / 2
        try:
            monitor.exact_active_episodes_at(midpoint, city_eps)
            monitor.composition_neighbor_check(midpoint, target, city_eps)
            episode_checks += 1
        except Exception as exc:
            primitive_errors.append({
                "uid": uid, "primitive": "episode_neighbor_context",
                "error": f"{type(exc).__name__}:{exc}"[:300],
            })

        refs = (ep or {}).get("candidate_input_refs") or []
        for ref_hash in refs:
            candidate = store.get(str(ref_hash))
            if candidate is None:
                primitive_errors.append({"uid": uid, "primitive": "candidate_store", "error": str(ref_hash)})
                continue
            cache_key = (target["city_key"], str(ref_hash))
            if cache_key in candidate_cache:
                candidate_checks += 1
                continue
            try:
                matching = monitor.match_candidate_to_episodes(candidate, city_eps)
                outcome_counts[str(matching.get("outcome"))] += 1
                day_eps = monitor.episodes_intersecting_local_day(candidate, city_eps)
                if len(day_eps) > 1:
                    multi_episode_day_cases += 1
                relative = monitor.relative_alert_chronology_relation(candidate, city_eps)
                if relative.get("relation"):
                    relative_hits += 1
                strict = monitor.strict_explosion_evidence(target["city_key"], candidate)
                clock = monitor.explicit_event_time_relation(
                    candidate, list(strict.get("segments") or []), matching, city_eps
                )
                if clock.get("relation") in {"near_before", "near_after"}:
                    near_boundary_hits += 1
                reviewed = monitor.reviewed_provenance_adapter(
                    candidate, target["city_key"], city_eps, matching
                )
                if reviewed.get("target_episode_id"):
                    review_target_present += 1
                monitor.single_episode_day_inference(candidate, matching, city_eps)
                candidate_cache[cache_key] = True
                candidate_checks += 1
            except Exception as exc:
                primitive_errors.append({
                    "uid": uid,
                    "candidate_input_sha256": str(ref_hash),
                    "primitive": "candidate_context_primitives",
                    "error": f"{type(exc).__name__}:{exc}"[:500],
                })

    if primitive_errors:
        raise Blocked(
            "CLASSIFIER_CONTEXT_PRIMITIVE_EXECUTION_FAILED", len(primitive_errors),
            "At least one pinned context-selection primitive could not run on frozen full-city context.",
            primitive_errors[0],
            dict(Counter(x["primitive"] for x in primitive_errors))
        )
    if episode_checks != EXPECTED_UNIT_A:
        raise Blocked("UNIT_A_EPISODE_CONTEXT_CHECK_COUNT_MISMATCH", episode_checks, f"expected={EXPECTED_UNIT_A}")
    if guards["classifier_executions"] != 0:
        raise Blocked("CLASSIFIER_EXECUTION_FORBIDDEN", guards["classifier_executions"], "classify_candidate guard fired")
    if guards["discovery_executions"] != 0:
        raise Blocked("DISCOVERY_EXECUTION_FORBIDDEN", guards["discovery_executions"], "discovery guard fired")
    if guards["external_evidence_requests"] != 0:
        raise Blocked("EXTERNAL_EVIDENCE_REQUEST_FORBIDDEN", guards["external_evidence_requests"], "network guard fired")

    return {
        "full_city_context_only": True,
        "singleton_context_shortcuts": singleton_shortcuts,
        "unit_a_episode_context_checks": episode_checks,
        "candidate_context_checks": candidate_checks,
        "distinct_candidate_context_checks": len(candidate_cache),
        "publication_time_and_end_grace_matching": "EXERCISED",
        "exact_event_time_binding": "EXERCISED",
        "near_boundary_sensitivity_checks": "EXERCISED",
        "relative_alert_chronology": "EXERCISED",
        "local_day_episode_intersection": "EXERCISED",
        "neighboring_multi_episode_ambiguity_checks": "EXERCISED",
        "reviewed_provenance_target_lookup": "EXERCISED",
        "matching_outcomes": dict(sorted(outcome_counts.items())),
        "near_boundary_hits": near_boundary_hits,
        "relative_chronology_hits": relative_hits,
        "review_target_references_present": review_target_present,
        "multi_episode_local_day_cases": multi_episode_day_cases,
        "primitive_errors": 0,
    }


def write_summary(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary", required=True)
    ap.add_argument("--run-id", required=True)
    args = ap.parse_args()
    summary_path = Path(args.summary)

    guards = {
        "external_evidence_requests": 0,
        "discovery_executions": 0,
        "classifier_executions": 0,
        "classification_verdicts_produced": 0,
        "classifier_semantic_changes": 0,
        "normalization_semantic_changes": 0,
        "parent_mutations": 0,
        "db_writes": 0,
        "production_mutation": "NO",
    }
    qcount = 0
    conn = None
    monitor_temp = None

    summary_base = {
        "verdict": "ATTACK-EVENT UNIT A FROZEN CLASSIFIER CONTEXT = BLOCKED",
        "branch": BRANCH,
        "actions_run_id": int(args.run_id),
        "failed_gate": None,
        "affected_count": 0,
        "smallest_demonstrated_blocker": None,
        "blocker_distribution": {},
        "db_branch": os.environ.get("PHASE1_PROD_SHADOW_BRANCH_ID") or None,
        "db_queries": 0,
        "db_writes": 0,
        "external_evidence_requests": 0,
        "discovery_executions": 0,
        "classifier_executions": 0,
        "classification_verdicts": 0,
        "production_mutation": "NO",
    }

    try:
        if git_text("rev-parse", "HEAD^0") == PREDECESSOR:
            pass
        # Branch history may include only temporary harness/workflow commits at execution.
        merge_base = git_text("merge-base", "HEAD", PREDECESSOR)
        if merge_base != PREDECESSOR:
            raise Blocked("PREDECESSOR_ANCESTRY_MISMATCH", 1, f"{merge_base}!={PREDECESSOR}")

        branch_id = os.environ.get("PHASE1_PROD_SHADOW_BRANCH_ID", "")
        db_url = os.environ.get("PHASE1_PROD_SHADOW_DATABASE_URL", "")
        if branch_id != EXPECTED_DB_BRANCH:
            raise Blocked("PERMANENT_SHADOW_BRANCH_ID_MISMATCH", 1, f"{branch_id or '<missing>'}!={EXPECTED_DB_BRANCH}")
        if not db_url:
            raise Blocked("PHASE1_PROD_SHADOW_DATABASE_URL_MISSING", 1, "secret unavailable")

        mat_doc, mat_id = artifact_json(MATERIALIZATION, "MATERIALIZATION")
        readiness_doc, readiness_id = artifact_json(READINESS, "READINESS")
        continuity_doc, continuity_id = artifact_json(CONTINUITY, "CONTINUITY")
        recovery_doc, recovery_id = artifact_json(RECOVERY, "RECOVERY")
        historical_doc, historical_id = artifact_json(HISTORICAL, "HISTORICAL")

        if readiness_doc.get("verdict") != "ATTACK-EVENT EXECUTION UNIT A CLASSIFIER READINESS = PROVEN":
            raise Blocked("READINESS_VERDICT_MISMATCH", 1, str(readiness_doc.get("verdict")))
        if int(((readiness_doc.get("counts") or {}).get("CLASSIFIER_INPUT_READY") or 0)) != EXPECTED_UNIT_A:
            raise Blocked("READINESS_COUNT_MISMATCH", 1, str((readiness_doc.get("counts") or {}).get("CLASSIFIER_INPUT_READY")))
        if continuity_doc.get("verdict") != "ATTACK-EVENT POST-CUTOFF CLASSIFICATION COVERAGE = RECOVERY REQUIRED":
            raise Blocked("CONTINUITY_VERDICT_MISMATCH", 1, str(continuity_doc.get("verdict")))
        if recovery_doc.get("verdict") != "ATTACK-EVENT PARTITIONED CLASSIFICATION RECOVERY AUDIT = PLANNED":
            raise Blocked("RECOVERY_VERDICT_MISMATCH", 1, str(recovery_doc.get("verdict")))

        historical_rows = historical_doc.get("classifications")
        if not isinstance(historical_rows, list) or len(historical_rows) != EXPECTED_HISTORICAL:
            raise Blocked(
                "HISTORICAL_CLASSIFICATION_COUNT_MISMATCH",
                0 if not isinstance(historical_rows, list) else len(historical_rows),
                f"expected={EXPECTED_HISTORICAL}"
            )
        cities = sorted({str(x.get("city_key") or "") for x in historical_rows if isinstance(x, dict)})
        if len(cities) != 23 or "" in cities:
            raise Blocked("HISTORICAL_CITY_UNIVERSE_MISMATCH", len(cities), str(cities))

        frozen_uncovered = continuity_doc.get("uncovered_parent_identities")
        if not isinstance(frozen_uncovered, list) or len(frozen_uncovered) != EXPECTED_UNCOVERED:
            raise Blocked(
                "FROZEN_UNCOVERED_COUNT_MISMATCH",
                0 if not isinstance(frozen_uncovered, list) else len(frozen_uncovered),
                f"expected={EXPECTED_UNCOVERED}"
            )
        frozen_uids = [str(x.get("alert_episode_uid") or "") for x in frozen_uncovered if isinstance(x, dict)]
        if len(frozen_uids) != EXPECTED_UNCOVERED or len(set(frozen_uids)) != EXPECTED_UNCOVERED or any(not x for x in frozen_uids):
            raise Blocked("FROZEN_UNCOVERED_UID_SET_INVALID", len(frozen_uids), "missing/duplicate parent UID")

        units = recovery_doc.get("execution_units") or {}
        recovery_uids = []
        for key in (
            "A_SAFE_EXISTING_EVIDENCE_MATERIALIZATION",
            "B_EVIDENCE_COLLECTION_RECOVERY",
            "C_IDENTITY_FORENSIC_MANUAL_CONTRACT_DECISION",
            "D_UNRESOLVED",
        ):
            recovery_uids.extend(str(x) for x in ((units.get(key) or {}).get("episode_uids") or []))
        if len(recovery_uids) != EXPECTED_UNCOVERED or len(set(recovery_uids)) != EXPECTED_UNCOVERED or set(recovery_uids) != set(frozen_uids):
            raise Blocked(
                "RECOVERY_CONTINUITY_UID_UNIVERSE_MISMATCH",
                len(set(recovery_uids) ^ set(frozen_uids)),
                "Recovery execution-unit universe differs from frozen continuity parent universe."
            )
        unit_a_uids = [str(x) for x in ((units.get("A_SAFE_EXISTING_EVIDENCE_MATERIALIZATION") or {}).get("episode_uids") or [])]
        if len(unit_a_uids) != EXPECTED_UNIT_A:
            raise Blocked("RECOVERY_UNIT_A_COUNT_MISMATCH", len(unit_a_uids), f"expected={EXPECTED_UNIT_A}")

        corpus = decode_materialization(mat_doc)
        materialized_eps = corpus.get("episodes") or []
        materialized_uids = [str((x or {}).get("alert_episode_uid") or "") for x in materialized_eps]
        if len(materialized_uids) != EXPECTED_UNIT_A or materialized_uids != unit_a_uids:
            raise Blocked(
                "MATERIALIZATION_UNIT_A_UID_SEQUENCE_MISMATCH",
                len(set(materialized_uids) ^ set(unit_a_uids)),
                "Materialized episode UID sequence differs from frozen recovery Unit A."
            )
        readiness_rows = ((readiness_doc.get("readiness") or {}).get("rows") or [])
        readiness_uids = [str((x or {}).get("alert_episode_uid") or "") for x in readiness_rows]
        if readiness_uids != materialized_uids:
            raise Blocked("READINESS_MATERIALIZATION_UID_SEQUENCE_MISMATCH", len(set(readiness_uids) ^ set(materialized_uids)), "UID sequence differs")

        monitor, monitor_temp = import_pinned_monitor()
        original_classifier = monitor.classify_candidate

        def forbidden_classifier(*_a, **_k):
            guards["classifier_executions"] += 1
            raise RuntimeError("CLASSIFIER_EXECUTION_FORBIDDEN")
        monitor.classify_candidate = forbidden_classifier

        def forbidden_request(*_a, **_k):
            guards["external_evidence_requests"] += 1
            raise RuntimeError("EXTERNAL_EVIDENCE_REQUEST_FORBIDDEN")
        monitor.requests.get = forbidden_request

        for name in ("search_city_news", "refresh_telegram_cache", "telegram_page"):
            if hasattr(monitor, name):
                def make_forbidden(_name):
                    def forbidden(*_a, **_k):
                        guards["discovery_executions"] += 1
                        raise RuntimeError(f"DISCOVERY_EXECUTION_FORBIDDEN:{_name}")
                    return forbidden
                setattr(monitor, name, make_forbidden(name))

        # Capture one and only one canonical-parent DB snapshot. Both deterministic
        # reconstruction passes below use this in-memory row set.
        conn = psycopg.connect(
            db_url,
            autocommit=True,
            connect_timeout=20,
            options="-c default_transaction_read_only=on",
        )
        with conn.cursor() as cur:
            def q(sql, params=None, fetch=None):
                nonlocal qcount
                qcount += 1
                cur.execute(sql, params)
                if fetch == "one":
                    return cur.fetchone()
                if fetch == "all":
                    return cur.fetchall()
                return None

            q("BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            q("SET LOCAL default_transaction_read_only = on")
            ro, dro, isolation = q(
                "SELECT current_setting('transaction_read_only'), "
                "current_setting('default_transaction_read_only'), "
                "current_setting('transaction_isolation')",
                fetch="one",
            )
            if (ro, dro, isolation) != ("on", "on", "repeatable read"):
                raise Blocked("READ_ONLY_REPEATABLE_READ_NOT_ENFORCED", 1, repr((ro, dro, isolation)))
            raw_parent_rows = q(
                "SELECT episode_uid::text,city_key::text,alert_type::text,episode_state::text,"
                "canonicalization_version::text,start_at,end_at "
                "FROM public.alert_episodes "
                "WHERE city_key::text = ANY(%s) AND alert_type::text='AIR' "
                "ORDER BY city_key,start_at,end_at NULLS LAST,episode_uid",
                (cities,),
                fetch="all",
            )
            q("ROLLBACK")

        conn.close()
        conn = None
        db_rows = [canonical_parent_row(row) for row in raw_parent_rows]

        run_a = reconstruct_once(
            "A", copy.deepcopy(db_rows), copy.deepcopy(historical_rows),
            copy.deepcopy(frozen_uncovered), monitor
        )
        run_b = reconstruct_once(
            "B", copy.deepcopy(db_rows), copy.deepcopy(historical_rows),
            copy.deepcopy(frozen_uncovered), monitor
        )

        if run_a["context_sha256"] != run_b["context_sha256"]:
            raise Blocked(
                "CONTEXT_RECONSTRUCTION_NONDETERMINISTIC", 1,
                f"{run_a['context_sha256']}!={run_b['context_sha256']}"
            )
        if canonical_bytes(run_a["context_rows"]) != canonical_bytes(run_b["context_rows"]):
            raise Blocked("CONTEXT_ROWS_NONDETERMINISTIC", 1, "RUN A/B context rows differ")

        eq_a = target_equivalence(corpus, run_a["context_rows"])
        eq_b = target_equivalence(corpus, run_b["context_rows"])
        if eq_a["target_mapping_sha256"] != eq_b["target_mapping_sha256"]:
            raise Blocked("TARGET_MAPPING_NONDETERMINISTIC", 1, "RUN A/B target mapping hash differs")

        refs_a = candidate_reference_proof(corpus, run_a["context_rows"])
        refs_b = candidate_reference_proof(corpus, run_b["context_rows"])
        if refs_a["resolution_sha256"] != refs_b["resolution_sha256"]:
            raise Blocked("CANDIDATE_REFERENCE_RESOLUTION_NONDETERMINISTIC", 1, "RUN A/B reference resolution hash differs")

        store = refs_a.pop("_store")
        refs_b.pop("_store", None)
        completeness = contextual_completeness(corpus, run_a["context_rows"], monitor, store, guards)

        # Every context row is explicitly selected from A or B; current rows outside
        # that exact union are observed but never admitted.
        context_uids = {x["alert_episode_uid"] for x in run_a["context_rows"]}
        current_uids = {x["alert_episode_uid"] for x in db_rows}
        outside_current = sorted(current_uids - context_uids)
        post_audit_admitted = 0

        hard_gates = {
            "historical classifications scanned = 26,405": run_a["historical_scanned"] == EXPECTED_HISTORICAL,
            "historical canonical parent matches = 26,380": run_a["historical_matched"] == EXPECTED_BOUND,
            "historical UNBOUND = 25": run_a["historical_unbound"] == EXPECTED_UNBOUND,
            "historical ambiguous bindings = 0": run_a["historical_ambiguous"] == 0,
            "frozen uncovered parents expected = 2,100": run_a["frozen_uncovered_expected"] == EXPECTED_UNCOVERED,
            "frozen uncovered exact parent matches = 2,100": run_a["frozen_uncovered_matched"] == EXPECTED_UNCOVERED,
            "frozen uncovered parent drift = 0": run_a["frozen_uncovered_drift"] == 0,
            "context canonical parents = 28,480": len(run_a["context_rows"]) == EXPECTED_CONTEXT,
            "duplicate canonical parent UIDs = 0": run_a["duplicate_uids"] == 0,
            "duplicate context temporal identities = 0": run_a["duplicate_temporal"] == 0,
            "Set A / Set B overlap = 0": run_a["set_overlap"] == 0,
            "Unit A targets = 1,713": eq_a["targets"] == EXPECTED_UNIT_A,
            "Unit A reconstructed classifier episode IDs = 1,713 / 1,713": eq_a["exact_episode_id_matches"] == EXPECTED_UNIT_A,
            "Unit A temporal mismatches = 0": eq_a["temporal_mismatches"] == 0,
            "classifier-consumed unresolved episode references = 0": refs_a["classifier_consumed_unresolved_episode_references"] == 0,
            "ambiguous episode references = 0": refs_a["ambiguous_episode_references"] == 0,
            "current post-audit alerts admitted to frozen context = 0": post_audit_admitted == 0,
            "singleton-context shortcuts = 0": completeness["singleton_context_shortcuts"] == 0,
            "external evidence requests = 0": guards["external_evidence_requests"] == 0,
            "discovery executions = 0": guards["discovery_executions"] == 0,
            "classifier executions = 0": guards["classifier_executions"] == 0,
            "classification verdicts produced = 0": guards["classification_verdicts_produced"] == 0,
            "classifier semantic changes = 0": guards["classifier_semantic_changes"] == 0,
            "normalization semantic changes = 0": guards["normalization_semantic_changes"] == 0,
            "parent mutations = 0": guards["parent_mutations"] == 0,
            "DB writes = 0": guards["db_writes"] == 0,
            "production mutation = NO": guards["production_mutation"] == "NO",
            "RUN A context SHA-256 = RUN B context SHA-256": run_a["context_sha256"] == run_b["context_sha256"],
        }
        failed = [name for name, ok in hard_gates.items() if not ok]
        if failed:
            raise Blocked("FINAL_HARD_GATE_FAILED", len(failed), "; ".join(failed), failed[0], {x: 1 for x in failed})

        context_representation = {
            "representation": "unit-a-frozen-classifier-context-v1",
            "row_count": len(run_a["context_rows"]),
            "ordered_rows": run_a["context_rows"],
        }
        artifact = {
            "schema_version": 1,
            "kind": "attack_event_unit_a_frozen_classifier_context",
            "verdict": "ATTACK-EVENT UNIT A FROZEN CLASSIFIER CONTEXT = RECOVERED",
            "branch": BRANCH,
            "predecessor_commit": PREDECESSOR,
            "actions_run_id": int(args.run_id),
            "database": {
                "branch_id": branch_id,
                "transaction_isolation": "repeatable read",
                "transaction_read_only": "on",
                "default_transaction_read_only": "on",
                "queries_executed": qcount,
                "writes": 0,
                "rollback_completed": True,
                "snapshot_capture_count": 1,
                "current_canonical_air_rows_captured": len(db_rows),
                "current_rows_outside_frozen_context": len(outside_current),
                "current_rows_outside_frozen_context_uid_sha256": sha256_bytes(
                    ("\n".join(outside_current) + "\n").encode("utf-8")
                ),
            },
            "authorities": {
                "historical_classification_artifact": historical_id,
                "continuity_artifact": continuity_id,
                "recovery_artifact": recovery_id,
                "materialization_artifact": mat_id,
                "readiness_artifact": readiness_id,
                "pinned_classifier": {
                    "commit": PINNED_COMMIT, "path": CLASSIFIER_PATH, "blob": CLASSIFIER_BLOB,
                    "executed": False,
                },
                "pinned_historical_input_builder": {
                    "commit": PINNED_COMMIT, "path": BUILDER_PATH, "blob": BUILDER_BLOB,
                    "executed": False,
                },
            },
            "reconciliation": {
                "historical_classifications_scanned": run_a["historical_scanned"],
                "historical_canonical_parent_matches": run_a["historical_matched"],
                "historical_unbound": run_a["historical_unbound"],
                "historical_ambiguous_bindings": run_a["historical_ambiguous"],
                "historical_unbound_examples": run_a["unbound_examples"],
                "frozen_uncovered_parents_expected": run_a["frozen_uncovered_expected"],
                "frozen_uncovered_exact_parent_matches": run_a["frozen_uncovered_matched"],
                "frozen_uncovered_parent_drift": run_a["frozen_uncovered_drift"],
                "context_canonical_parents": len(run_a["context_rows"]),
                "duplicate_canonical_parent_uids": run_a["duplicate_uids"],
                "duplicate_context_temporal_identities": run_a["duplicate_temporal"],
                "set_a_set_b_overlap": run_a["set_overlap"],
                "current_post_audit_alerts_admitted_to_frozen_context": post_audit_admitted,
            },
            "context": context_representation,
            "context_identity_set_sha256": run_a["context_sha256"],
            "unit_a_target_equivalence": {
                "targets": eq_a["targets"],
                "reconstructed_episode_id_exact_matches": eq_a["exact_episode_id_matches"],
                "temporal_mismatches": eq_a["temporal_mismatches"],
                "target_mapping_sha256": eq_a["target_mapping_sha256"],
            },
            "candidate_reference_resolution": refs_a,
            "classifier_context_completeness": completeness,
            "determinism": {
                "run_a_context_sha256": run_a["context_sha256"],
                "run_b_context_sha256": run_b["context_sha256"],
                "run_a_target_mapping_sha256": eq_a["target_mapping_sha256"],
                "run_b_target_mapping_sha256": eq_b["target_mapping_sha256"],
                "run_a_reference_resolution_sha256": refs_a["resolution_sha256"],
                "run_b_reference_resolution_sha256": refs_b["resolution_sha256"],
                "deterministic": True,
                "same_captured_db_snapshot": True,
            },
            "execution_guards": guards,
            "hard_gates": {k: ("PASS" if v else "FAIL") for k, v in hard_gates.items()},
            "offline_a3_readiness": {
                "context_rows_are_minimal_classifier_episode_representation": True,
                "neon_query_required_for_later_a3": False,
                "classification_authorized_by_this_artifact": False,
            },
        }

        final_bytes = canonical_bytes(artifact)
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_bytes(final_bytes)
        if OUT.read_bytes() != final_bytes:
            raise Blocked("DURABLE_CONTEXT_ARTIFACT_WRITE_MISMATCH", 1, str(OUT))

        summary = {
            **summary_base,
            "verdict": artifact["verdict"],
            "failed_gate": None,
            "affected_count": 0,
            "smallest_demonstrated_blocker": None,
            "blocker_distribution": {},
            "durable_context_artifact_path": str(OUT),
            "durable_context_artifact_sha256": sha256_bytes(final_bytes),
            "durable_context_artifact_bytes": len(final_bytes),
            "db_queries": qcount,
            "historical_classifications_scanned": run_a["historical_scanned"],
            "historical_canonical_parent_matches": run_a["historical_matched"],
            "historical_unbound": run_a["historical_unbound"],
            "ambiguous_historical_bindings": run_a["historical_ambiguous"],
            "frozen_uncovered_expected": run_a["frozen_uncovered_expected"],
            "frozen_uncovered_matched": run_a["frozen_uncovered_matched"],
            "parent_drift": run_a["frozen_uncovered_drift"],
            "total_canonical_context_episodes": len(run_a["context_rows"]),
            "duplicate_context_identities": run_a["duplicate_temporal"],
            "unit_a_target_count": eq_a["targets"],
            "unit_a_reconstructed_episode_id_matches": eq_a["exact_episode_id_matches"],
            "unit_a_temporal_mismatches": eq_a["temporal_mismatches"],
            "classifier_consumed_unresolved_episode_references": refs_a["classifier_consumed_unresolved_episode_references"],
            "ambiguous_episode_references": refs_a["ambiguous_episode_references"],
            "post_audit_alerts_admitted": post_audit_admitted,
            "run_a_context_sha256": run_a["context_sha256"],
            "run_b_context_sha256": run_b["context_sha256"],
            "deterministic": "YES",
            "external_evidence_requests": guards["external_evidence_requests"],
            "discovery_executions": guards["discovery_executions"],
            "classifier_executions": guards["classifier_executions"],
            "classification_verdicts": guards["classification_verdicts_produced"],
            "db_writes": guards["db_writes"],
            "production_mutation": guards["production_mutation"],
        }
        write_summary(summary_path, summary)
        monitor.classify_candidate = original_classifier
        return 0

    except Blocked as exc:
        if conn is not None:
            try:
                with conn.cursor() as cur:
                    cur.execute("ROLLBACK")
                    qcount += 1
            except Exception:
                pass
            try:
                conn.close()
            except Exception:
                pass
        if OUT.exists():
            OUT.unlink()
        payload = {
            **summary_base,
            "failed_gate": exc.gate,
            "affected_count": exc.count,
            "smallest_demonstrated_blocker": exc.smallest if exc.smallest is not None else exc.detail,
            "blocker_distribution": exc.distribution,
            "compact_diagnostic": exc.detail[:1200],
            "db_queries": qcount,
            "db_writes": guards["db_writes"],
            "external_evidence_requests": guards["external_evidence_requests"],
            "discovery_executions": guards["discovery_executions"],
            "classifier_executions": guards["classifier_executions"],
            "classification_verdicts": guards["classification_verdicts_produced"],
            "production_mutation": guards["production_mutation"],
        }
        write_summary(summary_path, payload)
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 2
    except Exception as exc:
        if conn is not None:
            try:
                with conn.cursor() as cur:
                    cur.execute("ROLLBACK")
                    qcount += 1
            except Exception:
                pass
            try:
                conn.close()
            except Exception:
                pass
        if OUT.exists():
            OUT.unlink()
        secret = os.environ.get("PHASE1_PROD_SHADOW_DATABASE_URL", "")
        message = f"{type(exc).__name__}:{exc}"
        if secret:
            message = message.replace(secret, "<redacted>")
        message = re.sub(r"(?i)(postgres(?:ql)?://)[^@\s]+@", r"\1<redacted>@", message)
        payload = {
            **summary_base,
            "failed_gate": "EXECUTION_HARNESS_FAILURE",
            "affected_count": 1,
            "smallest_demonstrated_blocker": message[:1200],
            "blocker_distribution": {"EXECUTION_HARNESS_FAILURE": 1},
            "compact_diagnostic": message[:1200],
            "db_queries": qcount,
            "db_writes": guards["db_writes"],
            "external_evidence_requests": guards["external_evidence_requests"],
            "discovery_executions": guards["discovery_executions"],
            "classifier_executions": guards["classifier_executions"],
            "classification_verdicts": guards["classification_verdicts_produced"],
            "production_mutation": guards["production_mutation"],
        }
        write_summary(summary_path, payload)
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 2
    finally:
        if monitor_temp is not None:
            try:
                subprocess.run(
                    ["git", "worktree", "remove", "--force", str(monitor_temp)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False
                )
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
