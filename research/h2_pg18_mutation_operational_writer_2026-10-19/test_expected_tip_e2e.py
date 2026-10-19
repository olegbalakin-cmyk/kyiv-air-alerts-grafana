#!/usr/bin/env python3
"""Executable synthetic PG18 expected-tip CAS and transaction control."""
import concurrent.futures
import dataclasses
import hashlib
import importlib.util
import json
import os
import sys
import threading
from pathlib import Path

import psycopg
from psycopg.conninfo import conninfo_to_dict, make_conninfo

ROOT = Path(__file__).resolve().parent
APP = ROOT.parent.parent / "kyiv-air-alerts-grafana" / "scripts"
sys.path.insert(0, str(APP))
sys.path.insert(0, str(ROOT))
import test_mutation_operational as baseline
import attack_event_canonical_persistence as writer
import attack_event_tip_snapshot as snap

report = {"copy": os.environ.get("H2_COPY", "A"), "cases": [], "errors": [], "assertions": []}
def check(name, ok, detail=None):
    report["assertions"].append({"name": name, "pass": bool(ok), "detail": str(detail)[:120] if detail is not None else None})
    if not ok: raise AssertionError(name + ": " + str(detail))
def fail_closed(fn, code):
    try: fn()
    except writer.PersistenceContractError as exc:
        check(code, code in str(exc), str(exc))
    else: check(code, False, "no failure")
def case(name, fn):
    try: fn(); report["cases"].append({"id": name, "status": "PASS"})
    except Exception as e:
        report["errors"].append({"case": name, "type": type(e).__name__, "error": str(e)[:300]})
        report["cases"].append({"id": name, "status": "FAIL"})
def dsn(database):
    return make_conninfo(**{**conninfo_to_dict(baseline.WRITER), "dbname": database})
def session(database):
    return baseline.connect(baseline.WRITER, database)
def init(label, episode=None):
    db=baseline.new_database(label)
    baseline.seed_parent(db, "kyiv", episode or "0"*24)
    return db
def item(episode="0"*24, label="immediate"):
    return {"city_key":"kyiv","episode_id":episode,
            "alert_start":baseline.START,"alert_end":baseline.END}, {"label":label,"due_at":"2026-01-01T03:00:00+00:00"}
def snapshot(db, ep, chk):
    return snap.observe_expected_tips({"kyiv":[(ep,chk)]},dsn=dsn(db))[snap.episode_identity(ep)]
def classification(tag):
    return baseline.record(writer,tag=tag)[0]
def put(db, record, authority, fault=None):
    with session(db) as conn:
        return writer.persist_episode_classification(conn,record,expected_snapshot=authority,fault_after=fault)
def counts(db):
    with baseline.connect(baseline.OWNER,db) as c:
        return tuple(baseline.query(c,f"SELECT count(*) FROM public.{t}")[0][0] for t in
                     ["attack_event_classifications","attack_events","attack_event_sources","h2_classification_heads"])
def tip(db):
    with session(db) as conn:
        cur=conn.cursor();return writer._current_tip(cur,classification("probe"))
def batch(db, ep, chk, authority, tag):
    rec,e,q=baseline.record(writer,tag=tag)
    return writer.persist_due_episode_classifications(
        queue=q,due={"kyiv":[(ep,chk)]},coverage_by_city={"kyiv":True},
        dsn=dsn(db),expected_snapshots={snap.episode_identity(ep):authority})

def first_revision_and_idempotency():
    db=init("first")
    ep,ck=item()
    s0=snapshot(db,ep,ck)
    check("authoritative_null_tip",s0.expected_current_tip is None)
    check("immutable_token",dataclasses.is_dataclass(s0) and s0.__dataclass_params__.frozen)
    a=put(db,classification("first"),s0)
    check("first_committed",a["commit_state"]=="COMMITTED")
    check("first_independent_tip",tip(db)["classification_uid"]==a["classification_uid"])
    s1=snapshot(db,ep,ck)
    check("tip_matches_prior",s1.expected_current_tip==a["classification_uid"])
    b=put(db,classification("second"),s1)
    check("revision_committed",b["revision_inserted"] and b["commit_state"]=="COMMITTED")
    retry=put(db,classification("second"),s1)
    check("exact_retry_idempotent",not retry["classification_inserted"] and counts(db)[0]==2)
    check("no_idempotent_event_side_effects",not retry["event_updated"] and not retry["source_inserts"])
    fail_closed(lambda:put(db,classification("third"),s0),"STALE_EXPECTED_TIP")
    check("stale_zero_rows",counts(db)[0]==2)

def bad_authority():
    db=init("invalid")
    ep,ck=item(); s=snapshot(db,ep,ck)
    fail_closed(lambda:put(db,classification("missing"),None),"EXPECTED_TIP_SNAPSHOT_AUTHORITY_INVALID")
    fake=dataclasses.replace(s)
    fail_closed(lambda:put(db,classification("forge"),fake),"EXPECTED_TIP_SNAPSHOT_AUTHORITY_INVALID")
    other=dict(ep,episode_id="different")
    fail_closed(lambda:snap.require_snapshot_authority(s,episode=other),"EXPECTED_TIP_SNAPSHOT_EPISODE_MISMATCH")
    fail_closed(lambda:snap.require_snapshot_authority(s,check={"label":"24h","due_at":ck["due_at"]}),"EXPECTED_TIP_SNAPSHOT_ATTEMPT_MISMATCH")
    check("invalid_zero_rows",counts(db)[0]==0)

def concurrency():
    db=init("race")
    ep,ck=item(); initial=snapshot(db,ep,ck)
    barrier=threading.Barrier(2)
    def run(tag):
        barrier.wait(timeout=15)
        try: return {"tag":tag,"value":put(db,classification(tag),initial)}
        except writer.PersistenceContractError as exc: return {"tag":tag,"error":str(exc)}
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        outcomes=list(pool.map(run,["concurrentA","concurrentB"]))
    commits=[o for o in outcomes if o.get("value",{}).get("commit_state")=="COMMITTED"]
    stale=[o for o in outcomes if "STALE_EXPECTED_TIP" in o.get("error","")]
    check("two_sessions_one_commit_one_stale",len(commits)==len(stale)==1,outcomes)
    check("concurrent_no_rejected_side_effects",counts(db)[0]==1,counts(db))
    with session(db) as c:
        rows=baseline.query(c,"SELECT count(DISTINCT supersedes_classification_uid) FROM public.attack_event_classifications")
        check("single_revision_chain",len(rows)==1)

def rollback_faults():
    for fault in ("classification","event","source"):
        db=init("fault_"+fault);ep,ck=item();a=snapshot(db,ep,ck)
        try: put(db,classification("fault"+fault),a,fault=fault)
        except RuntimeError as exc: check("fault_"+fault+"_raised",fault.upper() in str(exc))
        else: check("fault_"+fault+"_raised",False)
        check("fault_"+fault+"_zero_effects",counts(db)[0:3]==(0,0,0),counts(db))

def transaction_contract():
    db=init("outer");ep,ck=item();a=snapshot(db,ep,ck)
    conn=baseline.connect(baseline.WRITER,db,autocommit=False)
    try:
        conn.execute("SELECT 1")
        o=writer.persist_episode_classification(conn,classification("outer"),expected_snapshot=a)
        check("caller_pending_no_durable_ack",o["commit_state"]=="CALLER_TRANSACTION_PENDING")
        with session(db) as other: check("pending_not_visible",baseline.query(other,"SELECT count(*) FROM public.attack_event_classifications")[0][0]==0)
        conn.rollback()
        check("caller_rollback_zero_rows",counts(db)[0]==0)
        conn.execute("SELECT 1")
        fail_closed(lambda:writer.persist_due_episode_classifications(
            queue=[],due={"kyiv":[(ep,ck)]},coverage_by_city={"kyiv":True},
            connection=conn,dsn=dsn(db),expected_snapshots={snap.episode_identity(ep):a}),
            "CALLER_TRANSACTION_PENDING")
        conn.rollback()
        result=put(db,classification("after"),a)
        check("commit_ack_after_context_exit",result["commit_state"]=="COMMITTED")
        check("reader_sees_committed",counts(db)[0]==1)
    finally: conn.close()

def batch_readback():
    db=init("batch");ep,ck=item();a=snapshot(db,ep,ck)
    res=batch(db,ep,ck,a,"batch")
    check("batch_commit_readback",res["commit_state"]=="COMMITTED" and res["independent_readback"]=="PASS")
    check("batch_one_ack",res["episodes_persisted"]==1 and res["records"][0]["observation_id"]==a.observation_id)
    again=batch(db,ep,ck,a,"batch")
    check("retry_no_duplicate",counts(db)[0]==1 and again["classification_inserts"]==0)
    old=a
    other=snapshot(db,ep,ck)
    put(db,classification("competitor"),other)
    fail_closed(lambda:batch(db,ep,ck,old,"third"),"STALE_EXPECTED_TIP")
    check("batch_stale_no_effects",counts(db)[0]==2)

def negative_control():
    db=init("mutation");ep,ck=item();old=snapshot(db,ep,ck)
    first=put(db,classification("one"),old)
    rival=snapshot(db,ep,ck)
    put(db,classification("two"),rival)
    original=writer._assert_expected_tip_cas
    try:
        writer._assert_expected_tip_cas=lambda *args:None
        third=put(db,classification("three"),old)
        violated=third["commit_state"]=="COMMITTED" and counts(db)[0]==3
        check("disabled_guard_detects_unsafe_commit",violated)
    finally: writer._assert_expected_tip_cas=original
    fail_closed(lambda:put(db,classification("four"),old),"STALE_EXPECTED_TIP")

def main():
    with baseline.connect(baseline.OWNER) as c:
        check("PG18",baseline.query(c,"SHOW server_version")[0][0].split(".")[0]=="18")
    for name,fn in [
        ("authority_and_revision",first_revision_and_idempotency),
        ("missing_forged_incompatible",bad_authority),
        ("independent_concurrency",concurrency),
        ("injected_rollback",rollback_faults),
        ("transaction_ownership",transaction_contract),
        ("batch_independent_readback",batch_readback),
        ("negative_guard_bypass",negative_control),
    ]: case(name,fn)
    report["passed"]=sum(c["pass"] for c in report["assertions"])
    report["total"]=len(report["assertions"])
    report["verdict"]="PASS" if not report["errors"] and all(c["pass"] for c in report["assertions"]) else "FAIL"
    output=Path(os.environ.get("H2_REPORT","/tmp/h2_expected_tip.json"))
    output.write_text(json.dumps(report,indent=2,sort_keys=True,default=str)+"\n")
    print(json.dumps({"copy":report["copy"],"total":report["total"],"passed":report["passed"],"errors":report["errors"],"verdict":report["verdict"]}))
    if report["verdict"]!="PASS":raise SystemExit(1)
if __name__=="__main__":main()
