#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path

PREDECESSOR = "ccb2e6ea2637b2bdbde5d21744a79d8f4a91ff4d"
RECOVERY_PATH = "research/attack_event_partitioned_classification_recovery_audit_2026-10-06.json"
RECOVERY_BLOB = "d65a545add6125ca16514fa4f9c8cb7a0b74a76c"
RECOVERY_SHA256 = "641cd7f4d1ca3c58755150ba0ff4f436794f558d5060ef416638adfed0513a98"
EXPECTED_A = 1713
EXPECTED_B = 352
EXPECTED_C = 35


def run(*args: str) -> bytes:
    p = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if p.returncode:
        raise RuntimeError(p.stderr.decode("utf-8", "replace")[-4000:])
    return p.stdout


def git_text(*args: str) -> str:
    return run("git", *args).decode("utf-8", "replace").strip()


def git_show(ref: str, path: str) -> bytes:
    return run("git", "show", f"{ref}:{path}")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


raw = git_show(PREDECESSOR, RECOVERY_PATH)
assert git_text("rev-parse", f"{PREDECESSOR}:{RECOVERY_PATH}") == RECOVERY_BLOB
assert sha256(raw) == RECOVERY_SHA256
doc = json.loads(raw.decode("utf-8"))

units = doc.get("execution_units") or {}
a = units.get("A_SAFE_EXISTING_EVIDENCE_MATERIALIZATION") or {}
b = units.get("B_EVIDENCE_COLLECTION_RECOVERY") or {}
c = units.get("C_IDENTITY_FORENSIC_MANUAL_CONTRACT_DECISION") or {}
a_uids = list(a.get("episode_uids") or [])
b_uids = list(b.get("episode_uids") or [])
c_uids = list(c.get("episode_uids") or [])
assert len(a_uids) == EXPECTED_A == int(a.get("count") or 0)
assert len(b_uids) == EXPECTED_B == int(b.get("count") or 0)
assert len(c_uids) == EXPECTED_C == int(c.get("count") or 0)
assert len(a_uids) == len(set(a_uids))
assert not (set(a_uids) & set(b_uids))
assert not (set(a_uids) & set(c_uids))

rows = list(((doc.get("materialization_cohort") or {}).get("rows") or []))
by_uid = {str(r.get("alert_episode_uid") or ""): r for r in rows if isinstance(r, dict)}
assert all(uid in by_uid for uid in a_uids)
a_rows = [by_uid[uid] for uid in a_uids]

projection = (((doc.get("normalization_forensic") or {})
               .get("frozen_classifier_input_projection") or {}))
required = list(projection.get("required_input_fields") or [])
optional = list(projection.get("optional_input_fields") or [])
assert projection.get("representation") == "FROZEN_LIVE_CANDIDATE_INPUT_BUNDLE"
assert required
assert all(str(r.get("recovery_action") or "") == "SAFE_EXISTING_EVIDENCE_MATERIALIZATION" for r in a_rows)
assert all(str(r.get("deterministic_episode_mapping") or "") == "YES" for r in a_rows)
assert all(not (r.get("missing_input_fields") or []) for r in a_rows)

queue_identities = {}
missing_queue_authority = []
subtypes = Counter()
empty = 0
candidate_total = 0
row_keys = set()
for r in a_rows:
    row_keys.update(r)
    subtypes[str(r.get("subtype") or "")] += 1
    n = int(r.get("candidate_input_count") or 0)
    candidate_total += n
    empty += int(n == 0)
    qi = r.get("collection_queue_identity") or {}
    commit = str(qi.get("commit") or "")
    path = str(qi.get("path") or "")
    blob = str(qi.get("blob") or "")
    if n > 0 and (not commit or not path or not blob):
        missing_queue_authority.append(str(r.get("alert_episode_uid") or ""))
    if commit and path:
        queue_identities[(commit, path)] = blob

unavailable = []
queue_blob_mismatches = []
for (commit, path), expected_blob in sorted(queue_identities.items()):
    try:
        actual = git_text("rev-parse", f"{commit}:{path}")
    except Exception:
        unavailable.append({"commit": commit, "path": path})
        continue
    if expected_blob and actual != expected_blob:
        queue_blob_mismatches.append({"commit": commit, "path": path})

# Inspect only structural keys from a bounded sample; never print candidate content.
sample_candidate_keys = set()
sample_explicit_availability = Counter()
for r in a_rows:
    if len(sample_candidate_keys) >= 40:
        break
    qi = r.get("collection_queue_identity") or {}
    commit = str(qi.get("commit") or "")
    path = str(qi.get("path") or "")
    eid = str(r.get("live_monitor_episode_id") or "")
    if not commit or not path or not eid:
        continue
    q = json.loads(git_show(commit, path).decode("utf-8"))
    for item in q:
        if not isinstance(item, dict):
            continue
        matched = str(item.get("matched_episode_id") or "")
        triggers = {str(x) for x in (item.get("trigger_episode_ids") or []) if str(x)}
        if eid != matched and eid not in triggers:
            continue
        sample_candidate_keys.update(item.keys())
        for key in ("source_type", "source_timestamp", "telegram_channel",
                    "telegram_message_id", "retrieval_provenance", "review_provenance",
                    "published_at"):
            if key in item:
                sample_explicit_availability[key] += 1
        if len(sample_candidate_keys) >= 40:
            break

continuity = doc.get("frozen_continuity_artifact_identity") or {}
source_ids = list(doc.get("source_artifact_identities") or [])

summary = {
    "probe": "UNIT_A_FROZEN_SHAPE_VALIDATED",
    "recovery_blob": RECOVERY_BLOB,
    "unit_A_count": len(a_uids),
    "unit_B_count": len(b_uids),
    "unit_C_count": len(c_uids),
    "A_B_overlap": len(set(a_uids) & set(b_uids)),
    "A_C_overlap": len(set(a_uids) & set(c_uids)),
    "materialization_row_count": len(a_rows),
    "materialization_row_keys": sorted(row_keys),
    "subtypes": dict(sorted(subtypes.items())),
    "candidate_input_total": candidate_total,
    "accepted_empty_candidate_sets": empty,
    "unique_queue_snapshots": len(queue_identities),
    "missing_queue_authority_rows": len(missing_queue_authority),
    "unavailable_queue_snapshots": len(unavailable),
    "queue_blob_mismatches": len(queue_blob_mismatches),
    "projection": {
        "representation": projection.get("representation"),
        "required_input_fields": required,
        "optional_input_fields": optional,
        "projection_rule": projection.get("projection_rule"),
    },
    "sample_candidate_key_names_only": sorted(sample_candidate_keys),
    "sample_explicit_availability_key_presence_counts": dict(sorted(sample_explicit_availability.items())),
    "frozen_continuity_identity": continuity,
    "source_artifact_identity_count": len(source_ids),
    "pinned_live_monitor_commit": doc.get("pinned_live_monitor_commit"),
}
print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
