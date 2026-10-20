#!/usr/bin/env python3
"""Expanded synthetic PG18.6 ACL, future grant/revoke and bounded rollback controls.
Does not claim raw relacl NULL restoration or live Neon parity.
"""
import hashlib,importlib.util,json,os,re,subprocess,sys,traceback
from pathlib import Path
import psycopg
from psycopg import sql
ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/"research/h2_non_superuser_guard_acl_2026-10-20/test_non_superuser_acl_pg18.py"
spec=importlib.util.spec_from_file_location("accepted_nonsuperuser",SOURCE)
ns=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=ns
spec.loader.exec_module(ns)
COPY=os.environ.get("H2_COPY","A")
OUT=Path("/tmp/h2_expanded_acl_"+COPY+".json")
rep={"schema":"h2-expanded-acl-rollback-pg18-v1","tested_commit":os.environ.get("GITHUB_SHA"),
     "copy":COPY,"checks":[],"cases":[],"errors":[],"before":{},"after":{},
     "physical_catalog_residual":[],"sqlstates":[],"future_ops":[]}
def check(name,yes,detail=None):
    rep["checks"].append({"name":name,"pass":bool(yes),"detail":str(detail)[:250]})
    if not yes:raise AssertionError(name+": "+str(detail))
def case(name,fn):
    try:fn();rep["cases"].append({"name":name,"status":"PASS"})
    except Exception as e:
        rep["cases"].append({"name":name,"status":"FAIL"})
        rep["errors"].append({"case":name,"error":repr(e),"trace":traceback.format_exc()[-1500:]})
def owner(db,statement,args=()):
    return ns.q(db,statement,args)
def command(db,query):
    with ns.dbconn(db) as c:c.execute(query)
def denied(db,user,password,statement,allowed):
    got=ns.denied(db,user,password,statement)
    rep["sqlstates"].append({"database":db,"role":user,"sql":statement[:120],
                             "observed_sqlstate":got,"expected":allowed})
    check("denied_"+str(len(rep["sqlstates"])),got in allowed,got)
    return got
def create_roles():
    ns.roles()
    for role,inherits in (("h2_inherited_test","INHERIT"),("h2_noinherit_test","NOINHERIT")):
        owner("postgres","DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='"+role+
              "') THEN CREATE ROLE "+role+" LOGIN "+inherits+
              " PASSWORD 'synthetic_acl_only' NOSUPERUSER NOCREATEROLE NOCREATEDB NOBYPASSRLS; END IF; END $$")
    owner("postgres","GRANT h2_readonly_test TO h2_inherited_test WITH INHERIT TRUE,SET TRUE,ADMIN FALSE")
    owner("postgres","GRANT h2_readonly_test TO h2_noinherit_test WITH INHERIT FALSE,SET TRUE,ADMIN FALSE")
    check("inherit_membership_flag",
          owner("postgres","SELECT inherit_option FROM pg_auth_members WHERE roleid='h2_readonly_test'::regrole AND member='h2_inherited_test'::regrole")==[(True,)])
    check("noinherit_membership_flag",
          owner("postgres","SELECT inherit_option FROM pg_auth_members WHERE roleid='h2_readonly_test'::regrole AND member='h2_noinherit_test'::regrole")==[(False,)])
def decorate(db):
    command(db,"GRANT SELECT ON TABLE public.alert_episodes TO h2_readonly_test WITH GRANT OPTION")
    command(db,"GRANT UPDATE(event_status) ON TABLE public.attack_events TO h2_readonly_test")
    command(db,"GRANT USAGE ON SCHEMA public TO h2_readonly_test")
    command(db,"GRANT SELECT ON TABLE public.ingestion_runs TO PUBLIC")
    command(db,"CREATE FUNCTION public.h2_acl_probe() RETURNS integer LANGUAGE sql AS 'SELECT 11'")
    command(db,"GRANT EXECUTE ON FUNCTION public.h2_acl_probe() TO PUBLIC")
    command(db,"ALTER DEFAULT PRIVILEGES FOR ROLE h2_schema_owner_test IN SCHEMA public GRANT SELECT ON TABLES TO h2_readonly_test")
def roles_matrix(db):
    principals=("h2_schema_owner_test","h2_migrator_test","h2_app_ingest_writer_test",
      "h2_head_guard_test","h2_readonly_test","h2_unrelated_test","h2_inherited_test","h2_noinherit_test")
    relations=[x[0] for x in owner(db,"SELECT oid::regclass::text FROM pg_class WHERE relnamespace='public'::regnamespace AND relkind IN ('r','v') ORDER BY 1")]
    columns=owner(db,"SELECT c.oid::regclass::text,a.attname FROM pg_attribute a JOIN pg_class c ON a.attrelid=c.oid WHERE c.relnamespace='public'::regnamespace AND a.attnum>0 AND NOT a.attisdropped ORDER BY 1,2")
    out={}
    for role in principals:
        for rel in relations:
            for perm in ("SELECT","INSERT","UPDATE","DELETE","TRUNCATE","REFERENCES","TRIGGER",
                         "SELECT WITH GRANT OPTION","INSERT WITH GRANT OPTION","UPDATE WITH GRANT OPTION"):
                out[str((role,rel,perm))]=owner(db,"SELECT has_table_privilege(%s,%s,%s)",(role,rel,perm))[0][0]
        for rel,col in columns:
            for perm in ("SELECT","INSERT","UPDATE","REFERENCES","SELECT WITH GRANT OPTION",
                         "UPDATE WITH GRANT OPTION"):
                out[str((role,rel,col,perm))]=owner(db,"SELECT has_column_privilege(%s,%s,%s,%s)",(role,rel,col,perm))[0][0]
        for perm in ("USAGE","CREATE","USAGE WITH GRANT OPTION","CREATE WITH GRANT OPTION"):
            out[str((role,"public",perm))]=owner(db,"SELECT has_schema_privilege(%s,%s,%s)",(role,"public",perm))[0][0]
        for perm in ("EXECUTE","EXECUTE WITH GRANT OPTION"):
            out[str((role,"h2_acl_probe()",perm))]=owner(db,"SELECT has_function_privilege(%s,'public.h2_acl_probe()'::regprocedure,%s)",(role,perm))[0][0]
    return out
def catalog(db):
    return {
        "relation":owner(db,"SELECT relname,relowner::regrole::text,relacl::text FROM pg_class WHERE relnamespace='public'::regnamespace ORDER BY 1"),
        "schema":owner(db,"SELECT nspowner::regrole::text,nspacl::text FROM pg_namespace WHERE nspname='public'"),
        "column":owner(db,"SELECT c.relname,a.attname,a.attacl::text FROM pg_attribute a JOIN pg_class c ON a.attrelid=c.oid WHERE c.relnamespace='public'::regnamespace AND a.attnum>0 AND NOT a.attisdropped ORDER BY 1,2"),
        "function":owner(db,"SELECT proname,proowner::regrole::text,prosecdef,proacl::text,proconfig::text FROM pg_proc WHERE pronamespace='public'::regnamespace ORDER BY 1"),
        "defaults":owner(db,"SELECT defaclrole::regrole::text,defaclnamespace::regnamespace::text,defaclobjtype,defaclacl::text FROM pg_default_acl ORDER BY 1,2,3"),
        "membership":owner("postgres","SELECT roleid::regrole::text,member::regrole::text,inherit_option,set_option,admin_option FROM pg_auth_members WHERE roleid::regrole::text LIKE 'h2_%' ORDER BY 1,2"),
        "public":owner(db,"SELECT c.relname,a.privilege_type,a.is_grantable FROM pg_class c CROSS JOIN LATERAL aclexplode(COALESCE(c.relacl,acldefault('r',c.relowner))) a WHERE c.relnamespace='public'::regnamespace AND c.relkind='r' AND a.grantee=0 ORDER BY 1,2,3")}
def perform_007_008(db):
    orig=ns.history(db)
    ns.base(db)
    ns.temp(db)
    try:ns.run(db,ns.UP,role="h2_migrator_test")
    finally:ns.untemp(db)
    check("guard_transferred_"+db,owner(db,"SELECT proowner::regrole::text FROM pg_proc WHERE oid='public.h2_enforce_revision_head()'::regprocedure")==[("h2_head_guard_test",)])
    ns.temp(db)
    try:ns.run(db,ns.DOWN,role="h2_migrator_test",history=orig)
    finally:ns.untemp(db)
    check("guard_restored_and_removed_"+db,owner(db,"SELECT to_regprocedure('public.h2_enforce_revision_head()')")[0][0] is None)
    check("history_after_rollback_"+db,ns.history(db)==orig)
def future(db):
    results=[]
    for stmt in (
        "GRANT SELECT ON TABLE public.alert_episodes TO h2_unrelated_test",
        "REVOKE SELECT ON TABLE public.alert_episodes FROM h2_unrelated_test",
        "GRANT SELECT ON TABLE public.alert_episodes TO h2_unrelated_test WITH GRANT OPTION",
        "REVOKE GRANT OPTION FOR SELECT ON TABLE public.alert_episodes FROM h2_unrelated_test",
        "REVOKE SELECT ON TABLE public.alert_episodes FROM h2_unrelated_test",
    ):
        command(db,stmt)
        rights=owner(db,"SELECT has_table_privilege('h2_unrelated_test','public.alert_episodes','SELECT'),has_table_privilege('h2_unrelated_test','public.alert_episodes','SELECT WITH GRANT OPTION')")
        results.append((stmt,rights))
    rep["future_ops"].append({"database":db,"sequence":results})
    return results
def expanded_equivalence():
    pre=ns.fresh("acl_pre")
    post=ns.fresh("acl_post")
    for db in (pre,post):decorate(db)
    before=catalog(post)
    mbefore=roles_matrix(post)
    perform_007_008(post)
    after=catalog(post)
    mafter=roles_matrix(post)
    rep["before"]=before
    rep["after"]=after
    differences=[k for k in before if before[k]!=after[k]]
    rep["physical_catalog_residual"]=differences
    check("raw_difference_recorded",differences==["relation"],differences)
    check("expanded_effective_privilege_equivalence",mbefore==mafter,
          [k for k in mbefore if mbefore[k]!=mafter[k]][:15])
    check("catalog_column_default_function_membership_public_preserved",
          all(before[k]==after[k] for k in ("column","defaults","function","membership","public")))
    check("original_unrelated_acl_preserved",
          owner(post,"SELECT has_table_privilege('h2_readonly_test','public.alert_episodes','SELECT WITH GRANT OPTION')")==[(True,)])
    check("inherited_role_effective_select",
          owner(post,"SELECT has_table_privilege('h2_inherited_test','public.alert_episodes','SELECT')")==[(True,)])
    check("noinherit_role_not_automatically_select",
          owner(post,"SELECT has_table_privilege('h2_noinherit_test','public.alert_episodes','SELECT')")==[(False,)])
    check("public_select_retained",
          owner(post,"SELECT has_table_privilege('h2_unrelated_test','public.ingestion_runs','SELECT')")==[(True,)])
    check("column_update_retained",
          owner(post,"SELECT has_column_privilege('h2_readonly_test','public.attack_events','event_status','UPDATE')")==[(True,)])
    a=future(pre);b=future(post)
    check("future_grant_revoke_semantic_equivalence",a==b,(a,b))
    check("future_final_effective_access_identical",roles_matrix(pre)==roles_matrix(post))
    return post
def public_create_denied():
    db=ns.fresh("unsafe_public")
    ns.run(db,ns.REF/"001_revision_invariants.sql",role="h2_migrator_test")
    command(db,"GRANT CREATE ON SCHEMA public TO PUBLIC")
    before=ns.snapshot(db)
    state=ns.run(db,ns.ROLE,role="h2_migrator_test",ok=False)
    check("public_create_sqlstate",state=="42501",state)
    check("public_create_precondition_atomic",before==ns.snapshot(db))
def negative_guard():
    db=ns.fresh("unexpected_owner")
    ns.base(db)
    command(db,"ALTER FUNCTION public.h2_enforce_revision_head() OWNER TO h2_schema_owner_test")
    ns.temp(db)
    try:
        before=ns.snapshot(db)
        state=ns.run(db,ns.UP,role="h2_migrator_test",ok=False)
        check("wrong_guard_function_owner_rejected",state=="23514",state)
        check("wrong_owner_no_mutations",before==ns.snapshot(db))
    finally:ns.untemp(db)
def main():
    try:
        check("postgres_exact_18_6",owner("postgres","SHOW server_version")[0][0].startswith("18.6"))
        create_roles()
        case("expanded_catalog_and_future_grants",expanded_equivalence)
        case("public_create_negative",public_create_denied)
        case("unexpected_owner_negative",negative_guard)
    except Exception as e:rep["errors"].append({"case":"bootstrap","error":repr(e),"trace":traceback.format_exc()[-1500:]})
    finally:
        rep["total"]=len(rep["checks"])
        rep["passed"]=sum(x["pass"] for x in rep["checks"])
        rep["skipped"]=0
        rep["raw_equivalence"]="PARTIAL" if rep["physical_catalog_residual"] else "UNVERIFIED"
        rep["verdict"]="FAIL" if rep["errors"] or rep["total"]!=rep["passed"] else ("PARTIAL" if rep["physical_catalog_residual"] else "PASS_BOUNDED")
        OUT.write_text(json.dumps(rep,indent=2,default=str,sort_keys=True)+"\n")
        print(json.dumps({"copy":COPY,"total":rep["total"],"passed":rep["passed"],"cases":rep["cases"],
                          "raw_residual":rep["physical_catalog_residual"],"errors":rep["errors"],
                          "verdict":rep["verdict"]}))
    if rep["errors"] or rep["total"]!=rep["passed"]:raise SystemExit(1)
if __name__=="__main__":main()
