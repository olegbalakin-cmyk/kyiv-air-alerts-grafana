#!/usr/bin/env python3
"""Real PostgreSQL 18 snapshot -> canonical batch writer integration.

Reduced synthetic schema only. No production credentials, no network services.
"""
import os
import sys
import json
import runpy
import hashlib
from pathlib import Path
from datetime import datetime,timezone,timedelta

import psycopg
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import attack_event_canonical_persistence as w
import attack_event_tip_snapshot as snap

# Run the exact accepted writer regression suite first, then use its fixture
# constructors with a freshly reset schema for the snapshot/caller matrix.
os.environ["H2_TEST_PHASE"]="post_fix"
legacy=runpy.run_path(str(Path(__file__).with_name("test_h2_canonical_writer_pg18_offline.py")))
conn=legacy["conn"]; setup=legacy["setup"]; counts=legacy["read"]
episode=legacy["_batch_episode"]; evidence=legacy["_batch_source"]
results={}
def check(name,callback):
    try:
        callback()
        results[name]="PASS"
    except Exception as exc:
        results[name]=f"FAIL:{type(exc).__name__}:{exc}"
        raise
def due(eid="a"*24,city="testcity",label="immediate"):
    e=episode(eid);e["city_key"]=city
    return {city:[(e,{"label":label,"due_at":"2026-01-01T00:20:00Z","checked_at":None})]}
def read_due(d,connection=None):
    return snap.observe_expected_tips(d,dsn=None if connection else os.environ["H2_OFFLINE_POSTGRES_DSN"],connection=connection)
def batch(d,s,queue=None):
    return w.persist_due_episode_classifications(
        queue=evidence() if queue is None else queue,
        due=d,coverage_by_city={k:True for k in d},
        dsn=os.environ["H2_OFFLINE_POSTGRES_DSN"],expected_snapshots=s)
def evidence():
    return [legacy["_batch_source"]()]
def reset():
    setup()
def fails(fn,match):
    try:fn()
    except w.PersistenceContractError as exc:
        assert match in str(exc),(match,str(exc))
        return str(exc)
    raise AssertionError("expected contract rejection: "+match)
def state():
    with conn() as c:return counts(c)
def first():
    reset()
    d=due();s=read_due(d)
    assert len(s)==1 and next(iter(s.values()))["expected_current_tip"] is None
    r=batch(d,s)
    assert r["episodes_persisted"]==1 and state()==(1,1,1)
    results["I1"]="PASS"
    return d,s,r
d,s,r=first()
def i2():
    uid=next(iter(s.values()))
    d2=due(label="24h")
    sn=read_due(d2)
    assert next(iter(sn.values()))["expected_current_tip"] is not None
    x=batch(d2,sn,[legacy["_batch_source"](label="followup",status="approved_sensitivity")])
    assert x["classification_revisions"]==1 and state()==(2,2,1)
check("I2",i2)
def i3():
    d2=due(label="retry");sn=read_due(d2)
    q=[legacy["_batch_source"](label="followup",status="approved_sensitivity")]
    x=batch(d2,sn,q)
    assert x["classification_inserts"]==0 and state()==(2,2,1)
check("I3",i3)
def i4():
    reset()
    d=due();planned=read_due(d)
    with conn() as c:
        rec=w.build_episode_classification(d["testcity"][0][0],[legacy["_batch_source"]()],origin=w._origin_context())
        w.persist_episode_classification(c,rec,expected_current_tip=None)
    assert next(iter(planned.values()))["expected_current_tip"] is None
    fails(lambda:batch(d,planned,[legacy["_batch_source"](label="different")]),"STALE_EXPECTED_TIP")
    assert state()==(1,1,1)
check("I4",i4)
def i5():
    reset()
    d=due();a=read_due(d);b=read_due(d)
    batch(d,a)
    fails(lambda:batch(d,b,[legacy["_batch_source"](label="competing")]),"STALE_EXPECTED_TIP")
    assert state()==(1,1,1)
check("I5",i5)
check("I6",lambda:fails(lambda:batch(d,{}),"EXPECTED_TIP_SNAPSHOT_IDENTITY_MISSING"))
def i7():
    reset()
    d=due()
    with conn() as c:
        z=w.build_episode_classification(d["testcity"][0][0],evidence(),origin=w._origin_context())
        w.persist_episode_classification(c,z,expected_current_tip=None)
        z2=w.build_episode_classification(d["testcity"][0][0],[legacy["_batch_source"](label="other")],origin=w._origin_context())
        # Controlled negative fixture: create another unsuperseded tip using the
        # same genuine insert SQL but a different classification key.
        w._insert_classification(c,z2,alert_episode_uid=str(c.execute(
            "SELECT episode_uid FROM alert_episodes").fetchone()[0]),
            supersedes_uid=None,revision_reason=None,correction_provenance={})
    fails(lambda:read_due(d),"EXPECTED_TIP_MULTIPLE_CURRENT_REVISIONS")
check("I7",i7)
def i8():
    reset()
    with conn() as c:c.execute("DELETE FROM public.alert_episodes")
    fails(lambda:read_due(due()),"EXPECTED_TIP_CANONICAL_PARENT_NOT_UNIQUE")
check("I8",i8)
def i9():
    reset()
    e=episode();id=e["episode_id"]
    with conn() as c:
        c.execute("""INSERT INTO public.alert_episodes
        (legacy_episode_id,city_key,alert_type,episode_state,canonicalization_version,start_at,end_at)
        VALUES (%s,'othercity','AIR','closed','alert-canonicalization-v1',%s,%s)""",
        (id,datetime(2026,1,1,tzinfo=timezone.utc),datetime(2026,1,1,0,20,tzinfo=timezone.utc)))
    d={**due(),**due(city="othercity")}
    ss=read_due(d)
    assert len(ss)==2 and len({k[0] for k in ss})==2
    assert all(v["expected_current_tip"] is None for v in ss.values())
check("I9",i9)
def i10():
    reset()
    d=due()
    with conn() as c:
        z=legacy["record"]("frozen",frozen=True)
        w.persist_episode_classification(c,z,expected_current_tip=None)
    sn=read_due(d)
    assert next(iter(sn.values()))["observed_origin_kind"]=="frozen"
    fails(lambda:batch(d,sn),"refusing to revise a pre-existing non-live")
check("I10",i10)
def i11():
    reset()
    d=due();sn=read_due(d)
    x=w.persist_due_episode_classifications(queue=evidence(),due=d,
        coverage_by_city={"testcity":False},dsn=os.environ["H2_OFFLINE_POSTGRES_DSN"],
        expected_snapshots=sn)
    assert x["episodes_persisted"]==0 and state()==(0,0,0)
check("I11",i11)
def i12():
    reset()
    fails(lambda:snap.observe_expected_tips(due(),dsn=None),"EXPECTED_TIP_SNAPSHOT_DATABASE_UNAVAILABLE")
check("I12",i12)
def i13():
    reset()
    d=due();sn=read_due(d)
    bad={**d,"wrong":[(dict(d["testcity"][0][0]),dict(d["testcity"][0][1]))]}
    fails(lambda:batch(bad,sn),"EXPECTED_TIP_SNAPSHOT_IDENTITY_MISSING")
    assert state()==(1,1,1)
check("I13",i13)
def i14():
    reset()
    d=due();sn=read_due(d)
    changed=due(label="24h")
    fails(lambda:batch(changed,sn),"EXPECTED_TIP_SNAPSHOT_ATTEMPT_MISMATCH")
    assert state()==(0,0,0)
check("I14",i14)
def i15():
    reset()
    d=due();sn=read_due(d)
    assert batch(d,sn)["episodes_persisted"]==1
    with conn() as c:
        p=c.execute("SELECT c.classification_uid,s.classification_uid,e.current_classification_uid FROM attack_event_classifications c JOIN attack_event_sources s ON c.classification_uid=s.classification_uid JOIN attack_events e ON e.current_classification_uid=c.classification_uid").fetchall()
    assert len(p)==1 and p[0][0]==p[0][1]==p[0][2]
check("I15",i15)
with conn() as c:version=c.execute("SHOW server_version").fetchone()[0]
report={"scope":"REAL_POSTGRESQL_SNAPSHOT_AND_WRITER_CALLER_HELPER_REDUCED_SCHEMA",
        "postgres_version":version,"matrix":results,
        "old_writer_tests":legacy["test_results"],
        "note":"full monitor main(), two-connection concurrent barrier and checkpoint state not independently exercised",
        "verdict":"PARTIAL"}
Path(os.environ.get("H2_CALLER_OUTPUT","/tmp/h2_caller_report.json")).write_text(json.dumps(report,indent=2,default=str))
print(json.dumps(report,indent=2,default=str))
