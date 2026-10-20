#!/usr/bin/env python3
"""Synthetic PG18.6 selected ACL after-rollback and late-error transaction probe."""
import os,sys,json,subprocess,hashlib,traceback
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"h2_rollback_adversarial_2026-10-20"))
from harness import *
rep={"copy":COPY,"commit":os.environ.get("GITHUB_SHA"),"version":query("postgres","SHOW server_version")[0][0],"cases":[]}
assert rep["version"].startswith("18.6")
ns.roles()
def dump(db):
 p=subprocess.run(["pg_dump","-h","127.0.0.1","-U","h2_local","--schema-only","--no-owner","-d",db],env={**os.environ,"PGPASSWORD":"synthetic_only"},capture_output=True,timeout=40)
 if p.returncode:raise RuntimeError(p.stderr.decode()[-700:])
 return {"sha256":hashlib.sha256(p.stdout).hexdigest(),"bytes":len(p.stdout),"text":p.stdout.decode()}
def record(case,valid,details):
 rep["cases"].append({"id":case,"status":"PASS" if valid else "FAIL","details":details})
 print(json.dumps(rep["cases"][-1],default=str),flush=True)
 if not valid:raise AssertionError(case)
try:
 # Untouched synthetic baseline vs migrated and clean rollback of another same-stage fixture.
 ctl=new("aclcontrol",stage="raw")
 mutated=new("aclrollback",stage="installed")
 assert temp_rollback(mutated,historical(mutated))=="00000"
 original=snapshot(ctl);rolled=snapshot(mutated)
 original_dump=dump(ctl);rolled_dump=dump(mutated)
 rel1={x[0]:x for x in original["relations"]};rel2={x[0]:x for x in rolled["relations"]}
 delta=[k for k in rel1.keys()|rel2.keys() if rel1.get(k)!=rel2.get(k)]
 record("raw_catalog_residual_identified",bool(delta),{"changed_relations":delta})
 record("history_stable",original["history"]==rolled["history"],{"before":original["history"],"after":rolled["history"]})
 record("pg_dump_actual",True,{"control_sha256":original_dump["sha256"],"rollback_sha256":rolled_dump["sha256"],"bytes":[original_dump["bytes"],rolled_dump["bytes"]],"equal":original_dump["sha256"]==rolled_dump["sha256"],"note":"Dump equality is NOT assumed; differences are preserved, not accepted as equivalent"})
 for i,stmt in enumerate(["GRANT SELECT ON public.alert_episodes TO h2_unrelated_test",
                         "REVOKE SELECT ON public.alert_episodes FROM h2_unrelated_test",
                         "GRANT UPDATE ON public.alert_episodes TO h2_unrelated_test",
                         "REVOKE UPDATE ON public.alert_episodes FROM h2_unrelated_test"]):
  query(ctl,stmt);query(mutated,stmt)
  a=query(ctl,"SELECT has_table_privilege('h2_unrelated_test','public.alert_episodes','SELECT'),has_table_privilege('h2_unrelated_test','public.alert_episodes','UPDATE')")
  b=query(mutated,"SELECT has_table_privilege('h2_unrelated_test','public.alert_episodes','SELECT'),has_table_privilege('h2_unrelated_test','public.alert_episodes','UPDATE')")
  record("future_grant_revoke_"+str(i+1),a==b,{"control":a,"rollback":b})
 # Fail intentionally after multiple separate DDL ACL writes within one transaction.
 before=snapshot(mutated)
 with conn(mutated,autocommit=False) as c:
  try:
   c.execute("GRANT SELECT ON public.alert_episodes TO h2_unrelated_test")
   c.execute("GRANT UPDATE ON public.ingestion_runs TO h2_unrelated_test")
   c.execute("GRANT USAGE ON SCHEMA public TO h2_unrelated_test")
   staged=c.execute("SELECT has_table_privilege('h2_unrelated_test','public.alert_episodes','SELECT'),has_table_privilege('h2_unrelated_test','public.ingestion_runs','UPDATE')").fetchone()
   assert staged==(True,True),staged
   c.execute("DO $$ BEGIN RAISE EXCEPTION 'H2_LATE_ACL_FAULT' USING ERRCODE='23514'; END $$")
   raise AssertionError("controlled SQL failure unexpectedly returned")
  except psycopg.Error as e:
   sqlstate=e.sqlstate
   c.rollback()
 after=snapshot(mutated)
 record("late_three_changes_transaction_abort",sqlstate=="23514" and before==after,{"sqlstate":sqlstate,"staged":staged,"before_equal_after":before==after})
except Exception as e:
 rep["error"]=repr(e);rep["trace"]=traceback.format_exc()[-1500:]
finally:
 rep["verdict"]="PARTIAL" if not rep.get("error") else "FAIL"
 Path("/tmp/h2_acl_"+COPY+".json").write_text(json.dumps(rep,indent=2,default=str)+"\n")
 print(rep["verdict"],flush=True)
if rep["verdict"]=="FAIL":raise SystemExit(1)
