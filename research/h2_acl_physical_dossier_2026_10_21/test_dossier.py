#!/usr/bin/env python3
"""Isolated H2 seven-relacl physical/semantic decision experiment. No external DSNs."""
import hashlib
import json
import os
import subprocess
import sys
import traceback
from pathlib import Path

import psycopg
from psycopg import sql

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "research/h2_rollback_adversarial_2026-10-20"))
import harness as h

ns = h.ns
COPY = os.environ.get("H2_COPY", "A")
P = "h2_acl_" + COPY.lower() + "_"
PATH = Path("/tmp/h2_acl_decision_" + COPY + ".json")
SEVEN = (
    "alert_episodes", "ingestion_runs", "ingestion_checkpoints",
    "current_ingestion_checkpoints", "attack_event_classifications",
    "attack_event_sources", "attack_events"
)
ROLES = {
    "direct": P + "direct",
    "group": P + "group",
    "inherited": P + "inherited",
    "setonly": P + "setonly",
    "public": P + "public",
    "grantor": P + "grantor",
    "recipient": P + "recipient",
    "swap": P + "swap",
}
ROLE_SET = [
    "h2_schema_owner_test", "h2_migrator_test", "h2_app_ingest_writer_test",
    "h2_head_guard_test", "h2_readonly_test", "h2_unrelated_test",
    *ROLES.values()
]
REPORT = {
    "copy": COPY, "source_commit": os.getenv("GITHUB_SHA"),
    "original_008_blob": "59eab59235f8aee14837ce7494649edba674e1ce",
    "original_007_blob": "8dc20d11f28db2d8c2b6244b5c43e8bd23548abd",
    "checks": [], "errors": [], "evidence": {},
    "verdict": "UNSTARTED",
}
def ck(label, ok, details=None):
    REPORT["checks"].append({"id": label, "pass": bool(ok), "details": details})
    if not ok:
        raise AssertionError(label + ": " + str(details)[:1400])

def qry(db, statement, params=()):
    return ns.q(db, statement, params)

def clone(src, suffix):
    dest = "h2_" + COPY.lower() + "_acl_" + suffix
    ns.q("postgres", sql.SQL("CREATE DATABASE {} WITH TEMPLATE {}").format(
        sql.Identifier(dest), sql.Identifier(src)))
    return dest

def get_rel(db):
    rows = qry(db, """SELECT relname,oid::text,relkind::text,
                               relowner::regrole::text,relacl::text
                        FROM pg_class WHERE relnamespace='public'::regnamespace
                        AND relname=ANY(%s) ORDER BY 1""", (list(SEVEN),))
    return {r[0]: {"oid": r[1], "kind": r[2],
                    "owner": r[3], "acl": r[4]} for r in rows}

def catalog_except_seven(a, b):
    x = ns.snapshot(a)
    y = ns.snapshot(b)
    diffs = {}
    for key in x.keys() | y.keys():
        if key == "relations":
            xr = {z[0]: z[1:] for z in x[key]}
            yr = {z[0]: z[1:] for z in y[key]}
            diffs[key] = {name: {"before": xr.get(name), "after": yr.get(name)}
                          for name in xr.keys() | yr.keys()
                          if xr.get(name) != yr.get(name)}
        elif x.get(key) != y.get(key):
            diffs[key] = {"before": x.get(key), "after": y.get(key)}
    return {k:v for k,v in diffs.items() if v}

def rows(db):
    return qry(db, """SELECT classification_uid::text,to_jsonb(c)::text
                      FROM public.attack_event_classifications c
                      ORDER BY classification_uid""")

def true_heads(db):
    return qry(db, """SELECT c.city_key,c.historical_episode_id,
                      c.alert_start_at::text,c.alert_end_at::text,
                      c.classification_uid::text
                      FROM public.attack_event_classifications c
                      WHERE NOT EXISTS (
                        SELECT 1 FROM public.attack_event_classifications x
                        WHERE x.supersedes_classification_uid=c.classification_uid)
                      ORDER BY 1,2,3,4""")

def explicit_acl_items(db):
    return qry(db, """SELECT c.relname,
       CASE WHEN a.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee) END,
       pg_get_userbyid(a.grantor),a.privilege_type,a.is_grantable
       FROM pg_class c
       CROSS JOIN LATERAL aclexplode(
           COALESCE(c.relacl,acldefault('r',c.relowner))) a
       WHERE c.relnamespace='public'::regnamespace
       AND c.relname=ANY(%s)
       ORDER BY 1,2,3,4,5""", (list(SEVEN),))

def privilege_matrix(db):
    result = {}
    result["table"] = qry(db, """SELECT r.rolname,c.relname,p.priv,
          has_table_privilege(r.oid,c.oid,p.priv),
          has_table_privilege(r.oid,c.oid,p.priv||' WITH GRANT OPTION')
      FROM pg_roles r CROSS JOIN pg_class c
      CROSS JOIN LATERAL unnest(ARRAY[
          'SELECT','INSERT','UPDATE','DELETE','TRUNCATE',
          'REFERENCES','TRIGGER','MAINTAIN']) p(priv)
      WHERE r.rolname=ANY(%s) AND c.relnamespace='public'::regnamespace
        AND c.relname=ANY(%s)
      ORDER BY 1,2,3""", (ROLE_SET,list(SEVEN)))
    result["column"] = qry(db, """SELECT r.rolname,c.relname,a.attname,p.priv,
          has_column_privilege(r.oid,c.oid,a.attname,p.priv),
          has_column_privilege(r.oid,c.oid,a.attname,
                               p.priv||' WITH GRANT OPTION')
      FROM pg_roles r CROSS JOIN pg_class c
      JOIN pg_attribute a ON a.attrelid=c.oid AND a.attnum>0
                         AND NOT a.attisdropped
      CROSS JOIN LATERAL unnest(ARRAY[
          'SELECT','INSERT','UPDATE','REFERENCES']) p(priv)
      WHERE r.rolname=ANY(%s) AND c.relnamespace='public'::regnamespace
        AND c.relname=ANY(%s)
        AND (a.attname IN ('updated_at','classification_uid','event_status')
             OR a.attnum<=2)
      ORDER BY 1,2,3,4""", (ROLE_SET,list(SEVEN)))
    result["schema"] = qry(db, """SELECT r.rolname,n.nspname,p.priv,
          has_schema_privilege(r.oid,n.oid,p.priv),
          has_schema_privilege(r.oid,n.oid,p.priv||' WITH GRANT OPTION')
      FROM pg_roles r CROSS JOIN pg_namespace n
      CROSS JOIN LATERAL unnest(ARRAY['USAGE','CREATE']) p(priv)
      WHERE r.rolname=ANY(%s) AND n.nspname='public'
      ORDER BY 1,2,3""", (ROLE_SET,))
    result["functions"] = qry(db, """SELECT r.rolname,p.proname,
          has_function_privilege(r.oid,p.oid,'EXECUTE'),
          has_function_privilege(r.oid,p.oid,'EXECUTE WITH GRANT OPTION')
      FROM pg_roles r CROSS JOIN pg_proc p
      WHERE r.rolname=ANY(%s) AND p.pronamespace='public'::regnamespace
      ORDER BY 1,2""", (ROLE_SET,))
    result["default"] = qry(db, """SELECT defaclrole::regrole::text,
          CASE WHEN defaclnamespace=0 THEN 'GLOBAL'
               ELSE defaclnamespace::regnamespace::text END,
          defaclobjtype::text,defaclacl::text
      FROM pg_default_acl ORDER BY 1,2,3,4""")
    result["membership"] = qry("postgres", """SELECT r.rolname,
          pg_has_role(r.oid,%s::regrole,'MEMBER'),
          pg_has_role(r.oid,%s::regrole,'USAGE'),
          pg_has_role(r.oid,%s::regrole,'SET')
      FROM pg_roles r WHERE r.rolname=ANY(%s) ORDER BY 1""",
      (ROLES["group"],ROLES["group"],ROLES["group"],ROLE_SET))
    result["acl_items"] = explicit_acl_items(db)
    return result

def actor(db, who, commands):
    password = "synthetic_acl_only"
    with h.conn(db, user=who, password=password, autocommit=True) as c:
        out=[]
        for stmt in commands:
            try:
                cur=c.execute(stmt)
                out.append({"sql":stmt,"state":"00000",
                            "result": cur.fetchall() if cur.description else None})
            except psycopg.Error as exc:
                out.append({"sql":stmt,"state":exc.sqlstate or "UNKNOWN",
                            "error":str(exc)[:300]})
        return out

def privilege_changes(db):
    direct, group, grantor, recip = (
        ROLES["direct"],ROLES["group"],ROLES["grantor"],ROLES["recipient"])
    commands = [
        "GRANT USAGE ON SCHEMA public TO PUBLIC",
        "GRANT CREATE ON SCHEMA public TO " + ROLES["swap"],
        "GRANT SELECT ON TABLE public.alert_episodes TO PUBLIC",
        "GRANT SELECT ON TABLE public.ingestion_runs TO " + direct,
        "GRANT UPDATE ON TABLE public.attack_events TO " + group + " WITH GRANT OPTION",
        "GRANT SELECT ON TABLE public.attack_event_sources TO " + grantor + " WITH GRANT OPTION",
        "GRANT UPDATE (updated_at) ON TABLE public.attack_events TO " + direct + " WITH GRANT OPTION",
        "GRANT SELECT (classification_uid) ON TABLE public.attack_event_classifications TO " + direct,
        "ALTER DEFAULT PRIVILEGES FOR ROLE h2_schema_owner_test IN SCHEMA public "
          "GRANT SELECT ON TABLES TO " + direct,
        "ALTER DEFAULT PRIVILEGES FOR ROLE h2_schema_owner_test IN SCHEMA public "
          "GRANT EXECUTE ON FUNCTIONS TO " + direct,
    ]
    for command in commands:
        qry(db,command)
    grantor_actions=actor(db,grantor,[
        "GRANT SELECT ON TABLE public.attack_event_sources TO " + recip,
        "REVOKE GRANT OPTION FOR SELECT ON TABLE public.attack_event_sources "
           "FROM " + recip,
        "GRANT SELECT ON TABLE public.attack_event_sources TO " + recip + " WITH GRANT OPTION",
    ])
    ck(db+"_grantor_sql", all(x["state"]=="00000" for x in grantor_actions),grantor_actions)
    return grantor_actions

def future(db):
    with h.conn(db,autocommit=True) as c:
        c.execute("SET ROLE h2_schema_owner_test")
        c.execute("CREATE TABLE public.h2_acl_future_table (id bigint, comment text)")
        c.execute("""CREATE FUNCTION public.h2_acl_future_func() RETURNS integer
                      LANGUAGE SQL AS 'SELECT 1'""")
        c.execute("RESET ROLE")
    for stmt in [
        "ALTER TABLE public.alert_episodes OWNER TO " + ROLES["swap"],
        "ALTER TABLE public.alert_episodes OWNER TO h2_schema_owner_test",
        "ALTER VIEW public.current_ingestion_checkpoints OWNER TO " + ROLES["swap"],
        "ALTER VIEW public.current_ingestion_checkpoints OWNER TO h2_schema_owner_test",
        "ALTER TABLE public.alert_episodes ADD COLUMN h2_acl_future_col text",
        "GRANT UPDATE ON TABLE public.ingestion_runs TO " + ROLES["direct"]+" WITH GRANT OPTION",
        "REVOKE GRANT OPTION FOR UPDATE ON TABLE public.ingestion_runs FROM "+ROLES["direct"],
        "GRANT EXECUTE ON FUNCTION public.h2_acl_future_func() TO "+ROLES["grantor"]+" WITH GRANT OPTION",
        "REVOKE GRANT OPTION FOR EXECUTE ON FUNCTION public.h2_acl_future_func() FROM "+ROLES["grantor"],
    ]:
        qry(db,stmt)
    return qry(db, """SELECT c.relname,c.relowner::regrole::text,
          c.relacl::text FROM pg_class c
      WHERE c.relnamespace='public'::regnamespace
        AND c.relname IN ('h2_acl_future_table','alert_episodes','current_ingestion_checkpoints')
      ORDER BY 1"""), qry(db, """SELECT p.proname,p.proowner::regrole::text,p.proacl::text
      FROM pg_proc p WHERE p.pronamespace='public'::regnamespace
        AND p.proname='h2_acl_future_func'""")

def future_rights(db):
    return qry(db, """SELECT r.rolname,
        has_table_privilege(r.oid,'public.h2_acl_future_table','SELECT'),
        has_function_privilege(r.oid,'public.h2_acl_future_func()','EXECUTE'),
        has_function_privilege(r.oid,'public.h2_acl_future_func()','EXECUTE WITH GRANT OPTION')
      FROM pg_roles r WHERE r.rolname=ANY(%s) ORDER BY 1""", (ROLE_SET,))

def normalized_dump(db):
    proc = subprocess.run([
        "docker","run","--rm","--network","host","-e","PGPASSWORD=synthetic_only",
        "postgres:18.6","pg_dump","--schema-only","--no-owner",
        "-h","127.0.0.1","-U","h2_local","-d",db],
        capture_output=True,text=True,timeout=100,
        env={**os.environ,"PGPASSWORD":"synthetic_only"})
    if proc.returncode != 0:
        raise RuntimeError("PG18.6 pg_dump failed: "+proc.stderr[-1000:])
    normalized = "".join(line for line in proc.stdout.splitlines(keepends=True)
                         if not line.startswith("\\restrict ")
                         and not line.startswith("\\unrestrict "))
    return normalized

def physical_probes(rolled):
    db = clone(rolled,"physprobe")
    qry(db,"CREATE SCHEMA h2_acl_scratch")
    before=get_rel(db)
    results=[]
    for name in SEVEN:
        obj="public."+name
        typ="VIEW" if before[name]["kind"]=="v" else "TABLE"
        sequences=[
            ("grant_owner_all", ["GRANT ALL PRIVILEGES ON TABLE "+obj+" TO h2_schema_owner_test"]),
            ("revoke_public_all", ["REVOKE ALL PRIVILEGES ON TABLE "+obj+" FROM PUBLIC"]),
            ("grant_revoke_other", [
                "GRANT SELECT ON TABLE "+obj+" TO "+ROLES["direct"],
                "REVOKE SELECT ON TABLE "+obj+" FROM "+ROLES["direct"]]),
            ("revoke_regrant_owner", [
                "REVOKE ALL PRIVILEGES ON TABLE "+obj+" FROM h2_schema_owner_test",
                "GRANT ALL PRIVILEGES ON TABLE "+obj+" TO h2_schema_owner_test"]),
            ("owner_roundtrip", [
                "ALTER "+typ+" "+obj+" OWNER TO "+ROLES["swap"],
                "ALTER "+typ+" "+obj+" OWNER TO h2_schema_owner_test"]),
            ("schema_roundtrip", [
                "ALTER "+typ+" "+obj+" SET SCHEMA h2_acl_scratch",
                "ALTER "+typ+" h2_acl_scratch."+name+" SET SCHEMA public"]),
        ]
        if typ=="VIEW":
            definition=qry(db,"SELECT pg_get_viewdef(%s::regclass,true)",(obj,))[0][0]
            sequences.append(("replace_view", [
                "CREATE OR REPLACE VIEW "+obj+" AS "+definition]))
        for key,stmts in sequences:
            outcome={"object":name,"probe":key,"commands":stmts,"sqlstate":"00000"}
            with h.conn(db,autocommit=False) as c:
                try:
                    for statement in stmts:
                        c.execute(statement)
                    new = c.execute("""SELECT oid::text,relacl::text,relowner::regrole::text
                                  FROM pg_class WHERE oid=%s::regclass""",(obj,)).fetchone()
                    outcome.update({"same_oid":new[0]==before[name]["oid"],
                                    "became_null":new[1] is None,
                                    "acl":new[1],"owner":new[2]})
                except psycopg.Error as exc:
                    outcome["sqlstate"]=exc.sqlstate or "UNKNOWN"
                    outcome["message"]=str(exc)[:350]
                finally:
                    c.rollback()
            results.append(outcome)
            if outcome.get("became_null"):
                REPORT["evidence"].setdefault("candidate_physical_methods",[]).append(outcome)
        # None of the committed state changes; exact identity and ACL must persist.
        after=get_rel(db)[name]
        ck("probe_aborts_preserve_"+name,before[name]==after,
           {"before":before[name],"after":after})
    REPORT["evidence"]["physical_probes"]=results
    successes=[x for x in results if x["sqlstate"]=="00000"]
    ck("supported_sequence_execution",len(successes)>=len(SEVEN)*4,
       {"successful":len(successes),"attempted":len(results)})
    return successes, [x for x in results if x.get("became_null")]

def contention(db):
    with h.conn(db,autocommit=False) as locker:
        locker.execute("LOCK TABLE public.alert_episodes IN ACCESS EXCLUSIVE MODE")
        with h.conn(db,autocommit=False) as contender:
            contender.execute("SET LOCAL lock_timeout='400ms'")
            outcomes=[]
            for stmt in (
                "ALTER TABLE public.alert_episodes ADD COLUMN h2_concurrent_probe text",
                "GRANT SELECT ON TABLE public.alert_episodes TO "+ROLES["recipient"],
            ):
                try:
                    contender.execute("SAVEPOINT h2_probe")
                    contender.execute(stmt)
                    state="00000"
                    contender.execute("ROLLBACK TO SAVEPOINT h2_probe")
                except psycopg.Error as exc:
                    state=exc.sqlstate or "UNKNOWN"
                    contender.execute("ROLLBACK TO SAVEPOINT h2_probe")
                outcomes.append((stmt,state))
            contender.rollback()
        locker.rollback()
    return outcomes

def main():
    v=qry("postgres","SHOW server_version")[0][0]
    REPORT["version"]=v
    ck("postgres_18_6",v.startswith("18.6"),v)
    for path,expected in [(ns.DOWN,REPORT["original_008_blob"]),
                          (ns.UP,REPORT["original_007_blob"])]:
        actual=subprocess.check_output(["git","hash-object",str(path)],text=True).strip()
        ck("unchanged_"+path.name,actual==expected,actual)
    ns.roles()
    for key,name in ROLES.items():
        kind = "NOLOGIN" if key in ("group","swap") else "LOGIN PASSWORD 'synthetic_acl_only'"
        qry("postgres","CREATE ROLE "+name+" "+kind+
            " NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS")
    qry("postgres","GRANT "+ROLES["group"]+" TO "+ROLES["inherited"]+
        " WITH INHERIT TRUE, SET FALSE, ADMIN FALSE")
    qry("postgres","GRANT "+ROLES["group"]+" TO "+ROLES["setonly"]+
        " WITH INHERIT FALSE, SET TRUE, ADMIN FALSE")
    control=ns.fresh("dossier_control")
    a=h.put(control,"root_a",identity=801)
    h.put(control,"revision_a",identity=801,parent=a)
    h.put(control,"root_b",identity=802)
    before_rows=rows(control)
    ck("populated_baseline_three_records",len(before_rows)==3,len(before_rows))
    rolled=clone(control,"rolled")
    # Actual accepted uninstrumented 001 -> role 003 -> 007 -> 008.
    ns.base(rolled)
    ck("populated_head_registry_backfill",h.heads(rolled)==true_heads(rolled),
       {"registry":h.heads(rolled),"tips":true_heads(rolled)})
    ck("two_distinct_heads",len(h.heads(rolled))==2,len(h.heads(rolled)))
    ns.temp(rolled)
    try:
        ck("accepted_007_installs",ns.run(rolled,ns.UP,role="h2_migrator_test")=="00000")
    finally:
        ns.untemp(rolled)
    ck("heads_unchanged_after_007",h.heads(rolled)==true_heads(rolled))
    ns.temp(rolled)
    try:
        ck("original_008_succeeds_populated",ns.run(
           rolled,ns.DOWN,role="h2_migrator_test",
           history=ns.history(rolled))=="00000")
    finally:
        ns.untemp(rolled)
    ck("populated_history_byte_rows",rows(rolled)==before_rows)
    ck("registry_expected_dropped_by_008",h.heads(rolled) is None)
    raw=catalog_except_seven(control,rolled)
    REPORT["evidence"]["initial_catalog_delta"]=raw
    expected=set(SEVEN)
    actual=set(raw.get("relations",{}))
    ck("only_seven_raw_catalog_differences",
       set(raw)=={"relations"} and actual==expected,raw)
    pre=get_rel(control); post=get_rel(rolled)
    ck("physical_null_to_owner_only_seven",
       all(pre[x]["acl"] is None and
           post[x]["acl"]=="{h2_schema_owner_test=arwdDxtm/h2_schema_owner_test}"
           and pre[x]["oid"]==post[x]["oid"] for x in SEVEN),
       {"control":pre,"rolled":post})
    ck("normalized_implicit_explicit_acl_entries",
       explicit_acl_items(control)==explicit_acl_items(rolled))
    control_matrix=privilege_matrix(control); rolled_matrix=privilege_matrix(rolled)
    ck("initial_14_principal_rights_and_grant_options",
       control_matrix==rolled_matrix,
       {k:len(v) for k,v in control_matrix.items()})
    successes,candidates=physical_probes(rolled)
    REPORT["evidence"]["restoration"]={
        "successful_sequences":len(successes),
        "attempted_sequences":len(REPORT["evidence"]["physical_probes"]),
        "null_candidates":len(candidates),"no_candidate_is_not_impossibility_proof":True}
    left=clone(control,"semanticcontrol")
    right=clone(rolled,"semanticrolled")
    l_grants=privilege_changes(left); r_grants=privilege_changes(right)
    ck("grantor_actor_results",l_grants==r_grants,l_grants)
    ck("grantor_identity_in_acl",explicit_acl_items(left)==explicit_acl_items(right))
    changed_left=privilege_matrix(left); changed_right=privilege_matrix(right)
    ck("public_direct_inherited_setonly_and_grant_options",
       changed_left==changed_right,
       {k:len(v) for k,v in changed_left.items()})
    role_actions={}
    for d in (left,right):
        setonly=actor(d,ROLES["setonly"],[
          "SELECT has_table_privilege(current_user,'public.attack_events','UPDATE')",
          "SET ROLE "+ROLES["group"],
          "SELECT has_table_privilege(current_user,'public.attack_events','UPDATE')",
          "RESET ROLE"])
        inherited=actor(d,ROLES["inherited"],[
          "SELECT has_table_privilege(current_user,'public.attack_events','UPDATE')",
          "SET ROLE "+ROLES["group"]])
        role_actions[d]={"setonly":setonly,"inherited":inherited}
    ck("role_setonly_vs_inherit_sessions",
       role_actions[left]["setonly"]==role_actions[right]["setonly"]
       and role_actions[left]["inherited"]==role_actions[right]["inherited"],
       role_actions)
    ck("setonly_executability",
       [x["state"] for x in role_actions[left]["setonly"]]==["00000"]*4
       and role_actions[left]["setonly"][0]["result"]==[(False,)]
       and role_actions[left]["setonly"][2]["result"]==[(True,)]
       and role_actions[left]["inherited"][0]["result"]==[(True,)]
       and role_actions[left]["inherited"][1]["state"]=="42501",
       role_actions[left])
    l_future=future(left); r_future=future(right)
    ck("future_ddl_owner_change_and_grants",l_future==r_future)
    ck("future_table_function_default_acl",
       future_rights(left)==future_rights(right),
       {"control":future_rights(left),"rolled":future_rights(right)})
    ck("post_future_all_rights_matrix",
       privilege_matrix(left)==privilege_matrix(right))
    ck("canonical_identity_unchanged_after_ddl",
       all(get_rel(left)[x]["oid"]==pre[x]["oid"]
           and get_rel(right)[x]["oid"]==post[x]["oid"] for x in SEVEN))
    before_membership=privilege_matrix(left)
    qry("postgres","REVOKE "+ROLES["group"]+" FROM "+ROLES["inherited"])
    ck("membership_revoke_same_rights",
       privilege_matrix(left)==privilege_matrix(right))
    qry("postgres","GRANT "+ROLES["group"]+" TO "+ROLES["inherited"]+
        " WITH INHERIT TRUE, SET FALSE, ADMIN FALSE")
    ck("membership_regrant_recovered_rights",
       privilege_matrix(left)==privilege_matrix(right)
       and privilege_matrix(left)==before_membership)
    l_concurrent=contention(left);r_concurrent=contention(right)
    REPORT["evidence"]["concurrency"]={"control":l_concurrent,"rolled":r_concurrent}
    ck("real_pg_lock_concurrent_ddl",l_concurrent==r_concurrent
       and l_concurrent[0][1]=="55P03",l_concurrent)
    raw_after=catalog_except_seven(left,right)
    REPORT["evidence"]["after_mutations_raw_delta"]=raw_after
    ck("only_seven_or_fewer_canonical_acl_differences",
       not set(raw_after)-{"relations"} and
       not set(raw_after.get("relations",{}))-expected,raw_after)
    dl=normalized_dump(left);dr=normalized_dump(right)
    REPORT["evidence"]["normalized_dump"]={
      "control_sha256":hashlib.sha256(dl.encode()).hexdigest(),
      "rolled_sha256":hashlib.sha256(dr.encode()).hexdigest(),
      "identical":dl==dr,
      "first_diff":next((i for i,(x,y) in enumerate(zip(dl,dr)) if x!=y),None)}
    ck("normalized_pg18_6_dump_post_future_ddl",dl==dr,
       REPORT["evidence"]["normalized_dump"])
    # Reapply the accepted 001/003/007 in an independent clone of the populated rollback.
    replay=clone(rolled,"reapply")
    ns.base(replay)
    ck("populated_reapply_restores_exact_tips",
       h.heads(replay)==true_heads(replay) and len(h.heads(replay))==2)
    ns.temp(replay)
    try:
        ck("reapply_007_succeeds",ns.run(replay,ns.UP,role="h2_migrator_test")=="00000")
    finally:
        ns.untemp(replay)
    ck("reapply_007_preserves_history",rows(replay)==before_rows)
    REPORT["evidence"]["population"]={
      "row_count":len(before_rows),"tip_count":2,
      "original_008_drops_registry":True,
      "reapply_rebuilds_correct_heads":h.heads(replay)==true_heads(replay)}
    REPORT["verdict"]="PARTIAL_NO_EXACT_RESTORATION_PROVEN" if not candidates else \
                      "PHYSICAL_CANDIDATE_REQUIRES_FULL_SEVEN_PROOF"
excepted=False

try:
    main()
except Exception as exc:
    REPORT["errors"].append({"error":repr(exc),"trace":traceback.format_exc()[-5500:]})
    REPORT["verdict"]="FAIL"
finally:
    REPORT["tests_total"]=len(REPORT["checks"])
    REPORT["tests_passed"]=sum(x["pass"] for x in REPORT["checks"])
    PATH.write_text(json.dumps(REPORT,indent=2,default=str)+"\n")
    print(json.dumps({"copy":COPY,"verdict":REPORT["verdict"],
      "passed":REPORT["tests_passed"],"total":REPORT["tests_total"],
      "errors":REPORT["errors"],"restoration":REPORT["evidence"].get("restoration"),
      "dump":REPORT["evidence"].get("normalized_dump")}),flush=True)
if REPORT["verdict"]=="FAIL":
    raise SystemExit(1)
