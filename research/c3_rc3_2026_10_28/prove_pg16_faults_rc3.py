#!/usr/bin/env python3
"""Executed PG16 observations. Every nonexecuted fault remains NOT_PROVEN."""
import json
import os
import subprocess
import sys
from pathlib import Path
import psycopg

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(os.getenv("C3_RC3_REPORT_DIR","/tmp/c3-rc3-proof"))
OUT.mkdir(parents=True,exist_ok=True)
DSN=os.environ["LOCAL_PROOF_POSTGRES_DSN"]
SCENARIOS=[
"two_concurrent_workers",
"post_commit_pre_ack",
"independent_readback_failure",
"classification_conflict",
"source_identity_conflict",
"stale_current_tip",
"pruned_state_legacy_checked_at",
"event_stage_rollback",
"source_failure_retry",
"repeated_normal_execution",
]
result={"gate":"C3-RC3","test_engine":"disposable PostgreSQL 16",
        "scenarios":{x:{"status":"NOT_PROVEN","reason":"No scenario-specific executable independent SQL proof obtained"} for x in SCENARIOS},
        "baseline_monitor_main":{"status":"NOT_EXECUTED"},"sql_snapshots":[],"result":"PARTIAL"}
def snapshot(label):
    with psycopg.connect(DSN,autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SHOW server_version")
            v=cur.fetchone()[0]
            if not v.startswith("16."):raise AssertionError("not PostgreSQL 16: "+v)
            counts={}
            for table in ["alert_episodes","attack_event_classifications","attack_events","attack_event_sources"]:
                cur.execute("SELECT count(*) FROM public."+table)
                counts[table]=cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM (SELECT classification_key FROM public.attack_event_classifications GROUP BY classification_key HAVING count(*)>1) x")
            counts["duplicate_classification_keys"]=cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM (SELECT attack_event_key FROM public.attack_events GROUP BY attack_event_key HAVING count(*)>1) x")
            counts["duplicate_event_keys"]=cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM public.attack_event_classifications c WHERE c.supersedes_classification_uid IS NOT NULL")
            counts["revision_count"]=cur.fetchone()[0]
    result["sql_snapshots"].append({"point":label,"counts":counts})
    return counts
try:
    before=snapshot("before")
    run=subprocess.run(
        [sys.executable,str(ROOT/"kyiv-air-alerts-grafana/tests/prove_pg16_monitor_main.py")],
        cwd=ROOT,capture_output=True,text=True,timeout=240
    )
    (OUT/"monitor_main_execution.log").write_text(run.stdout+"\n--- STDERR ---\n"+run.stderr)
    rows=[x for x in run.stdout.splitlines() if x.startswith("MAIN_INTEGRATION_REPORT=")]
    if run.returncode==0 and len(rows)==1:
        receipt=json.loads(rows[0].split("=",1)[1])
        after=snapshot("after_two_real_main_calls")
        good=(receipt.get("pass") is True and receipt.get("monitor_main_calls")==2
              and receipt.get("first_committed")==1 and receipt.get("first_independent_readback")==1
              and receipt.get("second_committed")==0
              and after["duplicate_classification_keys"]==0 and after["duplicate_event_keys"]==0
              and after["attack_event_classifications"]-before["attack_event_classifications"]==1)
        result["baseline_monitor_main"]={"status":"PASS" if good else "FAIL","receipt":receipt}
        if good:
            result["scenarios"]["repeated_normal_execution"]={"status":"PASS","SQL_before":before,"SQL_after":after,"receipt":receipt}
    else:
        result["baseline_monitor_main"]={"status":"FAIL","returncode":run.returncode,"receipt_count":len(rows)}

    # Real SQL fault injections; never mock the persistence entry points.
    from concurrent.futures import ThreadPoolExecutor
    from datetime import datetime, timedelta, timezone
    import copy
    import importlib
    import time
    sys.path.insert(0,str(ROOT/"kyiv-air-alerts-grafana/scripts"))
    sys.path.insert(0,str(ROOT/"kyiv-air-alerts-grafana/tests/fixtures/parent_contract"))
    os.environ["CANONICAL_PARENT_CONTRACT_DIR"]=str(ROOT/"kyiv-air-alerts-grafana/tests/fixtures/parent_contract")
    os.environ["CANONICAL_PARENT_DB_BRANCH"]="offline-disposable-postgres-16"
    os.environ["ATTACK_EVENT_ORIGIN_COMMIT_SHA"]=os.environ.get("GITHUB_SHA","0"*40)
    import db_phase1_core as core
    import attack_event_canonical_persistence as p
    import live_parent_ordering as ordering
    import live_canonical_queue as queue
    UTC=timezone.utc
    cutoff=datetime(2026,10,7,19,5,tzinfo=UTC)
    now=datetime(2026,10,28,20,tzinfo=UTC)
    def ep(i):
        start=datetime(2026,10,17,tzinfo=UTC)+timedelta(minutes=40*i)
        end=start+timedelta(minutes=15)
        return {"city_key":"kyiv","episode_id":core.legacy_episode_id("kyiv",start,end),
                "alert_start":start.isoformat(),"alert_end":end.isoformat(),
                "checks":[{"label":"immediate","due_at":end.isoformat(),"checked_at":None}]}
    def parent(e):
        with psycopg.connect(DSN,autocommit=False) as c:
            ordering.ensure_canonical_parent(c,e)
    def rec(e):
        return p.build_episode_classification(e,[],origin=p._origin_context())
    def persist(e,expected=None):
        with psycopg.connect(DSN,autocommit=False) as c:
            return p.persist_episode_classification(c,rec(e),expected_tip=expected)

    # Actual two concurrent connections: advisory xact lock, exactly one CAS admission.
    case="two_concurrent_workers"
    try:
        e=ep(200)
        parent(e)
        initial=snapshot(case+"_before")
        def worker(_):
            try:
                return {"ok":True,"saved":persist(e,None)}
            except Exception as exc:
                return {"ok":False,"error":type(exc).__name__+":"+str(exc)}
        with ThreadPoolExecutor(max_workers=2) as pool:
            workers=list(pool.map(worker,[0,1]))
        final=snapshot(case+"_after")
        accepted=[r for r in workers if r["ok"]]
        rejected=[r for r in workers if not r["ok"]]
        check=(len(accepted)==1 and len(rejected)==1
               and "STALE_EXPECTED_CURRENT_CLASSIFICATION_TIP" in rejected[0]["error"]
               and final["attack_event_classifications"]==initial["attack_event_classifications"]+1
               and final["duplicate_classification_keys"]==0)
        result["scenarios"][case]={"status":"PASS" if check else "FAIL","before":initial,"after":final,"worker_outcomes":workers}
    except Exception as exc:
        result["scenarios"][case]={"status":"FAIL","error":str(exc)}

    # Stale expected current tip is a real on-database compare-and-swap rejection.
    case="stale_current_tip"
    try:
        e=ep(200)
        initial=snapshot(case+"_before")
        try:
            persist(e,"00000000-0000-0000-0000-000000000000")
            rejected=None
        except Exception as exc:
            rejected=type(exc).__name__+":"+str(exc)
        final=snapshot(case+"_after")
        ok=bool(rejected and "STALE_EXPECTED_CURRENT_CLASSIFICATION_TIP" in rejected and final==initial)
        result["scenarios"][case]={"status":"PASS" if ok else "FAIL","before":initial,"after":final,"exception":rejected}
    except Exception as exc:
        result["scenarios"][case]={"status":"FAIL","error":str(exc)}

    # Existing classification key cannot silently change the old verdict.
    case="classification_conflict"
    try:
        e=ep(201)
        parent(e)
        saved=persist(e,None)
        initial=snapshot(case+"_before")
        distorted=rec(e)
        distorted["verdict"]="NEEDS_REVIEW"
        try:
            with psycopg.connect(DSN,autocommit=False) as c:
                p.persist_episode_classification(c,distorted,expected_tip=saved["classification_uid"])
            rejected=None
        except Exception as exc:
            rejected=type(exc).__name__+":"+str(exc)
        final=snapshot(case+"_after")
        ok=bool(rejected and final==initial and "conflict" in rejected.lower())
        result["scenarios"][case]={"status":"PASS" if ok else "FAIL","before":initial,"after":final,"exception":rejected}
    except Exception as exc:
        result["scenarios"][case]={"status":"FAIL","error":str(exc)}

    # Simulate a process dying after a genuine SQL COMMIT but before journal ACK.
    case="post_commit_pre_ack"
    try:
        e=ep(202)
        parent(e)
        state={"cities":{"kyiv":{"episodes":[e]}}}
        queue.register_city(state,"kyiv",[e],cutoff)
        entries=queue.store(state)
        assert len(entries)==1
        work_id=next(iter(entries))
        for x in entries[work_id]["coverage_checks"].values():
            x.update({"status":"complete","completed_at":now.isoformat(),"reason":None})
        initial=snapshot(case+"_before")
        saved=persist(e,None)
        assert entries[work_id]["status"]=="pending"
        persisted=json.loads(json.dumps(state))
        with psycopg.connect(DSN,autocommit=False) as c:
            tips=queue.read_current_tips(c,cutoff)
            c.rollback()
        selection=queue.reconcile_and_select(persisted,tips=tips,candidates=[],cutoff=cutoff,max_episodes=10,now=now)
        final=snapshot(case+"_after")
        ok=(saved["classification_inserted"] and final["attack_event_classifications"]==initial["attack_event_classifications"]+1
            and len(selection["selected"])==0 and selection["db_committed_current"]==1
            and queue.store(persisted)[work_id]["status"]=="committed"
            and final["duplicate_classification_keys"]==0)
        result["scenarios"][case]={"status":"PASS" if ok else "FAIL","before":initial,"after":final,
                                   "pre_crash_status":entries[work_id]["status"],"retry_status":queue.store(persisted)[work_id]["status"]}
    except Exception as exc:
        result["scenarios"][case]={"status":"FAIL","error":str(exc)}

    # A legacy checked_at and missing WIP row cannot falsify a source certificate.
    case="pruned_state_legacy_checked_at"
    try:
        e=ep(203)
        e["checks"][0]["checked_at"]=now.isoformat()
        state={"cities":{"kyiv":{"episodes":[e]}}}
        queue.register_state(state,cutoff)
        key=next(iter(queue.store(state)))
        before_state=queue.store(state)[key]["coverage_checks"]["immediate"]
        state["cities"]["kyiv"]["episodes"]=[]
        restored=json.loads(json.dumps(state))
        selection=queue.reconcile_and_select(restored,tips={},candidates=[],cutoff=cutoff,max_episodes=10,now=now)
        after_state=queue.store(restored)[key]
        initial=snapshot(case+"_before")
        final=snapshot(case+"_after")
        ok=(before_state["status"]=="legacy_unverified" and
            after_state["status"]=="blocked_evidence" and selection["blocked_evidence"]==1
            and selection["total_registered"]==1 and selection["selected"]==[]
            and final==initial)
        result["scenarios"][case]={"status":"PASS" if ok else "FAIL","before":initial,"after":final,
                                   "journal_remaining":selection["total_registered"],"state":after_state["status"]}
    except Exception as exc:
        result["scenarios"][case]={"status":"FAIL","error":str(exc)}

    # Actual SQL exception after event stage, though no modeled positive event:
    # may prove atomic rollback, but not a positive attack-event rollback.
    case="event_stage_rollback"
    try:
        e=ep(204)
        parent(e)
        initial=snapshot(case+"_before")
        try:
            with psycopg.connect(DSN,autocommit=False) as c:
                p.persist_episode_classification(c,rec(e),expected_tip=None,fault_after="event")
            rejected=None
        except Exception as exc:
            rejected=type(exc).__name__+":"+str(exc)
        final=snapshot(case+"_after")
        proven=bool(rejected and "FORCED_PERSISTENCE_FAILURE_AFTER_EVENT" in rejected and final==initial)
        result["scenarios"][case]={"status":"NOT_PROVEN" if proven else "FAIL",
                                   "bounded_sql_rollback":proven,
                                   "reason":"Negative event-stage fault not positive attack_event insertion; positive-event rollback still required",
                                   "before":initial,"after":final,"exception":rejected}
    except Exception as exc:
        result["scenarios"][case]={"status":"FAIL","error":str(exc)}

except Exception as exc:
    result["errors"]=[str(exc)]
finally:
    out=OUT/"c3_rc3_fault_results.json"
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True,default=str)+"\n")
    print("C3_RC3_FAULT_RESULT="+json.dumps({
        "result":result["result"],"scenario_statuses":{k:v["status"] for k,v in result["scenarios"].items()},
        "baseline_monitor_main":result["baseline_monitor_main"].get("status"),
    },sort_keys=True))
# Fail closed: the full PG16 fault suite has NOT passed.
sys.exit(0 if all(x["status"]=="PASS" for x in result["scenarios"].values()) else 2)
