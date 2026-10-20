"""Synthetic-only PostgreSQL 18.6 H2 adversarial helpers.

The accepted source files are imported, not changed. All databases are fresh
GitHub Actions postgres:18.6 fixtures; never construct a Neon DSN here.
"""
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path

import psycopg
from psycopg import sql

ROOT = Path(__file__).resolve().parents[2]
OLD = ROOT / "research/h2_non_superuser_guard_acl_2026-10-20/test_non_superuser_acl_pg18.py"
spec = importlib.util.spec_from_file_location("accepted_h2_non_superuser", OLD)
ns = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = ns
spec.loader.exec_module(ns)
COPY = os.environ.get("H2_COPY", "A")
SOURCE = [ns.UP, ns.DOWN, ns.ROLE, ns.REF / "001_revision_invariants.sql"]
SOURCE_HASHES = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in SOURCE if p.is_relative_to(ROOT)}
# Reference is cloned under the checkout; hash it by stable relative identity.
SOURCE_HASHES["reference/001_revision_invariants.sql"] = hashlib.sha256((ns.REF / "001_revision_invariants.sql").read_bytes()).hexdigest()

ALL = {"schema":"h2-adversarial-pg18-v1", "copy":COPY, "tested_commit":os.environ.get("GITHUB_SHA"),
       "pg_version":None, "sources":SOURCE_HASHES, "records":[], "steps":[], "errors":[],
       "limitations":[], "race_timelines":[], "acl":{}, "gates":{}}
OUT = Path("/tmp/h2_adversarial_" + COPY + ".json")

def query(db, statement, params=(), user="h2_local", password="synthetic_only"):
    return ns.q(db, statement, params, name=user, pw=password)

def conn(db, user="h2_local", password="synthetic_only", **kwargs):
    return psycopg.connect("postgresql://%s:%s@127.0.0.1:5432/%s" % (user,password,db), **kwargs)

def snapshot(db):
    return ns.snapshot(db)

def digest(x):
    return hashlib.sha256(json.dumps(x, sort_keys=True, default=str).encode()).hexdigest()

def fingerprint(db):
    return digest(snapshot(db))

def historical(db):
    return ns.history(db)

def heads(db):
    if query(db,"SELECT to_regclass('public.h2_classification_heads')")[0][0] is None:
        return None
    return query(db, """SELECT city_key,historical_episode_id,alert_start_at::text,alert_end_at::text,tip_classification_uid::text
                        FROM public.h2_classification_heads ORDER BY 1,2,3,4""")

def truth(db):
    return {"history_md5":historical(db),"history_count":query(db,"SELECT count(*) FROM public.attack_event_classifications")[0][0],
            "head_rows":heads(db)}

def new(label, stage="installed"):
    db = ns.fresh(label)
    if stage in ("base","installed"):
        ns.base(db)
    if stage=="installed":
        ns.temp(db)
        try:
            result = ns.run(db,ns.UP,role="h2_migrator_test")
            assert result=="00000",result
        finally:
            ns.untemp(db)
    return db

def sqlstate(db, user, statement, params=(), password=None):
    if password is None:
        password = {"h2_local":"synthetic_only", "h2_migrator_test":"synthetic_migrator_only",
                    "h2_app_ingest_writer_test":"synthetic_only_local_role"}.get(user,"synthetic_acl_only")
    with conn(db,user,password,autocommit=True) as c:
        try:
            c.execute("SET statement_timeout = '8s'")
            c.execute(statement,params)
            return "00000"
        except psycopg.Error as exc:
            return exc.sqlstate or "UNKNOWN"

def psql_cmd(db, path, orig, fault="none", role="h2_migrator_test"):
    return ["psql","-X","-v","ON_ERROR_STOP=1","-v","VERBOSITY=verbose",
            "-v","expected_history="+orig,"-v","fault="+fault,"-h","127.0.0.1",
            "-U",role,"-d",db,"-f",str(path)]

def process(db,path,orig,env_name):
    env={**os.environ,"PGPASSWORD":"synthetic_migrator_only","PGAPPNAME":env_name}
    return subprocess.Popen(psql_cmd(db,path,orig),env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)

def finish_process(p,timeout=20):
    try:
        out,err=p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        p.kill();out,err=p.communicate()
        return {"returncode":p.returncode,"sqlstate":"TIMEOUT","stdout":out[-450:],"stderr":err[-900:]}
    m=re.search(r"ERROR:\s+([0-9A-Z]{5}):",err)
    return {"returncode":p.returncode,"sqlstate":m.group(1) if m else ("00000" if p.returncode==0 else "UNKNOWN"),
            "stdout":out[-450:],"stderr":err[-900:]}

def locks(db, app_names=()):
    if not app_names:
        app_names=["H2_R03_A","H2_R03_B","H2_R03_WRITER2"]
    rows=query(db,"""SELECT a.pid,a.application_name,a.state,a.wait_event_type,
                      l.mode,l.granted,coalesce(c.relname,'') AS relname
                      FROM pg_stat_activity a
                      JOIN pg_locks l ON a.pid=l.pid
                      LEFT JOIN pg_class c ON c.oid=l.relation
                      WHERE a.application_name=ANY(%s) AND
                      (l.relation IS NULL OR c.relname IN ('attack_event_classifications','h2_classification_heads'))
                      ORDER BY a.application_name,l.mode,l.granted""",(list(app_names),))
    return [dict(zip(["pid","app","activity","wait","mode","granted","relation"],r)) for r in rows]

def observed(db,predicate,seconds=8):
    end=time.monotonic()+seconds
    last=[]
    while time.monotonic()<end:
        last=locks(db)
        if predicate(last):
            return last
        time.sleep(.035)  # Polling is only a bound; a matching pg_locks row is the proof.
    raise AssertionError("NO_MATCHING_REAL_PG_LOCK: "+str(last)[-950:])

def step(section, id, subcase, db, operation, expected, got, before=None, after=None, sql_text=None):
    ok=(expected==got if isinstance(expected,str) else got in expected)
    data={"section":section,"id":id,"subcase":subcase,"database":db,"operation":operation,
          "sql":sql_text or operation,"expected":expected,"observed":got,"sqlstate":got,
          "before_sha256":before,"after_sha256":after,"match":ok}
    ALL["steps"].append(data)
    if not ok:
        raise AssertionError("%s/%s SQLSTATE expected %s actual %s" % (id,subcase,expected,got))
    return got

def negative(section,id,subcase,db,as_user,statement,expected,params=()):
    before=fingerprint(db)
    st=sqlstate(db,as_user,statement,params)
    after=fingerprint(db)
    step(section,id,subcase,db,statement,expected,st,before,after,statement)
    if before!=after:
        raise AssertionError("%s/%s changed persistent state despite refusal" % (id,subcase))
    return st

def requires(predicate,msg):
    if not predicate:raise AssertionError(msg)

def record(section,id,fn,expected=None):
    start=len(ALL["steps"])
    try:
        status=fn()
        if status not in ("PARTIAL","BLOCKED","FAIL"):
            status="PASS"
        note=None
    except Exception as exc:
        status="FAIL";note=repr(exc)
        ALL["errors"].append({"section":section,"id":id,"error":repr(exc)})
    executed=ALL["steps"][start:]
    record={"section":section,"id":id,"status":status,"expected":expected,
            "executed_subcases":len(executed),"steps":executed,"error":note}
    ALL["records"].append(record)
    print(json.dumps({"id":id,"section":section,"status":status,"checks":len(executed),"error":note}),flush=True)
    return status

def rollback(db,expected_history,fault="none",ok=True,path=None):
    return ns.run(db,path or ns.DOWN,role="h2_migrator_test",history=expected_history,fault=fault,ok=ok)

def temp_rollback(db,expected_history,fault="none",ok=True,path=None):
    ns.temp(db)
    try:
        return rollback(db,expected_history,fault,ok,path)
    finally:ns.untemp(db)

def put(db,tag,identity=1,city="kyiv",parent=None,user="h2_local",session=None):
    """Actual canonical INSERT using all required constraints, default uuid."""
    key=hashlib.sha256(tag.encode()).hexdigest()
    episode="%024x"%identity
    statement="""INSERT INTO public.attack_event_classifications(
       classification_key_version,classification_key,historical_episode_id,city_key,
       alert_type,alert_start_at,alert_end_at,verdict,is_event,qa_reasons_state,
       qa_reasons,classifier_blob_sha,classifier_methodology_version,
       normalization_version,evidence_set_sha256,binding_state,origin_repository,
       origin_provenance,origin_provenance_sha256,originating_frozen_case_id_state,
       supersedes_classification_uid,revision_reason)
       VALUES ('attack-event-classification-key-v2',%s,%s,%s,'AIR',
       '2026-01-01T01:00:00Z','2026-01-01T02:00:00Z','NO_CONFIRMED_EVENT',
       false,'MATERIALIZED','[]'::jsonb,%s,'synthetic','synthetic',%s,'UNBOUND',
       'synthetic','{}'::jsonb,%s,'NOT_APPLICABLE',%s,%s)
       RETURNING classification_uid"""
    vals=(key,episode,city,"a"*40,"b"*64,"c"*64,parent,"synthetic-correction" if parent else None)
    if session is not None:
        return str(session.execute(statement,vals).fetchone()[0])
    pw="synthetic_only" if user=="h2_local" else "synthetic_only_local_role"
    with conn(db,user,pw,autocommit=True) as c:
        return str(c.execute(statement,vals).fetchone()[0])

def invalid_put(db,tag,identity=1,city="kyiv",parent=None):
    before=fingerprint(db)
    try:
        put(db,tag,identity,city,parent)
        st="00000"
    except psycopg.Error as exc:
        st=exc.sqlstate or "UNKNOWN"
    after=fingerprint(db)
    return st,before,after

def close():
    ALL["pg_version"]=query("postgres","SHOW server_version")[0][0]
    groups=["R","H","C","D"]
    ALL["totals"]={p:{"passed":sum(r["status"]=="PASS" for r in ALL["records"] if r["section"]==p),
                      "partial":sum(r["status"]=="PARTIAL" for r in ALL["records"] if r["section"]==p),
                      "failed":sum(r["status"]=="FAIL" for r in ALL["records"] if r["section"]==p),
                      "executed":sum(r["section"]==p for r in ALL["records"])}
                   for p in groups}
    ALL["verdict"]="FAIL" if ALL["errors"] else ("PARTIAL" if any(r["status"]!="PASS" for r in ALL["records"]) else "PASS")
    OUT.write_text(json.dumps(ALL,indent=2,sort_keys=True,default=str)+"\n")
    print(json.dumps({"copy":COPY,"verdict":ALL["verdict"],"totals":ALL["totals"],
                       "errors":len(ALL["errors"])}),flush=True)
    if ALL["errors"]:raise SystemExit(1)
