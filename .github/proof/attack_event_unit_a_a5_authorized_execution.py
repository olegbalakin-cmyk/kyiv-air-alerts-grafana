#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import psycopg
from psycopg.types.json import Jsonb

BASE = "6a47d703a7bd4f236767fc39642c723c01aadf42"
PROOF_BRANCH = "attack-event-unit-a-a5-authorized-execution-2026-10-10"
PROJECT = "green-cake-44216048"
BRANCH = "br-bold-mode-b5rub8pq"
HOST = "ep-still-violet-b5bg6mhp.c-7.us-east-2.aws.neon.tech"
DELTA_SHA = "6070b6dbfc03e16b5236aed5b3cb090fa066100857a9c4f7bed502d6bb294aa3"
PROJECTION_SHA = "7978087ad00f37d0d1eb9f4326a478d5760e79cd7f7a68ae2be39fc5211bffa3"
REVAL_SHA = "dd8a30a764b9050b2024ce9197e144fd9126aa4555c6257534d5e2a0cab12430"
OUT = Path("research/attack_event_execution_unit_a_a5_authorized_execution_2026-10-10.json")
REVAL_HELPER = Path("/tmp/unit_a_a5_reval.py")

class Stop(Exception):
    def __init__(self, code, example=None):
        super().__init__(code)
        self.code = code
        self.example = example

def require(cond, code, example=None):
    if not cond:
        raise Stop(code, example)

def load_reval():
    spec = importlib.util.spec_from_file_location("unit_a_reval", REVAL_HELPER)
    require(spec and spec.loader, "REVALIDATION_HELPER_IMPORT_FAILED")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod

def jwrite(obj):
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")

def origin_payload(kind, artifact_blob):
    run = int(os.environ["GITHUB_RUN_ID"])
    sha = os.environ["GITHUB_SHA"]
    obj = {
        "kind": kind,
        "repository": "olegbalakin-cmyk/kyiv-air-alerts-grafana",
        "ref": PROOF_BRANCH,
        "commit": sha,
        "workflow_run_id": run,
        "accepted_delta_sha256": DELTA_SHA,
        "accepted_projection_sha256": PROJECTION_SHA,
        "accepted_revalidation_sha256": REVAL_SHA,
        "artifact_blob": artifact_blob,
    }
    return obj

def select_rows(cur, mod, classes, source_actions):
    ids = sorted(c["historical_episode_id"] for c in classes)
    keys = sorted(c["classification_key"] for c in classes)
    sk = sorted(a["source_link_key"] for a in source_actions)
    event_keys = sorted(c["attack_event_key"] for c in classes)
    parent = mod.rows_as_objects(cur.execute(
        "SELECT " + ",".join(mod.PARENT_FIELDS) +
        " FROM public.alert_episodes WHERE legacy_episode_id=ANY(%s)", (ids,)
    ).fetchall(), mod.PARENT_FIELDS)
    classifications = mod.rows_as_objects(cur.execute(
        "SELECT " + ",".join(mod.CLASS_FIELDS) +
        " FROM public.attack_event_classifications WHERE historical_episode_id=ANY(%s) OR classification_key=ANY(%s)",
        (ids, keys)
    ).fetchall(), mod.CLASS_FIELDS)
    sources = mod.rows_as_objects(cur.execute(
        "SELECT " + ",".join("s." + f for f in mod.SOURCE_FIELDS) +
        ",c.classification_key AS parent_classification_key" +
        " FROM public.attack_event_sources s LEFT JOIN public.attack_event_classifications c" +
        " ON c.classification_uid=s.classification_uid WHERE s.source_link_key=ANY(%s)",
        (sk,)
    ).fetchall(), mod.SOURCE_FIELDS + ["parent_classification_key"])
    events = mod.rows_as_objects(cur.execute(
        "SELECT " + ",".join(mod.EVENT_FIELDS) +
        " FROM public.attack_events WHERE historical_episode_id=ANY(%s) OR attack_event_key=ANY(%s)",
        (ids, event_keys)
    ).fetchall(), mod.EVENT_FIELDS)
    return parent, classifications, sources, events

def verify_schema(cur, mod):
    tables = list(mod.TABLE_FIELDS)
    rows = cur.execute(
        "SELECT table_name,column_name FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name=ANY(%s)", (tables,)
    ).fetchall()
    available = {}
    for table, col in rows:
        available.setdefault(table, set()).add(col)
    missing = {
        table: sorted(set(fields) - available.get(table, set()))
        for table, fields in mod.TABLE_FIELDS.items()
        if set(fields) - available.get(table, set())
    }
    require(not missing, "UNIT_A_A5_SCHEMA_DRIFT", missing)

def verify_preconditions_in_tx(cur, mod, ca, sa, ea, classes, positive, rebuilt):
    verify_schema(cur, mod)
    parent, classifications, sources, events = select_rows(cur, mod, classes, sa)
    report = mod.report_new()
    report["manifest"]["parent_binding_sha256"] = rebuilt["parent_binding_sha256"]
    mod.check_parents(report, classes, ca, parent, rebuilt)
    mod.check_classes(report, classes, ca, classifications)
    mod.check_sources(report, sa, sources)
    mod.check_events(report, classes, positive, events)
    checked = len(ca) + len(sa) + len(ea)
    valid = (
        report["preconditions"]["classifications"]["valid"] +
        report["preconditions"]["sources"]["valid"] +
        report["preconditions"]["positive_events"]["valid"]
    )
    require(checked == 3282 and valid == 3282, "UNIT_A_A5_IN_TX_PRECONDITION_DRIFT",
            {"checked": checked, "valid": valid})
    require(report["preconditions"]["parents"]["unchanged"] == 1713,
            "UNIT_A_A5_IN_TX_PARENT_DRIFT")
    require(report["preconditions"]["nonpositive_targets"]["unchanged"] == 1703,
            "UNIT_A_A5_IN_TX_EVENT_DRIFT")
    return report["preconditions"]

def insert_classifications(cur, mod, ca):
    uid_by_key = {}
    for action in ca:
        s = action["semantic_row"]
        provenance = origin_payload("unit_a_a5_authorized_execution", action["semantic_row_sha256"])
        provenance_sha = mod.hashed(provenance)
        row = cur.execute(
            """
            INSERT INTO public.attack_event_classifications (
                classification_key_version, classification_key,
                historical_episode_id, city_key, alert_type,
                alert_start_at, alert_end_at, verdict, is_event, positive_tier,
                event_types, qa_reasons_state, qa_reasons, classifier_reason_codes,
                classifier_blob_sha, classifier_methodology_version, normalization_version,
                evidence_set_sha256, review_provenance_sha256, human_review_state,
                review_provenance, originating_frozen_case_id,
                originating_frozen_case_id_state, binding_state, alert_episode_uid,
                origin_repository, origin_ref, origin_commit_sha, origin_artifact_path,
                origin_artifact_blob_sha, origin_target_state_sha256, origin_workflow_run_id,
                classified_at, supersedes_classification_uid, revision_reason,
                correction_provenance, persisted_by_run_id,
                origin_provenance, origin_provenance_sha256
            ) VALUES (
                %s,%s,%s,%s,'AIR',
                %s,%s,%s,%s,%s,
                %s,%s,%s,%s,
                %s,%s,%s,
                %s,%s,%s,
                %s,NULL,
                'NOT_APPLICABLE','BOUND',%s,
                %s,%s,%s,%s,
                %s,%s,%s,
                transaction_timestamp(),NULL,NULL,
                %s,NULL,
                %s,%s
            )
            RETURNING classification_uid
            """,
            (
                s["classification_key_version"], s["classification_key"],
                s["historical_episode_id"], s["city_key"],
                s["alert_start_at"], s["alert_end_at"], s["verdict"],
                s["is_event"], s["positive_tier"], s["event_types"],
                s["qa_reasons_state"], Jsonb(s["qa_reasons"]),
                s["classifier_reason_codes"], s["classifier_blob_sha"],
                s["classifier_methodology_version"], s["normalization_version"],
                s["evidence_set_sha256"], s["review_provenance_sha256"],
                s["human_review_state"], Jsonb(s["review_provenance"]),
                action["alert_episode_uid"],
                "olegbalakin-cmyk/kyiv-air-alerts-grafana", PROOF_BRANCH,
                os.environ["GITHUB_SHA"],
                "research/attack_event_execution_unit_a_a5_current_state_revalidation_2026-10-10.json",
                "6c94245a770ad199beff18e13e2892c59d104108",
                DELTA_SHA, int(os.environ["GITHUB_RUN_ID"]),
                Jsonb({}), Jsonb(provenance), provenance_sha,
            )
        ).fetchone()
        require(row is not None, "CLASSIFICATION_INSERT_RETURNING_MISSING", s["classification_key"])
        uid_by_key[s["classification_key"]] = str(row[0])
    require(len(uid_by_key) == 1713, "CLASSIFICATION_INSERT_COUNT_MISMATCH", len(uid_by_key))
    return uid_by_key

def insert_sources(cur, mod, sa, uid_by_key):
    count = 0
    for action in sa:
        s = action["semantic_source_row"]
        cuid = uid_by_key.get(action["target_classification_key"])
        require(cuid is not None, "SOURCE_TARGET_CLASSIFICATION_UID_MISSING", action["source_link_key"])
        provenance = origin_payload("unit_a_a5_authorized_execution_source", action["semantic_source_row_sha256"])
        provenance["observation_id"] = s["observation_id"]
        provenance_sha = mod.hashed(provenance)
        cur.execute(
            """
            INSERT INTO public.attack_event_sources (
                source_link_key_version, source_link_key, classification_uid,
                observation_id, source_family, source_type, source_type_state,
                source_url, telegram_channel, telegram_message_id,
                source_timestamp, source_timestamp_state, source_timestamp_raw,
                event_timestamp_if_stated, excerpt,
                content_sha256, content_hash_basis,
                observation_classification_outcome, classification_episode_id,
                evidence_payload, retrieval_provenance,
                origin_artifact_path, origin_git_ref, origin_git_blob_sha,
                raw_object_path, origin_provenance, origin_provenance_sha256
            ) VALUES (
                %s,%s,%s,
                %s,%s,%s,%s,
                %s,%s,%s,
                %s,%s,%s,
                %s,%s,
                %s,%s,
                %s,%s,
                %s,%s,
                %s,%s,%s,
                NULL,%s,%s
            )
            """,
            (
                s["source_link_key_version"], s["source_link_key"], cuid,
                s["observation_id"], s["source_family"], s["source_type"], s["source_type_state"],
                s["source_url"], s["telegram_channel"], s["telegram_message_id"],
                s["source_timestamp"], s["source_timestamp_state"], s["source_timestamp_raw"],
                s["event_timestamp_if_stated"], s["excerpt"],
                s["content_sha256"], s["content_hash_basis"],
                s["observation_classification_outcome"], s["classification_episode_id"],
                Jsonb(s["evidence_payload"]), Jsonb(s["retrieval_provenance"]),
                "research/attack_event_execution_unit_a_a5_current_state_revalidation_2026-10-10.json",
                PROOF_BRANCH, "6c94245a770ad199beff18e13e2892c59d104108",
                Jsonb(provenance), provenance_sha,
            )
        )
        require(cur.rowcount == 1, "SOURCE_INSERT_COUNT_MISMATCH", action["source_link_key"])
        count += 1
    require(count == 1559, "SOURCE_INSERT_TOTAL_MISMATCH", count)
    return count

def insert_events(cur, ea, ca, uid_by_key):
    by_key = {a["classification_key"]: a for a in ca}
    count = 0
    for action in ea:
        cact = by_key[action["desired_classification_key"]]
        s = cact["semantic_row"]
        cuid = uid_by_key[action["desired_classification_key"]]
        provenance = {
            "kind": "UNIT_A_A5_AUTHORIZED_INITIAL_EVENT",
            "accepted_delta_sha256": DELTA_SHA,
            "workflow_run_id": int(os.environ["GITHUB_RUN_ID"]),
        }
        cur.execute(
            """
            INSERT INTO public.attack_events (
                attack_event_key_version, attack_event_key, event_grain,
                historical_episode_id, city_key, alert_type,
                alert_start_at, alert_end_at, event_status,
                current_classification_uid, binding_state, alert_episode_uid,
                correction_provenance, created_by_run_id, updated_by_run_id
            ) VALUES (
                'attack-event-key-v1',%s,'HISTORICAL_ALERT_EPISODE',
                %s,%s,'AIR',%s,%s,'ACTIVE',
                %s,'BOUND',%s,%s,NULL,NULL
            )
            """,
            (
                action["attack_event_key"], action["historical_episode_id"], action["city_key"],
                s["alert_start_at"], s["alert_end_at"], cuid, cact["alert_episode_uid"],
                Jsonb(provenance),
            )
        )
        require(cur.rowcount == 1, "EVENT_INSERT_COUNT_MISMATCH", action["attack_event_key"])
        count += 1
    require(count == 10, "EVENT_INSERT_TOTAL_MISMATCH", count)
    return count

def semantic_readback(cur, mod, ca, sa, ea, classes):
    parent, classifications, sources, events = select_rows(cur, mod, classes, sa)
    cby = {str(r["classification_key"]): r for r in classifications}
    sby = {str(r["source_link_key"]): r for r in sources}
    eby = {str(r["attack_event_key"]): r for r in events}
    mismatches = []
    for a in ca:
        got = cby.get(a["classification_key"])
        if got is None:
            mismatches.append({"type":"classification_missing","key":a["classification_key"]})
            continue
        for f in mod.CLASS_FIELDS:
            if f == "classification_uid":
                continue
            if mod.normalize(got.get(f)) != mod.normalize(a["semantic_row"].get(f)):
                mismatches.append({"type":"classification_field","key":a["classification_key"],"field":f})
                break
        if str(got["alert_episode_uid"]) != str(a["alert_episode_uid"]):
            mismatches.append({"type":"classification_parent","key":a["classification_key"]})
    for a in sa:
        got = sby.get(a["source_link_key"])
        if got is None:
            mismatches.append({"type":"source_missing","key":a["source_link_key"]})
            continue
        for f in mod.SOURCE_FIELDS:
            if f == "classification_uid":
                continue
            if mod.normalize(got.get(f)) != mod.normalize(a["semantic_source_row"].get(f)):
                mismatches.append({"type":"source_field","key":a["source_link_key"],"field":f})
                break
        if str(got.get("parent_classification_key")) != str(a["target_classification_key"]):
            mismatches.append({"type":"source_parent","key":a["source_link_key"]})
    for a in ea:
        got = eby.get(a["attack_event_key"])
        if got is None:
            mismatches.append({"type":"event_missing","key":a["attack_event_key"]})
            continue
        if str(got["historical_episode_id"]) != str(a["historical_episode_id"]) or str(got["event_status"]) != "ACTIVE":
            mismatches.append({"type":"event_semantic","key":a["attack_event_key"]})
    return {
        "classification_rows": len(classifications),
        "source_rows": len(sources),
        "event_rows": len(events),
        "parent_rows": len(parent),
        "mismatch_count": len(mismatches),
        "bounded_mismatches": mismatches[:3],
    }

def post_commit_idempotency(conn, mod, ca, sa, ea, classes):
    conn.execute("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY")
    try:
        rb = semantic_readback(conn.cursor(), mod, ca, sa, ea, classes)
        require(rb["classification_rows"] == 1713, "POSTCOMMIT_CLASSIFICATION_COUNT_MISMATCH", rb)
        require(rb["source_rows"] == 1559, "POSTCOMMIT_SOURCE_COUNT_MISMATCH", rb)
        require(rb["event_rows"] == 10, "POSTCOMMIT_EVENT_COUNT_MISMATCH", rb)
        require(rb["mismatch_count"] == 0, "POSTCOMMIT_SEMANTIC_MISMATCH", rb["bounded_mismatches"])
        return rb
    finally:
        conn.execute("ROLLBACK")

def main():
    report = {
        "schema_version": 1,
        "kind": "unit_a_a5_authorized_execution",
        "authorization": {
            "explicit": True,
            "basis": "USER_EXPLICIT_AUTHORIZATION_IN_ACTIVE_COORDINATION_SESSION",
            "coordination_main": BASE,
        },
        "A5_AUTHORIZED": "YES",
        "A5_EXECUTED": "NO",
        "A5_EXECUTION_GATE": "NOT_RUN",
        "accepted_delta_sha256": DELTA_SHA,
        "accepted_projection_sha256": PROJECTION_SHA,
        "accepted_distribution": {"INSERT_INITIAL":1713,"INSERT_SOURCE_LINK":1559,"INSERT_EVENT":10},
        "transaction": {},
        "preconditions": {},
        "writes": {"classifications":0,"sources":0,"events":0,"total":0},
        "precommit_readback": {},
        "postcommit_readback": {},
        "idempotency": {"future_mutations": None},
        "first_failure": None,
        "bounded_example": None,
        "production_mutation": "NO",
        "site_prod_mutation": "NO",
    }
    committed = False
    conn = None
    try:
        require(os.environ.get("UNIT_A_A5_EXPLICIT_AUTHORIZATION") == "YES",
                "EXPLICIT_AUTHORIZATION_ENV_MISSING")
        require(os.environ.get("GITHUB_REF_NAME") == PROOF_BRANCH, "WRONG_PROOF_BRANCH")
        require(os.environ.get("PHASE1_PROD_SHADOW_BRANCH_ID") == BRANCH,
                "SHADOW_BRANCH_VARIABLE_MISMATCH")
        url = os.environ.get("PHASE1_PROD_SHADOW_DATABASE_URL")
        require(bool(url), "SHADOW_DATABASE_SECRET_UNAVAILABLE")
        require(urlparse(url).hostname == HOST, "SHADOW_DATABASE_HOST_NOT_APPROVED")

        mod = load_reval()
        base_report = mod.report_new()
        actual_ref = os.environ.get("GITHUB_REF_NAME")
        try:
            os.environ["GITHUB_REF_NAME"] = mod.PROOF_BRANCH
            ca, sa, ea, classes, positive, rebuilt = mod.prepare(base_report)
        finally:
            if actual_ref is None:
                os.environ.pop("GITHUB_REF_NAME", None)
            else:
                os.environ["GITHUB_REF_NAME"] = actual_ref
        require(mod.hashed(rebuilt) == DELTA_SHA, "FROZEN_DELTA_SHA_MISMATCH")
        require(base_report["manifest"]["recomputed_projection_sha256"] == PROJECTION_SHA,
                "FROZEN_PROJECTION_SHA_MISMATCH")
        require(len(ca)==1713 and len(sa)==1559 and len(ea)==10, "FROZEN_ACTION_COUNT_MISMATCH")

        conn = psycopg.connect(url, autocommit=True, connect_timeout=20,
                               options="-c statement_timeout=180000")
        with conn.cursor() as cur:
            cur.execute("BEGIN ISOLATION LEVEL SERIALIZABLE READ WRITE")
            try:
                state = cur.execute(
                    "SELECT current_setting('transaction_isolation'), "
                    "current_setting('transaction_read_only'), current_database()"
                ).fetchone()
                report["transaction"] = {
                    "isolation": state[0], "read_only": state[1] == "on",
                    "database": state[2], "branch": BRANCH, "project": PROJECT,
                    "advisory_lock": False, "committed": False, "rolled_back": False,
                }
                require(state[0] == "serializable" and state[1] == "off",
                        "WRITE_TRANSACTION_NOT_SERIALIZABLE_READ_WRITE", state)
                cur.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                            ("UNIT_A_A5|" + DELTA_SHA,))
                report["transaction"]["advisory_lock"] = True

                pre = verify_preconditions_in_tx(cur, mod, ca, sa, ea, classes, positive, rebuilt)
                report["preconditions"] = pre

                uid_by_key = insert_classifications(cur, mod, ca)
                report["writes"]["classifications"] = 1713
                report["writes"]["sources"] = insert_sources(cur, mod, sa, uid_by_key)
                report["writes"]["events"] = insert_events(cur, ea, ca, uid_by_key)
                report["writes"]["total"] = sum(report["writes"].values())
                require(report["writes"]["total"] == 3282, "WRITE_TOTAL_MISMATCH", report["writes"])

                rb = semantic_readback(cur, mod, ca, sa, ea, classes)
                report["precommit_readback"] = rb
                require(rb["classification_rows"] == 1713 and rb["source_rows"] == 1559
                        and rb["event_rows"] == 10 and rb["mismatch_count"] == 0,
                        "PRECOMMIT_READBACK_FAILED", rb)

                cur.execute("COMMIT")
                committed = True
                report["transaction"]["committed"] = True
            except Exception:
                if not committed:
                    cur.execute("ROLLBACK")
                    report["transaction"]["rolled_back"] = True
                raise

        report["postcommit_readback"] = post_commit_idempotency(conn, mod, ca, sa, ea, classes)
        report["idempotency"]["future_mutations"] = 0
        report["A5_EXECUTED"] = "YES"
        report["A5_EXECUTION_GATE"] = "PASS"
        report["verdict"] = "ATTACK-EVENT EXECUTION UNIT A A5 ATOMIC PERSISTENCE = COMMITTED"
    except Exception as exc:
        report["first_failure"] = getattr(exc, "code", getattr(exc, "category", type(exc).__name__))
        report["bounded_example"] = getattr(exc, "example", None)
        if committed:
            report["verdict"] = "A5_COMMITTED_POSTCOMMIT_PROOF_INCOMPLETE"
            report["A5_EXECUTED"] = "YES"
            report["A5_EXECUTION_GATE"] = "POSTCOMMIT_PROOF_INCOMPLETE"
        else:
            report["verdict"] = "ATTACK-EVENT EXECUTION UNIT A A5 ATOMIC PERSISTENCE = BLOCKED"
            report["A5_EXECUTION_GATE"] = "FAIL"
    finally:
        if conn is not None:
            conn.close()
        jwrite(report)
        print("VERDICT=" + report["verdict"])
        print("A5_AUTHORIZED=" + report["A5_AUTHORIZED"])
        print("A5_EXECUTED=" + report["A5_EXECUTED"])
        print("A5_EXECUTION_GATE=" + report["A5_EXECUTION_GATE"])
        print("WRITES=" + json.dumps(report["writes"], sort_keys=True))
        print("FUTURE_MUTATIONS=" + str(report["idempotency"]["future_mutations"]))

if __name__ == "__main__":
    main()
