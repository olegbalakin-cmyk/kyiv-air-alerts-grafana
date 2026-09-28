#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,os,re,time
from datetime import datetime,timezone
from pathlib import Path
import psycopg
from psycopg.rows import dict_row
from db_phase1_lviv_import import build_lviv_persistence_payload

TABLES=("ingestion_runs","alert_episodes","alert_episode_sources","ingestion_checkpoints")
EXPECTED0={k:0 for k in TABLES}
EXPECTED1={"ingestion_runs":1,"alert_episodes":126,"alert_episode_sources":140,"ingestion_checkpoints":1}
EXPECTED2={"ingestion_runs":2,"alert_episodes":126,"alert_episode_sources":140,"ingestion_checkpoints":1}

def req(x,m):
    if not x: raise AssertionError(m)
def iso(x):
    if x is None:return None
    if not isinstance(x,datetime):
        s=str(x).replace("Z","+00:00");x=datetime.fromisoformat(s)
    return x.astimezone(timezone.utc).isoformat().replace("+00:00","Z")
def conn(name):
    u=os.environ.get(name);req(u,f"missing {name}")
    last=None
    for _ in range(30):
        try:return psycopg.connect(u,row_factory=dict_row,connect_timeout=10)
        except Exception as e:last=e;time.sleep(2)
    raise RuntimeError(type(last).__name__)
def one(c,q,p=()):
    with c.cursor() as x:x.execute(q,p);r=x.fetchone()
    req(r is not None,"expected row");return dict(r)
def all_(c,q,p=()):
    with c.cursor() as x:x.execute(q,p);return [dict(r) for r in x.fetchall()]
def counts(c):
    r=one(c,"SELECT (SELECT count(*) FROM ingestion_runs)::int ingestion_runs,(SELECT count(*) FROM alert_episodes)::int alert_episodes,(SELECT count(*) FROM alert_episode_sources)::int alert_episode_sources,(SELECT count(*) FROM ingestion_checkpoints)::int ingestion_checkpoints")
    return {k:int(r[k]) for k in TABLES}
def dump(p,o):Path(p).write_text(json.dumps(o,indent=2,sort_keys=True,default=lambda x:iso(x) if isinstance(x,datetime) else str(x))+"\n")
def load(p):return json.loads(Path(p).read_text())

def parity(c,payload):
    rows=all_(c,"SELECT legacy_episode_id,start_at,end_at FROM alert_episodes ORDER BY legacy_episode_id")
    e={x["legacy_episode_id"]:x for x in payload["episodes"]};a={x["legacy_episode_id"]:x for x in rows}
    missing=sorted(set(e)-set(a));unexpected=sorted(set(a)-set(e));mm=[]
    for k in sorted(set(e)&set(a)):
        if iso(e[k]["start_at"])!=iso(a[k]["start_at"]) or iso(e[k]["end_at"])!=iso(a[k]["end_at"]):mm.append(k)
    dup=[r["legacy_episode_id"] for r in all_(c,"SELECT legacy_episode_id FROM alert_episodes GROUP BY legacy_episode_id HAVING count(*)>1")]
    boundary=[r["legacy_episode_id"] for r in all_(c,"SELECT e.legacy_episode_id FROM alert_episodes e LEFT JOIN alert_episode_sources s ON s.episode_uid=e.episode_uid GROUP BY e.episode_uid,e.legacy_episode_id HAVING NOT coalesce(bool_or(s.contributes_start_boundary),false) OR NOT coalesce(bool_or(s.contributes_end_boundary),false)")]
    out={"db_episodes":len(rows),"missing_ids":missing,"unexpected_ids":unexpected,"interval_mismatches":mm,"duplicate_ids":dup,"boundary_errors":boundary,"result":"PASS"}
    req(len(rows)==126 and not missing and not unexpected and not mm and not dup and not boundary,f"oracle parity {out}");return out

def canon(c):
    r=one(c,"SELECT (SELECT count(DISTINCT legacy_episode_id)::int FROM alert_episodes) episodes,(SELECT count(DISTINCT (source_key,source_record_key_version,source_record_key))::int FROM alert_episode_sources) sources,(SELECT count(*)::int FROM alert_episode_sources WHERE binding_state='bound') bound,(SELECT count(*)::int FROM alert_episode_sources WHERE canonicalization_role='canonical_input') canonical_input,(SELECT count(*)::int FROM alert_episode_sources WHERE canonicalization_role='duplicate_alias') duplicate_alias,(SELECT count(*)::int FROM alert_episode_sources WHERE source_retrieved_at IS NOT NULL) retrieved")
    split={x["source_key"]:int(x["n"]) for x in all_(c,"SELECT source_key,count(*)::int n FROM alert_episode_sources GROUP BY source_key")}
    req(r=={"episodes":126,"sources":140,"bound":140,"canonical_input":140,"duplicate_alias":0,"retrieved":0},f"canonical {r}")
    req(split=={"vadimkin_official_data_uk":120,"ukrainealarm_region_history":20},f"split {split}");return {**r,"source_split":split}
def checkpoint(c,payload):
    rows=all_(c,"SELECT checkpoint_id::text checkpoint_id,source_key,city_key,stream_key,checkpoint_seq,checkpoint_kind,previous_checkpoint_id::text previous_checkpoint_id,checked_at,continuity_verified,continuity_method,continuity_anchor_at,observed_oldest_start_at,observed_latest_end_at,observed_record_count,cursor,metadata,created_by_run_id::text created_by_run_id FROM ingestion_checkpoints")
    req(len(rows)==1,f"checkpoint count {len(rows)}");r=rows[0];e=payload["checkpoint_candidate"]
    for k in ("source_key","city_key","stream_key","checkpoint_seq","checkpoint_kind","observed_record_count"):req(r[k]==e[k],f"checkpoint {k}")
    req(r["previous_checkpoint_id"] is None and r["cursor"] is None,"bootstrap checkpoint shape")
    for k in ("checked_at","continuity_anchor_at","observed_oldest_start_at","observed_latest_end_at"):req(iso(r[k])==iso(e.get(k)),f"checkpoint time {k}")
    req(bool(r["continuity_verified"])==bool(e["continuity_verified"]) and r["continuity_method"]==e["continuity_method"] and r["metadata"]==e["metadata"],"checkpoint metadata")
    req(r["metadata"].get("observed_latest_end_is_coverage_watermark") is False,"watermark flag")
    cur=all_(c,"SELECT checkpoint_id::text checkpoint_id,checkpoint_seq FROM current_ingestion_checkpoints")
    req(len(cur)==1 and cur[0]["checkpoint_id"]==r["checkpoint_id"] and cur[0]["checkpoint_seq"]==1,"current checkpoint")
    return {"checkpoint_id":r["checkpoint_id"],"checkpoint_seq":1,"checkpoint_kind":"bootstrap","previous_checkpoint_id":None,"created_by_run_id":r["created_by_run_id"],"metadata":r["metadata"]}
def runs(c):return all_(c,"SELECT run_id::text run_id,run_kind,db_branch,schema_version,canonicalization_version,status,ingest_committed_at,finished_at,parameters,stats FROM ingestion_runs ORDER BY started_at,run_id")
def valid_run(r,branch,stats):
    req(r["run_kind"]=="bootstrap_import" and r["db_branch"]==branch and r["schema_version"]=="001_phase1_core" and r["canonicalization_version"]=="alert-canonicalization-v1" and r["status"]=="succeeded","run contract")
    req(r["ingest_committed_at"] is not None and r["finished_at"] is not None,"run timestamps")
    req(r["parameters"].get("assembly_profile")=="lviv-historical-v1" and r["stats"]==stats,f"run stats {r['stats']}")
def snap(c):
    ep={r["legacy_episode_id"]:[r["episode_uid"],iso(r["start_at"]),iso(r["end_at"]),r["created_by_run_id"],r["updated_by_run_id"]] for r in all_(c,"SELECT legacy_episode_id,episode_uid::text episode_uid,start_at,end_at,created_by_run_id::text created_by_run_id,updated_by_run_id::text updated_by_run_id FROM alert_episodes")}
    so={"\x1f".join((r["source_key"],r["source_record_key_version"],r["source_record_key"])):[r["source_observation_id"],r["first_persisted_by_run_id"],iso(r["first_persisted_at"]),r["last_seen_by_run_id"]] for r in all_(c,"SELECT source_key,source_record_key_version,source_record_key,source_observation_id::text source_observation_id,first_persisted_by_run_id::text first_persisted_by_run_id,first_persisted_at,last_seen_by_run_id::text last_seen_by_run_id FROM alert_episode_sources")}
    cp=one(c,"SELECT checkpoint_id::text checkpoint_id,checkpoint_seq,created_by_run_id::text created_by_run_id FROM ingestion_checkpoints")
    return {"episodes":ep,"sources":so,"checkpoint":cp}

def baseline(a):
    meta=load(a.meta);payload=build_lviv_persistence_payload();c=conn("PHASE1_E2E_DATABASE_URL")
    try:
        req(counts(c)==EXPECTED0,"baseline counts");req(one(c,"SELECT count(*)::int n FROM current_ingestion_checkpoints")["n"]==0,"baseline checkpoint")
        tabs={r["table_name"] for r in all_(c,"SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name=ANY(%s)",(list(TABLES),))};req(tabs==set(TABLES),f"schema tables {tabs}")
        req(one(c,"SELECT count(*)::int n FROM information_schema.views WHERE table_schema='public' AND table_name='current_ingestion_checkpoints'")["n"]==1,"view missing")
    finally:c.close()
    t=Path(a.tests).read_text();m=re.search(r"Ran\s+(\d+)\s+tests?",t);req(m and int(m.group(1))==23 and re.search(r"^OK\s*$",t,re.M),"tests")
    d=Path(a.dry).read_text();
    for x in ("canonical episodes = 126","source observations = 140","Vadimkin = 120","UkraineAlarm = 20","checkpoint candidates = 1","oracle parity = PASS"):req(x in d,f"dry {x}")
    req(len(payload["episodes"])==126 and len(payload["source_observations"])==140,"payload")
    out={"schema_version":"db-phase1-live-e2e-result-v1","code_commit":os.environ.get("GITHUB_SHA"),**meta,"workflow_run_id":os.environ.get("GITHUB_RUN_ID"),"tests":{"run":23,"passed":23,"failed":0,"result":"PASS"},"dry_run":{"canonical_episode_count":126,"source_observation_count":140,"vadimkin_count":120,"ukrainealarm_count":20,"checkpoint_candidate_count":1,"oracle_parity":"PASS"},"before_counts":EXPECTED0,"current_checkpoints_before":0,"credentials_exposed":False,"concurrency_gate":"PHASE-1 SAME-STREAM CONCURRENCY ENVIRONMENT-BLOCKED"};dump(a.result,out);print("LIVE_BASELINE_VERIFIED 0/0/0/0")
def first(a):
    out=load(a.result);payload=build_lviv_persistence_payload();c=conn("PHASE1_E2E_DATABASE_URL")
    try:
        req(counts(c)==EXPECTED1,"first counts");rr=runs(c);req(len(rr)==1,"first run count");st={"episodes_inserted":126,"episodes_existing":0,"source_observations_inserted":140,"source_observations_existing":0,"source_observations_last_seen_updated":0,"checkpoints_inserted":1,"exact_retry":False};valid_run(rr[0],out["neon_branch_id"],st);ca=canon(c);pa=parity(c,payload);cp=checkpoint(c,payload);s=snap(c)
    finally:c.close()
    dump(a.identities,s);out["first_apply"]={"run_id":rr[0]["run_id"],"counts":EXPECTED1,"stats":st,"canonical_state":ca,"oracle_parity":pa,"checkpoint":cp,"result":"success","exit_code":0};dump(a.result,out);print("FIRST_APPLY_VERIFIED 1/126/140/1")
def second(a):
    out=load(a.result);before=load(a.identities);payload=build_lviv_persistence_payload();c=conn("PHASE1_E2E_DATABASE_URL")
    try:
        req(counts(c)==EXPECTED2,"second counts");rr=runs(c);req(len(rr)==2 and rr[0]["run_id"]==out["first_apply"]["run_id"] and rr[1]["run_id"]!=rr[0]["run_id"],"run ids");st={"episodes_inserted":0,"episodes_existing":126,"source_observations_inserted":0,"source_observations_existing":140,"source_observations_last_seen_updated":140,"checkpoints_inserted":0,"exact_retry":True};valid_run(rr[1],out["neon_branch_id"],st);ca=canon(c);pa=parity(c,payload);cp=checkpoint(c,payload);after=snap(c);req(one(c,"SELECT count(*)::int n FROM ingestion_checkpoints WHERE checkpoint_seq=2")["n"]==0,"seq2")
    finally:c.close()
    req(before["episodes"]==after["episodes"] and len(after["episodes"])==126,"episode identity")
    req(set(before["sources"])==set(after["sources"]) and len(after["sources"])==140,"source keys")
    first_id=rr[0]["run_id"];second_id=rr[1]["run_id"]
    for k,v in after["sources"].items():
        b=before["sources"][k];req(v[:3]==b[:3] and v[1]==first_id and v[3]==second_id,f"source provenance {k}")
    req(before["checkpoint"]==after["checkpoint"] and cp["checkpoint_id"]==out["first_apply"]["checkpoint"]["checkpoint_id"],"checkpoint stable")
    p=conn("PHASE1_PRIMARY_DATABASE_URL");ac=conn("PHASE1_ACCEPTED_DATABASE_URL")
    try:pc=counts(p);acc=counts(ac)
    finally:p.close();ac.close()
    req(pc==EXPECTED0,f"primary {pc}");req(acc==EXPECTED1,f"accepted {acc}")
    out["second_apply"]={"run_id":second_id,"counts":EXPECTED2,"stats":st,"canonical_state":ca,"oracle_parity":pa,"checkpoint":cp,"result":"success","exit_code":0};out["identity_stability"]={"episodes":{"stable":True,"count":126,"second_run_created_or_updated":0},"source_observations":{"stable":True,"count":140},"first_persisted_provenance_stable":True,"last_seen_advanced_to_retry_run":{"updated":140,"expected":140,"result":"PASS"},"checkpoint":{"stable":True,"checkpoint_id":cp["checkpoint_id"],"checkpoint_seq":1}};out["parent_isolation"]={"primary_counts":pc,"primary_unchanged":True,"accepted_bootstrap_counts":acc,"accepted_bootstrap_branch_unchanged":True};out["verdict"]="PHASE-1 LIVE E2E PERSISTENCE ADAPTER PROVEN";dump(a.result,out);print("PHASE1_LIVE_E2E_RESULT PASS")
def main():
    p=argparse.ArgumentParser();p.add_argument("phase",choices=("baseline","first","second"));p.add_argument("--meta");p.add_argument("--tests");p.add_argument("--dry");p.add_argument("--identities",required=True);p.add_argument("--result",required=True);a=p.parse_args();{"baseline":baseline,"first":first,"second":second}[a.phase](a)
if __name__=="__main__":main()
