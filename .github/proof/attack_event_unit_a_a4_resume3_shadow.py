#!/usr/bin/env python3
"""Unit A A4: server-enforced READ ONLY / REPEATABLE READ shadow gap comparison."""
from __future__ import annotations
from collections import Counter, defaultdict
import hashlib, json, os, re, sys, traceback
from pathlib import Path
from urllib.parse import urlparse
import psycopg
from attack_event_unit_a_a4_resume3 import init, save, Blocked, need, canon, hobj, norm, sha, OUT, TEMP, NEON_PROJECT, NEON_BRANCH

def guard(report, statement, args=()):
    sql=statement.lstrip()
    need(re.match(r"(?is)^(SELECT|WITH|SHOW)\\b",sql) is not None,
         "UNIT_A_A4_SHADOW_CONFIGURATION_MISMATCH","non-readonly SQL rejected")
    report["neon"]["select_count"]+=1
    return args

def query(cursor, report, statement, args=()):
    guard(report, statement, args)
    cursor.execute(statement,args)
    return cursor.fetchall()

def obj(row,fields):
    return dict(zip(fields,row))

def lookup(rows,field):
    result=defaultdict(list)
    for row in rows:result[str(row[field])].append(row)
    return result

def dbnorm(v):
    if isinstance(v,(list,dict)):return norm(v)
    return norm(v)

def compare(record,actual,fields):
    return [field for field in fields if dbnorm(record.get(field))!=dbnorm(actual.get(field))]

def validate_schema(cur,report):
    names=("alert_episodes","attack_event_classifications","attack_events","attack_event_sources")
    catalog=query(cur,report,"""SELECT table_name,column_name,data_type,is_nullable
      FROM information_schema.columns
      WHERE table_schema='public' AND table_name=ANY(%s)
      ORDER BY table_name,ordinal_position""",(list(names),))
    indices=query(cur,report,"""SELECT tablename,indexname,indexdef FROM pg_indexes
      WHERE schemaname='public' AND tablename=ANY(%s)
      ORDER BY tablename,indexname""",(list(names),))
    constraints=query(cur,report,"""SELECT cl.relname,c.conname,c.contype,pg_get_constraintdef(c.oid)
      FROM pg_constraint c JOIN pg_class cl ON cl.oid=c.conrelid
      JOIN pg_namespace n ON n.oid=cl.relnamespace
      WHERE n.nspname='public' AND cl.relname=ANY(%s)
      ORDER BY cl.relname,c.conname""",(list(names),))
    cols=defaultdict(set)
    for table,col,*_ in catalog:cols[table].add(col)
    required={
      "alert_episodes":set("episode_uid legacy_episode_id city_key alert_type episode_state canonicalization_version start_at end_at".split()),
      "attack_event_classifications":set("classification_uid classification_key_version classification_key historical_episode_id city_key alert_start_at alert_end_at verdict is_event positive_tier event_types qa_reasons_state qa_reasons classifier_reason_codes classifier_blob_sha classifier_methodology_version normalization_version evidence_set_sha256 review_provenance_sha256 supersedes_classification_uid alert_episode_uid".split()),
      "attack_events":set("attack_event_uid attack_event_key_version attack_event_key event_grain historical_episode_id city_key alert_start_at alert_end_at event_status current_classification_uid alert_episode_uid".split()),
      "attack_event_sources":set("source_link_key_version source_link_key classification_uid observation_id source_family source_type source_type_state source_url telegram_channel telegram_message_id source_timestamp source_timestamp_state source_timestamp_raw event_timestamp_if_stated excerpt content_sha256 content_hash_basis observation_classification_outcome classification_episode_id evidence_payload retrieval_provenance".split())}
    missing={t:sorted(required[t]-cols[t]) for t in names if required[t]-cols[t]}
    uniq={}
    for t,key in (("attack_event_classifications","classification_key"),("attack_events","attack_event_key"),("attack_event_sources","source_link_key")):
        uniq[t]=any("UNIQUE" in str(v[2]).upper() and re.search(r"\\b"+re.escape(key)+r"\\b",str(v[2])) for v in indices if v[0]==t)
    report["neon"]["schema_catalog_sha256"]=hobj({"columns":catalog,"indices":indices,"constraints":constraints})
    report["neon"]["schema_missing_columns"]=missing
    report["neon"]["schema_unique_keys"]=uniq
    compatible=not missing and all(uniq.values()) and bool(constraints)
    report["neon"]["schema_compatible"]=compatible
    need(compatible,"UNIT_A_A4_SHADOW_SCHEMA_DRIFT",
         {"missing":missing,"unique_keys":uniq,"schema_sha":report["neon"]["schema_catalog_sha256"]})

def audit(cur,rep,projection):
    classes=projection["classifications"]
    sources=projection["sources"]
    positive_events=projection["events"]
    ids=sorted({x["historical_episode_id"] for x in classes})
    ck=sorted(x["classification_key"] for x in classes)
    sk=sorted(x["source_link_key"] for x in sources)
    by_id={x["historical_episode_id"]:x for x in classes}
    need(len(by_id)==len(classes)==1713,"UNIT_A_A4_CANONICAL_PROJECTION_SEMANTIC_DRIFT","nonunique parent IDs")
    validate_schema(cur,rep)
    pfields="episode_uid legacy_episode_id city_key alert_type episode_state canonicalization_version start_at end_at".split()
    parents=[obj(r,pfields) for r in query(cur,rep,
       """SELECT episode_uid,legacy_episode_id,city_key,alert_type,episode_state,canonicalization_version,start_at,end_at
       FROM public.alert_episodes WHERE legacy_episode_id=ANY(%s)""",(ids,))]
    pmap=lookup(parents,"legacy_episode_id")
    bindings={};missing=[];ambiguous=[]
    for c in classes:
        pid=c["historical_episode_id"]
        matches=[r for r in pmap.get(pid,[]) if
           all(dbnorm(r.get(k))==dbnorm(v) for k,v in c["parent_identity"].items())]
        if len(matches)==1:bindings[c["classification_key"]]=str(matches[0]["episode_uid"])
        elif not matches:missing.append((pid,c["city_key"]))
        else:ambiguous.append((pid,c["city_key"],len(matches)))
    rep["parents"]={"exact_bound":len(bindings),"missing":len(missing),"ambiguous":len(ambiguous),
       "identity_sha256":hobj(sorted(bindings.items()))}
    need(not missing and not ambiguous and len(bindings)==1713,
         "UNIT_A_A4_PARENT_BINDING_GAP",{"first_missing":sorted(missing)[:1],"first_ambiguous":sorted(ambiguous)[:1]})
    cf="classification_uid classification_key_version classification_key historical_episode_id city_key alert_start_at alert_end_at verdict is_event positive_tier event_types qa_reasons_state qa_reasons classifier_reason_codes classifier_blob_sha classifier_methodology_version normalization_version evidence_set_sha256 review_provenance_sha256 supersedes_classification_uid alert_episode_uid".split()
    crows=[obj(row,cf) for row in query(cur,rep,
      "SELECT "+",".join(cf)+" FROM public.attack_event_classifications WHERE historical_episode_id=ANY(%s)",(ids,))]
    ckey=lookup(crows,"classification_key")
    roots=defaultdict(list)
    for row in crows:roots[(row["city_key"],row["historical_episode_id"],dbnorm(row["alert_start_at"]),dbnorm(row["alert_end_at"]))].append(row)
    existing_by_uid={str(x["classification_uid"]):x for x in crows}
    superseded={str(x["supersedes_classification_uid"]) for x in crows if x["supersedes_classification_uid"] is not None}
    classifications=[];conflicts=[];tips_problem=[];tip_by_key={}
    cfields="classification_key_version classification_key historical_episode_id city_key alert_start_at alert_end_at verdict is_event positive_tier event_types qa_reasons_state qa_reasons classifier_reason_codes classifier_blob_sha classifier_methodology_version normalization_version evidence_set_sha256 review_provenance_sha256".split()
    for c in classes:
        key=c["classification_key"]
        rows=ckey.get(key,[])
        if len(rows)>1:conflicts.append({"key":key,"issue":"duplicate key"});continue
        if rows:
            mismatch=compare(c,rows[0],cfields)
            if mismatch or str(rows[0]["alert_episode_uid"])!=bindings[key]:
                conflicts.append({"key":key,"fields":mismatch,"parent_identity_changed":str(rows[0]["alert_episode_uid"])!=bindings[key]});continue
            classifications.append({"action":"NOOP_EXACT_PRESENT","classification_key":key,
               "classification_uid":str(rows[0]["classification_uid"])})
            tip_by_key[key]=str(rows[0]["classification_uid"])
            continue
        identity=(c["city_key"],c["historical_episode_id"],c["alert_start_at"],c["alert_end_at"])
        candidates=roots[identity]
        tips=[x for x in candidates if str(x["classification_uid"]) not in superseded]
        if len(tips)>1:tips_problem.append({"id":c["historical_episode_id"],"tips":len(tips)});continue
        tip=tips[0] if tips else None
        action="INSERT_REVISION" if tip else "INSERT_INITIAL"
        classifications.append({"action":action,"classification_key":key,
          "historical_episode_id":c["historical_episode_id"],"city_key":c["city_key"],
          "alert_episode_uid":bindings[key],"semantic_row_sha256":hobj(c),
          "semantic_row":c,"expected_tip_uid":str(tip["classification_uid"]) if tip else None,
          "expected_tip_key":tip["classification_key"] if tip else None,
          "expected_prior_verdict":tip["verdict"] if tip else None})
    rep["classification_gap"]={
       "exact_present":sum(x["action"]=="NOOP_EXACT_PRESENT" for x in classifications),
       "missing_no_prior_revision":sum(x["action"]=="INSERT_INITIAL" for x in classifications),
       "missing_with_prior_revision":sum(x["action"]=="INSERT_REVISION" for x in classifications),
       "semantic_conflicts":len(conflicts),"multiple_current_tips":len(tips_problem)}
    need(not conflicts,"UNIT_A_A4_CLASSIFICATION_SEMANTIC_CONFLICT",sorted(conflicts,key=str)[:1])
    need(not tips_problem,"UNIT_A_A4_MULTIPLE_CURRENT_CLASSIFICATION_TIPS",sorted(tips_problem,key=str)[:1])
    need(len(classifications)==1713,"UNIT_A_A4_DELTA_NOT_LOSSLESS","classification action count")
    sf="source_link_key_version source_link_key classification_uid observation_id source_family source_type source_type_state source_url telegram_channel telegram_message_id source_timestamp source_timestamp_state source_timestamp_raw event_timestamp_if_stated excerpt content_sha256 content_hash_basis observation_classification_outcome classification_episode_id evidence_payload retrieval_provenance".split()
    srows=[obj(row,sf+["parent_classification_key"]) for row in query(cur,rep,
      "SELECT "+",".join("s."+s for s in sf)+",c.classification_key AS parent_classification_key FROM public.attack_event_sources s JOIN public.attack_event_classifications c ON c.classification_uid=s.classification_uid WHERE s.source_link_key=ANY(%s)",(sk,))]
    existing_sources=lookup(srows,"source_link_key")
    source_actions=[];source_conflicts=[]
    source_fields=[x for x in sf if x not in ("classification_uid",)]
    for source in sources:
        key=source["source_link_key"];rows=existing_sources.get(key,[])
        if rows:
            mismatch=compare(source,rows[0],source_fields)
            if len(rows)>1 or mismatch or str(rows[0]["parent_classification_key"])!=source["classification_key"]:
                source_conflicts.append({"key":key,"mismatch":mismatch,"parent_key":rows[0]["parent_classification_key"]});continue
            source_actions.append({"action":"NOOP_EXACT_PRESENT","source_link_key":key})
        else:
            source_actions.append({"action":"INSERT_SOURCE_LINK","source_link_key":key,
              "target_classification_key":source["classification_key"],
              "observation_id":source["observation_id"],"content_sha256":source["content_sha256"],
              "semantic_source_row_sha256":hobj(source),"semantic_source_row":source})
    rep["source_gap"]={"exact_present":sum(x["action"]=="NOOP_EXACT_PRESENT" for x in source_actions),
       "missing":sum(x["action"]=="INSERT_SOURCE_LINK" for x in source_actions),
       "semantic_conflicts":len(source_conflicts)}
    need(not source_conflicts,"UNIT_A_A4_SOURCE_LINK_SEMANTIC_CONFLICT",sorted(source_conflicts,key=str)[:1])
    need(len(source_actions)==1559,"UNIT_A_A4_DELTA_NOT_LOSSLESS","source action count")
    ef="attack_event_uid attack_event_key_version attack_event_key event_grain historical_episode_id city_key alert_start_at alert_end_at event_status current_classification_uid alert_episode_uid".split()
    erows=[obj(row,ef) for row in query(cur,rep,
       "SELECT "+",".join(ef)+" FROM public.attack_events WHERE historical_episode_id=ANY(%s)",(ids,))]
    ev_by_id=lookup(erows,"historical_episode_id")
    e_actions=[];e_conflicts=[];positives={x["historical_episode_id"]:x for x in positive_events}
    for c in classes:
        eid=c["historical_episode_id"];found=[row for row in ev_by_id.get(eid,[]) if row["city_key"]==c["city_key"]]
        if len(found)>1:e_conflicts.append({"id":eid,"issue":"multiple episode events"});continue
        desired=positives.get(eid);current=found[0] if found else None
        if current:
            expkey=c["attack_event_key"]
            if (current["attack_event_key"]!=expkey or
                dbnorm(current["alert_start_at"])!=c["alert_start_at"] or
                dbnorm(current["alert_end_at"])!=c["alert_end_at"] or
                str(current["alert_episode_uid"])!=bindings[c["classification_key"]]):
                e_conflicts.append({"id":eid,"issue":"stable event identity/parent conflict"});continue
        if not current:
            if desired:e_actions.append({"action":"INSERT_EVENT","attack_event_key":desired["attack_event_key"],
               "historical_episode_id":eid,"city_key":c["city_key"],
               "desired_classification_key":c["classification_key"],"semantic_precondition_hash":hobj({"absent":True,"episode":eid})})
            continue
        current_pointer=str(current["current_classification_uid"]) if current["current_classification_uid"] else None
        desired_uid=tip_by_key.get(c["classification_key"])
        good_status=current["event_status"]==("ACTIVE" if desired else "WITHDRAWN")
        good_pointer=desired_uid is not None and current_pointer==desired_uid
        if good_status and good_pointer:e_actions.append({"action":"NOOP_EXACT_PRESENT","attack_event_key":c["attack_event_key"]});continue
        action="WITHDRAW_EVENT" if not desired and not good_status else "UPDATE_CURRENT_CLASSIFICATION_POINTER"
        e_actions.append({"action":action,"attack_event_key":c["attack_event_key"],
         "historical_episode_id":eid,"city_key":c["city_key"],
         "expected_current_db_state":{"event_uid":str(current["attack_event_uid"]),
            "event_status":current["event_status"],"current_classification_uid":current_pointer},
         "desired_classification_key":c["classification_key"],
         "semantic_precondition_hash":hobj({"event_key":current["attack_event_key"],
           "event_status":current["event_status"],"current_uid":current_pointer})})
    rep["event_gap"]={
       "exact_present":sum(x["action"]=="NOOP_EXACT_PRESENT" for x in e_actions),
       "missing":sum(x["action"]=="INSERT_EVENT" for x in e_actions),
       "pointer_updates_required":sum(x["action"]=="UPDATE_CURRENT_CLASSIFICATION_POINTER" for x in e_actions),
       "withdrawals_required":sum(x["action"]=="WITHDRAW_EVENT" for x in e_actions),
       "semantic_conflicts":len(e_conflicts)}
    need(not e_conflicts,"UNIT_A_A4_EVENT_SEMANTIC_CONFLICT",sorted(e_conflicts,key=str)[:1])
    action_counts=Counter(x["action"] for x in classifications+source_actions+e_actions)
    nonnoop={x:v for x,v in action_counts.items() if not x.startswith("NOOP")}
    delta={"schema_version":1,"project":NEON_PROJECT,"branch":NEON_BRANCH,
      "parent_binding_sha256":rep["parents"]["identity_sha256"],
      "projection_sha256":rep["offline_projection"]["run_a_hashes"]["complete"],
      "classification_actions":[x for x in classifications if x["action"]!="NOOP_EXACT_PRESENT"],
      "source_actions":[x for x in source_actions if x["action"]!="NOOP_EXACT_PRESENT"],
      "event_actions":[x for x in e_actions if x["action"]!="NOOP_EXACT_PRESENT"],
      "action_counts":dict(sorted(nonnoop.items()))}
    h1=hobj(delta);h2=hobj(json.loads(canon(delta)))
    need(h1==h2,"UNIT_A_A4_DELTA_NONDETERMINISTIC",{"a":h1,"b":h2})
    rep["A5_frozen_delta_manifest"]=delta
    rep["A5_DELTA_SHA256"]=h1
    rep["A5_delta_run_a_sha256"]=h1
    rep["A5_delta_run_b_sha256"]=h2
    rep["A5_REQUIRED"]="YES" if sum(nonnoop.values()) else "NO"
    rep["A5_AUTHORIZED"]="NO"
    rep["A5_PERSISTENCE_DELTA_GATE"]="PASS"
    rep["A4_CANONICAL_PROJECTION_GATE"]="PASS"
    rep["verdict"]="ATTACK-EVENT EXECUTION UNIT A SHADOW PERSISTENCE GAP AUDIT = PROVEN"
    rep["first_failing_gate"]=None
    rep["phase_reached"]="FROZEN_A5_DELTA"
    save(rep)
    print("A4_VERDICT=PROVEN")
    print("A5_REQUIRED="+rep["A5_REQUIRED"])
    print("A5_AUTHORIZED=NO")
    print("A5_DELTA_SHA256="+h1)
    print("A5_MUTATION_ACTIONS="+str(sum(nonnoop.values())))
    print("READ_ONLY_SELECT_COUNT="+str(rep["neon"]["select_count"]))

def main():
    rep=init()
    try:
        rep=json.loads(OUT.read_bytes())
        need(rep.get("A4_OFFLINE_PROJECTION_GATE")=="PASS" and
             rep.get("A4_CANONICAL_PROJECTION_GATE")=="PASS" and
             rep.get("A5_AUTHORIZED")=="NO",
             "UNIT_A_A4_CANONICAL_PROJECTION_SEMANTIC_DRIFT","offline gate not passed")
        proj=TEMP.read_bytes()
        need(sha(proj)==rep["offline_projection"]["temp_projection_sha256"] and
             hobj(json.loads(proj))==rep["offline_projection"]["run_a_hashes"]["complete"]==
                rep["offline_projection"]["run_b_hashes"]["complete"],
             "UNIT_A_A4_PROJECTION_NONDETERMINISTIC","temp projection checksum mismatch")
        need(os.environ.get("PHASE1_PROD_SHADOW_BRANCH_ID")==NEON_BRANCH,
             "UNIT_A_A4_SHADOW_CONFIGURATION_MISMATCH","wrong approved branch variable")
        url=os.environ.get("PHASE1_PROD_SHADOW_DATABASE_URL")
        need(url is not None and bool(url.strip()),"UNIT_A_A4_SHADOW_CONFIGURATION_MISMATCH","shadow secret absent")
        host=urlparse(url).hostname
        expecthost=os.environ.get("A4_EXPECTED_SHADOW_HOST")
        need(bool(host) and bool(expecthost) and host==expecthost,
             "UNIT_A_A4_SHADOW_CONFIGURATION_MISMATCH","Neon endpoint does not match approved permanent branch")
        import psycopg
        conn=psycopg.connect(url,autocommit=True,connect_timeout=15)
        rep["neon"]["contacted"]=True
        try:
            with conn.cursor() as cur:
                cur.execute("BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                state=query(cur,rep,"SELECT current_setting('transaction_isolation'),current_setting('transaction_read_only'),current_database()")
                iso,ro,dbname=state[0]
                rep["neon"]["repeatable_read"]=iso=="repeatable read"
                rep["neon"]["read_only_transaction"]=ro=="on"
                rep["neon"]["branch_identity_verified"]=True
                rep["neon"]["database_name"]=dbname
                need(rep["neon"]["repeatable_read"] and rep["neon"]["read_only_transaction"],
                     "UNIT_A_A4_SHADOW_CONFIGURATION_MISMATCH","server transaction not repeatable-read/read-only")
                audit(cur,rep,json.loads(proj))
        finally:
            try:conn.execute("ROLLBACK")
            finally:conn.close()
        save(rep)
    except Blocked as exc:
        rep["verdict"]="ATTACK-EVENT EXECUTION UNIT A SHADOW PERSISTENCE GAP AUDIT = BLOCKED"
        rep["A5_PERSISTENCE_DELTA_GATE"]="FAIL"
        rep["first_failing_gate"]=exc.code
        rep["smallest_deterministic_blocker_example"]=norm(exc.example)
        rep["A5_AUTHORIZED"]="NO"
        save(rep)
        print("A4_VERDICT=BLOCKED FIRST_FAILING_GATE="+exc.code)
        if exc.example:print("BLOCKER="+str(exc.example)[:500])
    except Exception as exc:
        rep["verdict"]="ATTACK-EVENT EXECUTION UNIT A SHADOW PERSISTENCE GAP AUDIT = BLOCKED"
        rep["A5_PERSISTENCE_DELTA_GATE"]="FAIL"
        rep["first_failing_gate"]="UNIT_A_A4_SHADOW_CONFIGURATION_MISMATCH"
        rep["smallest_deterministic_blocker_example"]={"error":type(exc).__name__,"traceback":traceback.format_exc(limit=2)[-500:]}
        rep["A5_AUTHORIZED"]="NO"
        save(rep)
        print("A4_VERDICT=BLOCKED FIRST_FAILING_GATE="+rep["first_failing_gate"])

if __name__=="__main__": main()
