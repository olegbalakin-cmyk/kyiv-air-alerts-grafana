#!/usr/bin/env python3
"""Bounded executable PG18 role-v2 mutation counterexample and v3 atomic repair."""
import hashlib
import json
import os
from pathlib import Path
import psycopg
from psycopg import sql
import importlib.util
import subprocess
import traceback

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
OLD=REPO/'research/h2_pg18_migration_role_rollback_2026-10-20'
REF=REPO/'reference/research/h2_pg18_revision_invariant_hardening_2026-10-19'
CAND=REPO/'research/h2_neon_contract_role_pg18_2026-10-20'
COPY=os.environ.get("H2_COPY","A")
dsn="postgresql://h2_local:synthetic_only@127.0.0.1:5432/"
report={"copy":COPY,"commit":os.environ.get("GITHUB_SHA"),"checks":[],"errors":[],"source_sha256":{}}
def check(name,yes,details=None):
 report["checks"].append({"id":name,"pass":bool(yes),"detail":str(details)[:400] if details is not None else None})
 if not yes: raise AssertionError(f"{name}: {details}")
def conn(db="postgres",user="h2_local",password="synthetic_only"):
 return psycopg.connect(f"postgresql://{user}:{password}@127.0.0.1:5432/{db}",autocommit=True)
def query(c,s,params=()):
 with c.cursor() as cur:
  cur.execute(s,params)
  return cur.fetchall() if cur.description else []
def apply(db,filepath,expected_success=True):
 filepath=Path(filepath)
 raw=filepath.read_bytes()
 report["source_sha256"][str(filepath.relative_to(REPO))]=hashlib.sha256(raw).hexdigest()
 result=subprocess.run(["psql","-X","-v","ON_ERROR_STOP=1","-v","VERBOSITY=verbose",
     "-h","127.0.0.1","-U","h2_local","-d",db,"-f",str(filepath)],
     env={**os.environ,"PGPASSWORD":"synthetic_only"},capture_output=True,text=True,timeout=100)
 check(f"{db}:{filepath.name}:"+("ok" if expected_success else "fail"),
       (result.returncode==0)==expected_success,result.stderr[-250:])
 return result
def acl(c):
 return query(c,"""SELECT
  (SELECT coalesce(nspacl::text,'NULL') FROM pg_namespace WHERE nspname='public'),
  (SELECT coalesce(array_agg(relname||':'||coalesce(relacl::text,'NULL') ORDER BY relname)::text,'NULL')
   FROM pg_class WHERE relnamespace='public'::regnamespace AND relkind IN ('r','v')),
  (SELECT coalesce(array_agg(proname||':'||coalesce(proacl::text,'NULL') ORDER BY proname)::text,'NULL')
   FROM pg_proc WHERE pronamespace='public'::regnamespace),
  (SELECT coalesce(array_agg(rolname||':'||rolcanlogin::text ORDER BY rolname)::text,'NULL')
   FROM pg_roles WHERE rolname LIKE 'h2_%')
  """)[0]
def prepare(label):
 db="h2_"+COPY.lower()+"_v3_"+label
 with conn() as c: c.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db)))
 apply(db,REF/'observed_partial_schema.sql')
 apply(db,OLD/'current_view_fixture.sql')
 apply(db,REF/'001_revision_invariants.sql')
 # Original superuser-only guard setup is not claimed as a Neon role transfer.
 apply(db,CAND/'003_candidate_app_role.sql')
 apply(db,CAND/'004_candidate_guard_owner.sql')
 apply(db,OLD/'005_guard_search_path_v2.sql')
 return db
def scenario_public_create(label,filename,expect_atomic):
 db=prepare(label)
 with conn(db) as c:
  c.execute("GRANT CREATE ON SCHEMA public TO PUBLIC")
  before=acl(c)
  check(label+"_public_create",query(c,"SELECT EXISTS(SELECT 1 FROM pg_namespace n, LATERAL aclexplode(coalesce(n.nspacl,acldefault('n',n.nspowner))) a WHERE n.nspname='public' AND a.grantee=0 AND a.privilege_type='CREATE')")[0][0])
 result=apply(db,filename,False)
 check(label+"_sqlstate_42501",'42501' in result.stderr and 'H2_UNSAFE_PUBLIC_SCHEMA_CREATE' in result.stderr,result.stderr[-300:])
 with conn(db) as c:
  after=acl(c)
  same=before==after
  if expect_atomic:
   check(label+"_acl_and_roles_unchanged",same,{"before":before,"after":after})
  else:
   check(label+"_detects_v2_partial_side_effect",not same,{"before":before,"after":after})
 return db
def positive():
 db=prepare('positive')
 with conn(db) as c:
  check("public_create_absent",not query(c,"SELECT EXISTS(SELECT 1 FROM pg_namespace n, LATERAL aclexplode(coalesce(n.nspacl,acldefault('n',n.nspowner))) a WHERE n.nspname='public' AND a.grantee=0 AND a.privilege_type='CREATE')")[0][0])
 apply(db,ROOT/'003_candidate_app_role_v3_atomic.sql')
 with conn(db) as c:
  check("v3_writer_no_create",not query(c,"SELECT has_schema_privilege('h2_app_ingest_writer_test','public','CREATE')")[0][0])
  check("v3_writer_not_guard",not query(c,"SELECT pg_has_role('h2_app_ingest_writer_test','h2_head_guard_test','MEMBER')")[0][0])
  check("v3_writer_classification_insert",query(c,"SELECT has_table_privilege('h2_app_ingest_writer_test','public.attack_event_classifications','INSERT')")[0][0])
  check("v3_writer_history_update_denied",not query(c,"SELECT has_table_privilege('h2_app_ingest_writer_test','public.attack_event_classifications','UPDATE')")[0][0])
  check("v3_writer_heads_update_denied",not query(c,"SELECT has_table_privilege('h2_app_ingest_writer_test','public.h2_classification_heads','UPDATE')")[0][0])
  check("v3_writer_events_insert",query(c,"SELECT has_table_privilege('h2_app_ingest_writer_test','public.attack_events','INSERT')")[0][0])
  check("v3_writer_events_column_update",query(c,"SELECT has_column_privilege('h2_app_ingest_writer_test','public.attack_events','event_status','UPDATE')")[0][0])
  check("v3_writer_events_unrelated_update_denied",not query(c,"SELECT has_column_privilege('h2_app_ingest_writer_test','public.attack_events','classification_key','UPDATE')")[0][0] if query(c,"SELECT EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='attack_events' AND column_name='classification_key')")[0][0] else True)
  check("v3_public_create_unchanged",not query(c,"SELECT EXISTS(SELECT 1 FROM pg_namespace n, LATERAL aclexplode(coalesce(n.nspacl,acldefault('n',n.nspowner))) a WHERE n.nspname='public' AND a.grantee=0 AND a.privilege_type='CREATE')")[0][0])
 with conn(db,'h2_app_ingest_writer_test','synthetic_only_local_role') as c:
  for name,stmt in [
   ("forbid_create","CREATE TABLE public.v3_forbidden(x int)"),
   ("forbid_update","UPDATE public.attack_event_classifications SET origin_repository='tamper'"),
   ("forbid_heads","UPDATE public.h2_classification_heads SET changed_at=now()"),
   ("forbid_set_role","SET ROLE h2_head_guard_test")]:
   try:
    with c.transaction():query(c,stmt)
    code="ALLOWED"
   except psycopg.Error as exc:code=exc.sqlstate
   check(name,code in ("42501","0LP01"),code)
def main():
 try:
  with conn() as c:check("postgres_18",query(c,"SHOW server_version")[0][0].split('.')[0]=="18")
  scenario_public_create("v2",OLD/"003_candidate_app_role_v2.sql",False)
  scenario_public_create("v3",ROOT/'003_candidate_app_role_v3_atomic.sql',True)
  positive()
 except Exception as exc: report["errors"].append({"error":repr(exc),"traceback":traceback.format_exc()[-2500:]})
 finally:
  report["total"]=len(report["checks"])
  report["passed"]=sum(x["pass"] for x in report["checks"])
  report["verdict"]="PASS" if not report["errors"] and report["passed"]==report["total"] else "FAIL"
  Path("/tmp/h2_v3_"+COPY+".json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
  print(json.dumps({"copy":COPY,"verdict":report["verdict"],"passed":report["passed"],"total":report["total"],"errors":report["errors"]}))
 if report["verdict"]!="PASS":raise SystemExit(1)
if __name__=="__main__":main()
