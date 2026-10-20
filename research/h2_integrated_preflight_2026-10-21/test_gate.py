#!/usr/bin/env python3
"""Synthetic PG18.6 independent H11/R09 007 integration A/B, no Neon."""
import hashlib, json, os, subprocess, sys, time, traceback
from pathlib import Path
import psycopg
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"h2_rollback_adversarial_2026-10-20"))
from harness import ns, query, conn, new, put, truth, fingerprint, COPY
from build_gate import generate

ROOT=Path(__file__).resolve().parents[2]
OUT=Path("/tmp/h2_integrated_preflight_"+COPY+".json")
REPORT={"schema":"h2-integrated-gate-1","copy":COPY,"tested_commit":os.getenv("GITHUB_SHA"),
"postgres":query("postgres","SHOW server_version")[0][0],"cases":[],"limitations":
["Synthetic roles; external Neon role topology unverified","Physical ACL rollback remains separately PARTIAL"]}
assert REPORT["postgres"].startswith("18.6")
ns.roles()
SCRIPT,REPORT["sources"]=generate()
REPORT["sql_sha256"]=hashlib.sha256(SCRIPT.encode()).hexdigest()
BASE=Path("/tmp/h2_integrated_"+COPY+".sql")
BASE.write_text(SCRIPT)
def exec_gate(db,lock="3s",hold=0,fault="none"):
    text,_=generate(hold_seconds=hold,lock_timeout=lock)
    path=Path("/tmp/h2_integrated_"+COPY+"_"+str(os.getpid())+".sql")
    path.write_text(text)
    c=subprocess.run(["psql","-X","-v","ON_ERROR_STOP=1","-v","VERBOSITY=verbose",
      "-v","fault="+fault,"-h","127.0.0.1","-U","h2_migrator_test","-d",db,
      "-f",str(path)],capture_output=True,text=True,timeout=50,
      env={**os.environ,"PGPASSWORD":"synthetic_migrator_only",
      "PGAPPNAME":"H2_INTEGRATED_MIGRATION_"+COPY})
    import re
    m=re.search(r"ERROR:\s+([0-9A-Z]{5}):",c.stderr)
    return (m.group(1) if m else ("00000" if c.returncode==0 else "UNKNOWN"),
       c.stderr[-800:],c.returncode)
def case(name,mutator=None,expected="23514",prepare=None,lock="3s",hold=0,fault="none"):
    db=new("integ"+name)
    if prepare:prepare(db)
    if mutator:mutator(db)
    before=fingerprint(db);hist=truth(db)
    result=exec_gate(db,lock,hold,fault=fault)
    after=fingerprint(db);post=truth(db)
    status=result[0]
    good=(status==expected and
      (expected=="00000" or (before==after and hist==post)))
    # After a successful guarded migration, a repeat must be deterministic/no-op.
    if expected=="00000":
        prior=fingerprint(db);second=exec_gate(db)
        good=good and second[0]=="00000" and prior==fingerprint(db)
        good=good and hist["history_md5"]==truth(db)["history_md5"]
    item={"case":name,"expected":expected,"sqlstate":status,
          "exit":result[2],"stderr":result[1],"preserved_on_refusal":
          before==after if expected!="00000" else None,
          "repeat":second[0] if expected=="00000" else None,
          "status":"PASS" if good else "FAIL"}
    REPORT["cases"].append(item)
    print(json.dumps(item),flush=True)
    if not good:raise AssertionError(name)
    return db
def q(db,s,args=()):return query(db,s,args)
def chain(d):
    a=put(d,"first_"+d);b=put(d,"next_"+d,parent=a);return a,b
def missing(d): put(d,"missing_"+d);q(d,"DELETE FROM public.h2_classification_heads")
def stale(d):a,b=chain(d);q(d,"UPDATE public.h2_classification_heads SET tip_classification_uid=%s",(a,))
def orphan(d):
    a=put(d,"orphan_"+d)
    q(d,"INSERT INTO public.h2_classification_heads(city_key,historical_episode_id,alert_start_at,alert_end_at,tip_classification_uid) VALUES ('wrong','999999999999999999999999','2026-01-01T01:00:00Z','2026-01-01T02:00:00Z',%s)",(a,))
def wrong(d):
    a=put(d,"wrong1"+d)
    b=put(d,"wrong2"+d,identity=2,city="kharkiv")
    q(d,"UPDATE public.h2_classification_heads SET tip_classification_uid=%s WHERE city_key='kyiv'",(b,))
def duplicate_successor(d):
    a,b=chain(d)
    # Existing 001 unique successor index prevents this synthetic corruption;
    # explicitly remove only in disposable fixture.
    q(d,"DROP INDEX public.h2_classification_one_successor_uidx")
    q(d,"DROP TRIGGER h2_revision_head_after_insert ON public.attack_event_classifications")
    put(d,"fork_"+d,parent=a)
def duplicate_roots(d):
    q(d,"DROP INDEX public.h2_classification_one_root_uidx")
    q(d,"DROP TRIGGER h2_revision_head_after_insert ON public.attack_event_classifications")
    put(d,"root1"+d)
    put(d,"root2"+d)
def invalid_parent(d):
    q(d,"DROP TRIGGER h2_revision_head_after_insert ON public.attack_event_classifications")
    a=put(d,"badparent1"+d)
    put(d,"badparent2"+d,identity=2,city="kharkiv",parent=a)
def disconnected(d):
    q(d,"DROP TRIGGER h2_revision_head_after_insert ON public.attack_event_classifications")
    q(d,"DROP INDEX public.h2_classification_one_root_uidx")
    a,b=chain(d) # inserts fail if trigger removed? chain bypass head but inserts work
    q(d,"UPDATE public.attack_event_classifications SET supersedes_classification_uid=classification_uid WHERE classification_uid=%s",(a,))
def cycle(d):
    a,b=chain(d)
    q(d,"UPDATE public.attack_event_classifications SET supersedes_classification_uid=%s WHERE classification_uid=%s",(b,a))
def late_007_fault(d):
    # Existing fixture is valid, so the fault must occur AFTER 007's GRANT,
    # ALTER FUNCTION configuration and function-owner modifications.
    chain(d)
def deny_role(role,opts):
    q("postgres","GRANT "+role+" TO h2_app_ingest_writer_test WITH "+opts)
def unsafe_owner(d):deny_role("h2_schema_owner_test","INHERIT TRUE, SET TRUE, ADMIN FALSE")
def unsafe_set(d):deny_role("h2_schema_owner_test","INHERIT FALSE, SET TRUE, ADMIN FALSE")
def unsafe_guard(d):deny_role("h2_head_guard_test","INHERIT FALSE, SET TRUE, ADMIN FALSE")
def unsafe_history(d):q(d,"GRANT UPDATE ON public.attack_event_classifications TO h2_app_ingest_writer_test")
def unsafe_schema(d):q(d,"GRANT CREATE ON SCHEMA public TO h2_app_ingest_writer_test")
def unsafe_function(d):
    q(d,"GRANT CREATE ON SCHEMA public TO h2_app_ingest_writer_test")
def main():
 try:
    case("safe_empty",expected="00000")
    case("safe_chain",mutator=chain,expected="00000")
    case("missing_head",mutator=missing)
    case("stale_tip",mutator=stale)
    case("orphan_head",mutator=orphan)
    case("wrong_head_identity",mutator=wrong)
    case("duplicate_successor",mutator=duplicate_successor)
    case("duplicate_roots",mutator=duplicate_roots)
    case("invalid_parent",mutator=invalid_parent)
    case("cycle",mutator=cycle)
    case("late_007_owner_fault",mutator=late_007_fault,fault="owner")
    # Membership is cluster-global: remove each inherited grant after the case.
    for name,mutate,cleanup in [
     ("owner_inherited",unsafe_owner,"h2_schema_owner_test"),
     ("owner_set_only",unsafe_set,"h2_schema_owner_test"),
     ("guard_set_only",unsafe_guard,"h2_head_guard_test")]:
        try:case(name,mutator=mutate,expected="42501")
        finally:q("postgres","REVOKE "+cleanup+" FROM h2_app_ingest_writer_test")
    case("history_update_grant",mutator=unsafe_history,expected="42501")
    case("schema_create_grant",mutator=unsafe_schema,expected="42501")
    # Real concurrent restricted writer blocked while gate lock held.
    db=new("concurrent")
    before=truth(db)
    with conn(db,autocommit=False) as blocker:
        blocker.execute("LOCK TABLE public.attack_event_classifications, public.h2_classification_heads IN SHARE ROW EXCLUSIVE MODE")
        # Distinct restricted session times out attempting legitimate append.
        with conn(db,"h2_app_ingest_writer_test","synthetic_only_local_role",autocommit=True) as writer:
            writer.execute("SET lock_timeout='350ms'")
            try:put(db,"blocked_"+db,session=writer);st="00000"
            except psycopg.Error as e:st=e.sqlstate
        assert st=="55P03" and before==truth(db)
        blocker.commit()
    item={"case":"writer_lock_contention","expected":"55P03","sqlstate":st,"status":"PASS"}
    REPORT["cases"].append(item)
    # Migration blocked by another session's writer-owned lock; must roll back.
    db=new("migrationlock")
    before=fingerprint(db)
    with conn(db,autocommit=False) as writer:
        writer.execute("LOCK TABLE public.attack_event_classifications IN ROW EXCLUSIVE MODE")
        fail=exec_gate(db,lock="350ms")
        writer.commit()
    good=fail[0]=="55P03" and before==fingerprint(db)
    REPORT["cases"].append({"case":"migration_lock_timeout","expected":"55P03",
         "sqlstate":fail[0],"status":"PASS" if good else "FAIL"})
    if not good:raise AssertionError("migration_lock_timeout")
 except Exception as e:
    REPORT["error"]=repr(e)
    REPORT["trace"]=traceback.format_exc()[-1800:]
 finally:
    REPORT["passed"]=sum(x["status"]=="PASS" for x in REPORT["cases"])
    REPORT["total"]=len(REPORT["cases"])
    REPORT["verdict"]="PASS_BOUNDED" if not REPORT.get("error") and REPORT["total"]==REPORT["passed"] else "FAIL"
    OUT.write_text(json.dumps(REPORT,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"verdict":REPORT["verdict"],"passed":REPORT["passed"],"total":REPORT["total"],"error":REPORT.get("error")}),flush=True)
 if REPORT["verdict"]!="PASS_BOUNDED":raise SystemExit(1)
if __name__=="__main__":main()
