#!/usr/bin/env python3
"""Isolated execution checks; reports failures rather than treating them as passes."""
import hashlib, json, os, subprocess, sys, traceback
from pathlib import Path
import psycopg
from psycopg import sql
ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
REFERENCE=REPO/'reference'
BASE=REFERENCE/'research/h2_pg18_revision_invariant_hardening_2026-10-19'
CAND=REPO/'research/h2_neon_contract_role_pg18_2026-10-20'
COPY=os.environ.get('H2_COPY','A')
ADMIN='postgresql://h2_local:synthetic_only@127.0.0.1:5432/postgres'
DATABASE='h2_'+COPY.lower()+'_migration'
def con(db=DATABASE,user='h2_local',password='synthetic_only'):
 return psycopg.connect(f'postgresql://{user}:{password}@127.0.0.1:5432/{db}',autocommit=True)
report={'copy':COPY,'git_commit':os.environ.get('GITHUB_SHA'),'checks':[],'cases':[],'source_sha256':{},'errors':[]}
def ck(name,ok,detail=None):
 report['checks'].append({'id':name,'pass':bool(ok),'detail':str(detail)[:280] if detail is not None else None})
 if not ok:raise AssertionError(name+': '+str(detail))
def q(c,s,args=()):
 with c.cursor() as cur:
  cur.execute(s,args)
  return cur.fetchall() if cur.description else []
def execfile(path,db=DATABASE,valid=True):
 p=Path(path)
 raw=p.read_bytes()
 report['source_sha256'][str(p.relative_to(REPO))]=hashlib.sha256(raw).hexdigest()
 e=dict(os.environ,PGPASSWORD='synthetic_only')
 cp=subprocess.run(['psql','-X','-v','ON_ERROR_STOP=1','-h','127.0.0.1','-U','h2_local','-d',db,'-f',str(p)],capture_output=True,text=True,env=e,timeout=120)
 if valid:ck('psql:'+p.name+':'+db,cp.returncode==0,cp.stderr[-350:])
 return cp
def case(name,fn):
 try:fn();report['cases'].append({'id':name,'status':'PASS'})
 except Exception as exc:
  report['cases'].append({'id':name,'status':'FAIL'})
  report['errors'].append({'id':name,'type':type(exc).__name__,'error':str(exc)[:450],'traceback':traceback.format_exc()[-800:]})
def mkrow(c,tag,predecessor=None,city='kyiv',episode='0'*24):
 import hashlib
 key=hashlib.sha256((tag+city+episode).encode()).hexdigest()
 with c.cursor() as cur:
  cur.execute("""INSERT INTO public.attack_event_classifications(
 classification_key_version,classification_key,historical_episode_id,city_key,
 alert_type,alert_start_at,alert_end_at,verdict,is_event,qa_reasons_state,
 qa_reasons,classifier_blob_sha,classifier_methodology_version,
 normalization_version,evidence_set_sha256,binding_state,origin_repository,
 origin_provenance,origin_provenance_sha256,originating_frozen_case_id_state,
 supersedes_classification_uid)
 VALUES ('attack-event-classification-key-v2',%s,%s,%s,'AIR',
 '2026-01-01T01:00:00Z','2026-01-01T02:00:00Z','NO_CONFIRMED_EVENT',
 false,'MATERIALIZED','[]'::jsonb,%s,'synthetic','synthetic',%s,'UNBOUND',
 'synthetic','{}'::jsonb,%s,'NOT_APPLICABLE',%s)
 RETURNING classification_uid""",
 (key,episode,city,'a'*40,'b'*64,'c'*64,predecessor))
  return cur.fetchone()[0]
def footprint(c):
 return q(c,"""SELECT coalesce(jsonb_agg(to_jsonb(c) ORDER BY c.classification_uid),'[]'::jsonb)::text
 FROM public.attack_event_classifications c""")[0][0]
def objects(c):
 return q(c,"""SELECT
 to_regclass('public.h2_classification_heads') IS NOT NULL,
 to_regclass('public.h2_classification_one_root_uidx') IS NOT NULL,
 to_regclass('public.h2_classification_one_successor_uidx') IS NOT NULL,
 to_regprocedure('public.h2_enforce_revision_head()') IS NOT NULL,
 EXISTS(SELECT 1 FROM pg_trigger WHERE tgname='h2_revision_head_after_insert' AND NOT tgisinternal)
 """)[0]
def setup():
 with con('postgres') as c:
  ck('server_major_18',q(c,'SHOW server_version')[0][0].split('.')[0]=='18')
  c.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(DATABASE)))
 execfile(BASE/'observed_partial_schema.sql')
 # The exact 18-column view is an acknowledged reconstruction adaptation.
 execfile(REPO/'research/h2_neon_contract_role_pg18_2026-10-20/current_view_fixture.sql')
def clean():
 with con() as c:
  original=objects(c)
  ck('clean_before_objects',original==(False,False,False,False,False),original)
  root=mkrow(c,'cleanroot')
  mkrow(c,'cleanchild',root)
  before=footprint(c)
 execfile(BASE/'001_revision_invariants.sql')
 with con() as c:
  ck('clean_migration_objects',objects(c)==(True,True,True,True,True),objects(c))
  ck('clean_migration_rows_immutable',footprint(c)==before)
  ck('clean_backfilled_tip',q(c,'SELECT count(*) FROM public.h2_classification_heads')[0][0]==1)
  second=execfile(BASE/'001_revision_invariants.sql',valid=False)
  ck('repeat_migration_rejected',second.returncode!=0,second.stderr[-300:])
  ck('repeat_kept_objects',objects(c)==(True,True,True,True,True))
def invalid_history():
 # Construct contradictory logical roots BEFORE 001, confirm atomic rejection.
 name='h2_'+COPY.lower()+'_invalid'
 with con('postgres') as c:c.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
 execfile(BASE/'observed_partial_schema.sql',name)
 with con(name) as c:
  mkrow(c,'invalidone');mkrow(c,'invalidtwo')
  before=footprint(c)
 attempt=execfile(BASE/'001_revision_invariants.sql',name,valid=False)
 ck('invalid_migration_rejected',attempt.returncode!=0,attempt.stderr[-300:])
 with con(name) as c:
  ck('invalid_schema_rolled_back',objects(c)==(False,False,False,False,False),objects(c))
  ck('invalid_historical_rows_identical',footprint(c)==before)
def roles():
 # Original 003 and 004, then tightened research candidates, without live credentials.
 execfile(CAND/'003_candidate_app_role.sql')
 execfile(CAND/'004_candidate_guard_owner.sql')
 execfile(ROOT/'005_guard_search_path_v2.sql')
 with con() as c:
  p=q(c,"""SELECT r.rolsuper,r.rolcreatedb,r.rolcreaterole,r.rolreplication,r.rolbypassrls
 FROM pg_roles r WHERE r.rolname='h2_app_ingest_writer_test'""")[0]
  ck('writer_has_no_special_role_flags',p==(False,False,False,False,False),p)
  ck('guard_nonlogin',q(c,"SELECT rolcanlogin FROM pg_roles WHERE rolname='h2_head_guard_test'")[0][0]==False)
  ck('guard_is_function_owner',q(c,"SELECT pg_get_userbyid(proowner) FROM pg_proc WHERE oid='public.h2_enforce_revision_head()'::regprocedure")[0][0]=='h2_head_guard_test')
  ck('guard_temp_explicit',q(c,"SELECT proconfig::text FROM pg_proc WHERE oid='public.h2_enforce_revision_head()'::regprocedure")[0][0].find('pg_temp')>=0)
 with con(user='h2_app_ingest_writer_test',password='synthetic_only_local_role') as w:
  ck('writer_can_read_classification',len(q(w,'SELECT classification_uid FROM public.attack_event_classifications'))==2)
  ck('writer_can_read_checkpoint_view',q(w,"SELECT count(*) FROM public.current_ingestion_checkpoints")[0][0]==0)
  for tag,statement in [('historical_update',"UPDATE public.attack_event_classifications SET origin_repository='tamper'"),('historical_delete','DELETE FROM public.attack_event_classifications'),('history_truncate','TRUNCATE public.attack_event_classifications'),('heads_update','UPDATE public.h2_classification_heads SET changed_at=now()'),('ddl','ALTER TABLE public.attack_event_classifications ADD COLUMN evil int'),('set_role','SET ROLE h2_head_guard_test'),('create','CREATE TABLE public.h2_writer_unauthorized(x int)')]:
   try:
    with w.transaction():q(w,statement)
    result='ALLOWED'
   except psycopg.Error as exc:result=exc.sqlstate
   ck('deny_'+tag,result in ('42501','0LP01'),result)
  tip=q(w,'SELECT tip_classification_uid FROM public.h2_classification_heads')[0][0]
  nextuid=mkrow(w,'legitimate-restricted-writer',tip)
  ck('legitimate_writer_triggers_cas',q(w,'SELECT tip_classification_uid FROM public.h2_classification_heads')[0][0]==nextuid)
  ck('writer_no_owner_membership',q(w,"SELECT pg_has_role(current_user,'h2_head_guard_test','MEMBER')")[0][0]==False)
def rollback():
 with con() as c:before=footprint(c)
 bad=None
 with con() as c:
  c.execute("UPDATE public.h2_classification_heads SET tip_classification_uid=(SELECT classification_uid FROM public.attack_event_classifications ORDER BY created_at LIMIT 1)")
 bad=execfile(ROOT/'rollback_revision_v2.sql',valid=False)
 ck('rollback_refuses_inconsistent_head',bad.returncode!=0,bad.stderr[-300:])
 with con() as c:
  c.execute("""UPDATE public.h2_classification_heads h SET tip_classification_uid=(
 SELECT c.classification_uid FROM public.attack_event_classifications c
 WHERE NOT EXISTS(SELECT 1 FROM public.attack_event_classifications x
 WHERE x.supersedes_classification_uid=c.classification_uid) LIMIT 1)""")
 execfile(ROOT/'rollback_revision_v2.sql')
 with con() as c:
  ck('rollback_removed_all_revision_objects',objects(c)==(False,False,False,False,False),objects(c))
  ck('rollback_preserved_history',footprint(c)==before)
  ck('rollback_did_not_restore_acl',q(c,"SELECT has_table_privilege('h2_app_ingest_writer_test','public.attack_event_classifications','INSERT')")[0][0] is True)
def main():
 try:
  case('setup',setup)
  if report['cases'][-1]['status']=='PASS':
   for name,fn in [('clean_migration',clean),('bad_preconditions',invalid_history),('roles_guard_owner',roles),('rollback',rollback)]:
    if report['errors']:break
    case(name,fn)
 finally:
  report['total']=len(report['checks']);report['passed']=sum(x['pass'] for x in report['checks'])
  report['verdict']='PASS' if not report['errors'] and report['total']>0 else 'FAIL'
  p=Path('/tmp/h2_migration_'+COPY+'.json');p.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
  print(json.dumps({'copy':COPY,'total':report['total'],'passed':report['passed'],'verdict':report['verdict'],'errors':report['errors']}))
 if report['verdict']!='PASS':sys.exit(1)
if __name__=='__main__':main()
