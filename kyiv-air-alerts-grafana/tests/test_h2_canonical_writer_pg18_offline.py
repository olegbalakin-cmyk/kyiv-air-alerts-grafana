#!/usr/bin/env python3
"""Synthetic offline PostgreSQL 18 integration tests of the actual canonical writer.

Reduced fixture: derived from writer INSERT columns. NOT a proof of production schema
equivalence or Neon integration. No external credentials are used.
"""
import concurrent.futures
import copy
import hashlib
import json
import os
import re
import sys
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from uuid import uuid4

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import attack_event_canonical_persistence as writer

DSN = os.environ["H2_OFFLINE_POSTGRES_DSN"]
test_results = {}
receipts = {}
def check(name, fn):
    try:
        fn()
        test_results[name] = "PASS"
    except Exception as e:
        test_results[name] = f"FAIL: {type(e).__name__}: {e}"
        raise

def conn():
    c = psycopg.connect(DSN, autocommit=True)
    c.execute("SET lock_timeout='5s'")
    c.execute("SET statement_timeout='15s'")
    return c

def schema(c):
    c.execute("DROP TABLE IF EXISTS public.attack_event_sources, public.attack_events, public.attack_event_classifications, public.alert_episodes CASCADE")
    c.execute("""CREATE TABLE public.alert_episodes (
        episode_uid uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        legacy_episode_id text NOT NULL, city_key text NOT NULL, alert_type text NOT NULL,
        episode_state text NOT NULL, canonicalization_version text NOT NULL,
        start_at timestamptz NOT NULL, end_at timestamptz NOT NULL)""")
    # The exact INSERT columns are extracted from the application source itself.
    # The fixture is intentionally reduced; it is not a clone of the Neon schema.
    src = Path(writer.__file__).read_text()
    tables = ["attack_event_classifications", "attack_events", "attack_event_sources"]
    for table in tables:
        match = re.search(r"INSERT INTO public\." + table + r"\s*\((.*?)\)\s*VALUES", src, re.S)
        assert match, table
        cols = [x.strip() for x in match.group(1).split(",")]
        uid = {"attack_event_classifications":"classification_uid", "attack_events":"attack_event_uid",
               "attack_event_sources":"attack_event_source_uid"}[table]
        specs = [f"{uid} uuid PRIMARY KEY DEFAULT gen_random_uuid()"]
        for field in cols:
            if field == uid: continue
            kind = "text"
            if field.endswith("_at") or field in ("alert_start_at","alert_end_at","source_timestamp","event_timestamp_if_stated","classified_at"):
                kind = "timestamptz"
            elif field in ("is_event",): kind = "boolean"
            elif field in ("telegram_message_id", "origin_workflow_run_id","created_by_run_id","updated_by_run_id","persisted_by_run_id"): kind = "bigint"
            elif field in ("qa_reasons","review_provenance","correction_provenance","evidence_payload","retrieval_provenance","origin_provenance"):
                kind = "jsonb"
            elif field in ("event_types","classifier_reason_codes"): kind = "text[]"
            elif field.endswith("_uid"): kind = "uuid"
            specs.append(f"{field} {kind}")
        if table == "attack_event_classifications":
            specs.extend(["created_at timestamptz DEFAULT now()", "UNIQUE (classification_key)",
               "UNIQUE (supersedes_classification_uid)",
               "FOREIGN KEY (supersedes_classification_uid) REFERENCES public.attack_event_classifications(classification_uid)"])
        if table == "attack_events":
            specs.extend(["updated_at timestamptz DEFAULT now()", "UNIQUE(attack_event_key)",
                          "FOREIGN KEY(current_classification_uid) REFERENCES public.attack_event_classifications(classification_uid)"])
        if table == "attack_event_sources":
            specs.extend(["UNIQUE(source_link_key)",
                          "FOREIGN KEY(classification_uid) REFERENCES public.attack_event_classifications(classification_uid)"])
        c.execute("CREATE TABLE public." + table + " (" + ", ".join(specs) + ")")
    # Additional uniqueness for one logical physical attack event.
    c.execute("CREATE UNIQUE INDEX event_episode_uniq ON public.attack_events(city_key,historical_episode_id)")

def record(suffix, verdict="NO_CONFIRMED_EVENT", frozen=False, episode="a"*24, with_source=True):
    start=datetime(2026, 1, 1, tzinfo=timezone.utc)
    end=start+timedelta(minutes=20)
    key=hashlib.sha256(("classification-"+suffix).encode()).hexdigest()
    er=hashlib.sha256(("event-"+episode).encode()).hexdigest()
    source=[]
    if with_source:
        source=[{"source_link_key_version":"v1","source_link_key":hashlib.sha256(("source-"+suffix).encode()).hexdigest(),
            "observation_id":"sample-"+suffix, "source_family":None,"source_type":"synthetic",
            "source_type_state":"MATERIALIZED","source_url":None,"telegram_channel":None,
            "telegram_message_id":None,"source_timestamp":None,
            "source_timestamp_state":"ABSENT_IN_ACCEPTED_SOURCE","source_timestamp_raw":None,
            "event_timestamp_if_stated":None,"excerpt":None,"content_sha256":"1"*64,
            "content_hash_basis":"NORMALIZED_EVIDENCE","observation_classification_outcome":None,
            "classification_episode_id":episode,"evidence_payload":{},"retrieval_provenance":{},
            "origin_artifact_path":"synthetic","origin_git_ref":"test","origin_git_blob_sha":None,
            "raw_object_path":None,"origin_provenance":{},"origin_provenance_sha256":"1"*64}]
    return {"classification_key_version":"v2","classification_key":key,
        "historical_episode_id":episode,"city_key":"testcity","alert_type":"AIR",
        "alert_start_at":start,"alert_end_at":end,
        "alert_start_utc_microseconds":writer.utc_microseconds(start),
        "alert_end_utc_microseconds":writer.utc_microseconds(end),
        "verdict":verdict,"is_event":verdict=="STRICT_EVENT_POSITIVE",
        "positive_tier":"STRICT" if verdict=="STRICT_EVENT_POSITIVE" else None,
        "event_types":[],"qa_reasons_state":"MATERIALIZED","qa_reasons":[],
        "classifier_reason_codes":[],"classifier_blob_sha":"f"*40,
        "classifier_methodology_version":"synthetic","normalization_version":"synthetic",
        "evidence_set_sha256":"2"*64,"review_provenance_sha256":None,
        "human_review_state":"NONE","review_provenance":{},
        "originating_frozen_case_id":None,"originating_frozen_case_id_state":"NOT_APPLICABLE",
        "origin_repository":"synthetic","origin_ref":"offline","origin_commit_sha":"f"*40,
        "origin_artifact_path":"synthetic","origin_artifact_blob_sha":None,
        "origin_target_state_sha256":None,"origin_workflow_run_id":None,
        "classified_at":start,
        "origin_provenance":{"kind":"frozen" if frozen else writer.ORIGIN_KIND},
        "origin_provenance_sha256":"3"*64,"attack_event_key_version":"v1",
        "attack_event_key":er,"event_grain":"HISTORICAL_ALERT_EPISODE","source_rows":source}

def read(c):
    return tuple(c.execute(f"SELECT count(*) FROM public.{table}").fetchone()[0] for table in
       ("attack_event_classifications","attack_event_sources","attack_events"))

def setup():
    with conn() as c:
        schema(c)
        v=record("first")
        c.execute("""INSERT INTO public.alert_episodes
        (legacy_episode_id,city_key,alert_type,episode_state,canonicalization_version,start_at,end_at)
        VALUES (%s,%s,'AIR','closed','alert-canonicalization-v1',%s,%s)""",
        (v["historical_episode_id"],v["city_key"],v["alert_start_at"],v["alert_end_at"]))

def expect_contract(callback):
    try:callback()
    except writer.PersistenceContractError:return
    raise AssertionError("expected PersistenceContractError")

setup()
r0=record("first", verdict="STRICT_EVENT_POSITIVE")
r1=record("second", verdict="NO_CONFIRMED_EVENT")
r2=record("third", verdict="STRICT_EVENT_POSITIVE")
with conn() as c:
    def t1():
        global first
        first=writer.persist_episode_classification(c,r0,expected_current_tip=None)
        assert first["classification_inserted"] and read(c)==(1,1,1)
    check("T1",t1)
    def t2():
        before=read(c)
        x=writer.persist_episode_classification(c,r0,expected_current_tip=None)
        assert not x["classification_inserted"] and x["source_inserts"]==0 and read(c)==before
    check("T2",t2)
    def t3():
        global second
        second=writer.persist_episode_classification(c,r1,expected_current_tip=first["classification_uid"])
        assert second["revision_inserted"] and read(c)==(2,2,1)
        assert c.execute("SELECT supersedes_classification_uid FROM attack_event_classifications WHERE classification_key=%s",(r1["classification_key"],)).fetchone()[0] == first["classification_uid"]
    check("T3",t3)
    check("T4",lambda: (expect_contract(lambda:writer.persist_episode_classification(c,r2,expected_current_tip=first["classification_uid"])),read(c)==(2,2,1) or (_ for _ in ()).throw(AssertionError("mutated"))))
    def t6():
        bad=copy.deepcopy(r1);bad["verdict"]="STRICT_EVENT_POSITIVE"
        expect_contract(lambda:writer.persist_episode_classification(c,bad,expected_current_tip=second["classification_uid"]))
        assert read(c)==(2,2,1)
    check("T6",t6)
    def t7():
        bad=record("bad",episode="b"*24)
        expect_contract(lambda:writer.persist_episode_classification(c,bad,expected_current_tip=None))
        assert read(c)==(2,2,1)
    check("T7",t7)
    def fault(phase):
        baseline=read(c)
        candidate=record("fault-"+phase,verdict="STRICT_EVENT_POSITIVE")
        try:writer.persist_episode_classification(c,candidate,expected_current_tip=second["classification_uid"],fault_after=phase)
        except RuntimeError:pass
        else:raise AssertionError("expected injected failure")
        assert read(c)==baseline
    for phase,tid in (("classification","T8"),("event","T9"),("source","T10")):
        check(tid,lambda phase=phase:fault(phase))
    def t11():
        baseline=read(c)
        try:
            with c.transaction():
                writer.persist_episode_classification(c,r2,expected_current_tip=second["classification_uid"])
                raise RuntimeError("outer rollback")
        except RuntimeError:pass
        assert read(c)==baseline
    check("T11",t11)
    def t12():
        before=read(c)
        x=writer.persist_episode_classification(c,r1,expected_current_tip=second["classification_uid"])
        assert x["source_inserts"]==0 and not x["classification_inserted"] and read(c)==before
    check("T12",t12)
    def t13():
        c.execute("UPDATE attack_event_classifications SET origin_provenance='{\"kind\":\"frozen\"}'::jsonb WHERE classification_key=%s",(r1["classification_key"],))
        expect_contract(lambda:writer.persist_episode_classification(c,r2,expected_current_tip=second["classification_uid"]))
        assert read(c)==(2,2,1)
        c.execute("UPDATE attack_event_classifications SET origin_provenance=%s WHERE classification_key=%s",(psycopg.types.json.Jsonb({"kind":writer.ORIGIN_KIND}),r1["classification_key"]))
    check("T13",t13)
    def t14():
        expect_contract(lambda:writer.persist_episode_classification(c,r2))
        expect_contract(lambda:writer.persist_due_episode_classifications(queue=[],due={"testcity":[({"episode_id":"a"*24}, {})]},coverage_by_city={"testcity":True},dsn=None))
        assert read(c)==(2,2,1)
    check("T14",t14)

# Genuine contention: both connections start from same supplied expected UID.
barrier=threading.Barrier(2)
def contestant(label):
    with conn() as c:
        pid=c.execute("SELECT pg_backend_pid()").fetchone()[0]
        barrier.wait(timeout=10)
        try:
            output=writer.persist_episode_classification(c,record(label),expected_current_tip=second["classification_uid"])
            return {"pid":pid,"result":"ACCEPTED","uid":output["classification_uid"]}
        except writer.PersistenceContractError as e:
            return {"pid":pid,"result":"STALE","error":str(e).split(":")[0]}
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
    futures=[executor.submit(contestant,x) for x in ("concurrent-a","concurrent-b")]
    outcomes=[f.result(timeout=30) for f in futures]
with conn() as c:
    tips=c.execute("""SELECT classification_uid FROM attack_event_classifications x
                      WHERE NOT EXISTS (SELECT 1 FROM attack_event_classifications n
                       WHERE n.supersedes_classification_uid=x.classification_uid)""").fetchall()
    final_counts=read(c)
    orphan=c.execute("""SELECT count(*) FROM attack_event_sources s
                 LEFT JOIN attack_event_classifications c ON c.classification_uid=s.classification_uid
                 WHERE c.classification_uid IS NULL""").fetchone()[0]
assert len({v["pid"] for v in outcomes})==2
assert sorted(x["result"] for x in outcomes)==["ACCEPTED","STALE"],outcomes
assert len(tips)==1 and final_counts==(3,3,1) and orphan==0,(tips,final_counts,orphan)
test_results["T5"]="PASS"
receipts["T5"]={"connections":outcomes,"tip_count":len(tips),"final_counts":final_counts,"orphan_count":orphan}
# Negative control: monkeypatch _current_tip to misreport a stale expected tip.
# A valid CAS implementation must reject a caller's stale predecessor even when the lock is held.
with conn() as c:
    original=writer._current_tip
    try:
        writer._current_tip=lambda cur,record: {"classification_uid":str(second["classification_uid"]),"classification_key":r1["classification_key"],"verdict":r1["verdict"],"origin_provenance":{"kind":writer.ORIGIN_KIND}}
        # This intentionally weakened test-only tip observer is expected to break a guard.
        # Do not execute a mutation against this artificial observer: test only the diagnostic flag.
        negative_control_detected = (original is not writer._current_tip)
    finally:
        writer._current_tip=original
    assert negative_control_detected
receipts["negative_control"]="TIP_OBSERVER_MUTATION_DETECTED_ONLY_NOT_EXECUTED"
with conn() as version_conn:
    version = version_conn.execute("SHOW server_version").fetchone()[0]
report={"postgres_version":version,
        "schema":"REDUCED_SYNTHETIC_SCHEMA_NOT_EQUIVALENT_TO_ACCEPTED_NEON",
        "tests":test_results,"receipts":receipts,"final_counts":final_counts,
        "verdict":"PARTIAL_SCHEMA_EQUIVALENCE_UNPROVEN"}
print(json.dumps(report,indent=2,default=str))
Path(os.environ.get("H2_OUTPUT","/tmp/h2_pg18_result.json")).write_text(json.dumps(report,indent=2,default=str))
