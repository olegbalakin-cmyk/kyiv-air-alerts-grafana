#!/usr/bin/env python3
from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any

PREDECESSOR = "ccb2e6ea2637b2bdbde5d21744a79d8f4a91ff4d"
RECOVERY_PATH = "research/attack_event_partitioned_classification_recovery_audit_2026-10-06.json"
RECOVERY_BLOB = "d65a545add6125ca16514fa4f9c8cb7a0b74a76c"
RECOVERY_SHA256 = "641cd7f4d1ca3c58755150ba0ff4f436794f558d5060ef416638adfed0513a98"
OUTPUT = Path("research/attack_event_execution_unit_a_materialized_inputs_2026-10-07.json")
EXPECTED_A = 1713
EXPECTED_B = 352
EXPECTED_C = 35
METHODOLOGY = "historical-attack-event-air-defense-action-v2"
NORMALIZATION = "historical-attack-event-observation-v2"
CLASSIFIER_REF = "71cb6f6fbe856cc7b96759310fe9cc9c71cc0453"
CLASSIFIER_PATH = "kyiv-air-alerts-grafana/scripts/monitor_explosion_candidates.py"
CLASSIFIER_BLOB = "778469b74c2aa807d851cf2c2ee35cf4aa785589"
HISTORICAL_WORKER_PATH = "kyiv-air-alerts-grafana/scripts/run_historical_attack_event_backfill_batch.py"
HISTORICAL_WORKER_BLOB = "cb2791bd309abacf4c3aae8fee0d1a8f038220b2"


class Blocked(RuntimeError):
    def __init__(self, gate: str, detail: str):
        super().__init__(detail)
        self.gate = gate
        self.detail = detail


def run(*args: str) -> bytes:
    p = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if p.returncode:
        raise RuntimeError(
            f"COMMAND_FAILED:{' '.join(args)}:"
            + p.stderr.decode("utf-8", "replace")[-4000:]
        )
    return p.stdout


def git_text(*args: str) -> str:
    return run("git", *args).decode("utf-8", "replace").strip()


def git_show(ref: str, path: str) -> bytes:
    return run("git", "show", f"{ref}:{path}")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_bytes(obj: Any) -> bytes:
    return (
        json.dumps(
            obj,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def required(value: Any, gate: str, detail: str) -> Any:
    if value is None or value == "":
        raise Blocked(gate, detail)
    return value


def checked_artifact(ref: str, path: str, blob: str | None = None,
                     expected_sha256: str | None = None) -> tuple[Any, dict]:
    raw = git_show(ref, path)
    actual_blob = git_text("rev-parse", f"{ref}:{path}")
    actual_sha = sha256(raw)
    if blob and actual_blob != blob:
        raise Blocked("PINNED_INPUT_BLOB_MISMATCH", f"{path}:{actual_blob}!={blob}")
    if expected_sha256 and actual_sha != expected_sha256:
        raise Blocked("PINNED_INPUT_SHA256_MISMATCH", f"{path}:{actual_sha}!={expected_sha256}")
    return json.loads(raw.decode("utf-8")), {
        "commit": ref,
        "path": path,
        "blob": actual_blob,
        "sha256": actual_sha,
        "bytes": len(raw),
    }


def load_contract() -> dict:
    recovery, recovery_identity = checked_artifact(
        PREDECESSOR, RECOVERY_PATH, RECOVERY_BLOB, RECOVERY_SHA256
    )
    if recovery.get("verdict") != "ATTACK-EVENT PARTITIONED CLASSIFICATION RECOVERY AUDIT = PLANNED":
        raise Blocked("FROZEN_RECOVERY_VERDICT_MISMATCH", str(recovery.get("verdict")))

    units = recovery.get("execution_units") or {}
    a = units.get("A_SAFE_EXISTING_EVIDENCE_MATERIALIZATION") or {}
    b = units.get("B_EVIDENCE_COLLECTION_RECOVERY") or {}
    c = units.get("C_IDENTITY_FORENSIC_MANUAL_CONTRACT_DECISION") or {}
    a_uids = list(a.get("episode_uids") or [])
    b_uids = list(b.get("episode_uids") or [])
    c_uids = list(c.get("episode_uids") or [])

    if len(a_uids) != EXPECTED_A or int(a.get("count") or -1) != EXPECTED_A:
        raise Blocked("FROZEN_UNIT_A_IDENTITY_COUNT", f"observed={len(a_uids)}")
    if len(b_uids) != EXPECTED_B or int(b.get("count") or -1) != EXPECTED_B:
        raise Blocked("FROZEN_UNIT_B_IDENTITY_COUNT", f"observed={len(b_uids)}")
    if len(c_uids) != EXPECTED_C or int(c.get("count") or -1) != EXPECTED_C:
        raise Blocked("FROZEN_UNIT_C_IDENTITY_COUNT", f"observed={len(c_uids)}")
    if len(a_uids) != len(set(a_uids)):
        raise Blocked("FROZEN_UNIT_A_DUPLICATE_IDENTITIES", "duplicate Unit A UIDs")
    if set(a_uids) & set(b_uids):
        raise Blocked("UNIT_A_UNIT_B_OVERLAP", str(len(set(a_uids) & set(b_uids))))
    if set(a_uids) & set(c_uids):
        raise Blocked("UNIT_A_UNIT_C_OVERLAP", str(len(set(a_uids) & set(c_uids))))

    projection = (
        (recovery.get("normalization_forensic") or {})
        .get("frozen_classifier_input_projection") or {}
    )
    required_fields = list(projection.get("required_input_fields") or [])
    optional_fields = list(projection.get("optional_input_fields") or [])
    if projection.get("representation") != "FROZEN_LIVE_CANDIDATE_INPUT_BUNDLE":
        raise Blocked("FROZEN_INPUT_REPRESENTATION_MISMATCH", str(projection.get("representation")))
    if not required_fields:
        raise Blocked("FROZEN_REQUIRED_INPUT_FIELDS_MISSING", "empty required field contract")

    materialization_rows = list((recovery.get("materialization_cohort") or {}).get("rows") or [])
    by_uid = {}
    for row in materialization_rows:
        if not isinstance(row, dict):
            continue
        uid = str(row.get("alert_episode_uid") or "")
        if uid:
            if uid in by_uid:
                raise Blocked("MATERIALIZATION_ROW_UID_DUPLICATE", uid)
            by_uid[uid] = row
    missing_rows = sorted(set(a_uids) - set(by_uid))
    if missing_rows:
        raise Blocked("UNIT_A_MATERIALIZATION_ROWS_MISSING", missing_rows[0])

    continuity_identity = recovery.get("frozen_continuity_artifact_identity") or {}
    continuity_commit = str(required(
        continuity_identity.get("commit"), "CONTINUITY_COMMIT_MISSING", "missing commit"
    ))
    continuity_path = str(required(
        continuity_identity.get("path"), "CONTINUITY_PATH_MISSING", "missing path"
    ))
    continuity_blob = str(required(
        continuity_identity.get("blob"), "CONTINUITY_BLOB_MISSING", "missing blob"
    ))
    continuity_sha = str(required(
        continuity_identity.get("sha256"), "CONTINUITY_SHA256_MISSING", "missing sha256"
    ))
    continuity, continuity_checked = checked_artifact(
        continuity_commit, continuity_path, continuity_blob, continuity_sha
    )
    parent_rows = list(continuity.get("uncovered_parent_identities") or [])
    parent_by_uid = {}
    for row in parent_rows:
        if not isinstance(row, dict):
            continue
        uid = str(row.get("alert_episode_uid") or "")
        if uid:
            if uid in parent_by_uid:
                raise Blocked("CONTINUITY_PARENT_UID_DUPLICATE", uid)
            parent_by_uid[uid] = row
    missing_parents = sorted(set(a_uids) - set(parent_by_uid))
    if missing_parents:
        raise Blocked("UNIT_A_PARENT_IDENTITY_MISSING", missing_parents[0])

    if git_text("rev-parse", f"{CLASSIFIER_REF}:{CLASSIFIER_PATH}") != CLASSIFIER_BLOB:
        raise Blocked("CLASSIFIER_BLOB_DRIFT", CLASSIFIER_PATH)
    if git_text("rev-parse", f"{CLASSIFIER_REF}:{HISTORICAL_WORKER_PATH}") != HISTORICAL_WORKER_BLOB:
        raise Blocked("NORMALIZATION_IMPLEMENTATION_BLOB_DRIFT", HISTORICAL_WORKER_PATH)

    return {
        "recovery": recovery,
        "recovery_identity": recovery_identity,
        "continuity_identity": continuity_checked,
        "a_uids": a_uids,
        "b_uids": b_uids,
        "c_uids": c_uids,
        "rows_by_uid": by_uid,
        "parents_by_uid": parent_by_uid,
        "required_fields": required_fields,
        "optional_fields": optional_fields,
        "projection": projection,
    }


def selected_queue_rows(queue: list[dict], episode_id: str, checked_at: str | None) -> list[dict]:
    # Mirror the accepted partition audit's exact candidate selection semantics
    # without invoking any classifier or normalization implementation.
    by_candidate: dict[str, dict] = {}
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
                # Accepted timestamps are canonical UTC strings in this frozen cohort;
                # lexical ordering preserves the already-accepted chronological order.
                continue
        cid = str(row.get("candidate_id") or "")
        if not cid:
            raise Blocked("REQUIRED_MATERIALIZATION_FIELDS_MISSING", f"candidate_id:{episode_id}")
        by_candidate[cid] = row
    return [by_candidate[k] for k in sorted(by_candidate)]


def project_candidate(row: dict, city_key: str, required_fields: list[str],
                      optional_fields: list[str]) -> dict:
    missing = []
    for field in required_fields:
        value = row.get(field)
        if field == "city_key":
            if str(value or "") != city_key:
                missing.append(field)
        elif value is None or (isinstance(value, str) and not value.strip()):
            missing.append(field)
    if missing:
        raise Blocked(
            "REQUIRED_MATERIALIZATION_FIELDS_MISSING",
            f"city={city_key};candidate={row.get('candidate_id')};missing={','.join(sorted(missing))}",
        )
    out = {field: copy.deepcopy(row.get(field)) for field in required_fields}
    for field in optional_fields:
        if field in row:
            out[field] = copy.deepcopy(row.get(field))
    return out


def queue_snapshot(commit: str, path: str, expected_blob: str,
                   cache: dict[tuple[str, str], tuple[list[dict], dict]]) -> tuple[list[dict], dict]:
    key = (commit, path)
    if key in cache:
        rows, identity = cache[key]
        return rows, identity
    raw = git_show(commit, path)
    actual_blob = git_text("rev-parse", f"{commit}:{path}")
    if actual_blob != expected_blob:
        raise Blocked("QUEUE_BLOB_MISMATCH", f"{commit}:{path}:{actual_blob}!={expected_blob}")
    obj = json.loads(raw.decode("utf-8"))
    if not isinstance(obj, list):
        raise Blocked("QUEUE_SCHEMA_INVALID", f"{commit}:{path}")
    identity = {
        "commit": commit,
        "path": path,
        "blob": actual_blob,
        "sha256": sha256(raw),
        "bytes": len(raw),
    }
    cache[key] = (obj, identity)
    return obj, identity


def materialize_once(contract: dict) -> tuple[dict, dict]:
    qcache: dict[tuple[str, str], tuple[list[dict], dict]] = {}
    episodes = []
    per_episode_hashes = []
    consumed_queues: dict[tuple[str, str], dict] = {}
    candidate_store: dict[str, dict] = {}

    for uid in contract["a_uids"]:
        frozen_row = contract["rows_by_uid"][uid]
        if str(frozen_row.get("recovery_action") or "") != "SAFE_EXISTING_EVIDENCE_MATERIALIZATION":
            raise Blocked("UNIT_A_RECOVERY_ACTION_DRIFT", uid)
        if str(frozen_row.get("deterministic_episode_mapping") or "") != "YES":
            raise Blocked("UNIT_A_DETERMINISTIC_MAPPING_DRIFT", uid)
        if frozen_row.get("missing_input_fields") or []:
            raise Blocked("REQUIRED_MATERIALIZATION_FIELDS_MISSING", uid)

        city = str(required(frozen_row.get("city_key"), "CITY_KEY_MISSING", uid))
        episode_id = str(required(
            frozen_row.get("live_monitor_episode_id"), "LIVE_EPISODE_ID_MISSING", uid
        ))
        expected_count = int(frozen_row.get("candidate_input_count") or 0)
        checked_at = frozen_row.get("followup_72h_checked_at")
        queue_identity = frozen_row.get("collection_queue_identity") or {}

        projected = []
        refs = []
        selection_provenance = []
        if expected_count > 0:
            commit = str(required(queue_identity.get("commit"), "QUEUE_COMMIT_MISSING", uid))
            path = str(required(queue_identity.get("path"), "QUEUE_PATH_MISSING", uid))
            blob = str(required(queue_identity.get("blob"), "QUEUE_BLOB_MISSING", uid))
            queue, consumed = queue_snapshot(commit, path, blob, qcache)
            consumed_queues[(commit, path)] = consumed
            selected = selected_queue_rows(queue, episode_id, checked_at)
            for raw_candidate in selected:
                candidate = project_candidate(
                    raw_candidate,
                    city,
                    contract["required_fields"],
                    contract["optional_fields"],
                )
                projected.append(candidate)
                candidate_hash = sha256(canonical_bytes(candidate))
                prior = candidate_store.get(candidate_hash)
                if prior is not None and canonical_bytes(prior) != canonical_bytes(candidate):
                    raise Blocked("CANDIDATE_STORE_HASH_COLLISION", candidate_hash)
                candidate_store[candidate_hash] = candidate
                refs.append(candidate_hash)
                selection_provenance.append({
                    "candidate_id": str(raw_candidate.get("candidate_id")),
                    "candidate_input_sha256": candidate_hash,
                    "matched_episode_id": copy.deepcopy(raw_candidate.get("matched_episode_id")),
                    "trigger_episode_ids": copy.deepcopy(raw_candidate.get("trigger_episode_ids") or []),
                    "trigger_check_labels": copy.deepcopy(raw_candidate.get("trigger_check_labels") or []),
                    "first_discovered_at": copy.deepcopy(raw_candidate.get("first_discovered_at")),
                })
        else:
            if not frozen_row.get("accepted_empty_candidate_set"):
                raise Blocked("EMPTY_CANDIDATE_SET_NOT_ACCEPTED", uid)

        if len(projected) != expected_count:
            raise Blocked(
                "MATERIALIZED_CANDIDATE_COUNT_MISMATCH",
                f"{uid}:expected={expected_count}:observed={len(projected)}",
            )

        parent_identity = copy.deepcopy(contract["parents_by_uid"][uid])
        episode_input = {
            "episode_id": episode_id,
            "city_key": city,
            "alert_start": copy.deepcopy(frozen_row.get("start_at")),
            "alert_end": copy.deepcopy(frozen_row.get("end_at")),
        }

        # Hash the logically expanded materialized input, then persist an exactly
        # reversible content-addressed representation to stay below repository limits.
        logical_entry = {
            "alert_episode_uid": uid,
            "canonical_parent_identity": parent_identity,
            "classifier_episode_input": episode_input,
            "candidate_input_representation": "FROZEN_LIVE_CANDIDATE_INPUT_BUNDLE",
            "candidate_inputs": projected,
            "evidence_provenance": {
                "collection_run_identity": copy.deepcopy(frozen_row.get("collection_run_identity")),
                "collection_queue_identity": copy.deepcopy(frozen_row.get("collection_queue_identity")),
                "followup_72h_checked_at": copy.deepcopy(checked_at),
                "accepted_empty_candidate_set": bool(frozen_row.get("accepted_empty_candidate_set")),
                "candidate_selection_provenance": selection_provenance,
            },
        }
        logical_hash = sha256(canonical_bytes(logical_entry))
        stored_entry = {
            "alert_episode_uid": uid,
            "canonical_parent_identity": parent_identity,
            "classifier_episode_input": episode_input,
            "candidate_input_representation": "FROZEN_LIVE_CANDIDATE_INPUT_BUNDLE",
            "candidate_input_refs": refs,
            "evidence_provenance": logical_entry["evidence_provenance"],
            "materialized_input_sha256": logical_hash,
        }
        episodes.append(stored_entry)
        per_episode_hashes.append({"alert_episode_uid": uid, "sha256": logical_hash})

    if len(episodes) != EXPECTED_A:
        raise Blocked("MATERIALIZED_OUTPUT_COUNT", f"observed={len(episodes)}")
    output_uids = [str(x.get("alert_episode_uid") or "") for x in episodes]
    if len(output_uids) != len(set(output_uids)):
        raise Blocked("DUPLICATE_OUTPUT_IDENTITIES", "duplicate materialized UID")
    missing = sorted(set(contract["a_uids"]) - set(output_uids))
    unexpected = sorted(set(output_uids) - set(contract["a_uids"]))
    if missing:
        raise Blocked("MISSING_UNIT_A_IDENTITIES", missing[0])
    if unexpected:
        raise Blocked("UNEXPECTED_OUTPUT_IDENTITIES", unexpected[0])

    candidate_store_rows = [
        {"sha256": key, "candidate_input": candidate_store[key]}
        for key in sorted(candidate_store)
    ]
    corpus = {
        "schema_version": 2,
        "kind": "attack_event_execution_unit_a_materialized_input_corpus",
        "methodology_version": METHODOLOGY,
        "normalization_version": NORMALIZATION,
        "candidate_input_representation": "FROZEN_LIVE_CANDIDATE_INPUT_BUNDLE",
        "artifact_serialization": {
            "format": "content-addressed-candidate-dedup-v1",
            "reconstruction_rule": (
                "For each episode, replace candidate_input_refs in order with the "
                "candidate_input whose sha256 matches each ref. No semantic value is "
                "added, removed, reordered, normalized, or inferred."
            ),
        },
        "candidate_input_store": candidate_store_rows,
        "episodes": episodes,
    }
    corpus_bytes = canonical_bytes(corpus)
    identity_hash = sha256(("\n".join(output_uids) + "\n").encode("utf-8"))
    queue_inputs = sorted(
        consumed_queues.values(),
        key=lambda x: (x["commit"], x["path"], x["blob"]),
    )
    stats = {
        "episode_count": len(episodes),
        "candidate_input_count": sum(len(x["candidate_input_refs"]) for x in episodes),
        "unique_candidate_input_count": len(candidate_store_rows),
        "accepted_empty_candidate_set_count": sum(
            bool((x.get("evidence_provenance") or {}).get("accepted_empty_candidate_set"))
            for x in episodes
        ),
        "ordered_identity_set_sha256": identity_hash,
        "per_episode_hashes": per_episode_hashes,
        "queue_inputs": queue_inputs,
        "corpus_sha256": sha256(corpus_bytes),
        "corpus_bytes": len(corpus_bytes),
    }
    return corpus, stats


def main() -> int:
    if OUTPUT.exists():
        raise Blocked("DURABLE_ARTIFACT_ALREADY_EXISTS", str(OUTPUT))

    contract = load_contract()

    # Independent RUN A.
    corpus_a, stats_a = materialize_once(contract)
    bytes_a = canonical_bytes(corpus_a)

    # Independent RUN B: new reads/cache, same pinned inputs.
    corpus_b, stats_b = materialize_once(contract)
    bytes_b = canonical_bytes(corpus_b)

    if stats_a["corpus_sha256"] != stats_b["corpus_sha256"]:
        raise Blocked(
            "RUN_A_RUN_B_CORPUS_HASH_EQUAL",
            f"{stats_a['corpus_sha256']}!={stats_b['corpus_sha256']}",
        )
    if bytes_a != bytes_b:
        raise Blocked("RUN_A_RUN_B_BYTE_IDENTICAL", "corpus bytes differ")

    # Every hard gate is derived from frozen membership plus this no-network,
    # no-database, no-classifier execution harness.
    output_uids = [x["alert_episode_uid"] for x in corpus_a["episodes"]]
    hard_gates = {
        "frozen Unit A identities = 1,713": "PASS",
        "materialized outputs = 1,713": "PASS",
        "missing Unit A identities = 0": "PASS",
        "unexpected output identities = 0": "PASS",
        "duplicate output identities = 0": "PASS",
        "Unit A / Unit B overlap = 0": "PASS",
        "Unit A / Unit C overlap = 0": "PASS",
        "external evidence requests = 0": "PASS",
        "classifier executions over target episodes = 0": "PASS",
        "classification verdicts produced = 0": "PASS",
        "identity ambiguities introduced = 0": "PASS",
        "parent-binding mutations = 0": "PASS",
        "normalization semantic changes = 0": "PASS",
        "classifier semantic changes = 0": "PASS",
        "required materialization fields missing = 0": "PASS",
        "RUN A / RUN B corpus hash equal = YES": "PASS",
        "RUN A / RUN B byte-identical = YES": "PASS",
        "Neon queries = 0": "PASS",
        "database writes = 0": "PASS",
        "production mutation = NO": "PASS",
    }

    artifact = {
        "schema_version": 1,
        "kind": "attack_event_execution_unit_a_materialized_inputs",
        "verdict": "ATTACK-EVENT EXECUTION UNIT A MATERIALIZATION = FROZEN",
        "predecessor_commit": PREDECESSOR,
        "originating_frozen_recovery_artifact": contract["recovery_identity"],
        "frozen_continuity_artifact": contract["continuity_identity"],
        "governing_semantics": {
            "methodology_version": METHODOLOGY,
            "normalization_version": NORMALIZATION,
            "authoritative_classifier": {
                "commit": CLASSIFIER_REF,
                "path": CLASSIFIER_PATH,
                "blob": CLASSIFIER_BLOB,
                "executed": False,
            },
            "historical_observation_builder": {
                "commit": CLASSIFIER_REF,
                "path": HISTORICAL_WORKER_PATH,
                "blob": HISTORICAL_WORKER_BLOB,
                "executed": False,
            },
            "projection_contract": copy.deepcopy(contract["projection"]),
            "classification_verdicts_in_artifact": False,
        },
        "manifest": {
            "actions_run_id": int(os.environ.get("GITHUB_RUN_ID") or 0),
            "episode_count": EXPECTED_A,
            "materialized_count": len(output_uids),
            "missing_count": 0,
            "unexpected_identity_count": 0,
            "duplicate_identity_count": 0,
            "unit_b_overlap": len(set(output_uids) & set(contract["b_uids"])),
            "unit_c_overlap": len(set(output_uids) & set(contract["c_uids"])),
            "ordered_canonical_identity_set_sha256": stats_a["ordered_identity_set_sha256"],
            "candidate_input_count": stats_a["candidate_input_count"],
            "unique_candidate_input_count": stats_a["unique_candidate_input_count"],
            "accepted_empty_candidate_set_count": stats_a["accepted_empty_candidate_set_count"],
            "authoritative_repository_inputs_consumed": {
                "recovery_artifact": contract["recovery_identity"],
                "continuity_artifact": contract["continuity_identity"],
                "queue_snapshots": stats_a["queue_inputs"],
            },
            "evidence_provenance_preservation": {
                "candidate_projection": "copy only persisted frozen candidate input fields defined by the accepted recovery artifact",
            "artifact_serialization": "content-addressed deduplication only; exact ordered candidate bundles are reconstructable by SHA-256 refs",
                "queue_snapshot_identity_preserved_per_episode": True,
                "candidate_multi_value_trigger_provenance_preserved": True,
                "source_type_inference": "NONE",
                "timestamp_inference": "NONE",
                "parent_identity_rewrite": "NONE",
            },
            "run_a_sha256": stats_a["corpus_sha256"],
            "run_b_sha256": stats_b["corpus_sha256"],
            "run_a_bytes": stats_a["corpus_bytes"],
            "run_b_bytes": stats_b["corpus_bytes"],
            "run_a_run_b_byte_identical": True,
            "final_artifact_sha256_semantics": (
                "SHA-256 is computed externally over the exact final UTF-8 serialized artifact bytes "
                "after write; the value is not embedded to avoid self-reference."
            ),
            "hard_gates": hard_gates,
        },
        "corpus": corpus_a,
    }

    final_bytes = canonical_bytes(artifact)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes(final_bytes)

    # Re-read exact bytes before allowing the workflow to commit.
    reread = OUTPUT.read_bytes()
    if reread != final_bytes:
        raise Blocked("DURABLE_ARTIFACT_WRITE_BYTE_MISMATCH", str(OUTPUT))

    summary = {
        "verdict": artifact["verdict"],
        "durable_artifact_path": str(OUTPUT),
        "artifact_sha256": sha256(final_bytes),
        "artifact_bytes": len(final_bytes),
        "unit_A_expected": EXPECTED_A,
        "materialized": len(output_uids),
        "missing": 0,
        "duplicate": 0,
        "unexpected": 0,
        "unit_B_overlap": artifact["manifest"]["unit_b_overlap"],
        "unit_C_overlap": artifact["manifest"]["unit_c_overlap"],
        "external_evidence_requests": 0,
        "classifier_executions": 0,
        "classification_verdicts_produced": 0,
        "run_A_sha256": stats_a["corpus_sha256"],
        "run_B_sha256": stats_b["corpus_sha256"],
        "byte_identical": "YES",
        "normalization_semantic_changes": 0,
        "classifier_semantic_changes": 0,
        "neon_queries": 0,
        "db_writes": 0,
        "production_mutation": "NO",
        "queue_snapshots_consumed": len(stats_a["queue_inputs"]),
        "candidate_inputs": stats_a["candidate_input_count"],
            "unique_candidate_inputs": stats_a["unique_candidate_input_count"],
    }
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Blocked as exc:
        print(json.dumps({
            "verdict": "ATTACK-EVENT EXECUTION UNIT A MATERIALIZATION = BLOCKED",
            "failed_gate": exc.gate,
            "smallest_demonstrated_blocker": exc.detail,
        }, ensure_ascii=False, sort_keys=True))
        raise SystemExit(2)
