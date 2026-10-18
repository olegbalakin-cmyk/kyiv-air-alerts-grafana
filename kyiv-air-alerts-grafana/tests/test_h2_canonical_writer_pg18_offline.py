#!/usr/bin/env python3
"""Synthetic offline PostgreSQL 18 integration tests of the actual canonical writer.

Reduced fixture: derived from writer INSERT columns. NOT a proof of production schema
equivalence or Neon integration. No external credentials are used.
"""
import concurrent.futures
import copy
import hashlib
import inspect
import contextlib
import textwrap
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
        assert str(c.execute("SELECT supersedes_classification_uid FROM attack_event_classifications WHERE classification_key=%s",(r1["classification_key"],)).fetchone()[0]) == first["classification_uid"]
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
                pending = writer.persist_episode_classification(c,r2,expected_current_tip=second["classification_uid"])
                assert pending["commit_state"] == "CALLER_TRANSACTION_PENDING"
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
        expect_contract(lambda:writer.persist_due_episode_classifications(queue=[],due={"testcity":[({"episode_id":"a"*24}, {})]},coverage_by_city={"testcity":True},connection=c))
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
# Negative controls deliberately mutate application code ONLY in memory.
# The published, committed writer module remains untouched.
source = textwrap.dedent(inspect.getsource(writer.persist_episode_classification))
cas_gate = "if not exact_current_retry and actual_tip != expected_current_tip:"
tx_gate = "with conn.transaction():"
assert cas_gate in source and tx_gate in source
class ExpectedRollback(RuntimeError):
    pass
with conn() as c:
    before = read(c)
    # Disable the explicit stale expected-tip check: the stale caller now
    # incorrectly inserts a successor instead of producing STALE_EXPECTED_TIP.
    weakened_ns = dict(vars(writer))
    exec(source.replace(cas_gate,"if False and actual_tip != expected_current_tip:"),weakened_ns)
    weakened = weakened_ns["persist_episode_classification"]
    candidate = record("cas-disabled", verdict="NO_CONFIRMED_EVENT")
    try:
        with c.transaction():
            outcome=weakened(c,candidate,expected_current_tip=first["classification_uid"])
            assert outcome["classification_inserted"]
            raise ExpectedRollback("negative control isolated rollback")
    except ExpectedRollback:
        pass
    assert read(c)==before
    receipts["negative_cas"]={"stale_insert_observed_with_cas_disabled":True,
                              "persisted_after_rollback":False}
    # Disable the writer transaction and inject a fault. An autocommit
    # connection now leaks a classification row, proving the rollback test
    # detects absent transaction protection. Delete exact synthetic row.
    weakened_tx_ns = dict(vars(writer))
    weakened_tx_ns["contextlib"] = contextlib
    exec(source.replace(tx_gate,"with contextlib.nullcontext():"),weakened_tx_ns)
    weakened_tx = weakened_tx_ns["persist_episode_classification"]
    candidate_tx = record("tx-disabled",verdict="NO_CONFIRMED_EVENT")
    try:
        weakened_tx(c,candidate_tx,expected_current_tip=str(tips[0][0]),
                    fault_after="classification")
    except RuntimeError as exc:
        assert "FORCED_PERSISTENCE_FAILURE" in str(exc)
    else:
        raise AssertionError("injected fault missing")
    leaked = read(c)
    assert leaked[0] == before[0]+1, (before, leaked)
    c.execute("DELETE FROM public.attack_event_classifications WHERE classification_key=%s",
              (candidate_tx["classification_key"],))
    assert read(c)==before
    receipts["negative_rollback"]={"leaked_classification_with_tx_disabled":True,
                                  "synthetic_cleanup_confirmed":True}


# Phase A: actual positive batch call against the frozen predecessor writer.
# This is an EXPECTED DEFECT reproduction; no persistence function is mocked.
def _batch_episode(eid="a"*24):
    return {"episode_id": eid, "city_key": "testcity",
            "alert_start": "2026-01-01T00:00:00+00:00",
            "alert_end": "2026-01-01T00:20:00+00:00"}

def _batch_source(eid="a"*24, *, label="first", status="approved_strict"):
    return {"candidate_id": "synthetic-"+label, "city_key": "testcity",
            "matched_episode_id": eid,
            "classification_evidence": {"classification_episode_id": eid},
            "source": "synthetic", "status": status,
            "title": "Synthetic evidence "+label,
            "url": "https://example.invalid/"+label}

def _batch_call(c, queue, eid="a"*24, *, tip=None):
    return writer.persist_due_episode_classifications(
        queue=queue, due={"testcity":[(_batch_episode(eid), {"label":"offline"})]},
        coverage_by_city={"testcity":True}, connection=c,
        expected_tips={eid: tip})

if os.environ.get("H2_TEST_PHASE") == "pre_fix":
    setup()  # isolated fixture, independently readable on separate connection
    _eid = "a"*24
    _error = None
    with conn() as c:
        try:
            _batch_call(c, [_batch_source(_eid)])
        except writer.PersistenceContractError as exc:
            _error = str(exc)
    with conn() as independent:
        _counts = read(independent)
        _rows = independent.execute(
            """SELECT c.classification_key,c.classification_uid,
                      s.classification_uid,e.current_classification_uid
               FROM public.attack_event_classifications c
               JOIN public.attack_event_sources s ON s.classification_uid=c.classification_uid
               JOIN public.attack_events e ON e.current_classification_uid=c.classification_uid"""
        ).fetchall()
        _version = independent.execute("SHOW server_version").fetchone()[0]
    assert _error == "PERSISTENCE_ACK_BEFORE_COMMIT", (_error,_counts)
    assert _counts == (1,1,1) and len(_rows)==1, (_counts,_rows)
    assert _rows[0][1] == _rows[0][2] == _rows[0][3], _rows
    assert _version.startswith("18."), _version
    test_results["PRE_FIX_POSITIVE_BATCH"] = "EXPECTED_DEFECT_REPRODUCED"
    receipts["pre_fix"] = {
        "batch_error": _error,
        "independent_readback_counts": _counts,
        "classification_source_event_pointer_equal": True,
        "server_version": _version,
        "committed_rows_despite_error": True,
        "persistence_mocked": False
    }


if os.environ.get("H2_TEST_PHASE") == "post_fix":
    # The whole batch path uses the genuine classifier and genuine psycopg writer.
    # Each case begins from a fresh reduced fixture, with cross-session readback.
    os.environ["ATTACK_EVENT_ORIGIN_COMMIT_SHA"] = "f"*40
    os.environ["ATTACK_EVENT_ORIGIN_REF"] = "synthetic-pg18"
    eid = "a"*24
    def initial(c, *, label="first", status="approved_strict"):
        q = [_batch_source(eid, label=label, status=status)]
        return _batch_call(c, q, tip=None), q
    def counts_independent():
        with conn() as other:
            return read(other)
    def check_integrity():
        with conn() as other:
            rows = other.execute(
                """SELECT c.classification_uid,s.classification_uid,
                          e.current_classification_uid,c.verdict
                   FROM public.attack_event_classifications c
                   JOIN public.attack_event_sources s ON s.classification_uid=c.classification_uid
                   JOIN public.attack_events e ON e.current_classification_uid=c.classification_uid"""
            ).fetchall()
            assert all(row[0]==row[1]==row[2] for row in rows),rows
            return len(rows)
    def t15():
        setup()
        with conn() as c:
            out,q = initial(c)
        assert out["episodes_persisted"]==1 and out["classification_inserts"]==1,out
        assert out["event_inserts"]==1 and out["source_inserts"]==1,out
        assert counts_independent()==(1,1,1)
        receipts["T15"]={"counters":out,"readback":counts_independent()}
    check("T15",t15)
    def t16():
        assert counts_independent()==(1,1,1)
        assert check_integrity()==1
        receipts["T16"]={"committed_readback":True,"relationships_exact":True}
    check("T16",t16)
    def t17():
        with conn() as c:
            ret = _batch_call(c,[_batch_source(eid)],tip=None)
        assert ret["episodes_persisted"]==1 and ret["classification_inserts"]==0,ret
        assert ret["source_inserts"]==0 and counts_independent()==(1,1,1)
        receipts["T17"]={"retry":ret,"readback":counts_independent()}
    check("T17",t17)
    def t18():
        with conn() as c:
            prior = c.execute("SELECT classification_uid FROM attack_event_classifications").fetchone()[0]
            newer = _batch_call(c,[_batch_source(eid,label="second",status="approved_sensitivity")],tip=str(prior))
            assert newer["classification_revisions"]==1 and newer["episodes_persisted"]==1,newer
        with conn() as other:
            old = other.execute("SELECT classification_uid FROM attack_event_classifications WHERE supersedes_classification_uid IS NULL").fetchone()[0]
            successor = other.execute("SELECT classification_uid,supersedes_classification_uid FROM attack_event_classifications WHERE supersedes_classification_uid IS NOT NULL").fetchone()
            current=other.execute("SELECT current_classification_uid FROM attack_events").fetchone()[0]
        assert old==prior and successor[1]==prior and current==successor[0]
        assert counts_independent()==(2,2,1)
        receipts["T18"]={"revision":newer,"prior_preserved":True,"current_tip_updated":True}
    check("T18",t18)
    def t19():
        baseline=counts_independent()
        with conn() as c:
            prior=c.execute("SELECT classification_uid FROM attack_event_classifications WHERE supersedes_classification_uid IS NULL").fetchone()[0]
            expect_contract(lambda:_batch_call(c,[_batch_source(eid,label="third")],tip=str(prior)))
        assert counts_independent()==baseline
        receipts["T19"]={"no_mutation":True}
    check("T19",t19)
    def fault_batch(phase):
        setup()
        before=counts_independent()
        real=writer._ensure_event if phase=="classification" else writer._ensure_sources
        def fail(*args,**kwargs):
            raise RuntimeError("SYNTHETIC_"+phase+"_FAIL")
        try:
            if phase=="classification":writer._ensure_event=fail
            else:writer._ensure_sources=fail
            with conn() as c:
                try:_batch_call(c,[_batch_source(eid)])
                except RuntimeError as exc:assert "SYNTHETIC_" in str(exc)
                else:raise AssertionError("error was silently acknowledged")
        finally:
            if phase=="classification":writer._ensure_event=real
            else:writer._ensure_sources=real
        assert counts_independent()==before
        receipts["T20" if phase=="classification" else "T21"]={"rolled_back":True,"acknowledged":False}
    check("T20",lambda:fault_batch("classification"))
    check("T21",lambda:fault_batch("sources"))
    def t22():
        setup()
        with conn() as c:
            record = writer.build_episode_classification(_batch_episode(eid),[_batch_source(eid)],origin=writer._origin_context())
            try:
                with c.transaction():
                    state=writer.persist_episode_classification(c,record,expected_current_tip=None)
                    assert state["commit_state"]=="CALLER_TRANSACTION_PENDING"
                    with conn() as outside:
                        assert read(outside)==(0,0,0)
                    raise RuntimeError("caller aborted")
            except RuntimeError as exc:assert str(exc)=="caller aborted"
        assert counts_independent()==(0,0,0)
        receipts["T22"]={"caller_pending":True,"outside_read_before_commit":(0,0,0),"rollback_clean":True}
    check("T22",t22)
    def t23():
        setup()
        with conn() as c:
            record=writer.build_episode_classification(_batch_episode(eid),[_batch_source(eid)],origin=writer._origin_context())
            class CommitFailureWrapper:
                def __init__(self,real):self.real=real;self.info=real.info
                def cursor(self):return self.real.cursor()
                def transaction(self):
                    original=self.real.transaction()
                    class Trigger:
                        def __enter__(self):return original.__enter__()
                        def __exit__(self,typ,val,tb):
                            original.__exit__(typ,val,tb)
                            # Force a commit-stage failure (after context exit)
                            # and ensure caller never gets a false success.
                            raise psycopg.OperationalError("SYNTHETIC_COMMIT_ACK_FAILURE")
                    return Trigger()
            try:
                writer.persist_episode_classification(CommitFailureWrapper(c),record,expected_current_tip=None)
            except psycopg.OperationalError:pass
            else:raise AssertionError("false COMMITTED returned")
        # This injected exception models a lost commit response, NOT a proven failed
        # server commit. A durable readback could contain the row.
        receipts["T23"]={"no_false_commit_ack":True,"commit_outcome":"UNCERTAIN_INJECTED_ACK_FAILURE",
                         "independent_rows":counts_independent()}
    check("T23",t23)
    def t24():
        setup()
        with conn() as c:
            expect_contract(lambda:writer.persist_due_episode_classifications(
                queue=[_batch_source(eid)],due={"testcity":[(_batch_episode(eid),{})]},
                coverage_by_city={"testcity":True},connection=c,expected_tips=None))
            expect_contract(lambda:writer.persist_due_episode_classifications(
                queue=[_batch_source(eid)],due={"testcity":[(_batch_episode(eid),{})]},
                coverage_by_city={"testcity":True},connection=c,expected_tips={}))
            expect_contract(lambda:writer.persist_due_episode_classifications(
                queue=[_batch_source(eid)],due={"testcity":[(_batch_episode(eid),{})]},
                coverage_by_city={"testcity":True},dsn=None))
        assert counts_independent()==(0,0,0)
        receipts["T24"]={"failed_closed":True,"zero_mutations":True}
    check("T24",t24)
    def multi_partial():
        setup()
        second_eid="b"*24
        with conn() as c:
            c.execute("""INSERT INTO public.alert_episodes
            (legacy_episode_id,city_key,alert_type,episode_state,canonicalization_version,start_at,end_at)
            VALUES (%s,'testcity','AIR','closed','alert-canonicalization-v1',%s,%s)""",
            (second_eid,datetime(2026,1,1,tzinfo=timezone.utc),
             datetime(2026,1,1,0,20,tzinfo=timezone.utc)))
            try:
                writer.persist_due_episode_classifications(
                    queue=[_batch_source(eid),_batch_source(second_eid,label="second")],
                    due={"testcity":[(_batch_episode(eid),{}),(_batch_episode(second_eid),{})]},
                    coverage_by_city={"testcity":True},connection=c,expected_tips={eid:None})
            except writer.PersistenceContractError as exc:
                assert "EXPECTED_TIP_MISSING" in str(exc)
            else:raise AssertionError("partial failure silently succeeded")
        assert counts_independent()==(1,1,1)
        with conn() as c:
            retry=writer.persist_due_episode_classifications(
                queue=[_batch_source(eid),_batch_source(second_eid,label="second")],
                due={"testcity":[(_batch_episode(eid),{}),(_batch_episode(second_eid),{})]},
                coverage_by_city={"testcity":True},connection=c,
                expected_tips={eid:None,second_eid:None})
        assert retry["episodes_persisted"]==2
        assert retry["classification_inserts"]==1
        assert counts_independent()==(2,2,2)
        receipts["MULTI_EPISODE_PARTIAL_COMMIT"]={"first_durable_on_later_failure":True,
            "batch_overall_success_on_failure":False,
            "safe_retry":True,"final_counts":counts_independent()}
    check("MULTI_EPISODE_PARTIAL_COMMIT",multi_partial)
    # Negative control: restore the old inside-transaction commit status, ONLY
    # in memory, on a new fixture. Positive batch must reject it.
    def negative_early_ack():
        setup()
        original=writer.persist_episode_classification
        def broken(*args,**kwargs):
            with args[0].transaction():
                result=original(*args,**kwargs)
                result["commit_state"]="CALLER_TRANSACTION_PENDING"
                return result
        try:
            writer.persist_episode_classification=broken
            with conn() as c:
                try:_batch_call(c,[_batch_source(eid)])
                except writer.PersistenceContractError as exc:
                    assert "PERSISTENCE_ACK_BEFORE_COMMIT" in str(exc)
                else:raise AssertionError("old ACK defect not detected")
        finally:
            writer.persist_episode_classification=original
        assert counts_independent()==(1,1,1)
        receipts["NEGATIVE_EARLY_ACK"]={"defective_batch_rejected":True,
            "readback_committed":True,"mutation_type":"IN_MEMORY_WRAPPER_ONLY"}
    check("NEGATIVE_EARLY_ACK",negative_early_ack)

with conn() as version_conn:
    version = version_conn.execute("SHOW server_version").fetchone()[0]
report={"postgres_version":version,
        "schema":"REDUCED_SYNTHETIC_SCHEMA_NOT_EQUIVALENT_TO_ACCEPTED_NEON",
        "tests":test_results,"receipts":receipts,"final_counts":final_counts,
        "verdict":("EXPECTED_DEFECT_REPRODUCED" if os.environ.get("H2_TEST_PHASE")=="pre_fix" else "PARTIAL_OFFLINE_SCHEMA_EQUIVALENCE_UNPROVEN")}
print(json.dumps(report,indent=2,default=str))
Path(os.environ.get("H2_OUTPUT","/tmp/h2_pg18_result.json")).write_text(json.dumps(report,indent=2,default=str))
