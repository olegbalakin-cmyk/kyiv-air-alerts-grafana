#!/usr/bin/env python3
"""Bounded synthetic PostgreSQL 18.6 non-superuser role and ACL proof; failures are fatal."""
import hashlib,json,os,subprocess,re,traceback
from pathlib import Path
import psycopg
from psycopg import sql
P=Path(__file__).resolve().parent; R=P.parents[1]; COPY=os.environ.get('H2_COPY','A')
UP=P/'007_non_superuser_guard_transfer.sql'; DOWN=P/'008_non_superuser_acl_rollback.sql'
REF=R/'reference/research/h2_pg18_revision_invariant_hardening_2026-10-19'
ROLE=R/'research/h2_pg18_security_closure_2026-10-20/003_candidate_app_role_v3_atomic.sql'
OUT=Path('/tmp/h2_nonsuperuser_'+COPY+'.json')
rep={'copy':COPY,'sha':os.environ.get('GITHUB_SHA'),'checks':[],'cases':[],'errors':[],
     'sources':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (UP,DOWN,ROLE)},
     'raw_catalog_equivalence':'UNVERIFIED','effective_privilege_equivalence':'UNVERIFIED'}
def ck(k,ok,detail=''):
 rep['checks'].append({'id':k,'passed':bool(ok),'detail':str(detail)[:300]})
 if not ok:raise AssertionError(k+' '+str(detail))
def dbconn(db='postgres',name='h2_local',pw='synthetic_only'):
 return psycopg.connect(f'postgresql://{name}:{pw}@127.0.0.1:5432/{db}',autocommit=True)
def q(db,stmt,args=(),name='h2_local',pw='synthetic_only'):
 with dbconn(db,name,pw) as c:
  cur=c.execute(stmt,args);return cur.fetchall() if cur.description else []
def run(db,path,role='h2_local',history=None,fault='none',ok=True):
 pwd='synthetic_only' if role=='h2_local' else 'synthetic_migrator_only'
 cmd=['psql','-X','-v','ON_ERROR_STOP=1','-v','VERBOSITY=verbose','-h','127.0.0.1','-U',role,'-d',db]
 if path in (UP,DOWN):cmd+=['-v','fault='+fault]
 if history is not None:cmd+=['-v','expected_history='+history]
 x=subprocess.run(cmd+['-f',str(path)],env={**os.environ,'PGPASSWORD':pwd},capture_output=True,text=True,timeout=100)
 mt=re.search(r'ERROR:\s+([0-9A-Z]{5}):',x.stderr);state=mt.group(1) if mt else ('00000' if x.returncode==0 else 'UNKNOWN')
 rep.setdefault('sessions',[]).append({'file':path.name,'database':db,'user':role,'state':state,'exit':x.returncode,'error':x.stderr[-380:]})
 if ok and x.returncode:raise AssertionError(path.name+' '+x.stderr[-950:])
 if not ok and x.returncode==0:raise AssertionError('unexpected success '+path.name)
 return state
def case(name,fn):
 try:fn();rep['cases'].append({'name':name,'pass':True})
 except Exception as e:
  rep['cases'].append({'name':name,'pass':False})
  rep['errors'].append({'case':name,'error':repr(e),'trace':traceback.format_exc()[-1600:]})
def roles():
 for name,props in [
  ('h2_schema_owner_test','NOLOGIN'),('h2_head_guard_test','NOLOGIN NOINHERIT'),
  ('h2_migrator_test',"LOGIN INHERIT PASSWORD 'synthetic_migrator_only'"),
  ('h2_app_ingest_writer_test',"LOGIN NOINHERIT PASSWORD 'synthetic_only_local_role'"),
  ('h2_readonly_test','LOGIN'),('h2_unrelated_test','LOGIN')]:
  q('postgres',f"DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='{name}') THEN CREATE ROLE {name} {props} NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS; END IF; END $$;")
 q('postgres','GRANT h2_schema_owner_test TO h2_migrator_test WITH INHERIT TRUE, SET TRUE, ADMIN FALSE')
 ck('migration_principal_non_superuser',q('postgres',"SELECT rolsuper,rolcreaterole,rolbypassrls FROM pg_roles WHERE rolname='h2_migrator_test'")==[(False,False,False)])
def fresh(name):
 db='h2_'+COPY.lower()+'_ns_'+name
 q('postgres',sql.SQL('CREATE DATABASE {}').format(sql.Identifier(db)))
 run(db,REF/'observed_partial_schema.sql')
 run(db,R/'research/h2_pg18_migration_role_rollback_2026-10-20/current_view_fixture.sql')
 # Grant migrator direct DDL authority on schema, and inherited owner rights on fixture.
 q(db,'GRANT CREATE,USAGE ON SCHEMA public TO h2_migrator_test')
 rel=q(db,"SELECT relname,relkind FROM pg_class WHERE relnamespace='public'::regnamespace AND relkind IN ('r','p','v','S') ORDER BY 2,1")
 for name,kind in rel:
  type={'r':'TABLE','p':'TABLE','v':'VIEW','S':'SEQUENCE'}[kind]
  q(db,sql.SQL('ALTER {} public.{} OWNER TO h2_schema_owner_test').format(sql.SQL(type),sql.Identifier(name)))
 q(db,'GRANT CREATE,USAGE ON SCHEMA public TO h2_schema_owner_test')
 return db
def temp(db):
 q(db,'GRANT CREATE ON SCHEMA public TO h2_head_guard_test')
 q('postgres','GRANT h2_head_guard_test TO h2_migrator_test WITH INHERIT TRUE, SET TRUE, ADMIN FALSE')
def untemp(db):
 q('postgres','REVOKE h2_head_guard_test FROM h2_migrator_test')
 q(db,'REVOKE CREATE ON SCHEMA public FROM h2_head_guard_test')
def base(db):
 # Historical 001 is executed by the non-superuser migrator; no superuser inside DDL.
 run(db,REF/'001_revision_invariants.sql',role='h2_migrator_test')
 run(db,ROLE,role='h2_migrator_test')
def history(db):
 return q(db,"SELECT md5(coalesce(string_agg(to_jsonb(c)::text,'|' ORDER BY classification_uid::text),'')) FROM public.attack_event_classifications c")[0][0]
def snapshot(db):
 return {'relations':q(db,"SELECT relname,relowner::regrole::text,relacl::text FROM pg_class WHERE relnamespace='public'::regnamespace ORDER BY 1"),
 'schema':q(db,"SELECT nspowner::regrole::text,nspacl::text FROM pg_namespace WHERE nspname='public'"),
 'function':q(db,"SELECT proname,proowner::regrole::text,prosecdef,proacl::text,proconfig::text FROM pg_proc WHERE pronamespace='public'::regnamespace ORDER BY 1"),
 'column':q(db,"SELECT c.relname,a.attname,a.attacl::text FROM pg_attribute a JOIN pg_class c ON a.attrelid=c.oid WHERE c.relnamespace='public'::regnamespace AND a.attnum>0 AND NOT a.attisdropped ORDER BY 1,2"),
 'default':q(db,"SELECT defaclrole::regrole::text,defaclobjtype,defaclacl::text FROM pg_default_acl ORDER BY 1,2"),
 'membership':q('postgres',"SELECT roleid::regrole::text,member::regrole::text,inherit_option,set_option,admin_option FROM pg_auth_members WHERE roleid::regrole::text LIKE 'h2_%%' ORDER BY 1,2"),
 'history':history(db)}
def matrix(db):
 out=[]
 for role in ('h2_schema_owner_test','h2_migrator_test','h2_app_ingest_writer_test','h2_head_guard_test','h2_readonly_test','h2_unrelated_test'):
  for (rel,) in q(db,"SELECT oid::regclass::text FROM pg_class WHERE relnamespace='public'::regnamespace AND relkind IN ('r','v') ORDER BY 1"):
   for priv in ('SELECT','INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER'):
    out.append((role,rel,priv,q(db,'SELECT has_table_privilege(%s,%s,%s)',(role,rel,priv))[0][0]))
  for priv in ('USAGE','CREATE'):
   out.append((role,'public',priv,q(db,'SELECT has_schema_privilege(%s,%s,%s)',(role,'public',priv))[0][0]))
 return out
def no_role_change():
 return not q('postgres',"SELECT 1 FROM pg_auth_members WHERE roleid='h2_head_guard_test'::regrole AND member='h2_migrator_test'::regrole")
def good():
 d=fresh('good');orig=snapshot(d);rights=matrix(d);base(d)
 temp(d)
 try:ck('transfer_success',run(d,UP,role='h2_migrator_test')=='00000')
 finally:untemp(d)
 owner=q(d,"SELECT proowner::regrole::text,prosecdef,proconfig::text FROM pg_proc WHERE oid='public.h2_enforce_revision_head()'::regprocedure")[0]
 ck('new_guard_owner',owner[0]=='h2_head_guard_test' and owner[1],owner)
 ck('secure_fixed_path','pg_catalog, pg_temp' in owner[2],owner)
 ck('temp_membership_retracted',no_role_change())
 ck('writer_guard_set_denied',denied(d,'h2_app_ingest_writer_test','synthetic_only_local_role','SET ROLE h2_head_guard_test')=='42501')
 ck('writer_direct_head_update_denied',denied(d,'h2_app_ingest_writer_test','synthetic_only_local_role','UPDATE public.h2_classification_heads SET changed_at=now()')=='42501')
 temp(d)
 try:ck('rollback_success',run(d,DOWN,role='h2_migrator_test',history=orig['history'])=='00000')
 finally:untemp(d)
 now=snapshot(d);newrights=matrix(d)
 delta=[x for x in orig if orig[x]!=now[x]]
 rep['raw_residual']=delta;rep['raw_catalog_equivalence']='PASS' if not delta else 'PARTIAL'
 rep['effective_privilege_equivalence']='PASS' if rights==newrights else 'FAIL'
 ck('effective_relation_schema_rights_unchanged',rights==newrights,delta)
 ck('rollback_history_unchanged',orig['history']==now['history'])
 ck('membership_restored',orig['membership']==now['membership'])
 ck('repeat_rollback_fail_closed',run(d,DOWN,role='h2_migrator_test',history=orig['history'],ok=False)=='23514')
 rep['catalog_before']=orig;rep['catalog_after']=now
def denied(db,who,pwd,statement):
 with dbconn(db,who,pwd) as c:
  try:c.execute(statement);return 'SUCCESS'
  except psycopg.Error as e:return e.sqlstate
def fault():
 d=fresh('fault');base(d);temp(d)
 try:
  old=snapshot(d)
  ck('injected_transfer_fails',run(d,UP,role='h2_migrator_test',fault='owner',ok=False)=='23514')
  ck('transfer_transaction_atomic',snapshot(d)==old)
  run(d,UP,role='h2_migrator_test')
 finally:untemp(d)
 ck('rollback_without_guard_membership_denied',denied(d,'h2_migrator_test','synthetic_migrator_only','ALTER FUNCTION public.h2_enforce_revision_head() OWNER TO h2_migrator_test')=='42501')
 temp(d)
 try:
  for what in ('acl','owner'):
   old=snapshot(d)
   ck('rollback_'+what+'_failure_sqlstate',run(d,DOWN,role='h2_migrator_test',history=history(d),fault=what,ok=False)=='23514')
   ck('rollback_'+what+'_atomic',snapshot(d)==old)
 finally:untemp(d)
def negative():
 d=fresh('negative');base(d)
 ck('no_transfer_membership_denied',denied(d,'h2_migrator_test','synthetic_migrator_only','ALTER FUNCTION public.h2_enforce_revision_head() OWNER TO h2_head_guard_test')=='42501')
 q('postgres','GRANT h2_head_guard_test TO h2_migrator_test WITH INHERIT TRUE, SET TRUE, ADMIN FALSE')
 try:ck('destination_schema_create_required',denied(d,'h2_migrator_test','synthetic_migrator_only','ALTER FUNCTION public.h2_enforce_revision_head() OWNER TO h2_head_guard_test')=='42501')
 finally:q('postgres','REVOKE h2_head_guard_test FROM h2_migrator_test')
 ck('app_replace_function_denied',denied(d,'h2_app_ingest_writer_test','synthetic_only_local_role',"ALTER FUNCTION public.h2_enforce_revision_head() RESET ALL")=='42501')
def main():
 try:
  ver=q('postgres','SHOW server_version')[0][0];rep['server_version']=ver;ck('pg18_6_exact',ver.startswith('18.6'),ver)
  roles()
  for n,f in [('positive_transfer_and_restore',good),('fault_atomicity',fault),('permission_negative',negative)]:case(n,f)
 except Exception as e:rep['errors'].append({'case':'bootstrap','error':repr(e),'trace':traceback.format_exc()[-1800:]})
 finally:
  rep['total']=len(rep['checks']);rep['passed']=sum(x['passed'] for x in rep['checks']);rep['skipped']=0
  rep['verdict']='FAIL' if rep['errors'] or rep['total']==0 or rep['total']!=rep['passed'] else ('PARTIAL' if rep.get('raw_residual') else 'PASS_BOUNDED')
  OUT.write_text(json.dumps(rep,indent=2,default=str)+'\n')
  print(json.dumps({'copy':COPY,'passed':rep['passed'],'total':rep['total'],'cases':rep['cases'],'errors':rep['errors'],'raw_residual':rep.get('raw_residual'),'verdict':rep['verdict']}))
 if rep['errors'] or rep['total']!=rep['passed']:raise SystemExit(1)
if __name__=='__main__':main()
