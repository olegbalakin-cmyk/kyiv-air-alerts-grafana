#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import psycopg

REPO = "olegbalakin-cmyk/kyiv-air-alerts-grafana"
EXPECTED_SHADOW_BRANCH = "br-bold-mode-b5rub8pq"
AUDIT_BRANCH = "attack-event-postmigration-gap-audit-2026-10-06"
EXPECTED_MAIN_AT_PREPARATION = "5e9fa82694be6823841dcb468e5d847e8a4620e8"

SNAPSHOT = {
    "commit": "efefa399e69eadd3d7fc8393ac1553cfde35f138",
    "path": "research/attack_event_23city_persistence_snapshot_v2_2026-10-04.json",
    "blob": "8a2f6bd33f879be9db978da59c12c34e61f6f843",
    "sha256": "09458bcf0a019fa2939eb9dfa484da46cd8fa2be077343c5ba6d595c93d71788",
    "bytes": 90282029,
    "branch": "attack-event-23city-persistence-snapshot-v2-2026-10-04",
}
BINDING = {
    "commit": "e213f445f08bfc119b234c9460b66bd3efe75d36",
    "path": "research/attack_event_23city_parent_binding_map_v1_2026-10-05.json",
    "blob": "91e9bab3678e27296561c175b1b9776c3b765f68",
    "sha256": "b0ecd5ce980d76cf5ffce65f80ee1d5bd43c0d1b1438afb85424ae95aaef1241",
}
MIGRATION = {
    "commit": "2af665a845d68e37639032ba9736ec3ffaad6cd5",
    "path": "research/attack_event_23city_shadow_persistence_migration_2026-10-06.json",
    "blob": "f5a0b93cd79cae321b5e4c17915146ba99494cc0",
    "sha256": "4fa50cf84c32221ff7fca7f12c8a20bf6946015854f9e022f63ddb4ba1d2fda9",
}
SOURCE_HEADS = {
    "18-city persistence export": {
        "branch": "attack-event-18city-persistence-identity-v2-actions-replay-2026-10-04",
        "commit": "03a04d33f7616b77181741fd77a776c490391d07",
        "path": "research/attack_event_18city_persistence_identity_export_v2_2026-10-04.json",
        "blob": "a240f1950748afcb9fc974c49ac58da07adfff65",
    },
    "5-city persistence export": {
        "branch": "attack-event-5city-persistence-identity-v2-export-2026-10-04",
        "commit": "02ad2e8fadee78442753567bc2d3a540345d8e8a",
        "path": "research/attack_event_5city_persistence_identity_export_v2_2026-10-04.json",
        "blob": "a2e34c4a114ad335d35068d6c6a3a4606b09db7f",
    },
    "5-city historical campaign": {
        "branch": "historical-attack-event-backfill-2026-09-27",
        "commit": "71cb6f6fbe856cc7b96759310fe9cc9c71cc0453",
        "path": "research/historical_attack_event_backfill_status.json",
        "blob": "615b380b51c0da7aa052bad06222c12785090986",
    },
}

EXPECTED_COUNTS = {"classifications": 26405, "events": 1080, "source_links": 3769}
POSITIVE = {"STRICT_EVENT_POSITIVE", "SENSITIVITY_EVENT_POSITIVE"}
OUTDIR = Path(os.environ.get("RUNNER_TEMP", ".")) / "attack-event-postmigration-gap-audit"
OUTDIR.mkdir(parents=True, exist_ok=True)
OUT = OUTDIR / "attack_event_postmigration_gap_audit_2026-10-06.json"

CLASS_COLS = [
    "classification_key_version","classification_key","historical_episode_id","city_key","alert_type",
    "alert_start_at","alert_end_at","verdict","is_event","positive_tier","event_types","qa_reasons_state",
    "qa_reasons","classifier_reason_codes","classifier_blob_sha","classifier_methodology_version",
    "normalization_version","evidence_set_sha256","review_provenance_sha256","human_review_state",
    "review_provenance","originating_frozen_case_id","originating_frozen_case_id_state","binding_state",
    "alert_episode_uid","origin_repository","origin_ref","origin_commit_sha","origin_artifact_path",
    "origin_artifact_blob_sha","origin_target_state_sha256","origin_workflow_run_id","classified_at",
    "supersedes_classification_uid","revision_reason","correction_provenance","persisted_by_run_id",
    "origin_provenance","origin_provenance_sha256"
]
EVENT_COLS = [
    "attack_event_key_version","attack_event_key","event_grain","historical_episode_id","city_key","alert_type",
    "alert_start_at","alert_end_at","event_status","current_classification_uid","binding_state","alert_episode_uid",
    "correction_provenance","created_by_run_id","updated_by_run_id"
]
SOURCE_COLS = [
    "source_link_key_version","source_link_key","classification_uid","observation_id","source_family","source_type",
    "source_type_state","source_url","telegram_channel","telegram_message_id","source_timestamp",
    "source_timestamp_state","source_timestamp_raw","event_timestamp_if_stated","excerpt","content_sha256",
    "content_hash_basis","observation_classification_outcome","classification_episode_id","evidence_payload",
    "retrieval_provenance","origin_artifact_path","origin_git_ref","origin_git_blob_sha","raw_object_path",
    "origin_provenance","origin_provenance_sha256"
]

class GateError(RuntimeError):
    def __init__(self, gate, phase, category=None, count=None, detail=None):
        self.gate = gate
        self.phase = phase
        self.category = category
        self.count = count
        self.detail = detail
        super().__init__(gate)

def fail(gate, phase, category=None, count=None, detail=None):
    raise GateError(gate, phase, category, count, detail)

def now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def run(args, check=True, stdout=None):
    p = subprocess.run(list(map(str, args)), stdout=stdout if stdout is not None else subprocess.PIPE,
                       stderr=subprocess.PIPE, text=False)
    if check and p.returncode:
        raise RuntimeError((p.stderr or b"").decode("utf-8", "replace")[-800:])
    return p

def git_text(*args):
    return run(["git", *args]).stdout.decode("utf-8", "replace").strip()

def ls_remote(branch):
    p = run(["git", "ls-remote", "origin", f"refs/heads/{branch}"], check=False)
    if p.returncode:
        return None
    s = p.stdout.decode("utf-8", "replace").strip()
    return s.split()[0] if s else None

def ensure_commit(sha):
    p = run(["git", "cat-file", "-e", f"{sha}^{{commit}}"], check=False)
    if p.returncode:
        run(["git", "fetch", "--no-tags", "origin", sha])
    got = git_text("rev-parse", f"{sha}^{{commit}}")
    if got != sha:
        fail("FROZEN_INPUT_COMMIT_MISMATCH", "AUTHORITY_DISCOVERY", "repository_provenance", detail=sha)

def sha_file(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def materialize(spec, label):
    ensure_commit(spec["commit"])
    blob = git_text("rev-parse", f'{spec["commit"]}:{spec["path"]}')
    if spec.get("blob") and blob != spec["blob"]:
        fail(label + "_BLOB_MISMATCH", "AUTHORITY_DISCOVERY", label)
    out = OUTDIR / (label.lower().replace(" ", "_") + ".json")
    with out.open("wb") as f:
        p = run(["git", "show", f'{spec["commit"]}:{spec["path"]}'], check=False, stdout=f)
    if p.returncode:
        fail(label + "_MATERIALIZATION_FAILED", "AUTHORITY_DISCOVERY", label)
    if spec.get("bytes") is not None and out.stat().st_size != spec["bytes"]:
        fail(label + "_BYTE_COUNT_MISMATCH", "AUTHORITY_DISCOVERY", label)
    raw_sha = sha_file(out)
    if spec.get("sha256") and raw_sha != spec["sha256"]:
        fail(label + "_SHA256_MISMATCH", "AUTHORITY_DISCOVERY", label)
    return out, blob, raw_sha

def canonical_bytes(v):
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")

def canonical_sha(v):
    return hashlib.sha256(canonical_bytes(v)).hexdigest()

def parse_utc(value):
    if not isinstance(value, str) or not value:
        raise ValueError("timestamp unavailable")
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("naive timestamp")
    return dt.astimezone(timezone.utc)

def utc_micro(dt):
    if dt is None:
        return None
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

def normalize(v):
    if isinstance(v, UUID):
        return str(v)
    if isinstance(v, datetime):
        return utc_micro(v)
    if isinstance(v, dict):
        return {str(k): normalize(x) for k, x in sorted(v.items(), key=lambda kv: str(kv[0]))}
    if isinstance(v, (list, tuple)):
        return [normalize(x) for x in v]
    return v

def walk_values(obj, predicate):
    out = []
    def walk(x, key=""):
        if isinstance(x, dict):
            for k, v in x.items():
                walk(v, str(k))
        elif isinstance(x, list):
            for v in x:
                walk(v, key)
        elif predicate(key.lower(), x):
            out.append(x)
    walk(obj)
    return out

def walk_exact(obj, keys):
    out = []
    def walk(x, path="$"):
        if isinstance(x, dict):
            for k, v in x.items():
                p = path + "." + str(k)
                if str(k) in keys:
                    out.append((p, v))
                walk(v, p)
        elif isinstance(x, list):
            for i, v in enumerate(x):
                walk(v, f"{path}[{i}]")
    walk(obj)
    return out

def unique_string(obj, predicate):
    vals = sorted({str(v) for v in walk_values(obj, predicate)
                   if isinstance(v, (str, int)) and str(v).strip()})
    return vals[0] if len(vals) == 1 else None

def unique_nonempty_strings(obj, keys):
    vals = []
    for path, v in walk_exact(obj, set(keys)):
        if isinstance(v, (str, int)) and str(v).strip():
            vals.append((path, str(v)))
    return sorted({v for _, v in vals}), vals

def has_adjudication_marker(row):
    return bool(walk_values(row, lambda k, v: k in {"accepted_adjudication_artifact", "adjudication_class"} and v not in (None, "", False)))

def case_id_state(row):
    vals, _ = unique_nonempty_strings(row, {"originating_frozen_case_id", "frozen_case_id"})
    if len(vals) > 1:
        return "CONFLICT", None
    if len(vals) == 1:
        return "MATERIALIZED", vals[0]
    if has_adjudication_marker(row):
        return "UNMATERIALIZED_IN_ACCEPTED_SOURCE", None
    return "NOT_APPLICABLE", None

def source_type_state(row):
    vals, _ = unique_nonempty_strings(row, {"source_type"})
    if len(vals) > 1:
        return "CONFLICT", None
    if len(vals) == 1:
        return "MATERIALIZED", vals[0]
    return "UNMATERIALIZED_IN_ACCEPTED_SOURCE", None

def parse_availability_ts(v):
    if v in (None, ""):
        return "ABSENT_IN_ACCEPTED_SOURCE", None, None
    raw = str(v)
    try:
        return "MATERIALIZED", parse_utc(raw), None
    except Exception:
        return "UNPARSEABLE_IN_ACCEPTED_SOURCE", None, raw

def accepted_payload_projection(row):
    hits = walk_exact(row, {"evidence_payload", "classifier_evidence_payload"})
    by_hash = {}
    for path, value in hits:
        if isinstance(value, dict):
            by_hash.setdefault(canonical_sha(value), value)
    if len(by_hash) == 1:
        return "MATERIALIZED", next(iter(by_hash.values()))
    if len(by_hash) > 1:
        return "CONFLICT", None
    return "UNMATERIALIZED_IN_ACCEPTED_SOURCE", None

def classification_origin_projection(origin):
    return {
        "origin_repository": unique_string(origin, lambda k, v: k == "origin_repository") or REPO,
        "origin_ref": unique_string(origin, lambda k, v: k == "ref" or k.endswith("_ref")),
        "origin_commit_sha": unique_string(origin, lambda k, v: "commit" in k or k.endswith("_head") or k in {"tested_head", "accepted_final_head"}),
        "origin_artifact_path": unique_string(origin, lambda k, v: "path" in k),
        "origin_artifact_blob_sha": unique_string(origin, lambda k, v: "blob" in k),
        "origin_target_state_sha256": unique_string(origin, lambda k, v: k == "origin_target_state_sha256" or k.endswith("target_state_sha256")),
        "origin_workflow_run_id": unique_string(origin, lambda k, v: "run_id" in k and isinstance(v, (str, int))),
    }

def source_origin_projection(origin):
    return {
        "origin_artifact_path": unique_string(origin, lambda k, v: "path" in k),
        "origin_git_ref": unique_string(origin, lambda k, v: k == "ref" or k.endswith("_ref")),
        "origin_git_blob_sha": unique_string(origin, lambda k, v: "blob" in k),
    }

def nonempty_review(v):
    return isinstance(v, dict) and bool(v)

def derive_human_state(row):
    rv = row.get("review_provenance")
    rh = row.get("review_provenance_sha256")
    if nonempty_review(rv) and isinstance(rh, str) and rh:
        if canonical_sha(rv) != rh:
            raise ValueError("review provenance hash mismatch")
        return "REVIEWED_EVIDENCE"
    if nonempty_review(rv) != bool(rh):
        raise ValueError("review provenance/hash consistency mismatch")
    return "NEEDS_REVIEW" if row.get("verdict") == "NEEDS_REVIEW" else "NONE"

def build_expected(snapshot, binding):
    cls = snapshot.get("classifications")
    events = snapshot.get("attack_events")
    links = snapshot.get("source_links")
    records = binding.get("records")
    if not all(isinstance(x, list) for x in (cls, events, links, records)):
        fail("CURRENT_CLASSIFICATION_SOURCE_SCHEMA_MISMATCH", "AUTHORITY_DISCOVERY", "authoritative_source")
    if (len(cls), len(events), len(links), len(records)) != (26405, 1080, 3769, 26405):
        fail("CURRENT_CLASSIFICATION_SOURCE_COUNT_MISMATCH", "AUTHORITY_DISCOVERY", "authoritative_source")
    bind_by_ck = {str(r["classification_key"]): r for r in records}
    class_by_ck = {str(r["classification_key"]): r for r in cls}
    positive_keys = {str(r["classification_key"]) for r in cls if r.get("verdict") in POSITIVE}
    if set(bind_by_ck) != set(class_by_ck):
        fail("CURRENT_CLASSIFICATION_BINDING_KEYSET_MISMATCH", "AUTHORITY_DISCOVERY", "authoritative_source")

    class_rows = []
    for r in cls:
        ck = str(r["classification_key"])
        start_dt = parse_utc(str(r["alert_start_utc_microseconds"]))
        end_dt = parse_utc(str(r["alert_end_utc_microseconds"]))
        if end_dt <= start_dt:
            fail("CURRENT_CLASSIFICATION_TIMESTAMP_INVALID", "AUTHORITY_DISCOVERY", "classification", 1, ck)
        op = r.get("origin_provenance")
        if not isinstance(op, dict):
            fail("CURRENT_CLASSIFICATION_PROVENANCE_UNAVAILABLE", "AUTHORITY_DISCOVERY", "classification", 1, ck)
        p = classification_origin_projection(op)
        case_state, case_id = case_id_state(r)
        if case_state == "CONFLICT":
            fail("CURRENT_CLASSIFICATION_CASE_ID_AMBIGUOUS", "AUTHORITY_DISCOVERY", "classification", 1, ck)
        b = bind_by_ck[ck]
        verdict = str(r["verdict"])
        tier = "STRICT" if verdict == "STRICT_EVENT_POSITIVE" else "SENSITIVITY" if verdict == "SENSITIVITY_EVENT_POSITIVE" else None
        run_id = p.get("origin_workflow_run_id")
        run_id = int(run_id) if run_id is not None and str(run_id).isdigit() else None
        review = r.get("review_provenance")
        class_rows.append({
            "classification_key_version": r["classification_key_version"],
            "classification_key": ck,
            "historical_episode_id": r["historical_episode_id"],
            "city_key": r["city_key"],
            "alert_type": "AIR",
            "alert_start_at": start_dt,
            "alert_end_at": end_dt,
            "verdict": verdict,
            "is_event": verdict in POSITIVE,
            "positive_tier": tier,
            "event_types": list(r["event_types"]),
            "qa_reasons_state": r["qa_reasons_state"],
            "qa_reasons": r.get("qa_reasons"),
            "classifier_reason_codes": list(r["classifier_reason_codes"]),
            "classifier_blob_sha": r["classifier_blob_sha"],
            "classifier_methodology_version": r["classifier_methodology_version"],
            "normalization_version": r["normalization_version"],
            "evidence_set_sha256": r["evidence_set_sha256"],
            "review_provenance_sha256": r.get("review_provenance_sha256"),
            "human_review_state": derive_human_state(r),
            "review_provenance": review if nonempty_review(review) else {},
            "originating_frozen_case_id": case_id,
            "originating_frozen_case_id_state": case_state,
            "binding_state": b["binding_state"],
            "alert_episode_uid": b.get("alert_episode_uid"),
            "origin_repository": p.get("origin_repository"),
            "origin_ref": p.get("origin_ref"),
            "origin_commit_sha": p.get("origin_commit_sha"),
            "origin_artifact_path": p.get("origin_artifact_path"),
            "origin_artifact_blob_sha": p.get("origin_artifact_blob_sha"),
            "origin_target_state_sha256": p.get("origin_target_state_sha256"),
            "origin_workflow_run_id": run_id,
            "classified_at": None,
            "supersedes_classification_uid": None,
            "revision_reason": None,
            "correction_provenance": {},
            "persisted_by_run_id": None,
            "origin_provenance": op,
            "origin_provenance_sha256": canonical_sha(op),
        })

    event_rows = []
    for r in events:
        ck = str(r["classification_key_v2"])
        if ck not in positive_keys:
            fail("CURRENT_EVENT_CLASSIFICATION_MAPPING_MISMATCH", "AUTHORITY_DISCOVERY", "event", 1, ck)
        b = bind_by_ck[ck]
        event_rows.append({
            "attack_event_key_version": r["attack_event_key_version"],
            "attack_event_key": r["attack_event_key"],
            "event_grain": r["event_grain"],
            "historical_episode_id": r["historical_episode_id"],
            "city_key": r["city_key"],
            "alert_type": "AIR",
            "alert_start_at": parse_utc(str(r["alert_start_utc_microseconds"])),
            "alert_end_at": parse_utc(str(r["alert_end_utc_microseconds"])),
            "event_status": "ACTIVE",
            "classification_key_v2": ck,
            "binding_state": b["binding_state"],
            "alert_episode_uid": b.get("alert_episode_uid"),
            "correction_provenance": {},
            "created_by_run_id": None,
            "updated_by_run_id": None,
        })
    if len(event_rows) != 1080:
        fail("CURRENT_EVENT_COUNT_MISMATCH", "AUTHORITY_DISCOVERY", "event", len(event_rows))

    source_rows = []
    for r in links:
        ck = str(r["classification_key_v2"])
        if ck not in class_by_ck:
            fail("CURRENT_SOURCE_CLASSIFICATION_MAPPING_MISMATCH", "AUTHORITY_DISCOVERY", "source", 1, ck)
        st_state, st_value = source_type_state(r)
        if st_state == "CONFLICT":
            fail("CURRENT_SOURCE_TYPE_CONFLICT", "AUTHORITY_DISCOVERY", "source", 1, r.get("source_link_key"))
        payload_state, payload = accepted_payload_projection(r)
        if payload_state != "MATERIALIZED" or not isinstance(payload, dict):
            fail("CURRENT_EVIDENCE_PAYLOAD_UNAVAILABLE", "AUTHORITY_DISCOVERY", "source", 1, r.get("source_link_key"))
        source_ts_state, source_ts, source_ts_raw = parse_availability_ts(r.get("source_timestamp"))
        event_ts_state, event_ts, _ = parse_availability_ts(r.get("event_timestamp_if_stated"))
        if event_ts_state == "UNPARSEABLE_IN_ACCEPTED_SOURCE":
            fail("CURRENT_EVENT_TIMESTAMP_UNPARSEABLE", "AUTHORITY_DISCOVERY", "source", 1, r.get("source_link_key"))
        retrieval = r.get("retrieval_provenance")
        if retrieval is None:
            retrieval = {}
        if not isinstance(retrieval, dict):
            fail("CURRENT_RETRIEVAL_PROVENANCE_INVALID", "AUTHORITY_DISCOVERY", "source", 1, r.get("source_link_key"))
        op = r.get("origin")
        if not isinstance(op, dict):
            op = r.get("origin_provenance")
        if not isinstance(op, dict):
            fail("CURRENT_SOURCE_PROVENANCE_UNAVAILABLE", "AUTHORITY_DISCOVERY", "source", 1, r.get("source_link_key"))
        p = source_origin_projection(op)
        raw_path = r.get("raw_object_path")
        if raw_path is None:
            raw_path = unique_string(retrieval, lambda k, v: k == "raw_object_path")
        mid = r.get("telegram_message_id")
        source_rows.append({
            "source_link_key_version": r["source_link_key_version"],
            "source_link_key": r["source_link_key"],
            "classification_key_v2": ck,
            "observation_id": r["observation_id"],
            "source_family": r.get("source_family"),
            "source_type": st_value,
            "source_type_state": st_state,
            "source_url": r.get("source_url"),
            "telegram_channel": r.get("telegram_channel"),
            "telegram_message_id": int(mid) if mid is not None else None,
            "source_timestamp": source_ts,
            "source_timestamp_state": source_ts_state,
            "source_timestamp_raw": source_ts_raw,
            "event_timestamp_if_stated": event_ts,
            "excerpt": r.get("excerpt"),
            "content_sha256": r["content_sha256"],
            "content_hash_basis": r["content_hash_basis"],
            "observation_classification_outcome": r.get("observation_classification_outcome"),
            "classification_episode_id": r.get("classification_episode_id"),
            "evidence_payload": payload,
            "retrieval_provenance": retrieval,
            "origin_artifact_path": p.get("origin_artifact_path"),
            "origin_git_ref": p.get("origin_git_ref"),
            "origin_git_blob_sha": p.get("origin_git_blob_sha"),
            "raw_object_path": raw_path,
            "origin_provenance": op,
            "origin_provenance_sha256": canonical_sha(op),
        })
    if len(source_rows) != 3769:
        fail("CURRENT_SOURCE_LINK_COUNT_MISMATCH", "AUTHORITY_DISCOVERY", "source", len(source_rows))
    return cls, class_rows, event_rows, source_rows

def identity_time(city, start, end):
    return (str(city), utc_micro(start), utc_micro(end))

def write_result(result):
    OUT.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")), encoding="utf-8")

result = {
    "schema_version": 1,
    "kind": "attack_event_postmigration_gap_audit",
    "verdict": "ATTACK-EVENT POST-MIGRATION PERSISTENCE GAP AUDIT = BLOCKED",
    "first_failing_gate": None,
    "phase": "INIT",
    "affected_category": None,
    "affected_count": 0,
    "audit_branch": os.environ.get("GITHUB_REF_NAME") or AUDIT_BRANCH,
    "workflow_commit": os.environ.get("GITHUB_SHA"),
    "actions_run_id": int(os.environ.get("GITHUB_RUN_ID", "0") or 0),
    "target_neon_branch_id": EXPECTED_SHADOW_BRANCH,
    "audit_started_at": now_iso(),
    "audit_ended_at": None,
    "audited_main_commit": None,
    "audited_main_commit_end": None,
    "committed_migration": MIGRATION,
    "authoritative_current_classification_source": None,
    "baseline_persisted_counts": {},
    "current_classification_counts": {},
    "set_difference_counts": {},
    "persistence_backlog_by_city": {},
    "parent_coverage": {},
    "catch_up": {
        "classifications": 0,
        "events": 0,
        "source_links": 0,
        "binding": {"BOUND": 0, "UNBOUND": 0, "AMBIGUOUS": 0},
        "representability_gaps": [],
        "classification_identities": [],
        "event_identities": [],
        "source_link_identities": [],
    },
    "semantic_supersession_or_conflict_identities": [],
    "ambiguous_identities": [],
    "committed_baseline_drift": {
        "missing_classifications": 0,
        "extra_classifications": 0,
        "classification_semantic_mismatches": 0,
        "event_semantic_mismatches": 0,
        "source_link_semantic_mismatches": 0,
    },
    "observation_boundaries": {},
    "neon_queries_count": 0,
    "db_writes": 0,
    "production_mutation": "NO",
    "credentials_exposed": False,
    "safe_continuation_point": None,
}

conn = None
try:
    result["phase"] = "AUTHORITY_DISCOVERY"
    main_start = ls_remote("main")
    result["audited_main_commit"] = main_start
    if not main_start:
        fail("CURRENT_CLASSIFICATION_AUTHORITY_UNRESOLVED", "AUTHORITY_DISCOVERY", "main_head", 1, "main head unavailable")
    if main_start != EXPECTED_MAIN_AT_PREPARATION:
        fail("CURRENT_CLASSIFICATION_AUTHORITY_UNRESOLVED", "AUTHORITY_DISCOVERY", "main_head", 1,
             f"main advanced after audit branch preparation: {main_start}")

    snap_path, snap_blob, snap_sha = materialize(SNAPSHOT, "SNAPSHOT")
    bind_path, bind_blob, bind_sha = materialize(BINDING, "BINDING")
    mig_path, mig_blob, mig_sha = materialize(MIGRATION, "MIGRATION")
    migration = json.loads(mig_path.read_bytes())
    if migration.get("verdict") != "ATTACK-EVENT 23-CITY SHADOW PERSISTENCE MIGRATION COMMITTED":
        fail("COMMITTED_MIGRATION_PROVENANCE_INVALID", "AUTHORITY_DISCOVERY", "migration", 1)

    head_checks = {}
    for label, spec in SOURCE_HEADS.items():
        observed = ls_remote(spec["branch"])
        head_checks[label] = {"branch": spec["branch"], "expected": spec["commit"], "observed": observed}
        if observed != spec["commit"]:
            fail("CURRENT_CLASSIFICATION_AUTHORITY_UNRESOLVED", "AUTHORITY_DISCOVERY", label, 1,
                 f"authoritative source head advanced: expected {spec['commit']} observed {observed}")
        ensure_commit(spec["commit"])
        observed_blob = git_text("rev-parse", f'{spec["commit"]}:{spec["path"]}')
        if observed_blob != spec["blob"]:
            fail("CURRENT_CLASSIFICATION_AUTHORITY_UNRESOLVED", "AUTHORITY_DISCOVERY", label, 1,
                 "authoritative source blob mismatch")

    snapshot = json.loads(snap_path.read_bytes())
    binding = json.loads(bind_path.read_bytes())
    provenance = snapshot.get("snapshot_provenance") or {}
    if provenance.get("assembly_mode") != "OFFLINE_UNION_OF_ALREADY_FROZEN_EXPORTS":
        fail("CURRENT_CLASSIFICATION_AUTHORITY_UNRESOLVED", "AUTHORITY_DISCOVERY", "snapshot_provenance", 1,
             "snapshot is not the frozen authoritative union")
    if int(provenance.get("semantic_classification_changes", -1)) != 0:
        fail("CURRENT_CLASSIFICATION_AUTHORITY_UNRESOLVED", "AUTHORITY_DISCOVERY", "snapshot_provenance", 1,
             "snapshot changed classification semantics")

    cls, class_rows, event_rows, source_rows = build_expected(snapshot, binding)
    cities = sorted({str(r["city_key"]) for r in cls})
    if len(cities) != 23:
        fail("CURRENT_CLASSIFICATION_AUTHORITY_UNRESOLVED", "AUTHORITY_DISCOVERY", "city_coverage", len(cities))

    source_commits = {str(x.get("commit")) for x in (provenance.get("sources") or []) if x.get("commit")}
    if source_commits != {
        SOURCE_HEADS["18-city persistence export"]["commit"],
        SOURCE_HEADS["5-city persistence export"]["commit"],
    }:
        fail("CURRENT_CLASSIFICATION_AUTHORITY_UNRESOLVED", "AUTHORITY_DISCOVERY", "snapshot_sources",
             len(source_commits), str(sorted(source_commits)))

    methodology = Counter(str(r.get("classifier_methodology_version")) for r in cls)
    normalization = Counter(str(r.get("normalization_version")) for r in cls)
    classifiers = Counter(str(r.get("classifier_blob_sha")) for r in cls)
    result["authoritative_current_classification_source"] = {
        "status": "ESTABLISHED",
        "artifact": {
            "path": SNAPSHOT["path"],
            "commit": SNAPSHOT["commit"],
            "blob": snap_blob,
            "sha256": snap_sha,
            "branch": SNAPSHOT["branch"],
        },
        "component_sources": provenance.get("sources"),
        "head_checks": head_checks,
        "methodology_versions": dict(methodology),
        "normalization_versions": dict(normalization),
        "classifier_blob_shas": dict(classifiers),
        "city_coverage": cities,
        "city_count": len(cities),
        "logical_alert_episode_count": len(cls),
        "provenance_basis": {
            "assembly_mode": provenance.get("assembly_mode"),
            "semantic_classification_changes": provenance.get("semantic_classification_changes"),
            "governing_contracts": provenance.get("governing_contracts"),
            "source_branches_unchanged_at_audit": True,
            "five_city_campaign_head_unchanged": True,
        },
    }
    result["current_classification_counts"] = {
        "classifications": len(class_rows),
        "events": len(event_rows),
        "source_links": len(source_rows),
        "cities": len(cities),
        "verdict_distribution": dict(Counter(str(r.get("verdict")) for r in cls)),
    }

    result["phase"] = "VERIFY_PERSISTED_SHADOW_BASELINE"
    db_url = os.environ.get("PHASE1_PROD_SHADOW_DATABASE_URL", "")
    branch_id = os.environ.get("PHASE1_PROD_SHADOW_BRANCH_ID", "")
    if not db_url:
        fail("PHASE1_PROD_SHADOW_DATABASE_URL_MISSING", result["phase"], "database", 1)
    if branch_id != EXPECTED_SHADOW_BRANCH:
        fail("PERMANENT_NEON_BRANCH_ID_MISMATCH", result["phase"], "database", 1,
             f"expected={EXPECTED_SHADOW_BRANCH};actual={branch_id or '<missing>'}")

    conn = psycopg.connect(db_url, autocommit=True, connect_timeout=20, options="-c default_transaction_read_only=on")
    qcount = 0
    with conn.cursor() as cur:
        def q(sql, params=None):
            nonlocal_holder[0] += 1
            cur.execute(sql, params)
        nonlocal_holder = [0]

        q("BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        q("SET LOCAL default_transaction_read_only = on")
        q("SELECT current_setting('transaction_read_only'), current_setting('default_transaction_read_only')")
        if tuple(cur.fetchone()) != ("on", "on"):
            fail("READ_ONLY_TRANSACTION_NOT_ENFORCED", result["phase"], "database", 1)

        q("SELECT (SELECT count(*) FROM public.attack_event_classifications),"
          "(SELECT count(*) FROM public.attack_events),"
          "(SELECT count(*) FROM public.attack_event_sources)")
        ccount, ecount, scount = map(int, cur.fetchone())
        result["baseline_persisted_counts"] = {
            "classifications": ccount, "events": ecount, "source_links": scount
        }
        if (ccount, ecount, scount) != (26405, 1080, 3769):
            result["committed_baseline_drift"]["missing_classifications"] = max(0, 26405 - ccount)
            result["committed_baseline_drift"]["extra_classifications"] = max(0, ccount - 26405)
            fail("COMMITTED_SHADOW_BASELINE_DRIFT", result["phase"], "row_counts",
                 abs(ccount-26405) + abs(ecount-1080) + abs(scount-3769))

        q("SELECT classification_uid::text," + ",".join(CLASS_COLS) +
          " FROM public.attack_event_classifications ORDER BY classification_key")
        db_class = cur.fetchall()
        exp_class = sorted(class_rows, key=lambda r: str(r["classification_key"]))
        db_keys = [str(r[2]) for r in db_class]
        exp_keys = [str(r["classification_key"]) for r in exp_class]
        missing = sorted(set(exp_keys) - set(db_keys))
        extra = sorted(set(db_keys) - set(exp_keys))
        result["committed_baseline_drift"]["missing_classifications"] = len(missing)
        result["committed_baseline_drift"]["extra_classifications"] = len(extra)
        if missing or extra:
            result["committed_baseline_drift"]["missing_classification_identities"] = missing
            result["committed_baseline_drift"]["extra_classification_identities"] = extra
            fail("COMMITTED_SHADOW_BASELINE_DRIFT", result["phase"], "classification_identity_set",
                 len(missing) + len(extra))

        uid_map = {}
        class_mismatch = []
        for dbrow, erow in zip(db_class, exp_class):
            uid_map[str(erow["classification_key"])] = str(dbrow[0])
            actual = normalize(list(dbrow[1:]))
            expected = normalize([erow[c] for c in CLASS_COLS])
            if actual != expected:
                class_mismatch.append(str(erow["classification_key"]))
        result["committed_baseline_drift"]["classification_semantic_mismatches"] = len(class_mismatch)
        if class_mismatch:
            result["committed_baseline_drift"]["classification_semantic_mismatch_identities"] = class_mismatch
            fail("COMMITTED_SHADOW_BASELINE_DRIFT", result["phase"], "classification_semantics", len(class_mismatch))

        q("SELECT " + ",".join(EVENT_COLS) + " FROM public.attack_events ORDER BY attack_event_key")
        db_events = cur.fetchall()
        exp_events = sorted(event_rows, key=lambda r: str(r["attack_event_key"]))
        event_mismatch = []
        if len(db_events) != len(exp_events):
            event_mismatch = [str(r["attack_event_key"]) for r in exp_events]
        else:
            for dbrow, erow in zip(db_events, exp_events):
                ex = dict(erow)
                ex["current_classification_uid"] = uid_map[erow["classification_key_v2"]]
                if normalize(list(dbrow)) != normalize([ex[c] for c in EVENT_COLS]):
                    event_mismatch.append(str(erow["attack_event_key"]))
        result["committed_baseline_drift"]["event_semantic_mismatches"] = len(event_mismatch)
        if event_mismatch:
            result["committed_baseline_drift"]["event_semantic_mismatch_identities"] = event_mismatch
            fail("COMMITTED_SHADOW_BASELINE_DRIFT", result["phase"], "event_semantics", len(event_mismatch))

        q("SELECT " + ",".join(SOURCE_COLS) + " FROM public.attack_event_sources ORDER BY source_link_key")
        db_sources = cur.fetchall()
        exp_sources = sorted(source_rows, key=lambda r: str(r["source_link_key"]))
        source_mismatch = []
        if len(db_sources) != len(exp_sources):
            source_mismatch = [str(r["source_link_key"]) for r in exp_sources]
        else:
            for dbrow, erow in zip(db_sources, exp_sources):
                ex = dict(erow)
                ex["classification_uid"] = uid_map[erow["classification_key_v2"]]
                if normalize(list(dbrow)) != normalize([ex[c] for c in SOURCE_COLS]):
                    source_mismatch.append(str(erow["source_link_key"]))
        result["committed_baseline_drift"]["source_link_semantic_mismatches"] = len(source_mismatch)
        if source_mismatch:
            result["committed_baseline_drift"]["source_link_semantic_mismatch_identities"] = source_mismatch
            fail("COMMITTED_SHADOW_BASELINE_DRIFT", result["phase"], "source_link_semantics", len(source_mismatch))

        result["phase"] = "COMPARE_CURRENT_AUTHORITATIVE_CLASSIFICATIONS"
        result["set_difference_counts"] = {
            "EXACTLY_PERSISTED": len(class_rows),
            "NEW_CLASSIFICATION_NOT_PERSISTED": 0,
            "SEMANTIC_SUPERSESSION_OR_CONFLICT": 0,
            "CURRENT_CLASSIFICATION_IDENTITY_AMBIGUOUS": 0,
        }
        result["persistence_backlog_by_city"] = {city: 0 for city in cities}

        result["phase"] = "INVENTORY_CANONICAL_PARENT_GAPS"
        q("SELECT episode_uid::text,city_key::text,alert_type::text,episode_state::text,"
          "canonicalization_version::text,start_at,end_at "
          "FROM public.alert_episodes "
          "WHERE city_key::text = ANY(%s) AND alert_type::text='AIR' "
          "ORDER BY city_key,start_at,end_at NULLS LAST,episode_uid", (cities,))
        parents = cur.fetchall()

        frozen_logical = defaultdict(list)
        for r in class_rows:
            frozen_logical[(str(r["city_key"]), utc_micro(r["alert_start_at"]), utc_micro(r["alert_end_at"]))].append(str(r["classification_key"]))
        frozen_duplicate_logical = {k:v for k,v in frozen_logical.items() if len(v) > 1}
        if frozen_duplicate_logical:
            fail("CURRENT_CLASSIFICATION_IDENTITY_AMBIGUOUS", result["phase"], "frozen_logical_episode",
                 len(frozen_duplicate_logical))

        new_closed = []
        new_open = []
        covered_parent_count = 0
        canon_versions = Counter()
        state_dist = Counter()
        for uid, city, alert_type, state, canon, start_at, end_at in parents:
            canon_versions[str(canon)] += 1
            state_dist[str(state)] += 1
            start_s = utc_micro(start_at)
            end_s = utc_micro(end_at)
            logical = (str(city), start_s, end_s)
            if end_at is not None and logical in frozen_logical:
                covered_parent_count += 1
                continue
            rec = {
                "alert_episode_uid": str(uid),
                "city_key": str(city),
                "alert_type": str(alert_type),
                "episode_state": str(state),
                "canonicalization_version": str(canon),
                "start_at": start_s,
                "end_at": end_s,
            }
            if str(state).lower() == "closed" and end_at is not None:
                new_closed.append(rec)
            else:
                new_open.append(rec)

        by_city = Counter(r["city_key"] for r in new_closed)
        result["parent_coverage"] = {
            "current_canonical_air_parent_count": len(parents),
            "covered_by_current_authoritative_classification": covered_parent_count,
            "new_or_absent_from_frozen_classification_coverage": len(new_closed) + len(new_open),
            "HAS_CURRENT_AUTHORITATIVE_CLASSIFICATION": 0,
            "NO_CURRENT_AUTHORITATIVE_CLASSIFICATION": len(new_closed) + len(new_open),
            "closed_without_current_authoritative_classification": len(new_closed),
            "open_or_current_without_current_authoritative_classification": len(new_open),
            "closed_without_classification_by_city": dict(sorted(by_city.items())),
            "closed_parent_identities": new_closed,
            "open_or_current_parent_identities": new_open,
            "episode_state_distribution": dict(state_dist),
            "canonicalization_version_distribution": dict(canon_versions),
        }

        max_parent = None
        if parents:
            max_parent = max(parents, key=lambda r: ((r[6] or r[5]), r[5], str(r[0])))
        max_cls = max(class_rows, key=lambda r: (r["alert_end_at"], r["alert_start_at"], str(r["classification_key"])))
        result["observation_boundaries"] = {
            "current_maximum_canonical_alert": None if max_parent is None else {
                "alert_episode_uid": str(max_parent[0]),
                "city_key": str(max_parent[1]),
                "start_at": utc_micro(max_parent[5]),
                "end_at": utc_micro(max_parent[6]),
                "maximum_observed_time": utc_micro(max_parent[6] or max_parent[5]),
            },
            "current_maximum_authoritative_classification": {
                "classification_key": str(max_cls["classification_key"]),
                "city_key": str(max_cls["city_key"]),
                "alert_start_at": utc_micro(max_cls["alert_start_at"]),
                "alert_end_at": utc_micro(max_cls["alert_end_at"]),
            },
        }
        q("ROLLBACK")
        result["neon_queries_count"] = nonlocal_holder[0]

    conn.close()
    conn = None

    result["phase"] = "DERIVE_CATCH_UP_CORPUS"
    result["catch_up"] = {
        "classifications": 0,
        "events": 0,
        "source_links": 0,
        "binding": {"BOUND": 0, "UNBOUND": 0, "AMBIGUOUS": 0},
        "representability_gaps": [],
        "semantic_conflicts": 0,
        "classification_identities": [],
        "event_identities": [],
        "source_link_identities": [],
    }
    result["verdict"] = "ATTACK-EVENT POST-MIGRATION PERSISTENCE GAP AUDIT = ZERO"
    result["first_failing_gate"] = None
    result["affected_category"] = None
    result["affected_count"] = 0
    result["safe_continuation_point"] = (
        "Persistence catch-up corpus is empty at this bounded audit point. "
        "Do not persist parent-only gaps; they require upstream authoritative classification first. "
        "Any later persistence task must use this exact frozen audit corpus or rerun the gap audit if authoritative state advances."
    )

except GateError as exc:
    if conn is not None:
        try:
            conn.rollback()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass
    result["verdict"] = "ATTACK-EVENT POST-MIGRATION PERSISTENCE GAP AUDIT = BLOCKED"
    result["first_failing_gate"] = exc.gate
    result["phase"] = exc.phase
    result["affected_category"] = exc.category
    result["affected_count"] = int(exc.count or 0)
    if exc.detail is not None:
        result["compact_diagnostic"] = str(exc.detail)[:800]
    result["safe_continuation_point"] = (
        "Do not perform persistence catch-up. Resume only from the first failing gate after preserving this read-only audit result."
    )

except Exception as exc:
    if conn is not None:
        try:
            conn.rollback()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass
    secret = os.environ.get("PHASE1_PROD_SHADOW_DATABASE_URL", "")
    msg = str(exc)
    if secret:
        msg = msg.replace(secret, "<redacted>")
    msg = re.sub(r"(?i)(postgres(?:ql)?://)[^@\s]+@", r"\1<redacted>@", msg)
    result["verdict"] = "ATTACK-EVENT POST-MIGRATION PERSISTENCE GAP AUDIT = BLOCKED"
    result["first_failing_gate"] = "EXECUTION_HARNESS_FAILURE"
    result["affected_category"] = type(exc).__name__
    result["affected_count"] = 1
    result["compact_diagnostic"] = msg[:800]
    result["safe_continuation_point"] = "Fix audit tooling only; do not perform persistence catch-up."

finally:
    result["audited_main_commit_end"] = ls_remote("main")
    result["audit_ended_at"] = now_iso()
    write_result(result)
    print("AUDIT_RESULT=" + json.dumps({
        "verdict": result.get("verdict"),
        "first_failing_gate": result.get("first_failing_gate"),
        "phase": result.get("phase"),
        "affected_category": result.get("affected_category"),
        "affected_count": result.get("affected_count"),
        "baseline_persisted_counts": result.get("baseline_persisted_counts"),
        "current_classification_counts": result.get("current_classification_counts"),
        "set_difference_counts": result.get("set_difference_counts"),
        "parent_coverage": {
            "new_or_absent": (result.get("parent_coverage") or {}).get("new_or_absent_from_frozen_classification_coverage"),
            "closed_without_classification": (result.get("parent_coverage") or {}).get("closed_without_current_authoritative_classification"),
            "open_or_current_without_classification": (result.get("parent_coverage") or {}).get("open_or_current_without_current_authoritative_classification"),
            "closed_without_classification_by_city": (result.get("parent_coverage") or {}).get("closed_without_classification_by_city"),
        },
        "catch_up": result.get("catch_up"),
        "neon_queries_count": result.get("neon_queries_count"),
        "db_writes": result.get("db_writes"),
        "production_mutation": result.get("production_mutation"),
        "safe_continuation_point": result.get("safe_continuation_point"),
    }, ensure_ascii=False, sort_keys=True, separators=(",", ":")))

if result["verdict"].endswith("= BLOCKED"):
    sys.exit(1)
