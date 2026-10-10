#!/usr/bin/env python3
"""Unit A A5: read-only current-state revalidation of the frozen A4 v5 manifest.
One bounded Neon connection, one REPEATABLE READ READ ONLY transaction, no A5 execution.
"""
from __future__ import annotations
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from uuid import UUID
import hashlib
import json
import os
import re
import subprocess

BASE = "5ec3a60938da7bad1b0bd364b01bb36d31b9a72f"
PROOF_BRANCH = "attack-event-unit-a-a5-current-state-revalidation-2026-10-10"
OUT = Path("research/attack_event_execution_unit_a_a5_current_state_revalidation_2026-10-10.json")
A4_REF = "1b93d94cf9a11fd71b55483d9da0b443b954e25c"
A4_PATH = "research/attack_event_execution_unit_a_a4_independent_reacceptance_v5_2026-10-10.json"
A4_BLOB = "7e1becd3327ed3bfca4d4076ff99d45d4e4d3c8b"
A4_SHA = "6ff9b3d2e6dec717f8d5115705ce739915442b9f5530256107f0e42e0d501818"
PROD_REF = "36a5989229ed5c1ad1cd07fbb61df5033af22681"
PROD_PATH = "research/attack_event_execution_unit_a_shadow_persistence_gap_audit_resume3_2026-10-09.json"
PROD_BLOB = "d9bd54a946c3bb88faa0e351d18883eed7c44e60"
PROD_SHA = "2e6a3b0b8ab0dec2ac5d38c996a71325cabd257d5b80864e32b6c47756667e55"
PROJECTION_SHA = "7978087ad00f37d0d1eb9f4326a478d5760e79cd7f7a68ae2be39fc5211bffa3"
DELTA_SHA = "6070b6dbfc03e16b5236aed5b3cb090fa066100857a9c4f7bed502d6bb294aa3"
PROJECT = "green-cake-44216048"
BRANCH = "br-bold-mode-b5rub8pq"
HOST = "ep-still-violet-b5bg6mhp.c-7.us-east-2.aws.neon.tech"
ACTION_COUNTS = {"INSERT_INITIAL": 1713, "INSERT_SOURCE_LINK": 1559, "INSERT_EVENT": 10}
POSITIVE = {"STRICT_EVENT_POSITIVE", "SENSITIVITY_EVENT_POSITIVE"}
PARENT_FIELDS = "episode_uid legacy_episode_id city_key alert_type episode_state canonicalization_version start_at end_at".split()
CLASS_FIELDS = "classification_uid classification_key_version classification_key historical_episode_id city_key alert_start_at alert_end_at verdict is_event positive_tier event_types qa_reasons_state qa_reasons classifier_reason_codes classifier_blob_sha classifier_methodology_version normalization_version evidence_set_sha256 review_provenance_sha256 supersedes_classification_uid alert_episode_uid".split()
SOURCE_FIELDS = "source_link_key_version source_link_key classification_uid observation_id source_family source_type source_type_state source_url telegram_channel telegram_message_id source_timestamp source_timestamp_state source_timestamp_raw event_timestamp_if_stated excerpt content_sha256 content_hash_basis observation_classification_outcome classification_episode_id evidence_payload retrieval_provenance".split()
EVENT_FIELDS = "attack_event_uid attack_event_key_version attack_event_key event_grain historical_episode_id city_key alert_start_at alert_end_at event_status current_classification_uid alert_episode_uid".split()
TABLE_FIELDS = {
    "alert_episodes": PARENT_FIELDS, "attack_event_classifications": CLASS_FIELDS,
    "attack_event_sources": SOURCE_FIELDS, "attack_events": EVENT_FIELDS,
}

class ProofFailure(Exception):
    def __init__(self, category, count=0, examples=None, kind="execution"):
        super().__init__(category)
        self.category, self.count, self.examples, self.kind = category, count, examples or [], kind

def ensure(ok, category, count=0, examples=None, kind="input"):
    if not ok:
        raise ProofFailure(category, count, examples, kind)

def normalize(value):
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        ensure(value.tzinfo is not None, "NAIVE_SERVER_DATETIME", kind="execution")
        return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    if isinstance(value, dict):
        return {k: normalize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [normalize(v) for v in value]
    return value

def canonical(value):
    return json.dumps(normalize(value), sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")

def sha(value):
    return hashlib.sha256(value).hexdigest()

def hashed(value):
    return sha(canonical(value))

def git(*args):
    p = subprocess.run(["git", *args], capture_output=True, env=dict(
        os.environ, GIT_NO_LAZY_FETCH="1", GIT_TERMINAL_PROMPT="0"))
    ensure(p.returncode == 0, "IMMUTABLE_GIT_OBJECT_UNAVAILABLE", kind="execution")
    return p.stdout

def git_authority(commit, path, blob, digest):
    ensure(git("rev-parse", commit + ":" + path).decode().strip() == blob,
           "UNIT_A_A5_REVALIDATION_INPUT_DRIFT")
    b = git("show", commit + ":" + path)
    ensure(sha(b) == digest, "UNIT_A_A5_REVALIDATION_INPUT_DRIFT")
    return json.loads(b)

def report_new():
    return {
        "schema_version": 1, "kind": "unit_a_a5_current_state_precondition_revalidation",
        "execution_base_commit": BASE, "execution_base_branch": PROOF_BRANCH,
        "run_id": os.environ.get("GITHUB_RUN_ID"),
        "verdict": "A5_REVALIDATION_EXECUTION_BLOCKED",
        "A5_CURRENT_STATE_GATE": "NOT_RUN",
        "A5_MANIFEST_STILL_EXACT": "UNKNOWN",
        "A5_PRECONDITIONS_CHECKED": 0, "A5_PRECONDITIONS_VALID": 0,
        "A5_PRECONDITIONS_DRIFTED": 0,
        "A5_READY_FOR_EXPLICIT_AUTHORIZATION": "NO",
        "A5_AUTHORIZED": "NO", "A5_EXECUTED": "NO",
        "phase_reached": "INIT",
        "accepted_a4": {"artifact_commit": A4_REF, "path": A4_PATH,
                        "blob": A4_BLOB, "sha256": A4_SHA,
                        "actions_run": "38062605120", "job": "114243746070"},
        "manifest": {"accepted_delta_sha256": DELTA_SHA, "accepted_projection_sha256": PROJECTION_SHA,
                     "accepted_total": 3282, "accepted_distribution": ACTION_COUNTS,
                     "recomputed_delta_sha256_before": None,
                     "recomputed_delta_sha256_after": None, "hashes_equal": False},
        "neon": {"project": PROJECT, "branch": BRANCH, "expected_endpoint_host": HOST,
                 "branch_identity_verified": False, "database_name": None,
                 "connections": 0, "connection_attempts": 0,
                 "isolation": None, "read_only": False, "transaction_rolled_back": False,
                 "select_count": 0, "attempted_writes": 0, "committed_writes": 0},
        "preconditions": {
            "parents": {"checked": 0, "unchanged": 0, "missing": 0, "ambiguous": 0, "changed_binding": 0, "drifted": 0},
            "classifications": {"checked": 0, "valid": 0, "drifted": 0, "unexpected_tips": 0, "semantic_conflicts": 0},
            "sources": {"checked": 0, "valid": 0, "drifted": 0, "semantic_conflicts": 0},
            "positive_events": {"checked": 0, "valid": 0, "drifted": 0},
            "nonpositive_targets": {"checked": 0, "unchanged": 0, "drifted": 0},
            "mutations": {"checked": 0, "valid": 0, "drifted": 0}
        },
        "first_drift_category": None, "affected_action_count": 0, "bounded_examples": [],
        "safety": {"insert": 0, "update": 0, "delete": 0, "merge": 0, "ddl": 0,
                   "attempted_db_writes": 0, "committed_db_writes": 0,
                   "a5_actions_executed": 0, "production_mutation": "NO",
                   "site_prod_mutation": "NO"}
    }

def save(report):
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2,
                              allow_nan=False).encode("utf-8") + b"\n")

def prepare(report):
    ensure(os.environ.get("GITHUB_REF_NAME") == PROOF_BRANCH,
           "WRONG_PROOF_BRANCH", kind="execution")
    ensure(git("merge-base", "HEAD", BASE).decode().strip() == BASE,
           "BASE_NOT_ANCESTOR", kind="execution")
    a4 = git_authority(A4_REF, A4_PATH, A4_BLOB, A4_SHA)
    ensure(a4.get("A4_ACCEPTANCE_GATE") == "PASS"
           and a4.get("A5_MANIFEST_ACCEPTED") == "YES"
           and a4.get("A5_AUTHORIZED") == "NO"
           and a4.get("preconditions", {}).get("complete") == 3282
           and a4.get("preconditions", {}).get("incomplete") == 0
           and a4.get("delta", {}).get("run_a_sha256") == DELTA_SHA,
           "UNIT_A_A5_REVALIDATION_INPUT_DRIFT")
    producer = git_authority(PROD_REF, PROD_PATH, PROD_BLOB, PROD_SHA)
    frozen = producer.get("A5_frozen_delta_manifest")
    ensure(isinstance(frozen, dict), "UNIT_A_A5_REVALIDATION_INPUT_DRIFT")
    ca, sa, ea = (frozen.get(k) for k in
                  ("classification_actions", "source_actions", "event_actions"))
    ensure(all(isinstance(x, list) for x in (ca, sa, ea)),
           "UNIT_A_A5_REVALIDATION_INPUT_DRIFT")
    actions = ca + sa + ea
    counts = dict(Counter(x.get("action") for x in actions))
    ensure(counts == ACTION_COUNTS
           and len(ca) == 1713 and len(sa) == 1559 and len(ea) == 10
           and len(actions) == 3282
           and frozen.get("action_counts") == ACTION_COUNTS,
           "UNIT_A_A5_REVALIDATION_INPUT_DRIFT")
    classes = [a["semantic_row"] for a in ca]
    sources = [a["semantic_source_row"] for a in sa]
    cby = {c["classification_key"]: c for c in classes}
    sby = {s["source_link_key"]: s for s in sources}
    eids = {c["historical_episode_id"] for c in classes}
    ensure(len(cby) == len(classes) == len(eids) == 1713
           and len(sby) == len(sources) == 1559
           and len({a["attack_event_key"] for a in ea}) == 10,
           "UNIT_A_A5_REVALIDATION_INPUT_DRIFT")
    bindings = {}
    for a in ca:
        c = a["semantic_row"]
        k = a["classification_key"]
        ensure(a["action"] == "INSERT_INITIAL"
               and k == c["classification_key"]
               and a["historical_episode_id"] == c["historical_episode_id"]
               and a["city_key"] == c["city_key"]
               and a["semantic_row_sha256"] == hashed(c)
               and a["expected_tip_uid"] is None
               and a["expected_tip_key"] is None
               and a["expected_prior_verdict"] is None
               and isinstance(c.get("parent_identity"), dict),
               "UNIT_A_A5_REVALIDATION_INPUT_DRIFT")
        bindings[k] = a["alert_episode_uid"]
    for a in sa:
        s = a["semantic_source_row"]
        ensure(a["action"] == "INSERT_SOURCE_LINK"
               and a["source_link_key"] == s["source_link_key"]
               and a["target_classification_key"] == s["classification_key"]
               and s["classification_key"] in cby
               and a["observation_id"] == s["observation_id"]
               and a["content_sha256"] == s["content_sha256"]
               and a["semantic_source_row_sha256"] == hashed(s),
               "UNIT_A_A5_REVALIDATION_INPUT_DRIFT")
    positive = {c["historical_episode_id"]: c for c in classes if c["verdict"] in POSITIVE}
    ensure(len(positive) == 10, "UNIT_A_A5_REVALIDATION_INPUT_DRIFT")
    for a in ea:
        c = positive.get(a["historical_episode_id"])
        ensure(c is not None and a["action"] == "INSERT_EVENT"
               and c["attack_event_key"] == a["attack_event_key"]
               and a["city_key"] == c["city_key"]
               and a["desired_classification_key"] == c["classification_key"]
               and a["semantic_precondition_hash"] ==
                 hashed({"absent": True, "episode": a["historical_episode_id"]}),
               "UNIT_A_A5_REVALIDATION_INPUT_DRIFT")
    events = [{
        "attack_event_key": c["attack_event_key"],
        "attack_event_key_version": "attack-event-key-v1",
        "event_grain": "HISTORICAL_ALERT_EPISODE",
        "historical_episode_id": c["historical_episode_id"],
        "city_key": c["city_key"],
        "alert_start_at": c["alert_start_at"],
        "alert_end_at": c["alert_end_at"],
        "desired_status": "ACTIVE",
        "desired_classification_key": c["classification_key"]
    } for c in positive.values()]
    events.sort(key=lambda x: x["attack_event_key"])
    projection = {"classifications": classes, "events": events, "sources": sources}
    parent_sha = hashed(sorted(bindings.items()))
    proj_sha = hashed(projection)
    rebuilt = {
        "schema_version": 1, "project": PROJECT, "branch": BRANCH,
        "parent_binding_sha256": parent_sha, "projection_sha256": proj_sha,
        "classification_actions": ca, "source_actions": sa,
        "event_actions": ea, "action_counts": dict(sorted(counts.items()))
    }
    result_sha = hashed(rebuilt)
    report["manifest"]["recomputed_delta_sha256_before"] = result_sha
    report["manifest"]["recomputed_projection_sha256"] = proj_sha
    report["manifest"]["parent_binding_sha256"] = parent_sha
    ensure(frozen == rebuilt and proj_sha == PROJECTION_SHA
           and parent_sha == frozen["parent_binding_sha256"]
           and producer.get("A5_DELTA_SHA256") == DELTA_SHA
           and result_sha == DELTA_SHA,
           "UNIT_A_A5_REVALIDATION_INPUT_DRIFT")
    report["A5_MANIFEST_STILL_EXACT"] = "YES"
    report["manifest"]["hashes_equal"] = True
    report["phase_reached"] = "A_FROZEN_MANIFEST_EXACT_BEFORE_NEON"
    return ca, sa, ea, classes, positive, rebuilt

def query(cur, report, sql, args=()):
    ensure(re.match(r"^\s*SELECT\b", sql, re.I) is not None,
           "FORBIDDEN_NON_SELECT_SQL", kind="execution")
    report["neon"]["select_count"] += 1
    cur.execute(sql, args)
    return cur.fetchall()

def indexed(rows, field):
    out = defaultdict(list)
    for row in rows:
        out[str(row[field])].append(row)
    return out

def rows_as_objects(rows, fields):
    return [dict(zip(fields, normalize(row))) for row in rows]

def sample_examples(items):
    return sorted(items, key=lambda x: canonical(x))[:3]

def check_parents(r, classes, ca, rows, rebuilt):
    r["phase_reached"] = "C_PARENT_REVALIDATION"
    idx = indexed(rows, "legacy_episode_id")
    a_by_key = {a["classification_key"]: a for a in ca}
    examples = []
    p = r["preconditions"]["parents"]
    live = {}
    for c in classes:
        p["checked"] += 1
        k, eid = c["classification_key"], c["historical_episode_id"]
        matches = [row for row in idx.get(str(eid), [])
                   if all(row.get(f) == val for f, val in c["parent_identity"].items())]
        if not matches:
            p["missing"] += 1
            examples.append({"episode_id": eid, "reason": "missing_canonical_parent"})
        elif len(matches) != 1:
            p["ambiguous"] += 1
            examples.append({"episode_id": eid, "reason": "multiple_canonical_parents", "count": len(matches)})
        else:
            actual_uid = str(matches[0]["episode_uid"])
            live[k] = actual_uid
            if actual_uid != str(a_by_key[k]["alert_episode_uid"]):
                p["changed_binding"] += 1
                examples.append({"episode_id": eid, "reason": "changed_parent_uid",
                                 "expected_uid": str(a_by_key[k]["alert_episode_uid"]),
                                 "observed_uid": actual_uid})
            else:
                p["unchanged"] += 1
    p["drifted"] = p["checked"] - p["unchanged"]
    r["manifest"]["current_parent_binding_sha256"] = hashed(sorted(live.items()))
    if p["drifted"] or r["manifest"]["current_parent_binding_sha256"] != rebuilt["parent_binding_sha256"]:
        raise ProofFailure("UNIT_A_A5_PARENT_PRECONDITION_DRIFT", p["drifted"],
                           sample_examples(examples), "drift")
    r["phase_reached"] = "C_PARENTS_UNCHANGED"

def check_classes(r, classes, ca, rows):
    r["phase_reached"] = "D_CLASSIFICATION_REVALIDATION"
    idx = indexed(rows, "historical_episode_id")
    keys = indexed(rows, "classification_key")
    p = r["preconditions"]["classifications"]
    examples = []
    for c in classes:
        p["checked"] += 1
        eid, key = str(c["historical_episode_id"]), c["classification_key"]
        episode_rows, same_key = idx.get(eid, []), keys.get(key, [])
        superseded = {str(x["supersedes_classification_uid"]) for x in episode_rows
                      if x["supersedes_classification_uid"] is not None}
        tips = [x for x in episode_rows if str(x["classification_uid"]) not in superseded]
        p["unexpected_tips"] += len(tips)
        if same_key or episode_rows:
            p["drifted"] += 1
            mismatched = any(x.get("historical_episode_id") != c["historical_episode_id"]
                             or x.get("city_key") != c["city_key"]
                             or str(x.get("alert_episode_uid")) != str(ca[p["checked"] - 1]["alert_episode_uid"])
                             for x in same_key)
            if mismatched:
                p["semantic_conflicts"] += 1
            examples.append({"episode_id": eid, "classification_key": key,
                             "exact_key_rows": len(same_key),
                             "episode_rows": len(episode_rows),
                             "current_tips": len(tips), "semantic_conflict": mismatched})
        else:
            p["valid"] += 1
    if p["drifted"]:
        raise ProofFailure("UNIT_A_A5_CLASSIFICATION_PRECONDITION_DRIFT",
                           p["drifted"], sample_examples(examples), "drift")
    r["phase_reached"] = "D_CLASSIFICATIONS_ABSENT"

def check_sources(r, sa, rows):
    r["phase_reached"] = "E_SOURCE_REVALIDATION"
    idx = indexed(rows, "source_link_key")
    p = r["preconditions"]["sources"]
    examples = []
    for a in sa:
        p["checked"] += 1
        found = idx.get(a["source_link_key"], [])
        if found:
            p["drifted"] += 1
            semantic_conflict = any(
                x.get("parent_classification_key") != a["target_classification_key"]
                or any(normalize(x.get(k)) != normalize(a["semantic_source_row"].get(k))
                       for k in SOURCE_FIELDS if k != "classification_uid")
                for x in found)
            if semantic_conflict or len(found) > 1:
                p["semantic_conflicts"] += 1
            examples.append({"source_link_key": a["source_link_key"],
                             "found": len(found), "semantic_conflict": semantic_conflict})
        else:
            p["valid"] += 1
    if p["drifted"]:
        raise ProofFailure("UNIT_A_A5_SOURCE_PRECONDITION_DRIFT",
                           p["drifted"], sample_examples(examples), "drift")
    r["phase_reached"] = "E_SOURCE_KEYS_ABSENT"

def check_events(r, classes, positive, rows):
    r["phase_reached"] = "F_EVENT_REVALIDATION"
    by_id = indexed(rows, "historical_episode_id")
    by_key = indexed(rows, "attack_event_key")
    ep, non = r["preconditions"]["positive_events"], r["preconditions"]["nonpositive_targets"]
    examples = []
    for c in classes:
        eid, key = str(c["historical_episode_id"]), c["attack_event_key"]
        found = {str(x["attack_event_uid"]): x for x in
                 by_id.get(eid, []) + by_key.get(key, [])}
        is_pos = c["historical_episode_id"] in positive
        target = ep if is_pos else non
        target["checked"] += 1
        if found:
            target["drifted"] += 1
            examples.append({"episode_id": eid,
                             "positive": is_pos, "event_rows": len(found),
                             "statuses": sorted({str(x["event_status"]) for x in found.values()})[:3]})
        else:
            target["valid" if is_pos else "unchanged"] += 1
    total = ep["drifted"] + non["drifted"]
    if total:
        raise ProofFailure("UNIT_A_A5_EVENT_PRECONDITION_DRIFT",
                           total, sample_examples(examples), "drift")
    r["phase_reached"] = "F_EVENT_PARTITION_UNCHANGED"

def current_state(r, ca, sa, ea, classes, positive, rebuilt):
    ensure(os.environ.get("PHASE1_PROD_SHADOW_BRANCH_ID") == BRANCH,
           "SHADOW_BRANCH_VARIABLE_UNAVAILABLE_OR_MISMATCHED", kind="execution")
    url = os.environ.get("PHASE1_PROD_SHADOW_DATABASE_URL")
    ensure(bool(url), "SHADOW_DATABASE_SECRET_UNAVAILABLE", kind="execution")
    ensure(urlparse(url).hostname == HOST,
           "SHADOW_DATABASE_HOST_NOT_APPROVED", kind="execution")
    r["neon"]["branch_identity_verified"] = True
    r["phase_reached"] = "B_APPROVED_NEON_ENDPOINT"
    import psycopg
    r["neon"]["connection_attempts"] = 1
    conn = psycopg.connect(url, autocommit=True, connect_timeout=20,
                           options="-c default_transaction_read_only=on -c statement_timeout=120000")
    r["neon"]["connections"] = 1
    try:
        with conn.cursor() as cur:
            cur.execute("BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            try:
                state = query(cur, r, "SELECT current_setting('transaction_isolation'), current_setting('transaction_read_only'), current_database()")[0]
                iso, read_only, dbname = state
                r["neon"]["isolation"], r["neon"]["read_only"] = iso, read_only == "on"
                r["neon"]["database_name"] = dbname
                ensure(iso == "repeatable read" and read_only == "on",
                       "SERVER_TRANSACTION_NOT_READ_ONLY_REPEATABLE", kind="execution")
                table_names = list(TABLE_FIELDS)
                cols = query(cur, r, """SELECT table_name,column_name
                    FROM information_schema.columns
                    WHERE table_schema='public' AND table_name=ANY(%s)""",
                    (table_names,))
                available = defaultdict(set)
                for table, col in cols:
                    available[table].add(col)
                missing = {table: sorted(set(fields) - available[table])
                           for table, fields in TABLE_FIELDS.items()
                           if set(fields) - available[table]}
                ensure(not missing, "UNIT_A_A5_SCHEMA_DRIFT",
                       3282, [{"missing_columns": missing}], "drift")
                idxs = query(cur, r, """SELECT tablename,indexname,indexdef FROM pg_indexes
                    WHERE schemaname='public' AND tablename=ANY(%s)""", (table_names,))
                unique_keys = {}
                for table, key in (("attack_event_classifications", "classification_key"),
                                   ("attack_event_sources", "source_link_key"),
                                   ("attack_events", "attack_event_key")):
                    unique_keys[table] = any(
                        name == table and "UNIQUE" in str(defn).upper()
                        and re.search(r"\b" + re.escape(key) + r"\b", str(defn))
                        for name, _, defn in idxs)
                ensure(all(unique_keys.values()), "UNIT_A_A5_SCHEMA_DRIFT",
                       3282, [{"unique_keys": unique_keys}], "drift")
                ids = sorted(c["historical_episode_id"] for c in classes)
                keys = sorted(c["classification_key"] for c in classes)
                sk = sorted(a["source_link_key"] for a in sa)
                event_keys = sorted(c["attack_event_key"] for c in classes)
                parent = rows_as_objects(query(cur, r,
                    "SELECT " + ",".join(PARENT_FIELDS) +
                    " FROM public.alert_episodes WHERE legacy_episode_id=ANY(%s)",
                    (ids,)), PARENT_FIELDS)
                classifications = rows_as_objects(query(cur, r,
                    "SELECT " + ",".join(CLASS_FIELDS) +
                    " FROM public.attack_event_classifications WHERE historical_episode_id=ANY(%s) OR classification_key=ANY(%s)",
                    (ids, keys)), CLASS_FIELDS)
                sources = rows_as_objects(query(cur, r,
                    "SELECT " + ",".join("s." + f for f in SOURCE_FIELDS) +
                    ",c.classification_key AS parent_classification_key" +
                    " FROM public.attack_event_sources s LEFT JOIN public.attack_event_classifications c" +
                    " ON c.classification_uid=s.classification_uid WHERE s.source_link_key=ANY(%s)",
                    (sk,)), SOURCE_FIELDS + ["parent_classification_key"])
                events = rows_as_objects(query(cur, r,
                    "SELECT " + ",".join(EVENT_FIELDS) +
                    " FROM public.attack_events WHERE historical_episode_id=ANY(%s) OR attack_event_key=ANY(%s)",
                    (ids, event_keys)), EVENT_FIELDS)
                r["neon"]["snapshot_query_coverage"] = {
                    "parents_rows": len(parent), "classification_rows": len(classifications),
                    "source_rows": len(sources), "event_rows": len(events)}
                r["phase_reached"] = "B_SINGLE_SNAPSHOT_COLLECTED"
                check_parents(r, classes, ca, parent, rebuilt)
                check_classes(r, classes, ca, classifications)
                check_sources(r, sa, sources)
                check_events(r, classes, positive, events)
                p = r["preconditions"]["mutations"]
                p["checked"] = len(ca) + len(sa) + len(ea)
                p["valid"] = (r["preconditions"]["classifications"]["valid"] +
                              r["preconditions"]["sources"]["valid"] +
                              r["preconditions"]["positive_events"]["valid"])
                p["drifted"] = p["checked"] - p["valid"]
                ensure(p == {"checked": 3282, "valid": 3282, "drifted": 0},
                       "UNIT_A_A5_GLOBAL_COMPATIBILITY_DRIFT", p["drifted"], kind="drift")
                ensure(r["preconditions"]["parents"]["unchanged"] == 1713
                       and r["preconditions"]["nonpositive_targets"]["unchanged"] == 1703,
                       "UNIT_A_A5_GLOBAL_COMPATIBILITY_DRIFT", 3282, kind="drift")
                r["phase_reached"] = "G_GLOBAL_FROZEN_MANIFEST_COMPATIBLE"
            finally:
                cur.execute("ROLLBACK")
                r["neon"]["transaction_rolled_back"] = True
    finally:
        conn.close()

def main():
    r = report_new()
    try:
        ca, sa, ea, classes, positive, rebuilt = prepare(r)
        current_state(r, ca, sa, ea, classes, positive, rebuilt)
        final_delta = hashed(rebuilt)
        r["manifest"]["recomputed_delta_sha256_after"] = final_delta
        ensure(final_delta == DELTA_SHA
               and r["manifest"]["recomputed_delta_sha256_before"] == final_delta,
               "UNIT_A_A5_REVALIDATION_INPUT_DRIFT", kind="input")
        r["phase_reached"] = "H_MANIFEST_UNCHANGED_AFTER_SNAPSHOT"
        r["verdict"] = "ATTACK-EVENT EXECUTION UNIT A A5 CURRENT-STATE PRECONDITION REVALIDATION = PASS"
        r["A5_CURRENT_STATE_GATE"] = "PASS"
        r["A5_PRECONDITIONS_CHECKED"] = 3282
        r["A5_PRECONDITIONS_VALID"] = 3282
        r["A5_PRECONDITIONS_DRIFTED"] = 0
        r["A5_READY_FOR_EXPLICIT_AUTHORIZATION"] = "YES"
    except ProofFailure as exc:
        r["first_drift_category"] = exc.category if exc.kind in ("drift", "input") else None
        r["affected_action_count"] = exc.count
        r["bounded_examples"] = exc.examples[:3]
        if exc.kind in ("drift", "input"):
            r["verdict"] = "ATTACK-EVENT EXECUTION UNIT A A5 CURRENT-STATE PRECONDITION REVALIDATION = BLOCKED"
            r["A5_CURRENT_STATE_GATE"] = "FAIL"
        else:
            r["verdict"] = "A5_REVALIDATION_EXECUTION_BLOCKED"
        m = r["preconditions"]["mutations"]
        r["A5_PRECONDITIONS_CHECKED"], r["A5_PRECONDITIONS_VALID"], r["A5_PRECONDITIONS_DRIFTED"] = (
            m["checked"], m["valid"], m["drifted"])
    except Exception as exc:
        r["verdict"] = "A5_REVALIDATION_EXECUTION_BLOCKED"
        r["execution_error_type"] = type(exc).__name__
    finally:
        save(r)
        print("VERDICT=" + r["verdict"])
        print("A5_CURRENT_STATE_GATE=" + r["A5_CURRENT_STATE_GATE"])
        print("A5_MANIFEST_STILL_EXACT=" + r["A5_MANIFEST_STILL_EXACT"])
        print("FIRST_DRIFT_CATEGORY=" + str(r["first_drift_category"]))
        print("NEON_CONNECTIONS=" + str(r["neon"]["connections"]))
        print("NEON_SELECT_COUNT=" + str(r["neon"]["select_count"]))
        print("A5_EXECUTED=NO A5_AUTHORIZED=NO DB_WRITES=0")
        print("ARTIFACT_SHA256=" + sha(OUT.read_bytes()))

if __name__ == "__main__":
    main()
