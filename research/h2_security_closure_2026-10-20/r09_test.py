#!/usr/bin/env python3
"""R09 fail-closed actual PostgreSQL 18.6 role-path preflight, bounded synthetic."""
import os,sys,json,traceback
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"h2_rollback_adversarial_2026-10-20"))
from harness import *
report={"copy":COPY,"commit":os.environ.get("GITHUB_SHA"),"pg_version":query("postgres","SHOW server_version")[0][0],"cases":[]}
assert report["pg_version"].startswith("18.6")
ns.roles()
# Explicit trusted boundary: h2_local superuser is fixture bootstrap,
# not an application principal. Target principal is intended restricted login only.
def risky(db,principal):
 m=query(db,"SELECT pg_has_role(%s,'h2_schema_owner_test','MEMBER'),pg_has_role(%s,'h2_head_guard_test','MEMBER'),has_table_privilege(%s,'public.attack_event_classifications','UPDATE'),has_table_privilege(%s,'public.attack_event_classifications','DELETE'),has_table_privilege(%s,'public.attack_event_classifications','TRUNCATE'),has_table_privilege(%s,'public.h2_classification_heads','UPDATE'),has_schema_privilege(%s,'public','CREATE')",(principal,)*7)[0]
 # A SET-only owner route is caught by MEMBER even when USAGE/INHERIT is false.
 return {"owner_membership":m[0],"guard_membership":m[1],"history_update":m[2],"history_delete":m[3],"history_truncate":m[4],"head_update":m[5],"schema_create":m[6]}
def one(name,setup,expected):
 d=new("r09v2"+name)
 setup(d)
 before=fingerprint(d)
 actual=risky(d,"h2_app_ingest_writer_test")
 after=fingerprint(d)
 dangerous=any(actual.values())
 good=(dangerous==expected and before==after)
 item={"id":name,"expected_unsafe":expected,"actual_unsafe":dangerous,"authority":actual,"unchanged_schema":before==after,"status":"PASS" if good else "FAIL"}
 report["cases"].append(item)
 print(json.dumps(item),flush=True)
 if not good:raise AssertionError(name)
def grant(role="h2_schema_owner_test",opts="INHERIT TRUE, SET TRUE, ADMIN FALSE"):
 query("postgres","GRANT "+role+" TO h2_app_ingest_writer_test WITH "+opts)
def indirect(db):
 role="h2_r09_indirect_"+COPY.lower()
 query("postgres","CREATE ROLE "+role+" NOLOGIN")
 query("postgres","GRANT h2_schema_owner_test TO "+role+" WITH INHERIT TRUE, SET TRUE, ADMIN FALSE")
 query("postgres","GRANT "+role+" TO h2_app_ingest_writer_test WITH INHERIT TRUE, SET TRUE, ADMIN FALSE")
try:
 one("safe",lambda db:None,False)
 one("inherit_owner",lambda db:grant(),True)
 query("postgres","REVOKE h2_schema_owner_test FROM h2_app_ingest_writer_test")
 one("set_only_owner",lambda db:grant(opts="INHERIT FALSE, SET TRUE, ADMIN FALSE"),True)
 query("postgres","REVOKE h2_schema_owner_test FROM h2_app_ingest_writer_test")
 one("direct_history_grant",lambda db:query(db,"GRANT UPDATE ON public.attack_event_classifications TO h2_app_ingest_writer_test"),True)
 one("guard_membership",lambda db:grant(role="h2_head_guard_test"),True)
 query("postgres","REVOKE h2_head_guard_test FROM h2_app_ingest_writer_test")
 one("schema_create",lambda db:query(db,"GRANT CREATE ON SCHEMA public TO h2_app_ingest_writer_test"),True)
 one("indirect_owner",indirect,True)
except Exception as e:
 report["error"]=repr(e);report["trace"]=traceback.format_exc()[-1300:]
finally:
 report["verdict"]="PARTIAL" if report.get("error") else "PASS_BOUNDED_PRECHECK"
 Path("/tmp/h2_r09_"+COPY+".json").write_text(json.dumps(report,indent=2)+"\n")
 print(report["verdict"],flush=True)
if report["verdict"]!="PASS_BOUNDED_PRECHECK":raise SystemExit(1)
