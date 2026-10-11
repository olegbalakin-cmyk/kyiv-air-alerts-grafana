#!/usr/bin/env python3
"""Executable local PostgreSQL 16 acceptance: real queue, parent, writer, SQL rows."""
import copy
import hashlib
import json
import os
import sys
import tempfile
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg
from psycopg.pq import TransactionStatus

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests/fixtures/parent_contract"))
import db_phase1_core as core
import live_canonical_queue as q
import live_parent_ordering as po
import attack_event_canonical_persistence as p

UTC = timezone.utc
START = datetime(2026, 10, 8, tzinfo=UTC)
CUTOFF = datetime(2026, 10, 7, 19, 5, tzinfo=UTC)
NOW = datetime(2026, 11, 15, tzinfo=UTC)
DSN = os.environ["LOCAL_PROOF_POSTGRES_DSN"]
os.environ["CANONICAL_PARENT_CONTRACT_DIR"] = str(ROOT / "tests/fixtures/parent_contract")
os.environ["CANONICAL_PARENT_DB_BRANCH"] = "offline-disposable-postgres-16"
os.environ["ATTACK_EVENT_ORIGIN_COMMIT_SHA"] = os.environ.get("GITHUB_SHA", "0" * 40)
os.environ["ATTACK_EVENT_ORIGIN_REF"] = "kyiv-live-canonical-queue-pg16-proof-2026-10-11"
REPORT = {"postgres": {}, "cases": {}, "batches": [], "classification_count": 0, "source_count": 0, "event_count": 0}

def ep(i, city="kyiv"):
    start = START + timedelta(minutes=20*i)
    end = start + timedelta(minutes=15)
    return {
        "city_key": city, "episode_id": core.legacy_episode_id(city,start,end),
        "alert_start": start.isoformat(), "alert_end": end.isoformat(),
        "checks": [{"label":"immediate","due_at":end.isoformat(),"checked_at":NOW.isoformat()}],
    }

def ready_state(episodes):
    state={"cities":{}}
    for e in episodes:
        state["cities"].setdefault(e["city_key"],{"episodes":[]})["episodes"].append(e)
    q.register_state(state,CUTOFF)
    for ent in q.store(state).values():
        for check in ent["coverage_checks"].values():
            check.update({"status":"complete","completed_at":NOW.isoformat(),"reason":None})
    return state

def count(conn, table):
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM public."+table)
        return cur.fetchone()[0]

def db_assert(expected):
    with psycopg.connect(DSN,autocommit=True) as verifier:
        found={name:count(verifier,name) for name in expected}
    assert found==expected,(expected,found)
    return found

def with_case(name, fn):
    try:
        detail=fn()
        REPORT["cases"][name]={"pass":True,"detail":detail}
    except Exception as ex:
        REPORT["cases"][name]={"pass":False,"error":type(ex).__name__+":"+str(ex)}
        raise

def queue_persist(state, candidates=None):
    candidates=candidates or []
    with psycopg.connect(DSN, autocommit=False) as conn:
        tips=q.read_current_tips(conn,CUTOFF)
        conn.rollback()
        s=q.reconcile_and_select(state,tips=tips,candidates=candidates,cutoff=CUTOFF,max_episodes=10,now=NOW)
        parents=po.preclassification_parent_gate({"cities":{city:{"episodes":[row["episode"] for row in s["selected"] if row["episode"]["city_key"]==city]} for city in state["cities"]}},cutoff=CUTOFF,max_episodes=10,connection=conn)
        allowed={(x["city"],x["episode_id"]) for x in parents["records"]}
        selected={"selected":[row for row in s["selected"] if (row["episode"]["city_key"],row["episode"]["episode_id"]) in allowed]}
        persisted=p.persist_canonical_work(state=state,selection=selected,candidates=candidates,connection=conn,at=NOW)
    return s,persisted

def run():
    with psycopg.connect(DSN, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SHOW server_version")
            ver=cur.fetchone()[0]
            cur.execute("SELECT current_database(),current_user")
            db,user=cur.fetchone()
        REPORT["postgres"]={"version":ver,"database":db,"user":user}
    assert ver.startswith("16."),ver

    def initial():
        state=ready_state([ep(0)])
        sel,res=queue_persist(state)
        assert sel["ready_pending"]==1 and res["committed"]==1 and res["readback_verified"]==1,(sel,res)
        return db_assert({"alert_episodes":1,"attack_event_classifications":1,"attack_events":0})
    with_case("initial_postgres_commit_and_separate_readback",initial)

    def repeat():
        state=ready_state([ep(0)])
        sel,res=queue_persist(state)
        assert sel["db_committed_current"]==1 and not sel["selected"] and res["committed"]==0
        return db_assert({"alert_episodes":1,"attack_event_classifications":1})
    with_case("idempotent_identical_rerun",repeat)

    def crash():
        episode=ep(1)
        with psycopg.connect(DSN,autocommit=False) as conn:
            po.ensure_canonical_parent(conn,episode)
            baseline=db_assert({"attack_event_classifications":1})
            record=p.build_episode_classification(episode,[],origin=p._origin_context())
            try:
                p.persist_episode_classification(conn,record,expected_tip=None,fault_after="classification")
                raise AssertionError("missing crash")
            except RuntimeError as exc:
                assert "FORCED_PERSISTENCE_FAILURE" in str(exc),str(exc)
            assert conn.info.transaction_status==TransactionStatus.IDLE
        assert db_assert({"attack_event_classifications":1})==baseline
        return "no leaked classification"
    with_case("classification_crash_rolls_back",crash)

    def stale_tip():
        episode=ep(0)
        with psycopg.connect(DSN,autocommit=False) as conn:
            rec=p.build_episode_classification(episode,[],origin=p._origin_context())
            try:
                p.persist_episode_classification(conn,rec,expected_tip="00000000-0000-0000-0000-000000000000")
                raise AssertionError("stale tip admitted")
            except p.PersistenceContractError as exc:
                assert "STALE_EXPECTED" in str(exc)
            assert conn.info.transaction_status==TransactionStatus.IDLE
        return db_assert({"attack_event_classifications":1})
    with_case("stale_expected_tip_fail_closed",stale_tip)

    def missing_parent():
        episode=ep(2)
        record=p.build_episode_classification(episode,[],origin=p._origin_context())
        with psycopg.connect(DSN,autocommit=False) as conn:
            try:
                p.persist_episode_classification(conn,record,expected_tip=None)
                raise AssertionError("missing canonical parent admitted")
            except p.PersistenceContractError as exc:
                assert "requires exactly one canonical" in str(exc)
        return db_assert({"alert_episodes":2,"attack_event_classifications":1})
    with_case("missing_parent_fail_closed",missing_parent)

    def forward_469():
        # Distinct from safety cases; 469 pending episode identities.
        episodes=[ep(1000+i) for i in range(469)]
        state=ready_state(episodes)
        for batch_idx in range(47):
            sel,res=queue_persist(state)
            want=10 if batch_idx<46 else 9
            assert len(sel["selected"])==want,(batch_idx,len(sel["selected"]))
            assert res["committed"]==want and res["readback_verified"]==want,(batch_idx,res)
            ids=[row["episode_id"] for row in res["records"]]
            assert len(set(ids))==want
            REPORT["batches"].append({"batch":batch_idx+1,"ids":ids,"committed":want,"readback":want})
            with psycopg.connect(DSN,autocommit=True) as con:
                assert count(con,"attack_event_classifications")==1+sum(x["committed"] for x in REPORT["batches"])
        sel,res=queue_persist(state)
        assert not sel["selected"] and sel["db_committed_current"]==469
        blob=json.loads(json.dumps(state))
        sel,_=queue_persist(blob)
        assert not sel["selected"]
        assert q.store(blob).keys()==q.store(state).keys()
        return {"batches":47,"committed":469,"duplicates":0,"restart_preserved":True}
    with_case("469_real_postgres_commits_47_batches",forward_469)

    with psycopg.connect(DSN,autocommit=True) as con:
        REPORT["classification_count"]=count(con,"attack_event_classifications")
        REPORT["event_count"]=count(con,"attack_events")
        REPORT["source_count"]=count(con,"attack_event_sources")
    assert REPORT["classification_count"]==470
    REPORT["failures"]=[x for x,y in REPORT["cases"].items() if not y["pass"]]
    body=json.dumps(REPORT,sort_keys=True,separators=(",",":"),default=str)
    REPORT["fingerprint"]=hashlib.sha256(body.encode()).hexdigest()
    return REPORT

if __name__=="__main__":
    try:
        print(json.dumps(run(),sort_keys=True,indent=2,default=str))
    except Exception:
        print(json.dumps(REPORT,sort_keys=True,indent=2,default=str))
        raise
