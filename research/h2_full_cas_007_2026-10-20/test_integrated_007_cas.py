#!/usr/bin/env python3
"""Execute the UNMODIFIED accepted 77-assertion CAS suite using genuine 007.
Only synthetic provisioning / migration setup replaces the previous 004/005.
"""
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
import psycopg
from psycopg import sql

ROOT = Path(__file__).resolve().parents[2]
OLD = ROOT / "research/h2_pg18_full_offline_2026-10-20/restricted_cas/test_restricted_cas_pg18.py"
sys.path.insert(0, str(OLD.parent))
spec = importlib.util.spec_from_file_location("accepted_restricted_cas", OLD)
suite = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = suite
spec.loader.exec_module(suite)

BASE = ROOT / "reference/research/h2_pg18_revision_invariant_hardening_2026-10-19"
VIEW = ROOT / "research/h2_pg18_migration_role_rollback_2026-10-20/current_view_fixture.sql"
APP_SQL = ROOT / "research/h2_pg18_security_closure_2026-10-20/003_candidate_app_role_v3_atomic.sql"
TRANSFER = ROOT / "research/h2_non_superuser_guard_acl_2026-10-20/007_non_superuser_guard_transfer.sql"
COPY = os.environ.get("H2_COPY", "A")
suite.report["schema"] = "h2-integrated-non-superuser-007-full-cas-v1"
suite.report["original_suite_source_git_blob"] = "ce4bbb0d78cb622e9ba6815d78612079af31fbdf"
suite.report["migration_method"] = "actual 001/003/007 as non-superuser h2_migrator_test"
suite.OUT = Path("/tmp/h2_integrated_007_" + COPY + ".json")

def owner(sql_text, db="postgres", params=()):
    with suite.baseline.connect(suite.OWNER, db) as con:
        with con.cursor() as cur:
            cur.execute(sql_text, params)
            return cur.fetchall() if cur.description else []

def setup_roles():
    for role, props in [
        ("h2_schema_owner_test", "NOLOGIN"),
        ("h2_head_guard_test", "NOLOGIN NOINHERIT"),
        ("h2_migrator_test", "LOGIN INHERIT PASSWORD 'synthetic_migrator_only'"),
        ("h2_app_ingest_writer_test", "LOGIN NOINHERIT PASSWORD 'synthetic_only_local_role'"),
        ("h2_readonly_test", "LOGIN"),
        ("h2_unrelated_test", "LOGIN")]:
        owner("DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='" + role +
              "') THEN CREATE ROLE " + role + " " + props +
              " NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS; END IF; END $$")
    owner("GRANT h2_schema_owner_test TO h2_migrator_test WITH INHERIT TRUE, SET TRUE, ADMIN FALSE")
    suite.check("007_migrator_nosuperuser_nocreaterole_nobypassrls",
        owner("SELECT rolsuper,rolcreaterole,rolbypassrls FROM pg_roles WHERE rolname='h2_migrator_test'") ==
        [(False,False,False)])
    suite.check("007_app_not_guard_member",
        not owner("SELECT pg_has_role('h2_app_ingest_writer_test','h2_head_guard_test','MEMBER')")[0][0])

def run_sql(db, file, role="h2_migrator_test", vars=None):
    import hashlib
    suite.report["executed_sql_sha256"][str(file.relative_to(ROOT))] = hashlib.sha256(file.read_bytes()).hexdigest()
    cmd=["psql","-X","-v","ON_ERROR_STOP=1","-v","VERBOSITY=verbose",
         "-h","127.0.0.1","-U",role,"-d",db]
    for k,v in (vars or {}).items():cmd.extend(["-v",k+"="+v])
    cp=subprocess.run(cmd+["-f",str(file)],text=True,capture_output=True,timeout=100,
       env={**os.environ,"PGPASSWORD": "synthetic_migrator_only" if role=="h2_migrator_test" else "synthetic_only"})
    if cp.returncode:raise RuntimeError(file.name+" as "+role+" failed "+cp.stderr[-1400:])

def actual_007_database(label):
    db="h2_"+COPY.lower()+"_integrated_"+label
    with suite.baseline.connect(suite.OWNER) as c:
        c.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db)))
    run_sql(db,BASE/"observed_partial_schema.sql",role="h2_local")
    run_sql(db,VIEW,role="h2_local")
    owner("GRANT CREATE,USAGE ON SCHEMA public TO h2_migrator_test",db)
    rows=owner("""SELECT relname,relkind FROM pg_class
         WHERE relnamespace='public'::regnamespace AND relkind IN ('r','p','v','S') ORDER BY 2,1""",db)
    for name, kind in rows:
        obj={"r":"TABLE","p":"TABLE","v":"VIEW","S":"SEQUENCE"}[kind]
        with suite.baseline.connect(suite.OWNER,db) as c:
            c.execute(sql.SQL("ALTER {} public.{} OWNER TO h2_schema_owner_test").
                      format(sql.SQL(obj),sql.Identifier(name)))
    owner("GRANT CREATE,USAGE ON SCHEMA public TO h2_schema_owner_test",db)
    run_sql(db,BASE/"001_revision_invariants.sql")
    run_sql(db,APP_SQL)
    owner("GRANT CREATE ON SCHEMA public TO h2_head_guard_test",db)
    owner("GRANT h2_head_guard_test TO h2_migrator_test WITH INHERIT TRUE, SET TRUE, ADMIN FALSE")
    try:
        run_sql(db,TRANSFER,vars={"fault":"none"})
    finally:
        owner("REVOKE h2_head_guard_test FROM h2_migrator_test")
        owner("REVOKE CREATE ON SCHEMA public FROM h2_head_guard_test",db)
    who=owner("""SELECT proowner::regrole::text,prosecdef,proconfig::text
              FROM pg_proc WHERE oid='public.h2_enforce_revision_head()'::regprocedure""",db)[0]
    suite.check("007_guard_owner_actual",who[0]=="h2_head_guard_test",who)
    suite.check("007_security_definer_and_fixed_path",who[1] and "pg_catalog, pg_temp" in who[2],who)
    suite.check("007_migrator_guard_membership_removed",
        not owner("SELECT pg_has_role('h2_migrator_test','h2_head_guard_test','MEMBER')")[0][0])
    suite.check("007_guard_schema_create_removed",
        not owner("SELECT has_schema_privilege('h2_head_guard_test','public','CREATE')",db)[0][0])
    suite.check("007_app_schema_create_denied",
        not owner("SELECT has_schema_privilege('h2_app_ingest_writer_test','public','CREATE')",db)[0][0])
    return db

setup_roles()
suite.restricted_database=actual_007_database
suite.baseline.new_database=actual_007_database
suite.main()
assert suite.report["verdict"]=="PASS"
names=[a["name"] for a in suite.report["assertions"]]
assert len(names)>=77 and len(set(names))==len(names)
original_names=[n for n in names if not n.startswith("007_")]
assert len(original_names)==77, (len(names),len(original_names))
suite.report["accepted_original_77_executed"] = len(original_names)
suite.report["topology_additions"] = len(names)-77
suite.OUT.write_text(json.dumps(suite.report,indent=2,sort_keys=True,default=str)+"\n")
print(json.dumps({"verdict":"PASS","accepted_original_assertions":77,"topology_additions":len(names)-77,
                  "total":len(names),"copy":COPY}))
