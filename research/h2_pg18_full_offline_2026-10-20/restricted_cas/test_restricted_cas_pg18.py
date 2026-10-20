#!/usr/bin/env python3
"""Synthetic PostgreSQL 18.6: accepted real expected-tip writer with v3 application role.

The canonical writer, tip snapshot, monitor.main(), and test fixture are loaded
from the exact accepted reference commit. Only external publishers are mocked
by the accepted monitor-main harness; no Neon or real source polling occurs.
"""
from __future__ import annotations
import concurrent.futures
import hashlib
import json
import os
import subprocess
import sys
import threading
import traceback
from pathlib import Path
import psycopg

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
REF = REPO / "reference"
TESTS = REF / "research/h2_pg18_mutation_operational_writer_2026-10-19"
APP = REF / "kyiv-air-alerts-grafana/scripts"
sys.path[:0] = [str(APP), str(TESTS)]
import test_mutation_operational as baseline
import test_expected_tip_e2e as e2e
import attack_event_canonical_persistence as writer
import attack_event_tip_snapshot as snapshots

COPY = os.environ.get("H2_COPY", "A")
OUT = Path("/tmp/h2_restricted_cas_" + COPY + ".json")
OWNER = os.environ["H2_PG18_OWNER_DSN"]
APP_ROLE = "h2_app_ingest_writer_test"
APP_DSN = "postgresql://h2_app_ingest_writer_test:synthetic_only_local_role@127.0.0.1:5432/postgres"
report = e2e.report
report.update({"schema":"h2-restricted-real-cas-pg18-v1", "tested_commit":os.environ.get("GITHUB_SHA"),
 "reference_commit":"3c1cf86ac0eaee1b1de246022c19acbb58037948",
 "restricted_login":APP_ROLE,"database_version":None,
 "executed_sql_sha256":{},"real_components":[
 "attack_event_canonical_persistence","attack_event_tip_snapshot","monitor_explosion_candidates.main",
 "psycopg3","PostgreSQL 18.6 trigger/CAS","real two-session concurrency"],
 "stubbed_interfaces":["live external publisher HTTP","local-only synthetic monitor inputs and JSON file sink"]})

def check(name, ok, detail=None):
    e2e.check(name,ok,detail)

def apply(db, path):
    path=Path(path)
    raw=path.read_bytes()
    rel=str(path.relative_to(REPO))
    report["executed_sql_sha256"][rel]=hashlib.sha256(raw).hexdigest()
    done=subprocess.run(
      ["psql","-X","-v","ON_ERROR_STOP=1","-v","VERBOSITY=verbose",
       "-h","127.0.0.1","-U","h2_local","-d",db,"-f",str(path)],
      env={**os.environ,"PGPASSWORD":"synthetic_only"},capture_output=True,text=True,timeout=90)
    if done.returncode:
        raise RuntimeError("SQL setup failure "+rel+": "+done.stderr[-1600:])

original_new_database=baseline.new_database
def restricted_database(label):
    db=original_new_database("restricted_"+label)
    # The accepted reduced schema omits the reconstructed 18-column view.\n    # Install the previously tested exact synthetic view fixture before v3 grants.\n    apply(db,REPO/"research/h2_pg18_migration_role_rollback_2026-10-20/current_view_fixture.sql")\n    apply(db,REPO/"research/h2_pg18_security_closure_2026-10-20/003_candidate_app_role_v3_atomic.sql")
    apply(db,REPO/"research/h2_neon_contract_role_pg18_2026-10-20/004_candidate_guard_owner.sql")
    apply(db,REPO/"research/h2_pg18_migration_role_rollback_2026-10-20/005_guard_search_path_v2.sql")
    return db

# The original fixture creates an *unused* original writer login. Every
# application write in this suite uses the new, separate v3 non-owner login.
baseline.new_database=restricted_database
baseline.WRITER=APP_DSN

def sql(c, query, args=()):
    return baseline.query(c,query,args)

def privileges_and_persistence():
    db=restricted_database("privilege")
    with baseline.connect(APP_DSN,db) as c:
        ident=sql(c,"SELECT session_user,current_user,current_role")[0]
        check("v3_actual_login_and_role",ident==(APP_ROLE,APP_ROLE,APP_ROLE),ident)
        attrs=sql(c,"SELECT rolsuper,rolinherit,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname=current_user")[0]
        check("v3_no_superuser_inheritance_or_administration",attrs==(False,False,False,False,False,False),attrs)
        check("v3_not_guard_member",not sql(c,"SELECT pg_has_role(current_user,'h2_head_guard_test','MEMBER')")[0][0])
        check("v3_not_database_owner",not sql(c,"SELECT pg_has_role(current_user,'h2_local','MEMBER')")[0][0])
        check("v3_function_search_path",str(sql(c,"SELECT proconfig FROM pg_proc WHERE oid='public.h2_enforce_revision_head()'::regprocedure")[0][0]).find("pg_temp")>=0)
        for name,cmd in [
          ("deny_history_update","UPDATE public.attack_event_classifications SET origin_repository='forbidden'"),
          ("deny_history_delete","DELETE FROM public.attack_event_classifications"),
          ("deny_history_truncate","TRUNCATE public.attack_event_classifications"),
          ("deny_head_update","UPDATE public.h2_classification_heads SET changed_at=now()"),
          ("deny_head_insert","INSERT INTO public.h2_classification_heads(city_key) VALUES ('bad')"),
          ("deny_disable_trigger","ALTER TABLE public.attack_event_classifications DISABLE TRIGGER h2_revision_head_after_insert"),
          ("deny_guard_function_ddl","ALTER FUNCTION public.h2_enforce_revision_head() RESET ALL"),
          ("deny_schema_ddl","CREATE TABLE public.h2_app_forbidden(x int)"),
          ("deny_guard_set_role","SET ROLE h2_head_guard_test"),
          ("deny_grant_owner","GRANT h2_local TO h2_app_ingest_writer_test"),
          ("deny_role_escalation","ALTER ROLE h2_app_ingest_writer_test CREATEROLE"),
        ]:
            try:
                with c.transaction(): sql(c,cmd)
                observed="ALLOWED"
            except psycopg.Error as exc:
                observed=exc.sqlstate
            check(name,observed in ("42501","0LP01"),observed)
    ep,attempt=e2e.item()
    auth=e2e.snapshot(db,ep,attempt)
    rec=e2e.classification("role_integrity")
    with baseline.connect(APP_DSN,db) as c:
        before=baseline.fingerprint(c)
        result=writer.persist_episode_classification(c,rec,expected_snapshot=auth)
        check("v3_real_writer_committed",result["commit_state"]=="COMMITTED",result)
    with baseline.connect(OWNER,db) as read:
        rowcounts=e2e.counts(db)
        check("v3_classification_event_source_and_head",rowcounts==(1,1,1,1),rowcounts)
        check("v3_history_fingerprint_changed_only_by_append",before!=baseline.fingerprint(read))
        check("v3_head_unique",baseline.integrity_anomalies(read)==[],baseline.integrity_anomalies(read))
        check("v3_event_binds_classification",bool(sql(read,
          "SELECT 1 FROM public.attack_events WHERE current_classification_uid=%s",
          (result["classification_uid"],))))
        check("v3_source_binds_classification",bool(sql(read,
          "SELECT 1 FROM public.attack_event_sources WHERE classification_uid=%s",
          (result["classification_uid"],))))
    with baseline.connect(APP_DSN,db) as c:
        again=writer.persist_episode_classification(c,rec,expected_snapshot=auth)
        check("v3_semantic_retry_durable",again["commit_state"]=="COMMITTED" and not again["classification_inserted"],again)
    check("v3_semantic_retry_no_row_growth",e2e.counts(db)==(1,1,1,1),e2e.counts(db))

def concurrency_full_side_effects():
    db=restricted_database("concurrency")
    ep,ch=e2e.item()
    initial=e2e.snapshot(db,ep,ch)
    b=threading.Barrier(2)
    def attempt(tag):
        b.wait(timeout=20)
        try:
            outcome=e2e.put(db,e2e.classification(tag),initial)
            return {"tag":tag,"state":outcome["commit_state"]}
        except writer.PersistenceContractError as exc:
            return {"tag":tag,"failure":str(exc)}
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(attempt,["conflicting_left","conflicting_right"]))
    accepted=[x for x in results if x.get("state")=="COMMITTED"]
    rejected=[x for x in results if "STALE_EXPECTED_TIP" in x.get("failure","")]
    check("v3_two_sessions_one_commit_one_stale",len(accepted)==len(rejected)==1,results)
    with baseline.connect(OWNER,db) as c:
        cnt=e2e.counts(db)
        check("v3_stale_no_any_committed_side_effects",cnt==(1,1,1,1),cnt)
        check("v3_concurrent_single_tip",baseline.integrity_anomalies(c)==[])
        check("v3_concurrent_role_readback",str(sql(c,"SHOW server_version")[0][0]).startswith("18.6"))

def caller_owned_outer_commit():
    db=restricted_database("external_commit")
    ep,ch=e2e.item()
    auth=e2e.snapshot(db,ep,ch)
    c=baseline.connect(APP_DSN,db,autocommit=False)
    try:
        c.execute("SELECT 1")
        pending=writer.persist_episode_classification(c,e2e.classification("pending"),expected_snapshot=auth)
        check("v3_outer_does_not_claim_commit",pending["commit_state"]=="CALLER_TRANSACTION_PENDING",pending)
        check("v3_outer_not_yet_visible",e2e.counts(db)==(0,0,0,0),e2e.counts(db))
        c.commit()
        check("v3_outer_caller_commit_readback",e2e.counts(db)==(1,1,1,1),e2e.counts(db))
        with baseline.connect(APP_DSN,db) as fresh:
            check("v3_after_reconnect_tip",str(e2e.tip(db)["classification_uid"])==str(pending["classification_uid"]))
    finally:
        c.close()

def main():
    fatal=None
    try:
        with baseline.connect(OWNER) as c:
            version=str(sql(c,"SHOW server_version")[0][0])
            report["database_version"]=version
            check("postgres_version_exact_18_6",version.startswith("18.6"),version)
        for name,fn in [
            ("v3_restricted_privileges_and_actual_write",privileges_and_persistence),
            ("v3_expected_tip_initial_revision_retry",e2e.first_revision_and_idempotency),
            ("v3_bad_authoritative_snapshots",e2e.bad_authority),
            ("v3_genuine_competing_sessions",concurrency_full_side_effects),
            ("v3_fault_stage_rollback",e2e.rollback_faults),
            ("v3_external_transaction_rollback",e2e.transaction_contract),
            ("v3_external_transaction_commit",caller_owned_outer_commit),
            ("v3_batch_independent_commit_readback",e2e.batch_readback),
            ("v3_expected_tip_bypass_negative_control",e2e.negative_control),
            ("v3_real_monitor_main_stale_injection",e2e.real_monitor_main),
        ]: e2e.case(name,fn)
    except Exception as exc:
        fatal=repr(exc)
        report["errors"].append({"case":"main_setup","error":fatal,"traceback":traceback.format_exc()[-2500:]})
    finally:
        report["total"]=len(report["assertions"])
        report["passed"]=sum(bool(x["pass"]) for x in report["assertions"])
        report["verdict"]="PASS" if report["total"]>0 and report["total"]==report["passed"] and not report["errors"] else "FAIL"
        OUT.write_text(json.dumps(report,indent=2,sort_keys=True,default=str)+"\n")
        print(json.dumps({"copy":COPY,"passed":report["passed"],"total":report["total"],"errors":report["errors"],"verdict":report["verdict"]}))
    if report["verdict"]!="PASS":raise SystemExit(1)

if __name__=="__main__":main()
