#!/usr/bin/env python3
"""H2: executable PG18 mutation controls and unmodified operational writer integration.
Synthetic disposable databases only. A passing harness never implies Neon parity.
"""
from __future__ import annotations
import hashlib
import importlib.util
import inspect
import json
import os
from pathlib import Path
import subprocess
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

ROOT = Path(__file__).resolve().parent
BASE = ROOT.parent / "h2_pg18_revision_invariant_hardening_2026-10-19"
COPY = os.environ.get("H2_COPY", "A")
OUTPUT = Path(os.environ.get("H2_REPORT", "/tmp/h2_offline_writer_report.json"))
OWNER = os.environ["H2_PG18_OWNER_DSN"]
WRITER = os.environ["H2_PG18_WRITER_DSN"]
WRITER_BLOB = "0118ca9e5f1308173e657257f1b49fe91cc19fe1"
RESEARCH_WRITER_BLOB = "2a5354aa4ad2bc67893ffa40589024ecb84fa15e"
INPUT_BLOBS = {
    "observed_partial_schema.sql": "09f9c5a2f0c4eeddaba63e7c9c5834cce85f7ab3",
    "001_revision_invariants.sql": "339b9b44a90f8b5e8ba216576f63daac393a5eb3",
    "002_synthetic_writer_grants.sql": "b4c1be395b0cfdc16086729ad903ef10e00b1fb0",
}
TABLES = (
    ("attack_event_classifications", "classification_uid"),
    ("h2_classification_heads", "city_key,historical_episode_id"),
    ("attack_events", "attack_event_uid"),
    ("attack_event_sources", "attack_event_source_uid"),
    ("alert_episodes", "episode_uid"),
)
START = "2026-01-01T01:00:00+00:00"
END = "2026-01-01T02:00:00+00:00"
report = {
    "schema": "h2-offline-mutation-operational-v1",
    "copy": COPY,
    "test_commit": os.environ.get("GITHUB_SHA"),
    "source_ref": "multicity-wip-2026-09-16",
    "operational_source_commit": "b05d1ea61aabb7d9d476a88778a0599103407d94",
    "operational_writer_git_blob": WRITER_BLOB,
    "research_writer_git_blob": RESEARCH_WRITER_BLOB,
    "input_git_blobs": INPUT_BLOBS,
    "scope": "two fresh PostgreSQL 18.6 containers, synthetic only; no Neon SQL",
    "assertions": [], "cases": [], "traces": [], "unexpected": [],
}

def gitblob(path):
    raw = Path(path).read_bytes()
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()

def check(name, expected, observed, *, context=""):
    passed = expected == observed
    report["assertions"].append({
        "name": name, "pass": passed, "expected": expected,
        "observed": observed, "context": context,
    })
    return passed

def trace(name, **data):
    report["traces"].append({"step": name, **data})

def query(c, statement, args=()):
    with c.cursor() as cur:
        cur.execute(statement, args)
        return cur.fetchall() if cur.description else []

def execute(c, statement, args=()):
    return query(c, statement, args)

def try_sql(c, statement, args=(), allowed_errors=()):
    try:
        with c.transaction():
            rows = query(c, statement, args)
        return {"outcome": "committed", "rows": len(rows)}
    except psycopg.Error as exc:
        return {
            "outcome": "rejected", "sqlstate": exc.sqlstate,
            "expected_error": exc.sqlstate in allowed_errors,
            "error_class": type(exc).__name__,
        }
    except Exception as exc:
        return {"outcome": "unexpected", "type": type(exc).__name__, "message": str(exc)[:180]}

def rejection(name, c, statement, allowed=("42501",), args=()):
    before = fingerprint(c)
    observed = try_sql(c, statement, args, allowed)
    after = fingerprint(c)
    trace(name, result=observed, fingerprint_before=before, fingerprint_after=after)
    check(name + ".sql_error", True, observed.get("outcome") == "rejected" and observed.get("sqlstate") in allowed)
    check(name + ".no_persisted_mutation", before, after)
    return observed

def connect(dsn, dbname=None, autocommit=True):
    options = conninfo_to_dict(dsn)
    if dbname:
        options["dbname"] = dbname
    return psycopg.connect(make_conninfo(**options), autocommit=autocommit,
                           connect_timeout=8)

def fingerprint(c):
    # Stable complete-row, table-ordered SHA-256; compare from independent sessions.
    values = {}
    for table, key in TABLES:
        values[table] = [r[0] for r in query(
            c, "SELECT to_jsonb(t)::text FROM public." + table + " t ORDER BY " + key
        )]
    payload = json.dumps(values, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()

def stats(c, city="kyiv", episode="0"*24):
    rows = query(c, """
        SELECT classification_uid::text, supersedes_classification_uid::text
        FROM public.attack_event_classifications
        WHERE city_key=%s AND historical_episode_id=%s
        ORDER BY created_at, classification_uid
    """, (city, episode))
    tips = [r[0] for r in rows if r[0] not in {a[1] for a in rows if a[1]}]
    head = query(c, """
        SELECT tip_classification_uid::text
        FROM public.h2_classification_heads
        WHERE city_key=%s AND historical_episode_id=%s
    """, (city, episode))
    return {"count": len(rows), "tips": sorted(tips),
            "head": head[0][0] if len(head) == 1 else None,
            "head_count": len(head), "revisions": rows}

def integrity_anomalies(c, city="kyiv", episode="0"*24):
    s = stats(c, city, episode)
    errors = []
    if len(s["tips"]) != 1: errors.append("MULTIPLE_OR_NO_TIPS")
    if s["head_count"] != 1: errors.append("MISSING_OR_MULTIPLE_HEADS")
    if len(s["tips"]) == 1 and s["head"] != s["tips"][0]:
        errors.append("HEAD_DIFFERS_FROM_CLASSIFICATION_TIP")
    children = [r[1] for r in s["revisions"] if r[1]]
    if len(children) != len(set(children)): errors.append("DUPLICATE_SUCCESSOR")
    return errors

def new_database(label):
    name = "h2_" + COPY.lower() + "_" + label
    with connect(OWNER) as c:
        c.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    for file in ("observed_partial_schema.sql", "001_revision_invariants.sql", "002_synthetic_writer_grants.sql"):
        env = dict(os.environ, PGPASSWORD="synthetic_only")
        cp = subprocess.run(
            ["psql", "-X", "-v", "ON_ERROR_STOP=1", "-h", "127.0.0.1",
             "-U", "h2_local", "-d", name, "-q", "-f", str(BASE / file)],
            capture_output=True, text=True, env=env, timeout=90)
        if cp.returncode:
            raise RuntimeError("fixture SQL failed in " + label + " for " + file
                               + ": " + cp.stderr[-900:])
    trace("environment", name=label, dbname=name, schema="synthetic-frozen-partial")
    return name

def mkrow(city, episode, tag, predecessor=None):
    key = hashlib.sha256(f"{city}:{episode}:{tag}".encode()).hexdigest()
    return {
        "classification_key_version": "attack-event-classification-key-v2",
        "classification_key": key, "historical_episode_id": episode,
        "city_key": city, "alert_type": "AIR",
        "alert_start_at": START, "alert_end_at": END,
        "verdict": "NO_CONFIRMED_EVENT", "is_event": False,
        "qa_reasons_state": "MATERIALIZED", "qa_reasons": "[]",
        "classifier_blob_sha": "a"*40,
        "classifier_methodology_version": "synthetic-offline",
        "normalization_version": "synthetic-offline",
        "evidence_set_sha256": "b"*64,
        "binding_state": "UNBOUND", "origin_repository": "synthetic-offline",
        "origin_provenance": '{"kind":"synthetic"}',
        "origin_provenance_sha256": "c"*64,
        "originating_frozen_case_id_state": "NOT_APPLICABLE",
        "supersedes_classification_uid": predecessor,
    }

def raw_insert(c, row):
    cols = list(row)
    statement = sql.SQL("INSERT INTO public.attack_event_classifications ({}) VALUES ({}) RETURNING classification_uid::text").format(
        sql.SQL(",").join(map(sql.Identifier, cols)),
        sql.SQL(",").join(sql.Placeholder() for _ in cols))
    return query(c, statement, tuple(row.values()))[0][0]

def case_a1():
    db = new_database("a1")
    with connect(WRITER, db) as w, connect(OWNER, db) as owner:
        check("A1.restricted_role", "h2_app_writer_test", query(w, "SELECT current_user")[0][0])
        check("A1.owner_role", "h2_local", query(owner, "SELECT current_user")[0][0])
        a = raw_insert(w, mkrow("kyiv", "0"*24, "root"))
        b = raw_insert(w, mkrow("kyiv", "0"*24, "legitimate", a))
        check("A1.append_and_head", b, stats(w)["head"])
        before = fingerprint(w)
        reject = try_sql(w, "INSERT INTO public.attack_event_classifications "
            "(classification_key_version,classification_key,historical_episode_id,city_key,alert_type,"
            "alert_start_at,alert_end_at,verdict,is_event,qa_reasons_state,qa_reasons,classifier_blob_sha,"
            "classifier_methodology_version,normalization_version,evidence_set_sha256,binding_state,"
            "origin_repository,origin_provenance,origin_provenance_sha256,originating_frozen_case_id_state,"
            "supersedes_classification_uid) "
            "SELECT classification_key_version,%s,historical_episode_id,city_key,alert_type,"
            "alert_start_at,alert_end_at,verdict,is_event,qa_reasons_state,qa_reasons,classifier_blob_sha,"
            "classifier_methodology_version,normalization_version,evidence_set_sha256,binding_state,"
            "origin_repository,origin_provenance,origin_provenance_sha256,originating_frozen_case_id_state,%s "
            "FROM public.attack_event_classifications WHERE classification_uid=%s",
            (hashlib.sha256(b"a1-stale").hexdigest(), a, b), ("23505", "P0001"))
        trace("A1.duplicate_and_stale", sql_result=reject, fingerprint=before)
        check("A1.reject_stale_or_duplicate", True, reject["outcome"] == "rejected"
              and reject.get("sqlstate") in ("23505", "P0001"))
        check("A1.after_failed_insert_unchanged", before, fingerprint(w))
        check("A1.one_tip", [], integrity_anomalies(w))
        check("A1.independent_readback", fingerprint(w), fingerprint(owner))
        rejection("A1.immutable_history", w,
                  "UPDATE public.attack_event_classifications SET origin_repository='tampered'")
    report["cases"].append({"id": "A1", "kind": "protected_baseline", "result": "EXECUTED"})

def race_raw(dsn, db, parent):
    barrier = threading.Barrier(2)
    outcomes = []
    lock = threading.Lock()
    def worker(i):
        with connect(dsn, db) as cx:
            barrier.wait(timeout=15)
            try:
                uid = raw_insert(cx, mkrow("kyiv", "0"*24, "race-" + str(i), parent))
                val = {"session": i, "status": "committed", "uid": uid}
            except psycopg.Error as exc:
                val = {"session": i, "status": "rejected", "sqlstate": exc.sqlstate}
            with lock: outcomes.append(val)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker, i) for i in (1,2)]
        for f in futures: f.result(timeout=35)
    return sorted(outcomes, key=lambda x: x["session"])

def case_a2():
    db = new_database("a2")
    with connect(WRITER, db) as w, connect(OWNER, db) as owner:
        a = raw_insert(w, mkrow("kyiv", "0"*24, "root"))
        execute(owner, "DROP INDEX public.h2_classification_one_successor_uidx")
        check("A2.index_actually_removed", False, bool(query(owner, """
            SELECT 1 FROM pg_indexes WHERE indexname='h2_classification_one_successor_uidx'""")))
        before = fingerprint(owner)
        outcome = race_raw(WRITER, db, a)
        with connect(OWNER, db) as readback:
            s = stats(readback)
            trace("A2.race_without_index", outcomes=outcome, before=before,
                  after=fingerprint(readback), state=s)
            check("A2.CAS_rejects_one", ["committed", "rejected"],
                  sorted(o["status"] for o in outcome))
            check("A2.rejection_is_CAS_not_unique", ["P0001"],
                  [o.get("sqlstate") for o in outcome if o["status"] == "rejected"])
            check("A2.one_tip_without_index", [], integrity_anomalies(readback))
            check("A2.one_committed_successor", 2, s["count"])
    report["cases"].append({"id":"A2", "kind":"index_disabled_CAS_retained", "result":"EXECUTED"})

def case_a3():
    db = new_database("a3")
    with connect(WRITER, db) as w, connect(OWNER, db) as own:
        a = raw_insert(w, mkrow("kyiv", "0"*24, "root"))
        execute(own, "ALTER TABLE public.attack_event_classifications DISABLE TRIGGER h2_revision_head_after_insert")
        check("A3.trigger_disabled", "D", query(own, """
            SELECT tgenabled FROM pg_trigger WHERE tgname='h2_revision_head_after_insert'""")[0][0])
        b = raw_insert(w, mkrow("kyiv", "0"*24, "child", a))
        with connect(OWNER, db) as r:
            anomalies = integrity_anomalies(r)
            trace("A3.disabled_trigger_committed", before_tip=a, committed_child=b,
                  fingerprint=fingerprint(r), anomalies=anomalies, state=stats(r))
            check("A3.detect_head_mismatch", True,
                  "HEAD_DIFFERS_FROM_CLASSIFICATION_TIP" in anomalies)
            check("A3.index_still_enabled", True, bool(query(r, """
                SELECT 1 FROM pg_indexes WHERE indexname='h2_classification_one_successor_uidx'""")))
    report["cases"].append({"id":"A3", "kind":"trigger_disabled_index_retained", "result":"EXECUTED"})

def case_a4():
    db = new_database("a4")
    with connect(WRITER, db) as w, connect(OWNER, db) as own:
        a = raw_insert(w, mkrow("kyiv", "0"*24, "root"))
        execute(own, "ALTER TABLE public.attack_event_classifications DISABLE TRIGGER h2_revision_head_after_insert")
        execute(own, "DROP INDEX public.h2_classification_one_successor_uidx")
        b = raw_insert(w, mkrow("kyiv", "0"*24, "child-one", a))
        d = raw_insert(w, mkrow("kyiv", "0"*24, "child-two", a))
        with connect(OWNER, db) as r:
            anomalies = integrity_anomalies(r)
            trace("A4.both_disabled_committed", base=a, committed=[b,d],
                  fingerprint=fingerprint(r), anomalies=anomalies, state=stats(r))
            check("A4.two_tips_detected", True, "MULTIPLE_OR_NO_TIPS" in anomalies)
            check("A4.duplicate_successor_detected", True, "DUPLICATE_SUCCESSOR" in anomalies)
            check("A4.head_stale_detected", a, stats(r)["head"])
    report["cases"].append({"id":"A4", "kind":"index_and_trigger_disabled", "result":"EXECUTED"})

def case_a5():
    db = new_database("a5")
    with connect(WRITER, db) as w, connect(OWNER, db) as own:
        uid = raw_insert(w, mkrow("kyiv", "0"*24, "root"))
        forbidden = [
            ("update_history", "UPDATE public.attack_event_classifications SET origin_repository='not-allowed'"),
            ("delete_history", "DELETE FROM public.attack_event_classifications"),
            ("truncate_history", "TRUNCATE public.attack_event_classifications CASCADE"),
            ("alter_table", "ALTER TABLE public.attack_event_classifications ADD COLUMN unauthorized text"),
            ("disable_trigger", "ALTER TABLE public.attack_event_classifications DISABLE TRIGGER h2_revision_head_after_insert"),
            ("drop_index", "DROP INDEX public.h2_classification_one_successor_uidx"),
            ("change_head", "UPDATE public.h2_classification_heads SET changed_at=now()"),
            ("alter_role", "ALTER ROLE h2_app_writer_test CREATEROLE"),
            ("grant_owner", "GRANT h2_local TO h2_app_writer_test"),
        ]
        for label, statement in forbidden:
            rejection("A5.restricted." + label, w, statement, ("42501", "0LP01"))
        grant = try_sql(w, "GRANT UPDATE ON public.attack_event_classifications TO h2_app_writer_test",
                        allowed_errors=("42501",))
        priv = query(w, """SELECT has_table_privilege(current_user,
            'public.attack_event_classifications', 'UPDATE')""")[0][0]
        trace("A5.restricted.GRANT", result=grant, update_privilege=priv)
        check("A5.no_self_granted_update", False, priv)
        check("A5.no_owner_membership", False,
              query(w, "SELECT pg_has_role(current_user, 'h2_local', 'MEMBER')")[0][0])
        # Actual SQL from table OWNER: demonstrate the scope limitation of ACL.
        before = fingerprint(own)
        execute(own, "UPDATE public.attack_event_classifications "
                "SET origin_repository='owner_changed_it' WHERE classification_uid=%s", (uid,))
        after = fingerprint(own)
        check("A5.owner_update_executed", True, before != after)
        check("A5.owner_historical_column_changed", "owner_changed_it",
              query(own, "SELECT origin_repository FROM public.attack_event_classifications "
                    "WHERE classification_uid=%s", (uid,))[0][0])
        execute(own, "ALTER TABLE public.attack_event_classifications DISABLE TRIGGER h2_revision_head_after_insert")
        check("A5.owner_trigger_disable_executed", "D", query(own,
              "SELECT tgenabled FROM pg_trigger WHERE tgname='h2_revision_head_after_insert'")[0][0])
        execute(own, "ALTER TABLE public.attack_event_classifications ADD COLUMN owner_can_alter text")
        check("A5.owner_DDL_executed", True, bool(query(own,
              "SELECT 1 FROM information_schema.columns WHERE table_name="
              "'attack_event_classifications' AND column_name='owner_can_alter'")))
        execute(own, "DELETE FROM public.h2_classification_heads")
        execute(own, "DELETE FROM public.attack_event_classifications WHERE classification_uid=%s", (uid,))
        check("A5.owner_delete_executed", 0, query(own, "SELECT count(*) "
              "FROM public.attack_event_classifications")[0][0])
        raw_insert(w, mkrow("kyiv", "0"*24, "owner-truncate-probe"))
        execute(own, "TRUNCATE public.attack_event_classifications CASCADE")
        check("A5.owner_truncate_executed", 0, query(own, "SELECT count(*) "
              "FROM public.attack_event_classifications")[0][0])
        trace("A5.owner_bypass_executed", first_fingerprint=before,
              after_update_fingerprint=after, final_fingerprint=fingerprint(own),
              column_update=True, trigger_disabled=True, DDL=True,
              delete=True, truncate_cascade=True)
    report["cases"].append({"id":"A5", "kind":"owner_bypass_and_nonowner_denials", "result":"EXECUTED"})

def load_operational():
    src = ROOT / "operational_writer_snapshot.py"
    check("operational_blob_exact", WRITER_BLOB, gitblob(src))
    spec = importlib.util.spec_from_file_location("h2_pinned_operational_writer", src)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def seed_parent(db, city="kyiv", episode="0"*24):
    with connect(OWNER, db) as o:
        rid = query(o, "INSERT INTO public.ingestion_runs "
             "(run_kind,schema_version,status,started_at) "
             "VALUES ('synthetic_test','synthetic-only','running',now()) RETURNING run_id")[0][0]
        query(o, """INSERT INTO public.alert_episodes
            (legacy_episode_id,city_key,alert_type,start_at,end_at,episode_state,
             canonicalization_version,created_by_run_id,updated_by_run_id)
            VALUES (%s,%s,'AIR',%s,%s,'closed','alert-canonicalization-v1',%s,%s)
            RETURNING episode_uid""", (episode, city, START, END, rid, rid))

def record(op, city="kyiv", episode="0"*24, mode="strict", tag="one"):
    item = {"episode_id": episode, "city_key": city,
            "alert_start": START, "alert_end": END}
    queue = []
    if mode != "none":
        queue = [{
            "city_key": city, "candidate_id": "synthetic-" + tag,
            "status": {"strict":"approved_strict", "sensitivity":"approved_sensitivity",
                       "review":"needs_review"}[mode],
            "matched_episode_id": episode, "source": "SYNTHETIC_OFFLINE",
            "publisher_url":"example.invalid", "url": "https://example.invalid/" + tag,
            "title": "synthetic " + tag,
            "classification_evidence": {"classification_episode_id": episode},
        }]
    origin = {
        "ref": "multicity-wip-2026-09-16",
        "commit": "b05d1ea61aabb7d9d476a88778a0599103407d94",
        "run_id": None, "monitor_blob": None,
        "origin_provenance": {
            "kind": op.ORIGIN_KIND, "repository": "synthetic-offline",
            "ref": "multicity-wip-2026-09-16",
            "commit": "b05d1ea61aabb7d9d476a88778a0599103407d94",
            "monitor_path": op.MONITOR_RELATIVE_PATH, "monitor_blob": None,
        },
    }
    origin["origin_provenance_sha256"] = op.canonical_sha256(origin["origin_provenance"])
    return op.build_episode_classification(item, queue, origin=origin), item, queue

def case_operational(op):
    db = new_database("oper")
    seed_parent(db)
    first, episode, queue = record(op, tag="first")
    second, _, _ = record(op, mode="none", tag="second")
    with connect(WRITER, db) as w:
        before = fingerprint(w)
        receipt = op.persist_episode_classification(w, first)
        with connect(OWNER, db) as independently:
            after = fingerprint(independently)
            check("OP.initial_classification_durable", 1, stats(independently)["count"])
            check("OP.initial_event_durable", 1,
                  query(independently, "SELECT count(*) FROM public.attack_events")[0][0])
            check("OP.source_link_durable", 1,
                  query(independently, "SELECT count(*) FROM public.attack_event_sources")[0][0])
            check("OP.initial_independent_changed", True, before != after)
            trace("OP.initial", receipt=receipt, before=before, after=after)
        repeated = op.persist_episode_classification(w, first)
        check("OP.same_classification_idempotent", False, repeated["classification_inserted"])
        check("OP.no_duplicate_source_link", 1,
              query(w,"SELECT count(*) FROM public.attack_event_sources")[0][0])
        # Operational fault injection is built into the original writer, not a monkey patch.
        unchanged = fingerprint(w)
        for fault in ("classification", "event"):
            try:
                op.persist_episode_classification(w, second, fault_after=fault)
                observed = "RETURNED"
            except RuntimeError as exc:
                observed = str(exc)
            with connect(OWNER, db) as independently:
                check("OP.fault_" + fault + ".expected", True,
                      observed.startswith("FORCED_PERSISTENCE_FAILURE_AFTER_"))
                check("OP.fault_" + fault + ".rolled_back", unchanged,
                      fingerprint(independently))
                trace("OP.fault_"+fault, observed=observed, fingerprint=unchanged)
        changed = op.persist_episode_classification(w, second)
        with connect(OWNER, db) as r:
            check("OP.revision_inserted", True, changed["revision_inserted"])
            check("OP.event_updated", True, changed["event_updated"])
            check("OP.withdrawn_after_revision", "WITHDRAWN",
                  query(r,"SELECT event_status FROM public.attack_events")[0][0])
            check("OP.one_tip_after_revision", [], integrity_anomalies(r))
            check("OP.history_immutable", first["classification_key"],
                  query(r, """SELECT classification_key FROM public.attack_event_classifications
                     WHERE supersedes_classification_uid IS NULL""")[0][0])
            trace("OP.revision", receipt=changed, after=fingerprint(r))
        try:
            op.persist_episode_classification(w, first)
            stale = "RETURNED"
        except op.PersistenceContractError as exc:
            stale = type(exc).__name__ + ":" + str(exc)
        check("OP.old_existing_classification_rejected", True,
              stale.startswith("PersistenceContractError:"))
        trace("OP.old_existing_key", result=stale)
        sig = inspect.signature(op.persist_episode_classification)
        batch_sig = inspect.signature(op.persist_due_episode_classifications)
        check("OP.expected_tip_parameter_missing", False,
              "expected_current_tip" in sig.parameters or "expected_tips" in sig.parameters)
        check("OP.batch_expected_tips_missing", False, "expected_tips" in batch_sig.parameters)
        # Explicit stale-tip assertion is impossible through the real writer API.
        try:
            op.persist_episode_classification(w, second, expected_current_tip="stale")
            unsupported = False
        except TypeError:
            unsupported = True
        check("OP.explicit_expected_tip_unsupported", True, unsupported)
        trace("OP.expected_tip_authority", signature=str(sig),
              batch_signature=str(batch_sig), explicit_expected_tip_rejected=unsupported)
    seed_parent(db, "lviv", "1"*24)
    lviv, _, _ = record(op, "lviv", "1"*24, mode="none")
    with connect(WRITER, db) as w:
        op.persist_episode_classification(w, lviv)
        lv_original = stats(w,"lviv","1"*24)
        at_before = query(w, "SELECT classification_key,origin_repository "
                   "FROM public.attack_event_classifications "
                   "WHERE city_key='lviv'")
    start_tip = stats(connect_temp := connect(OWNER, db))["head"]
    connect_temp.close()
    one, _, _ = record(op, mode="strict", tag="race-one")
    two, _, _ = record(op, mode="sensitivity", tag="race-two")
    barrier = threading.Barrier(2)
    results = []
    lock = threading.Lock()
    def contender(i, rec):
        with connect(WRITER, db) as cx:
            barrier.wait(timeout=15)
            try:
                val = op.persist_episode_classification(cx, rec)
                outcome = {"session":i, "status":"committed", "classification_uid":val["classification_uid"]}
            except (psycopg.Error, op.PersistenceContractError) as exc:
                outcome = {"session":i, "status":"rejected",
                           "error_class":type(exc).__name__,
                           "sqlstate":getattr(exc,"sqlstate",None)}
            with lock: results.append(outcome)
    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(contender, 1, one)
        b = pool.submit(contender, 2, two)
        a.result(timeout=50); b.result(timeout=50)
    with connect(OWNER, db) as r:
        actual = stats(r)
        trace("OP.concurrent", both_started_from_tip=start_tip,
              outcomes=sorted(results,key=lambda x:x["session"]),
              final_state=actual, fingerprint=fingerprint(r))
        check("OP.concurrent_two_outcomes", 2, len(results))
        check("OP.concurrent_graph_consistent", [], integrity_anomalies(r))
        check("OP.unrelated_chain_tip_unchanged", lv_original,
              stats(r,"lviv","1"*24))
        check("OP.unrelated_row_unchanged", at_before,
              query(r,"SELECT classification_key,origin_repository "
                    "FROM public.attack_event_classifications WHERE city_key='lviv'"))
        check("OP.concurrent_no_expected_tip_reject", ["committed", "committed"],
              sorted(o["status"] for o in results))
        # A chain-consistent serial revision sequence is not the same as stale-tip CAS.
    report["cases"].append({"id":"OP", "kind":"real_operational_writer_all_paths", "result":"EXECUTED"})

def batch_due(op, db, city, episode, mode="strict", label="own"):
    rec, ep, queue = record(op, city=city, episode=episode, mode=mode, tag=label)
    return op.persist_due_episode_classifications(
        queue=queue, due={city:[(ep, {"synthetic":True})]},
        coverage_by_city={city:True}, dsn=make_conninfo(**{
            **conninfo_to_dict(WRITER), "dbname":db}),
    )

def case_commit(op):
    batch_db = new_database("batch")
    seed_parent(batch_db, "kyiv", "0"*24)
    before = None
    with connect(OWNER, batch_db) as r: before = fingerprint(r)
    batch_result = batch_due(op, batch_db, "kyiv", "0"*24, label="batch-first")
    with connect(OWNER, batch_db) as r:
        after = fingerprint(r)
        cls = stats(r)["count"]
        event_count = query(r,"SELECT count(*) FROM public.attack_events")[0][0]
        links = query(r,"SELECT count(*) FROM public.attack_event_sources")[0][0]
        trace("COMMIT.own_batch", result=batch_result, before=before, after=after,
              independent_rows={"classifications":cls,"events":event_count,"source_links":links})
        check("COMMIT.own_batch_independent_visible", [1,1,1],
              [cls,event_count,links])
        check("COMMIT.own_batch_ack_matches", 1, batch_result["episodes_persisted"])
    retry = batch_due(op,batch_db,"kyiv","0"*24,label="batch-first")
    with connect(OWNER,batch_db) as r:
        check("COMMIT.close_reopen_restart_idempotent", 1, stats(r)["count"])
        trace("COMMIT.restart", result=retry, fingerprint=fingerprint(r))
    outer_db = new_database("outer")
    seed_parent(outer_db,"kyiv","0"*24)
    first, _, _ = record(op,tag="outer")
    c = connect(WRITER,outer_db,autocommit=False)
    try:
        query(c, "SELECT 1")  # Begin real outer transaction.
        return_without_commit = op.persist_episode_classification(c,first)
        with connect(OWNER,outer_db) as observer:
            not_visible = stats(observer)["count"]
        check("COMMIT.nested_savepoint_not_durable", 0, not_visible)
        trace("COMMIT.caller_owned_uncommitted", inner_return=return_without_commit,
              independent_count=not_visible, transaction_status=str(c.info.transaction_status))
        c.rollback()
        with connect(OWNER,outer_db) as observer:
            check("COMMIT.external_rollback_undoes_return", 0, stats(observer)["count"])
        query(c,"SELECT 1")
        second_return = op.persist_episode_classification(c,first)
        c.commit()
        with connect(OWNER,outer_db) as observer:
            check("COMMIT.explicit_commit_second_connection", 1, stats(observer)["count"])
            trace("COMMIT.explicit_commit", result=second_return,
                  independent_fingerprint=fingerprint(observer))
        query(c,"SELECT 1")
        second, _, _ = record(op,mode="none")
        transient = op.persist_episode_classification(c,second)
        c.close()   # implicit rollback on connection close, even though function returned
        with connect(OWNER,outer_db) as observer:
            check("COMMIT.close_without_commit_rollback", 1, stats(observer)["count"])
            trace("COMMIT.close_without_commit", transient_result=transient,
                  independently_persisted=stats(observer)["count"])
    finally:
        if not c.closed: c.close()
    report["cases"].append({"id":"COMMIT","kind":"own_batch_nested_savepoint_commit_rollback_restart","result":"EXECUTED"})

def run_case(name, fn):
    before=len(report["assertions"])
    try:
        fn()
    except Exception as exc:
        report["unexpected"].append({
            "case":name,"type":type(exc).__name__,"message":str(exc)[:600],
            "traceback":traceback.format_exc()[-2000:],
        })
        trace("UNEXPECTED_HARNESS_FAILURE", case=name, type=type(exc).__name__, message=str(exc)[:240])
    failures=[a["name"] for a in report["assertions"][before:] if not a["pass"]]
    if failures: trace("ASSERTION_FAILURES", case=name, names=failures)

def main():
    try:
        version = None
        with connect(OWNER) as c:
            version=query(c,"SELECT current_setting('server_version')")[0][0]
        report["pg_version"] = version
        check("pg_major_is_18", "18", version.split(".")[0])
        for file, pinned in INPUT_BLOBS.items():
            check("input_blob."+file,pinned,gitblob(BASE/file))
        op = load_operational()
        check("real_writer_autocommit_false", True,
              "autocommit=False" in inspect.getsource(op.persist_due_episode_classifications))
        for name, fn in [("A1",case_a1),("A2",case_a2),("A3",case_a3),
                         ("A4",case_a4),("A5",case_a5),
                         ("OP",lambda:case_operational(op)),
                         ("COMMIT",lambda:case_commit(op))]:
            run_case(name,fn)
    except Exception as exc:
        report["unexpected"].append({
            "case":"setup","type":type(exc).__name__,
            "message":str(exc)[:600],"traceback":traceback.format_exc()[-2000:]
        })
    finally:
        names=[c["id"] for c in report["cases"]]
        failures=[a["name"] for a in report["assertions"] if not a["pass"]]
        report["assertions_total"]=len(report["assertions"])
        report["assertions_passed"]=sum(a["pass"] for a in report["assertions"])
        report["failed_assertions"]=failures
        report["harness_verdict"]="EXECUTED_COMPLETE" if (not report["unexpected"] and
            set(names)=={"A1","A2","A3","A4","A5","OP","COMMIT"} and not failures
        ) else "PARTIAL_OR_FAILED"
        OUTPUT.write_text(json.dumps(report,sort_keys=True,indent=2,ensure_ascii=False,default=str)+"\n")
        print(json.dumps({"copy":COPY,"pg_version":report.get("pg_version"),
            "harness_verdict":report["harness_verdict"],
            "cases":names,"assertions":report["assertions_total"],
            "passed":report["assertions_passed"],
            "unexpected":report["unexpected"],"failed":failures},default=str))
        # Real defects must be archived, not hidden behind a CI green job.
        # Freeze job can accept a failing report only while preserving exact failure.
if __name__=="__main__": main()
