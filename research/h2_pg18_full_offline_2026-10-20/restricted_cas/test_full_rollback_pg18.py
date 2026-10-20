#!/usr/bin/env python3
"""Execute guarded synthetic PG18 ACL + ownership rollback against actual catalogs."""
from __future__ import annotations
import hashlib,json,os,subprocess,traceback
from pathlib import Path
import psycopg
from psycopg import sql
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
REF=ROOT/"reference/research/h2_pg18_revision_invariant_hardening_2026-10-19"
ROLE=ROOT/"research/h2_pg18_security_closure_2026-10-20/003_candidate_app_role_v3_atomic.sql"
GUARD=ROOT/"research/h2_neon_contract_role_pg18_2026-10-20/004_candidate_guard_owner.sql"
HARDEN=ROOT/"research/h2_pg18_migration_role_rollback_2026-10-20/005_guard_search_path_v2.sql"
VIEW=ROOT/"research/h2_pg18_migration_role_rollback_2026-10-20/current_view_fixture.sql"
ROLLBACK=HERE/"006_full_acl_rollback_candidate.sql"
COPY=os.environ.get("H2_COPY","A")
OUT=Path("/tmp/h2_full_rollback_"+COPY+".json")
report={"copy":COPY,"tested_commit":os.environ.get("GITHUB_SHA"),"checks":[],"cases":[],"errors":[],"sql_sha256":{}}
def check(k,okay,detail=None):
 report["checks"].append({"id":k,"pass":bool(okay),"detail":str(detail)[:340]})
 if not okay:raise AssertionError(k+" "+str(detail))
def conn(db="postgres"):
 return psycopg.connect(f"postgresql://h2_local:synthetic_only@127.0.0.1:5432/{db}",autocommit=True)
def q(db,statement,args=()):
 with conn(db) as c:
  with c.cursor() as cur:
   cur.execute(statement,args)
   return cur.fetchall() if cur.description else []
def exec_sql(db,path,expect=True,history=None,fault="none"):
 raw=Path(path).read_bytes()
 report["sql_sha256"][str(Path(path).relative_to(ROOT))]=hashlib.sha256(raw).hexdigest()
 args=["psql","-X","-v","ON_ERROR_STOP=1","-v","VERBOSITY=verbose",
       "-h","127.0.0.1","-U","h2_local","-d",db]
 if history is not None: args.extend(["-v","expected_history="+history,"-v","fault="+fault])
 args.extend(["-f",str(path)])
 result=subprocess.run(args,env={**os.environ,"PGPASSWORD":"synthetic_only"},
         capture_output=True,text=True,timeout=100)
 if expect and result.returncode:raise RuntimeError(Path(path).name+" "+result.stderr[-1300:])
 if not expect and not result.returncode:raise AssertionError("Unexpected SQL success: "+str(path))
 return result
def history(db):
 return q(db,"SELECT md5(coalesce(string_agg(to_jsonb(t)::text,'|' ORDER BY classification_uid::text),'')) FROM public.attack_event_classifications t")[0][0]
def snapshot(db):
 return {
 "schema_acl":q(db,"SELECT coalesce(nspacl::text,'NULL'),nspowner::regrole::text FROM pg_namespace WHERE nspname='public'"),
 "relations":q(db,"SELECT relname,relkind,relowner::regrole::text,coalesce(relacl::text,'NULL') FROM pg_class WHERE relnamespace='public'::regnamespace ORDER BY relname"),
 "col_acls":q(db,"SELECT c.relname,a.attname,coalesce(a.attacl::text,'NULL') FROM pg_attribute a JOIN pg_class c ON a.attrelid=c.oid WHERE c.relnamespace='public'::regnamespace AND a.attnum>0 AND NOT a.attisdropped ORDER BY c.relname,a.attname"),
 "functions":q(db,"SELECT proname,proowner::regrole::text,coalesce(proacl::text,'NULL'),coalesce(proconfig::text,'NULL') FROM pg_proc WHERE pronamespace='public'::regnamespace ORDER BY proname"),
 "defaults":q(db,"SELECT defaclrole::regrole::text,defaclnamespace,defaclobjtype,defaclacl::text FROM pg_default_acl ORDER BY 1,2,3"),
 "memberships":q(db,"SELECT roleid::regrole::text,member::regrole::text,grantor::regrole::text,admin_option FROM pg_auth_members ORDER BY 1,2,3"),
 "roles":q(db,"SELECT rolname,rolsuper,rolinherit,rolcanlogin,rolcreaterole,rolcreatedb,rolbypassrls FROM pg_roles WHERE rolname LIKE 'h2_%%' ORDER BY rolname"),
 "history":history(db),
 }
def effective_relation_acl(db):
 return q(db,"SELECT relname,coalesce(relacl,acldefault('r',relowner))::text FROM pg_class WHERE relnamespace='public'::regnamespace AND relkind IN ('r','v','p') ORDER BY relname")
def newdb(label):
 db="h2_"+COPY.lower()+"_rollback_"+label
 with conn() as c:c.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db)))
 exec_sql(db,REF/"observed_partial_schema.sql")
 exec_sql(db,VIEW)
 return db
def migrate(db):
 exec_sql(db,REF/"001_revision_invariants.sql")
 exec_sql(db,ROLE)
 exec_sql(db,GUARD)
 exec_sql(db,HARDEN)
def case(name,fn):
 try:fn();report["cases"].append({"id":name,"outcome":"PASS"})
 except Exception as exc:
  report["cases"].append({"id":name,"outcome":"FAIL"})
  report["errors"].append({"case":name,"error":repr(exc),"traceback":traceback.format_exc()[-1300:]})
def clean():
 db=newdb("clean");original=snapshot(db);before_eff=effective_relation_acl(db)
 check("baseline_no_migration_roles",not any(x[0] in ("h2_head_guard_test","h2_app_ingest_writer_test") for x in original["roles"]),original["roles"])
 migrate(db)
 check("migrated_catalog_differs",snapshot(db)!=original)
 res=exec_sql(db,ROLLBACK,history=original["history"])
 check("rollback_psql_success",res.returncode==0)
 after=snapshot(db)
 check("rollback_effective_relation_ACL",effective_relation_acl(db)==before_eff)
 delta=[k for k in original if original[k]!=after[k]]
 check("rollback_no_other_catalog_deviation",set(delta).issubset({"relations"}),delta)
 report["acl_physical_residual"]=delta
 check("rollback_raw_catalog_difference_recorded",delta==["relations"],delta)
 again=exec_sql(db,ROLLBACK,False,history=original["history"])
 check("repeat_rollback_fails_23514","23514" in again.stderr,again.stderr[-500:])
 check("repeat_preserves_catalog",snapshot(db)==original)
def synthetic_insert(db):
 with conn(db) as c:
  c.execute("""INSERT INTO public.attack_event_classifications(
  classification_key_version,classification_key,historical_episode_id,city_key,
  alert_type,alert_start_at,alert_end_at,verdict,is_event,qa_reasons_state,
  qa_reasons,classifier_blob_sha,classifier_methodology_version,
  normalization_version,evidence_set_sha256,binding_state,origin_repository,
  origin_provenance,origin_provenance_sha256,originating_frozen_case_id_state)
  VALUES ('attack-event-classification-key-v2',%s,%s,'kyiv','AIR',
  '2026-01-01T01:00:00Z','2026-01-01T02:00:00Z','NO_CONFIRMED_EVENT',
  false,'MATERIALIZED','[]'::jsonb,%s,'synthetic','synthetic',%s,'UNBOUND',
  'synthetic','{}'::jsonb,%s,'NOT_APPLICABLE')""",
  ('a'*64,'0'*24,'a'*40,'b'*64,'c'*64))
def changed_history():
 db=newdb("committed");base=history(db);migrate(db);synthetic_insert(db)
 before=snapshot(db)
 failure=exec_sql(db,ROLLBACK,False,history=base)
 check("committed_revisions_block_23514","23514" in failure.stderr and "H2_FULL_ROLLBACK_HISTORY_CHANGED" in failure.stderr,failure.stderr[-450:])
 check("committed_history_preserved",snapshot(db)==before)
def missing_object():
 db=newdb("missing");base=history(db);migrate(db)
 q(db,"DROP INDEX public.h2_classification_one_successor_uidx")
 before=snapshot(db)
 failure=exec_sql(db,ROLLBACK,False,history=base)
 check("missing_object_rejected_23514","23514" in failure.stderr,failure.stderr[-350:])
 check("missing_object_no_partial_rollback",snapshot(db)==before)
def injected_fault(label):
 db=newdb(label);base=history(db);migrate(db)
 before=snapshot(db)
 failure=exec_sql(db,ROLLBACK,False,history=base,fault=label)
 check(label+"_rollback_injection_23514","23514" in failure.stderr,failure.stderr[-600:])
 check(label+"_snapshot_unchanged",snapshot(db)==before)
def main():
 try:
  version=q("postgres","SHOW server_version")[0][0]
  check("PG18_6",version.startswith("18.6"),version)
  for name,fn in [
   ("positive_full_catalog_rollback",clean),
   ("post_migration_history_fail_closed",changed_history),
   ("missing_migration_object",missing_object),
   ("mid_acl_failure",lambda:injected_fault("acl")),
   ("mid_owner_failure",lambda:injected_fault("owner"))]:
   case(name,fn)
 except Exception as exc:report["errors"].append({"case":"setup","error":repr(exc)})
 finally:
  report["total"]=len(report["checks"]);report["passed"]=sum(x["pass"] for x in report["checks"])
  report["verdict"]=("FAIL" if report["total"]==0 or report["passed"]!=report["total"] or report["errors"] else ("PARTIAL" if report.get("acl_physical_residual") else "PASS"))
  OUT.write_text(json.dumps(report,indent=2,sort_keys=True,default=str)+"\n")
  print(json.dumps({"copy":COPY,"passed":report["passed"],"total":report["total"],"cases":report["cases"],"errors":report["errors"],"verdict":report["verdict"]}))
 if report["verdict"]!="PASS":raise SystemExit(1)
if __name__=="__main__":main()
