#!/usr/bin/env python3
"""Research-only original 008 late ACL proof. No external databases, no Neon."""
import os,sys,json,hashlib,traceback,subprocess,re,difflib
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/"research/h2_rollback_adversarial_2026-10-20"))
from harness import *
ORIGINAL=ns.DOWN
INSTR=HERE/"008_late_fault_instrumented.sql"
assert subprocess.check_output(["git","hash-object",str(ORIGINAL)],text=True).strip()=="59eab59235f8aee14837ce7494649edba674e1ce"
a=ORIGINAL.read_text();b=INSTR.read_text()
start="-- RESEARCH ONLY: fault follows"
end="END $h2_research_late_acl$;\n"
assert b.count(start)==1 and b.count(end)==1
remove=b[:b.index(start)]+b[b.index(end)+len(end):]
assert remove==a, "instrumented SQL must only contain one additive block"
rep={"copy":COPY,"commit":os.environ.get("GITHUB_SHA"),"server_version":None,
     "original_008_git_blob":"59eab59235f8aee14837ce7494649edba674e1ce",
     "original_sha256":hashlib.sha256(ORIGINAL.read_bytes()).hexdigest(),
     "instrumented_sha256":hashlib.sha256(INSTR.read_bytes()).hexdigest(),
     "cases":[],"errors":[],"observations":{}}
def case(name,ok,details=None):
    rep["cases"].append({"case":name,"status":"PASS" if ok else "FAIL","details":details})
    if not ok: raise AssertionError(name+" "+str(details))
def rights(db):
    return matrix(db) if False else ns.matrix(db)
def acl(db):
    return ns.snapshot(db)
def dump(db):
    runp=subprocess.run(["docker","run","--rm","--network","host","-e","PGPASSWORD=synthetic_only","postgres:18.6","pg_dump","--schema-only","--no-owner",
       "-h","127.0.0.1","-U","h2_local","-d",db],
       env={**os.environ,"PGPASSWORD":"synthetic_only"},capture_output=True,text=True,timeout=90)
    if runp.returncode: raise RuntimeError(runp.stderr[-900:])
    raw=runp.stdout
    norm="".join(line for line in raw.splitlines(keepends=True)
       if not line.startswith("\\restrict ") and not line.startswith("\\unrestrict "))
    return {"raw_sha256":hashlib.sha256(raw.encode()).hexdigest(),
      "normalized_sha256":hashlib.sha256(norm.encode()).hexdigest(),"normalized":norm}
def relacl(db):
    return {x[0]:x[1] for x in ns.q(db,
      "SELECT relname,relacl::text FROM pg_class WHERE relnamespace='public'::regnamespace AND relkind IN ('r','v','p') ORDER BY 1")}
def grants(db):
    return ns.q(db,"""SELECT
       has_table_privilege('h2_app_ingest_writer_test','public.alert_episodes','SELECT'),
       has_table_privilege('h2_app_ingest_writer_test','public.attack_event_classifications','INSERT'),
       has_column_privilege('h2_app_ingest_writer_test','public.attack_events','updated_at','UPDATE')""")[0]
def probe(db,stmt):
    try: ns.q(db,stmt);return "00000"
    except Exception as e: return getattr(e,"sqlstate",type(e).__name__)
def continuation(label,db):
    observations=[]
    # Execute SAME supported follow-up operations in control and rollback fixtures.
    for sql in [
      "GRANT SELECT ON public.alert_episodes TO h2_unrelated_test",
      "REVOKE SELECT ON public.alert_episodes FROM h2_unrelated_test",
      "GRANT UPDATE ON public.ingestion_runs TO h2_unrelated_test WITH GRANT OPTION",
      "REVOKE GRANT OPTION FOR UPDATE ON public.ingestion_runs FROM h2_unrelated_test",
      "REVOKE UPDATE ON public.ingestion_runs FROM h2_unrelated_test",
      "ALTER TABLE public.alert_episodes OWNER TO h2_migrator_test",
      "ALTER TABLE public.alert_episodes OWNER TO h2_schema_owner_test",
      "CREATE TABLE public.h2_future_acl_probe_"+label+" (id integer)",
      "ALTER TABLE public.h2_future_acl_probe_"+label+" OWNER TO h2_schema_owner_test",
      "GRANT SELECT ON public.h2_future_acl_probe_"+label+" TO h2_unrelated_test",
      "ALTER TABLE public.h2_future_acl_probe_"+label+" ADD COLUMN value text",
      "DROP TABLE public.h2_future_acl_probe_"+label,
      "CREATE FUNCTION public.h2_future_acl_func_"+label+"() RETURNS integer LANGUAGE SQL AS 'SELECT 1'",
      "ALTER FUNCTION public.h2_future_acl_func_"+label+"() OWNER TO h2_schema_owner_test",
      "GRANT EXECUTE ON FUNCTION public.h2_future_acl_func_"+label+"() TO h2_unrelated_test",
      "REVOKE EXECUTE ON FUNCTION public.h2_future_acl_func_"+label+"() FROM h2_unrelated_test",
      "DROP FUNCTION public.h2_future_acl_func_"+label+"()",
    ]:
      observations.append([sql.replace(label,"LABEL"),probe(db,sql)])
    return observations
def run_instrumented(db,fault,ok):
    cmd=["psql","-X","-v","ON_ERROR_STOP=1","-v","VERBOSITY=verbose",
      "-v","fault="+fault,"-v","expected_history="+ns.history(db),
      "-h","127.0.0.1","-U","h2_migrator_test","-d",db,"-f",str(INSTR)]
    x=subprocess.run(cmd,env={**os.environ,"PGPASSWORD":"synthetic_migrator_only"},
      capture_output=True,text=True,timeout=90)
    match=re.search(r"ERROR:\s+([0-9A-Z]{5}):",x.stderr)
    sqlstate=match.group(1) if match else ("00000" if x.returncode==0 else "UNKNOWN")
    rep.setdefault("instrumented_sessions",[]).append(
      {"db":db,"fault":fault,"exit":x.returncode,"sqlstate":sqlstate,
       "stderr":x.stderr[-1800:],"stdout":x.stdout[-1800:]})
    if ok != (x.returncode==0): raise AssertionError("unexpected instrumented exit "+str(x.returncode)+" "+x.stderr[-900:])
    return sqlstate
def main():
    ver=ns.q("postgres","SHOW server_version")[0][0]
    rep["server_version"]=ver
    case("exact_pg18_6",ver.startswith("18.6"),ver)
    ns.roles()
    # control, original 008, instrumented fault, and nonfault instrumented 008
    control=ns.fresh("latecontrol")
    trial=ns.fresh("latefault")
    normal=ns.fresh("latenormal")
    for db in (trial,normal):
        ns.base(db)
        ns.temp(db)
        try:ns.run(db,ns.UP,role="h2_migrator_test")
        finally:ns.untemp(db)
    case("precondition_three_real_grants",grants(trial)==(True,True,True),grants(trial))
    ns.temp(trial)
    try:
        old=acl(trial);old_rights=rights(trial)
        state=run_instrumented(trial,"late_acl",False)
        case("actual_008_late_fault_sqlstate_23514",state=="23514",state)
        case("actual_008_late_fault_full_catalog_atomicity",acl(trial)==old,{"equal":acl(trial)==old})
        case("actual_008_late_fault_effective_rights_atomicity",rights(trial)==old_rights)
    finally:ns.untemp(trial)
    # Normal original execution and separately instrumented successful path.
    ns.temp(trial)
    try:case("actual_original_008_success",ns.run(trial,ORIGINAL,role="h2_migrator_test",history=ns.history(trial))=="00000")
    finally:ns.untemp(trial)
    ns.temp(normal)
    try:case("instrumented_008_no_fault_success",run_instrumented(normal,"none",True)=="00000")
    finally:ns.untemp(normal)
    c=acl(control);d=acl(trial);n=acl(normal)
    rep["observations"]["catalog_original_vs_rollback"]={"before":c,"after":d}
    rep["observations"]["raw_deltas"]={k:{"before":c[k],"after":d[k]} for k in c if c[k]!=d[k]}
    case("original_vs_instrumented_success_catalog",d==n,{"different_keys":[k for k in d if d[k]!=n[k]]})
    case("original_vs_rollback_effective_rights",rights(control)==rights(trial))
    case("original_vs_rollback_history",c["history"]==d["history"])
    case("original_vs_rollback_membership",c["membership"]==d["membership"])
    rc=relacl(control);rr=relacl(trial)
    changed={k:{"before":rc.get(k),"after":rr.get(k)} for k in rc.keys()|rr.keys() if rc.get(k)!=rr.get(k)}
    rep["observations"]["physical_relacl_delta"]=changed
    case("physical_residual_enumerated",len(changed)==7 and all(v["before"] is None and v["after"] is not None for v in changed.values()),changed)
    # Supported sequences: test GRANT/REVOKE both directions and revoke all then grant back
    # on already-explicit object, preserving data and OIDs.
    test_rel="public.alert_episodes"
    pre=ns.q(trial,"SELECT relacl::text FROM pg_class WHERE oid=%s::regclass",(test_rel,))[0][0]
    ns.q(trial,"REVOKE ALL ON "+test_rel+" FROM h2_unrelated_test")
    ns.q(trial,"GRANT SELECT ON "+test_rel+" TO h2_unrelated_test")
    ns.q(trial,"REVOKE SELECT ON "+test_rel+" FROM h2_unrelated_test")
    post=ns.q(trial,"SELECT relacl::text FROM pg_class WHERE oid=%s::regclass",(test_rel,))[0][0]
    rep["observations"]["supported_restoration_attempt"]={"before":pre,"after":post,"became_null":post is None}
    case("supported_grant_revoke_checked",post is not None,{"before":pre,"after":post})
    # Match probe output despite differing fixture names; run independent operation sequence.
    x=continuation("control",control);y=continuation("rolled",trial)
    case("future_ddl_owner_function_grant_matrix",x==y,{"control":x,"rolled":y})
    dc=dump(control);dr=dump(trial)
    rep["observations"]["dump"]={"control_raw_sha256":dc["raw_sha256"],"rollback_raw_sha256":dr["raw_sha256"],
       "control_normalized_sha256":dc["normalized_sha256"],"rollback_normalized_sha256":dr["normalized_sha256"],
       "normalized_diff":list(difflib.unified_diff(dc["normalized"].splitlines(),dr["normalized"].splitlines()))[:180]}
    case("pg_dump_normalized_comparison_recorded",True,{"normalized_equal":dc["normalized"]==dr["normalized"]})
    # Preserve physical difference as PARTIAL; never implicitly accept it.
    rep["verdict"]="PARTIAL" if changed else "PASS_BOUNDED"
try:main()
except Exception as ex:
    rep["errors"].append({"error":repr(ex),"trace":traceback.format_exc()[-2100:]})
    rep["verdict"]="FAIL"
finally:
    rep["tests_passed"]=sum(x["status"]=="PASS" for x in rep["cases"])
    rep["tests_total"]=len(rep["cases"])
    Path("/tmp/h2_008_late_acl_"+COPY+".json").write_text(json.dumps(rep,indent=2,default=str)+"\n")
    print(json.dumps({"copy":COPY,"verdict":rep.get("verdict"),"tests_passed":rep["tests_passed"],
       "tests_total":rep["tests_total"],"errors":rep["errors"],
       "residual":rep["observations"].get("physical_relacl_delta"),
       "dump":rep["observations"].get("dump")}),flush=True)
if rep.get("verdict")=="FAIL":raise SystemExit(1)
