#!/usr/bin/env python3
from __future__ import annotations

import ast
import base64
import collections
import hashlib
import io
import json
import os
import subprocess
import sys
import zlib
from datetime import datetime
from pathlib import Path
from typing import Any

PREDECESSOR = "2d07c81147932d39cb3a9d9934830f6eb707ee37"
BRANCH = "attack-event-unit-a-classifier-readiness-validation-2026-10-08"
MATERIALIZATION_PATH = "research/attack_event_execution_unit_a_materialized_inputs_2026-10-07.json"
MATERIALIZATION_BLOB = "52e89792352513664428da3a7fcb9b43f79f1ba1"
MATERIALIZATION_SHA256 = "07148ac498a6f4251e356bbf24be0aa40ebf220dd39c5df7ec99177a6f7214cc"
OUTPUT = Path("research/attack_event_execution_unit_a_classifier_readiness_validation_2026-10-08.json")
EXPECTED_EPISODES = 1713
METHODOLOGY = "historical-attack-event-air-defense-action-v2"
NORMALIZATION = "historical-attack-event-observation-v2"
CLASSIFIER_REF = "71cb6f6fbe856cc7b96759310fe9cc9c71cc0453"
CLASSIFIER_PATH = "kyiv-air-alerts-grafana/scripts/monitor_explosion_candidates.py"
CLASSIFIER_BLOB = "778469b74c2aa807d851cf2c2ee35cf4aa785589"
BUILDER_PATH = "kyiv-air-alerts-grafana/scripts/run_historical_attack_event_backfill_batch.py"
BUILDER_BLOB = "cb2791bd309abacf4c3aae8fee0d1a8f038220b2"
REPRESENTATION = "FROZEN_LIVE_CANDIDATE_INPUT_BUNDLE"


class Blocked(RuntimeError):
    def __init__(self, gate: str, detail: str):
        super().__init__(detail)
        self.gate = gate
        self.detail = detail


def run(*args: str) -> bytes:
    p = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if p.returncode:
        raise Blocked(
            "REPOSITORY_READ_FAILED",
            f"{' '.join(args)} :: {p.stderr.decode('utf-8', 'replace')[-1200:]}",
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


def valid_nonempty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def parse_timestamp_exact(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        return None
    return dt


def checked_git_json(identity: dict, label: str) -> tuple[dict, dict]:
    commit = str(identity.get("commit") or "")
    path = str(identity.get("path") or "")
    blob = str(identity.get("blob") or "")
    expected_sha = str(identity.get("sha256") or "")
    if not all([commit, path, blob, expected_sha]):
        raise Blocked(f"{label}_IDENTITY_INCOMPLETE", json.dumps(identity, sort_keys=True))
    raw = git_show(commit, path)
    actual_blob = git_text("rev-parse", f"{commit}:{path}")
    actual_sha = sha256(raw)
    if actual_blob != blob:
        raise Blocked(f"{label}_BLOB_MISMATCH", f"{actual_blob}!={blob}")
    if actual_sha != expected_sha:
        raise Blocked(f"{label}_SHA256_MISMATCH", f"{actual_sha}!={expected_sha}")
    try:
        obj = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise Blocked(f"{label}_JSON_INVALID", f"{type(exc).__name__}:{exc}")
    return obj, {
        "commit": commit,
        "path": path,
        "blob": actual_blob,
        "sha256": actual_sha,
        "bytes": len(raw),
    }


def decode_materialized_corpus(raw: bytes) -> tuple[dict, dict, bytes]:
    if sha256(raw) != MATERIALIZATION_SHA256:
        raise Blocked(
            "MATERIALIZATION_ARTIFACT_SHA256_MISMATCH",
            f"{sha256(raw)}!={MATERIALIZATION_SHA256}",
        )
    actual_blob = git_text("rev-parse", f"HEAD:{MATERIALIZATION_PATH}")
    if actual_blob != MATERIALIZATION_BLOB:
        raise Blocked(
            "MATERIALIZATION_ARTIFACT_BLOB_MISMATCH",
            f"{actual_blob}!={MATERIALIZATION_BLOB}",
        )
    try:
        artifact = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise Blocked("MATERIALIZATION_ARTIFACT_JSON_INVALID", f"{type(exc).__name__}:{exc}")
    if canonical_bytes(artifact) != raw:
        raise Blocked("MATERIALIZATION_ARTIFACT_NONCANONICAL_OR_TRAILING_DATA", "exact bytes differ from canonical JSON")

    corpus_block = artifact.get("corpus") or {}
    if corpus_block.get("encoding") != "gzip+base64":
        raise Blocked("CORPUS_ENCODING_MISMATCH", str(corpus_block.get("encoding")))
    payload = corpus_block.get("payload_base64")
    if not isinstance(payload, str) or not payload:
        raise Blocked("CORPUS_PAYLOAD_MISSING", "payload_base64")
    try:
        compressed = base64.b64decode(payload.encode("ascii"), validate=True)
    except Exception as exc:
        raise Blocked("CORPUS_BASE64_INVALID", f"{type(exc).__name__}:{exc}")

    declared_compressed_sha = str(corpus_block.get("compressed_sha256") or "")
    if declared_compressed_sha and sha256(compressed) != declared_compressed_sha:
        raise Blocked(
            "COMPRESSED_CORPUS_SHA256_MISMATCH",
            f"{sha256(compressed)}!={declared_compressed_sha}",
        )
    declared_compressed_bytes = corpus_block.get("compressed_bytes")
    if declared_compressed_bytes is not None and int(declared_compressed_bytes) != len(compressed):
        raise Blocked(
            "COMPRESSED_CORPUS_SIZE_MISMATCH",
            f"{len(compressed)}!={declared_compressed_bytes}",
        )

    dec = zlib.decompressobj(16 + zlib.MAX_WBITS)
    try:
        plain = dec.decompress(compressed) + dec.flush()
    except Exception as exc:
        raise Blocked("CORPUS_GZIP_INVALID", f"{type(exc).__name__}:{exc}")
    if not dec.eof:
        raise Blocked("CORPUS_GZIP_TRUNCATED", "gzip stream did not reach EOF")
    if dec.unused_data or dec.unconsumed_tail:
        raise Blocked(
            "CORPUS_TRAILING_OR_SUBSTITUTED_DATA",
            f"unused={len(dec.unused_data)} unconsumed={len(dec.unconsumed_tail)}",
        )

    declared_uncompressed_sha = str(corpus_block.get("uncompressed_sha256") or "")
    if sha256(plain) != declared_uncompressed_sha:
        raise Blocked(
            "UNCOMPRESSED_CORPUS_SHA256_MISMATCH",
            f"{sha256(plain)}!={declared_uncompressed_sha}",
        )
    declared_uncompressed_bytes = corpus_block.get("uncompressed_bytes")
    if declared_uncompressed_bytes is not None and int(declared_uncompressed_bytes) != len(plain):
        raise Blocked(
            "UNCOMPRESSED_CORPUS_SIZE_MISMATCH",
            f"{len(plain)}!={declared_uncompressed_bytes}",
        )
    try:
        corpus = json.loads(plain.decode("utf-8"))
    except Exception as exc:
        raise Blocked("UNCOMPRESSED_CORPUS_JSON_INVALID", f"{type(exc).__name__}:{exc}")
    if canonical_bytes(corpus) != plain:
        raise Blocked("UNCOMPRESSED_CORPUS_NONCANONICAL_OR_TRAILING_DATA", "exact decoded bytes differ from canonical JSON")

    return artifact, corpus, compressed


def function_def(tree: ast.AST, name: str) -> ast.FunctionDef | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def static_implementation_contract() -> dict:
    actual_classifier_blob = git_text("rev-parse", f"{CLASSIFIER_REF}:{CLASSIFIER_PATH}")
    actual_builder_blob = git_text("rev-parse", f"{CLASSIFIER_REF}:{BUILDER_PATH}")
    if actual_classifier_blob != CLASSIFIER_BLOB:
        raise Blocked("CLASSIFIER_IMPLEMENTATION_DRIFT", f"{actual_classifier_blob}!={CLASSIFIER_BLOB}")
    if actual_builder_blob != BUILDER_BLOB:
        raise Blocked("NORMALIZATION_INPUT_BUILDER_IMPLEMENTATION_DRIFT", f"{actual_builder_blob}!={BUILDER_BLOB}")

    classifier_source = git_show(CLASSIFIER_REF, CLASSIFIER_PATH).decode("utf-8")
    builder_source = git_show(CLASSIFIER_REF, BUILDER_PATH).decode("utf-8")
    try:
        classifier_tree = ast.parse(classifier_source, filename=CLASSIFIER_PATH)
        builder_tree = ast.parse(builder_source, filename=BUILDER_PATH)
    except SyntaxError as exc:
        raise Blocked("PINNED_IMPLEMENTATION_AST_INVALID", str(exc))

    classify = function_def(classifier_tree, "classify_candidate")
    classify_row = function_def(builder_tree, "classify_row")
    if classify is None:
        raise Blocked("CLASSIFIER_ENTRYPOINT_NOT_FOUND", "classify_candidate")
    if classify_row is None:
        raise Blocked("INPUT_BUILDER_ENTRYPOINT_NOT_FOUND", "classify_row")

    classifier_args = [arg.arg for arg in classify.args.args]
    builder_args = [arg.arg for arg in classify_row.args.args] + [arg.arg for arg in classify_row.args.kwonlyargs]
    if classifier_args[:3] != ["row", "city_key", "episodes"]:
        raise Blocked("CLASSIFIER_ENTRYPOINT_SIGNATURE_DRIFT", repr(classifier_args))
    for required in ["row", "city_key", "episodes", "source_type", "source_timestamp", "excerpt", "source_url"]:
        if required not in builder_args:
            raise Blocked("INPUT_BUILDER_SIGNATURE_DRIFT", f"missing:{required}")

    passes_row_directly = False
    for node in ast.walk(classify_row):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        is_target = (
            isinstance(func, ast.Attribute)
            and isinstance(func.value, ast.Name)
            and func.value.id == "monitor"
            and func.attr == "classify_candidate"
        )
        if is_target and len(node.args) >= 3:
            names = [x.id if isinstance(x, ast.Name) else None for x in node.args[:3]]
            if names == ["row", "city_key", "episodes"]:
                passes_row_directly = True
                break
    if not passes_row_directly:
        raise Blocked("INPUT_BUILDER_TO_CLASSIFIER_WIRING_DRIFT", "classify_row no longer passes row/city_key/episodes directly")

    return {
        "classifier_commit": CLASSIFIER_REF,
        "classifier_path": CLASSIFIER_PATH,
        "classifier_blob": actual_classifier_blob,
        "classifier_entrypoint": "classify_candidate",
        "classifier_signature": classifier_args,
        "input_builder_commit": CLASSIFIER_REF,
        "input_builder_path": BUILDER_PATH,
        "input_builder_blob": actual_builder_blob,
        "input_builder_entrypoint": "classify_row",
        "input_builder_signature": builder_args,
        "builder_passes_candidate_row_directly_to_classifier": True,
        "inspection_mode": "AST_ONLY_NO_IMPORT_NO_CLASSIFIER_EXECUTION",
    }


def add_reason(reasons: list[tuple[str, str]], code: str, detail: str) -> None:
    reasons.append((code, detail))


def validate_once(label: str) -> dict:
    raw = Path(MATERIALIZATION_PATH).read_bytes()
    artifact, corpus, compressed = decode_materialized_corpus(raw)
    impl = static_implementation_contract()

    if artifact.get("verdict") != "ATTACK-EVENT EXECUTION UNIT A MATERIALIZATION = FROZEN":
        raise Blocked("MATERIALIZATION_VERDICT_MISMATCH", str(artifact.get("verdict")))
    sem = artifact.get("governing_semantics") or {}
    if sem.get("methodology_version") != METHODOLOGY:
        raise Blocked("METHODOLOGY_VERSION_DRIFT", str(sem.get("methodology_version")))
    if sem.get("normalization_version") != NORMALIZATION:
        raise Blocked("NORMALIZATION_VERSION_DRIFT", str(sem.get("normalization_version")))
    auth = sem.get("authoritative_classifier") or {}
    hist = sem.get("historical_observation_builder") or {}
    if (
        auth.get("commit") != CLASSIFIER_REF
        or auth.get("path") != CLASSIFIER_PATH
        or auth.get("blob") != CLASSIFIER_BLOB
    ):
        raise Blocked("MATERIALIZATION_CLASSIFIER_PIN_MISMATCH", json.dumps(auth, sort_keys=True))
    if (
        hist.get("commit") != CLASSIFIER_REF
        or hist.get("path") != BUILDER_PATH
        or hist.get("blob") != BUILDER_BLOB
    ):
        raise Blocked("MATERIALIZATION_INPUT_BUILDER_PIN_MISMATCH", json.dumps(hist, sort_keys=True))

    recovery, recovery_identity = checked_git_json(
        artifact.get("originating_frozen_recovery_artifact") or {},
        "RECOVERY_ARTIFACT",
    )
    continuity, continuity_identity = checked_git_json(
        artifact.get("frozen_continuity_artifact") or {},
        "CONTINUITY_ARTIFACT",
    )

    units = recovery.get("execution_units") or {}
    unit_a = units.get("A_SAFE_EXISTING_EVIDENCE_MATERIALIZATION") or {}
    expected_uids = [str(x) for x in (unit_a.get("episode_uids") or [])]
    if int(unit_a.get("count") or -1) != EXPECTED_EPISODES or len(expected_uids) != EXPECTED_EPISODES:
        raise Blocked("FROZEN_UNIT_A_COUNT_MISMATCH", f"count={unit_a.get('count')} ids={len(expected_uids)}")
    if len(expected_uids) != len(set(expected_uids)):
        raise Blocked("FROZEN_UNIT_A_DUPLICATE_IDENTITIES", "recovery artifact")

    projection = ((recovery.get("normalization_forensic") or {}).get("frozen_classifier_input_projection") or {})
    artifact_projection = sem.get("projection_contract") or {}
    if projection != artifact_projection:
        raise Blocked("PROJECTION_CONTRACT_MISMATCH", "recovery artifact != materialization artifact")
    if projection.get("representation") != REPRESENTATION:
        raise Blocked("PROJECTION_REPRESENTATION_MISMATCH", str(projection.get("representation")))
    required_fields = [str(x) for x in (projection.get("required_input_fields") or [])]
    optional_fields = [str(x) for x in (projection.get("optional_input_fields") or [])]
    if not required_fields:
        raise Blocked("REQUIRED_CANDIDATE_FIELD_CONTRACT_EMPTY", "required_input_fields")
    allowed_fields = set(required_fields) | set(optional_fields)

    recovery_rows = {}
    for row in ((recovery.get("materialization_cohort") or {}).get("rows") or []):
        if isinstance(row, dict) and row.get("alert_episode_uid"):
            uid = str(row["alert_episode_uid"])
            if uid in recovery_rows:
                raise Blocked("RECOVERY_MATERIALIZATION_ROW_DUPLICATE", uid)
            recovery_rows[uid] = row
    missing_recovery_rows = [uid for uid in expected_uids if uid not in recovery_rows]
    if missing_recovery_rows:
        raise Blocked("RECOVERY_MATERIALIZATION_ROW_MISSING", missing_recovery_rows[0])

    parent_rows = {}
    for row in (continuity.get("uncovered_parent_identities") or []):
        if isinstance(row, dict) and row.get("alert_episode_uid"):
            uid = str(row["alert_episode_uid"])
            if uid in parent_rows:
                raise Blocked("CONTINUITY_PARENT_ROW_DUPLICATE", uid)
            parent_rows[uid] = row
    missing_parent_rows = [uid for uid in expected_uids if uid not in parent_rows]
    if missing_parent_rows:
        raise Blocked("CONTINUITY_PARENT_ROW_MISSING", missing_parent_rows[0])

    store_rows = corpus.get("candidate_input_store")
    episodes = corpus.get("episodes")
    if not isinstance(store_rows, list):
        raise Blocked("CANDIDATE_STORE_SCHEMA_INVALID", type(store_rows).__name__)
    if not isinstance(episodes, list):
        raise Blocked("EPISODE_CORPUS_SCHEMA_INVALID", type(episodes).__name__)
    if corpus.get("candidate_input_representation") != REPRESENTATION:
        raise Blocked("CORPUS_REPRESENTATION_MISMATCH", str(corpus.get("candidate_input_representation")))

    candidate_store_hash_mismatches = 0
    duplicate_key_semantic_disagreements = 0
    duplicate_store_keys = 0
    store: dict[str, dict] = {}
    for idx, row in enumerate(store_rows):
        if not isinstance(row, dict):
            candidate_store_hash_mismatches += 1
            continue
        key = str(row.get("sha256") or "")
        candidate = row.get("candidate_input")
        if not key or not isinstance(candidate, dict):
            candidate_store_hash_mismatches += 1
            continue
        actual = sha256(canonical_bytes(candidate))
        if actual != key:
            candidate_store_hash_mismatches += 1
        if key in store:
            duplicate_store_keys += 1
            if canonical_bytes(store[key]) != canonical_bytes(candidate):
                duplicate_key_semantic_disagreements += 1
        else:
            store[key] = candidate

    episode_uids = [str((x or {}).get("alert_episode_uid") or "") if isinstance(x, dict) else "" for x in episodes]
    duplicate_identities = len(episode_uids) - len(set(episode_uids))
    expected_set = set(expected_uids)
    actual_set = set(episode_uids)
    missing_identities = len(expected_set - actual_set)
    unexpected_identities = len(actual_set - expected_set)
    blank_identities = sum(1 for uid in episode_uids if not uid)
    ordered_identity_hash = sha256(("\n".join(episode_uids) + "\n").encode("utf-8"))
    expected_identity_hash = sha256(("\n".join(expected_uids) + "\n").encode("utf-8"))
    manifest = artifact.get("manifest") or {}
    manifest_identity_hash = str(manifest.get("ordered_canonical_identity_set_sha256") or "")

    candidate_ref_resolution_failures = 0
    episode_hash_mismatches = 0
    missing_required_episode_fields = 0
    missing_required_candidate_fields = 0
    unaccepted_empty_candidate_sets = 0
    identity_inconsistencies = 0
    unexpected_candidate_fields = 0
    selection_provenance_inconsistencies = 0
    accepted_empty_with_candidates = 0
    invalid_episode_timestamps = 0
    referenced_keys: set[str] = set()
    readiness_rows = []
    blocker_counter: collections.Counter[str] = collections.Counter()
    smallest_blocker: dict | None = None

    for ep_index, ep in enumerate(episodes):
        reasons: list[tuple[str, str]] = []
        if not isinstance(ep, dict):
            add_reason(reasons, "EPISODE_ROW_NOT_OBJECT", str(ep_index))
            uid = ""
            refs = []
        else:
            uid = str(ep.get("alert_episode_uid") or "")
            episode_input = ep.get("classifier_episode_input")
            refs = ep.get("candidate_input_refs")
            if not isinstance(episode_input, dict):
                episode_input = {}
                add_reason(reasons, "CLASSIFIER_EPISODE_INPUT_NOT_OBJECT", uid)
            if not isinstance(refs, list):
                refs = []
                add_reason(reasons, "CANDIDATE_REFS_NOT_LIST", uid)

            for field in ["episode_id", "city_key", "alert_start", "alert_end"]:
                if not valid_nonempty(episode_input.get(field)):
                    missing_required_episode_fields += 1
                    add_reason(reasons, "MISSING_REQUIRED_CLASSIFIER_EPISODE_FIELD", f"{uid}:{field}")

            start_dt = parse_timestamp_exact(episode_input.get("alert_start"))
            end_dt = parse_timestamp_exact(episode_input.get("alert_end"))
            if valid_nonempty(episode_input.get("alert_start")) and start_dt is None:
                invalid_episode_timestamps += 1
                add_reason(reasons, "INVALID_ALERT_START", uid)
            if valid_nonempty(episode_input.get("alert_end")) and end_dt is None:
                invalid_episode_timestamps += 1
                add_reason(reasons, "INVALID_ALERT_END", uid)
            if start_dt is not None and end_dt is not None and end_dt <= start_dt:
                invalid_episode_timestamps += 1
                add_reason(reasons, "NONPOSITIVE_ALERT_INTERVAL", uid)

            frozen_row = recovery_rows.get(uid)
            parent_row = parent_rows.get(uid)
            if frozen_row is None or parent_row is None:
                identity_inconsistencies += 1
                add_reason(reasons, "FROZEN_IDENTITY_BINDING_MISSING", uid)
            else:
                exact_pairs = [
                    ("episode_id", frozen_row.get("live_monitor_episode_id")),
                    ("city_key", frozen_row.get("city_key")),
                    ("alert_start", frozen_row.get("start_at")),
                    ("alert_end", frozen_row.get("end_at")),
                ]
                for field, expected in exact_pairs:
                    if episode_input.get(field) != expected:
                        identity_inconsistencies += 1
                        add_reason(
                            reasons,
                            "CLASSIFIER_EPISODE_IDENTITY_MISMATCH",
                            f"{uid}:{field}:{episode_input.get(field)!r}!={expected!r}",
                        )
                expected_uid = f"{episode_input.get('city_key')}:{episode_input.get('episode_id')}"
                if uid != expected_uid:
                    identity_inconsistencies += 1
                    add_reason(reasons, "ALERT_EPISODE_UID_MISMATCH", f"{uid}!={expected_uid}")
                if ep.get("canonical_parent_identity") != parent_row:
                    identity_inconsistencies += 1
                    add_reason(reasons, "CANONICAL_PARENT_BINDING_MISMATCH", uid)

            if ep.get("candidate_input_representation") != REPRESENTATION:
                add_reason(reasons, "EPISODE_REPRESENTATION_MISMATCH", uid)

            resolved = []
            for ref_index, ref in enumerate(refs):
                key = str(ref or "")
                if key not in store:
                    candidate_ref_resolution_failures += 1
                    add_reason(reasons, "CANDIDATE_REF_RESOLUTION_FAILURE", f"{uid}:{ref_index}:{key}")
                    continue
                referenced_keys.add(key)
                candidate = store[key]
                resolved.append(candidate)
                missing_here = []
                for field in required_fields:
                    if field not in candidate or not valid_nonempty(candidate.get(field)):
                        missing_here.append(field)
                if missing_here:
                    missing_required_candidate_fields += len(missing_here)
                    add_reason(
                        reasons,
                        "MISSING_REQUIRED_CANDIDATE_FIELD",
                        f"{uid}:{key}:{','.join(sorted(missing_here))}",
                    )
                extra = sorted(set(candidate) - allowed_fields)
                if extra:
                    unexpected_candidate_fields += len(extra)
                    add_reason(
                        reasons,
                        "CANDIDATE_FIELDS_OUTSIDE_FROZEN_PROJECTION",
                        f"{uid}:{key}:{','.join(extra)}",
                    )
                if "city_key" in candidate and candidate.get("city_key") != episode_input.get("city_key"):
                    identity_inconsistencies += 1
                    add_reason(
                        reasons,
                        "CANDIDATE_CITY_IDENTITY_MISMATCH",
                        f"{uid}:{key}:{candidate.get('city_key')}!={episode_input.get('city_key')}",
                    )
                # source_type is never inferred. If the frozen contract requires it,
                # absence is already a hard missing-field blocker above; if optional,
                # absence remains accepted without substitution.

            evidence = ep.get("evidence_provenance")
            if not isinstance(evidence, dict):
                evidence = {}
                add_reason(reasons, "EVIDENCE_PROVENANCE_NOT_OBJECT", uid)
            accepted_empty = evidence.get("accepted_empty_candidate_set") is True
            if not refs and not accepted_empty:
                unaccepted_empty_candidate_sets += 1
                add_reason(reasons, "UNACCEPTED_EMPTY_CANDIDATE_SET", uid)
            if refs and accepted_empty:
                accepted_empty_with_candidates += 1
                add_reason(reasons, "ACCEPTED_EMPTY_FLAG_WITH_CANDIDATES", uid)

            selection = evidence.get("candidate_selection_provenance")
            if selection is None:
                selection = []
            if not isinstance(selection, list) or len(selection) != len(refs):
                selection_provenance_inconsistencies += 1
                add_reason(reasons, "SELECTION_PROVENANCE_LENGTH_MISMATCH", uid)
            else:
                for idx, ref in enumerate(refs):
                    prov = selection[idx]
                    if not isinstance(prov, dict):
                        selection_provenance_inconsistencies += 1
                        add_reason(reasons, "SELECTION_PROVENANCE_ROW_INVALID", f"{uid}:{idx}")
                        continue
                    if prov.get("candidate_input_sha256") != ref:
                        selection_provenance_inconsistencies += 1
                        add_reason(reasons, "SELECTION_PROVENANCE_HASH_MISMATCH", f"{uid}:{idx}")
                    if ref in store:
                        cid = store[ref].get("candidate_id")
                        if valid_nonempty(cid) and prov.get("candidate_id") != str(cid):
                            selection_provenance_inconsistencies += 1
                            add_reason(reasons, "SELECTION_PROVENANCE_CANDIDATE_ID_MISMATCH", f"{uid}:{idx}")
                    for multi in ["trigger_episode_ids", "trigger_check_labels"]:
                        if multi in prov and not isinstance(prov.get(multi), list):
                            selection_provenance_inconsistencies += 1
                            add_reason(reasons, "MULTIVALUE_PROVENANCE_TYPE_MISMATCH", f"{uid}:{idx}:{multi}")

            if len(resolved) == len(refs):
                logical_entry = {
                    "alert_episode_uid": uid,
                    "canonical_parent_identity": ep.get("canonical_parent_identity"),
                    "classifier_episode_input": ep.get("classifier_episode_input"),
                    "candidate_input_representation": ep.get("candidate_input_representation"),
                    "candidate_inputs": resolved,
                    "evidence_provenance": ep.get("evidence_provenance"),
                }
                actual_hash = sha256(canonical_bytes(logical_entry))
                expected_hash = str(ep.get("materialized_input_sha256") or "")
                if actual_hash != expected_hash:
                    episode_hash_mismatches += 1
                    add_reason(reasons, "EPISODE_MATERIALIZED_INPUT_HASH_MISMATCH", f"{uid}:{actual_hash}!={expected_hash}")

        for code, _ in reasons:
            blocker_counter[code] += 1
        if reasons and smallest_blocker is None:
            smallest_blocker = {
                "alert_episode_uid": uid,
                "reason": reasons[0][0],
                "detail": reasons[0][1],
            }
        readiness_rows.append({
            "alert_episode_uid": uid,
            "readiness": "CLASSIFIER_INPUT_BLOCKED" if reasons else "CLASSIFIER_INPUT_READY",
        })

    orphan_store_entries = len(set(store) - referenced_keys)
    ready_count = sum(row["readiness"] == "CLASSIFIER_INPUT_READY" for row in readiness_rows)
    blocked_count = len(readiness_rows) - ready_count

    global_failures = []
    def gate(cond: bool, code: str, detail: str):
        if not cond:
            global_failures.append((code, detail))

    gate(len(episodes) == EXPECTED_EPISODES, "FROZEN_EPISODE_COUNT_MISMATCH", str(len(episodes)))
    gate(len(readiness_rows) == EXPECTED_EPISODES, "VALIDATED_EPISODE_COUNT_MISMATCH", str(len(readiness_rows)))
    gate(blank_identities == 0, "MISSING_IDENTITIES", str(blank_identities))
    gate(missing_identities == 0, "MISSING_IDENTITIES", str(missing_identities))
    gate(unexpected_identities == 0, "UNEXPECTED_IDENTITIES", str(unexpected_identities))
    gate(duplicate_identities == 0, "DUPLICATE_IDENTITIES", str(duplicate_identities))
    gate(episode_uids == expected_uids, "ORDERED_IDENTITY_MEMBERSHIP_MISMATCH", "episode UID sequence != frozen Unit A sequence")
    gate(ordered_identity_hash == expected_identity_hash, "ORDERED_IDENTITY_HASH_MISMATCH", f"{ordered_identity_hash}!={expected_identity_hash}")
    gate(ordered_identity_hash == manifest_identity_hash, "MANIFEST_IDENTITY_HASH_MISMATCH", f"{ordered_identity_hash}!={manifest_identity_hash}")
    gate(candidate_store_hash_mismatches == 0, "CANDIDATE_STORE_HASH_MISMATCHES", str(candidate_store_hash_mismatches))
    gate(duplicate_key_semantic_disagreements == 0, "CANDIDATE_STORE_DUPLICATE_KEY_SEMANTIC_DISAGREEMENT", str(duplicate_key_semantic_disagreements))
    gate(duplicate_store_keys == 0, "CANDIDATE_STORE_DUPLICATE_KEYS", str(duplicate_store_keys))
    gate(candidate_ref_resolution_failures == 0, "CANDIDATE_REF_RESOLUTION_FAILURES", str(candidate_ref_resolution_failures))
    gate(orphan_store_entries == 0, "ORPHAN_CANDIDATE_STORE_ENTRIES", str(orphan_store_entries))
    gate(episode_hash_mismatches == 0, "EPISODE_MATERIALIZED_INPUT_HASH_MISMATCHES", str(episode_hash_mismatches))
    gate(missing_required_episode_fields == 0, "MISSING_REQUIRED_CLASSIFIER_EPISODE_FIELDS", str(missing_required_episode_fields))
    gate(invalid_episode_timestamps == 0, "INVALID_CLASSIFIER_EPISODE_TIMESTAMPS", str(invalid_episode_timestamps))
    gate(missing_required_candidate_fields == 0, "MISSING_REQUIRED_CANDIDATE_FIELDS", str(missing_required_candidate_fields))
    gate(unexpected_candidate_fields == 0, "CANDIDATE_FIELDS_OUTSIDE_FROZEN_PROJECTION", str(unexpected_candidate_fields))
    gate(unaccepted_empty_candidate_sets == 0, "UNACCEPTED_EMPTY_CANDIDATE_SETS", str(unaccepted_empty_candidate_sets))
    gate(accepted_empty_with_candidates == 0, "ACCEPTED_EMPTY_FLAG_WITH_CANDIDATES", str(accepted_empty_with_candidates))
    gate(identity_inconsistencies == 0, "IDENTITY_INCONSISTENCIES", str(identity_inconsistencies))
    gate(selection_provenance_inconsistencies == 0, "SELECTION_PROVENANCE_INCONSISTENCIES", str(selection_provenance_inconsistencies))
    gate(blocked_count == 0, "CLASSIFIER_INPUT_BLOCKED", str(blocked_count))
    gate(ready_count == EXPECTED_EPISODES, "CLASSIFIER_INPUT_READY_COUNT", str(ready_count))

    for code, detail in global_failures:
        blocker_counter[code] += 1
        if smallest_blocker is None:
            smallest_blocker = {"alert_episode_uid": None, "reason": code, "detail": detail}

    readiness_payload = {
        "representation": "ordered-readiness-rows-v1",
        "ordered_identity_set_sha256": ordered_identity_hash,
        "rows": readiness_rows,
    }
    readiness_sha = sha256(canonical_bytes(readiness_payload))

    counts = {
        "frozen_episodes": len(expected_uids),
        "validated_episodes": len(readiness_rows),
        "CLASSIFIER_INPUT_READY": ready_count,
        "CLASSIFIER_INPUT_BLOCKED": blocked_count,
        "missing_identities": missing_identities + blank_identities,
        "unexpected_identities": unexpected_identities,
        "duplicate_identities": duplicate_identities,
        "candidate_ref_resolution_failures": candidate_ref_resolution_failures,
        "candidate_store_hash_mismatches": candidate_store_hash_mismatches,
        "candidate_store_duplicate_key_semantic_disagreements": duplicate_key_semantic_disagreements,
        "candidate_store_duplicate_keys": duplicate_store_keys,
        "orphan_candidate_store_entries": orphan_store_entries,
        "episode_materialized_input_hash_mismatches": episode_hash_mismatches,
        "missing_required_classifier_episode_fields": missing_required_episode_fields,
        "invalid_classifier_episode_timestamps": invalid_episode_timestamps,
        "missing_required_candidate_fields": missing_required_candidate_fields,
        "candidate_fields_outside_frozen_projection": unexpected_candidate_fields,
        "unaccepted_empty_candidate_sets": unaccepted_empty_candidate_sets,
        "accepted_empty_flag_with_candidates": accepted_empty_with_candidates,
        "identity_inconsistencies": identity_inconsistencies,
        "selection_provenance_inconsistencies": selection_provenance_inconsistencies,
        "candidate_store_entries": len(store_rows),
        "referenced_candidate_store_entries": len(referenced_keys),
        "episode_candidate_refs": sum(len((ep or {}).get("candidate_input_refs") or []) for ep in episodes if isinstance(ep, dict)),
        "accepted_empty_candidate_sets": sum(
            bool(((ep or {}).get("evidence_provenance") or {}).get("accepted_empty_candidate_set"))
            for ep in episodes if isinstance(ep, dict)
        ),
    }

    result = {
        "run_label": label,
        "materialization_identity": {
            "path": MATERIALIZATION_PATH,
            "blob": MATERIALIZATION_BLOB,
            "sha256": MATERIALIZATION_SHA256,
            "bytes": len(raw),
            "compressed_corpus_sha256": sha256(compressed),
            "uncompressed_corpus_sha256": sha256(canonical_bytes(corpus)),
        },
        "recovery_identity": recovery_identity,
        "continuity_identity": continuity_identity,
        "implementation_contract": impl,
        "projection_contract": projection,
        "counts": counts,
        "readiness_payload": readiness_payload,
        "readiness_set_sha256": readiness_sha,
        "blocker_reason_counts": dict(sorted(blocker_counter.items())),
        "smallest_demonstrated_blocker": smallest_blocker,
        "global_failure_count": len(global_failures),
    }
    return result


def main() -> int:
    if OUTPUT.exists():
        raise Blocked("DURABLE_VALIDATION_ARTIFACT_ALREADY_EXISTS", str(OUTPUT))

    # Independent RUN A and RUN B: each re-reads and independently revalidates
    # the exact frozen bytes and pinned repository objects. No classifier code is imported or executed.
    run_a = validate_once("A")
    run_b = validate_once("B")

    if run_a["readiness_set_sha256"] != run_b["readiness_set_sha256"]:
        raise Blocked(
            "READINESS_VALIDATOR_NONDETERMINISTIC",
            f"{run_a['readiness_set_sha256']}!={run_b['readiness_set_sha256']}",
        )
    if canonical_bytes(run_a["readiness_payload"]) != canonical_bytes(run_b["readiness_payload"]):
        raise Blocked("READINESS_PAYLOAD_NONDETERMINISTIC", "RUN A/B readiness payload bytes differ")
    if run_a["counts"] != run_b["counts"]:
        raise Blocked("READINESS_COUNTS_NONDETERMINISTIC", "RUN A/B counts differ")

    counts = run_a["counts"]
    success = (
        counts["frozen_episodes"] == EXPECTED_EPISODES
        and counts["validated_episodes"] == EXPECTED_EPISODES
        and counts["CLASSIFIER_INPUT_READY"] == EXPECTED_EPISODES
        and counts["CLASSIFIER_INPUT_BLOCKED"] == 0
        and counts["missing_identities"] == 0
        and counts["unexpected_identities"] == 0
        and counts["duplicate_identities"] == 0
        and counts["candidate_ref_resolution_failures"] == 0
        and counts["candidate_store_hash_mismatches"] == 0
        and counts["candidate_store_duplicate_key_semantic_disagreements"] == 0
        and counts["candidate_store_duplicate_keys"] == 0
        and counts["orphan_candidate_store_entries"] == 0
        and counts["episode_materialized_input_hash_mismatches"] == 0
        and counts["missing_required_classifier_episode_fields"] == 0
        and counts["invalid_classifier_episode_timestamps"] == 0
        and counts["missing_required_candidate_fields"] == 0
        and counts["candidate_fields_outside_frozen_projection"] == 0
        and counts["unaccepted_empty_candidate_sets"] == 0
        and counts["accepted_empty_flag_with_candidates"] == 0
        and counts["identity_inconsistencies"] == 0
        and counts["selection_provenance_inconsistencies"] == 0
        and run_a["global_failure_count"] == 0
    )
    if not success:
        print(json.dumps({
            "verdict": "ATTACK-EVENT EXECUTION UNIT A CLASSIFIER READINESS = BLOCKED",
            "blocked_count": counts["CLASSIFIER_INPUT_BLOCKED"],
            "smallest_demonstrated_blocker": run_a["smallest_demonstrated_blocker"],
            "blocker_reason_counts": run_a["blocker_reason_counts"],
            "counts": counts,
        }, ensure_ascii=False, sort_keys=True))
        return 2

    hard_gates = {
        "frozen episodes = 1,713": "PASS",
        "validated episodes = 1,713": "PASS",
        "CLASSIFIER_INPUT_READY = 1,713": "PASS",
        "CLASSIFIER_INPUT_BLOCKED = 0": "PASS",
        "missing identities = 0": "PASS",
        "unexpected identities = 0": "PASS",
        "duplicate identities = 0": "PASS",
        "candidate ref resolution failures = 0": "PASS",
        "candidate store hash mismatches = 0": "PASS",
        "episode materialized-input hash mismatches = 0": "PASS",
        "missing required classifier episode fields = 0": "PASS",
        "missing required candidate fields = 0": "PASS",
        "unaccepted empty candidate sets = 0": "PASS",
        "identity inconsistencies = 0": "PASS",
        "classifier implementation drift = 0": "PASS",
        "normalization/input-builder implementation drift = 0": "PASS",
        "external evidence requests = 0": "PASS",
        "classifier executions = 0": "PASS",
        "classification verdicts produced = 0": "PASS",
        "normalization semantic changes = 0": "PASS",
        "classifier semantic changes = 0": "PASS",
        "parent-binding mutations = 0": "PASS",
        "Neon queries = 0": "PASS",
        "DB writes = 0": "PASS",
        "production mutation = NO": "PASS",
    }

    artifact = {
        "schema_version": 1,
        "kind": "attack_event_execution_unit_a_classifier_readiness_validation",
        "verdict": "ATTACK-EVENT EXECUTION UNIT A CLASSIFIER READINESS = PROVEN",
        "branch": BRANCH,
        "predecessor_commit": PREDECESSOR,
        "validated_materialization_artifact": run_a["materialization_identity"],
        "frozen_recovery_artifact": run_a["recovery_identity"],
        "frozen_continuity_artifact": run_a["continuity_identity"],
        "governing_semantics": {
            "methodology_version": METHODOLOGY,
            "normalization_version": NORMALIZATION,
            "candidate_input_representation": REPRESENTATION,
            "projection_contract": run_a["projection_contract"],
            "authoritative_classifier": {
                "commit": CLASSIFIER_REF,
                "path": CLASSIFIER_PATH,
                "blob": CLASSIFIER_BLOB,
                "verified": True,
                "executed": False,
            },
            "historical_observation_input_builder": {
                "commit": CLASSIFIER_REF,
                "path": BUILDER_PATH,
                "blob": BUILDER_BLOB,
                "verified": True,
                "executed": False,
            },
            "static_compatibility_proof": run_a["implementation_contract"],
        },
        "counts": counts,
        "readiness": run_a["readiness_payload"],
        "blocker_reason_counts": {},
        "determinism": {
            "run_a_readiness_set_sha256": run_a["readiness_set_sha256"],
            "run_b_readiness_set_sha256": run_b["readiness_set_sha256"],
            "deterministic": True,
        },
        "execution_guards": {
            "external_evidence_requests": 0,
            "classifier_executions": 0,
            "classification_verdicts_produced": 0,
            "normalization_semantic_changes": 0,
            "classifier_semantic_changes": 0,
            "parent_binding_mutations": 0,
            "neon_queries": 0,
            "db_writes": 0,
            "production_mutation": "NO",
            "source_type_inference": "NONE",
            "timestamp_inference": "NONE",
            "tolerance_matching": "NONE",
        },
        "hard_gates": hard_gates,
        "actions_run_id": int(os.environ.get("GITHUB_RUN_ID") or 0),
    }

    final_bytes = canonical_bytes(artifact)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes(final_bytes)
    if OUTPUT.read_bytes() != final_bytes:
        raise Blocked("DURABLE_VALIDATION_ARTIFACT_WRITE_MISMATCH", str(OUTPUT))

    summary = {
        "verdict": artifact["verdict"],
        "branch": BRANCH,
        "durable_validation_artifact_path": str(OUTPUT),
        "durable_artifact_sha256": sha256(final_bytes),
        "durable_artifact_bytes": len(final_bytes),
        "validated_materialization_blob": MATERIALIZATION_BLOB,
        "validated_materialization_sha256": MATERIALIZATION_SHA256,
        **counts,
        "classifier_blob_verified": "YES",
        "input_builder_blob_verified": "YES",
        "external_evidence_requests": 0,
        "classifier_executions": 0,
        "classification_verdicts_produced": 0,
        "normalization_semantic_changes": 0,
        "classifier_semantic_changes": 0,
        "neon_queries": 0,
        "db_writes": 0,
        "production_mutation": "NO",
        "run_A_readiness_set_sha256": run_a["readiness_set_sha256"],
        "run_B_readiness_set_sha256": run_b["readiness_set_sha256"],
        "deterministic": "YES",
    }
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Blocked as exc:
        print(json.dumps({
            "verdict": "ATTACK-EVENT EXECUTION UNIT A CLASSIFIER READINESS = BLOCKED",
            "failed_gate": exc.gate,
            "blocked_count": None,
            "smallest_demonstrated_blocker": exc.detail,
        }, ensure_ascii=False, sort_keys=True))
        raise SystemExit(2)
