#!/usr/bin/env python3
"""Proof-only targeted repair for three reconciled Lviv canonical boundaries."""
from __future__ import annotations
import argparse, json, os
from dataclasses import dataclass
from typing import Any, Mapping
from db_phase1_core import alerts_in_ua_source_record_key, legacy_episode_id

FROZEN_PRODUCTION_REF="928a566b7a8dc7916c93810eaafe319da3b28ee4"
RECONCILIATION_PROOF_HEAD="16cad19f8862960ea50820288eb32fabd8e3dc68"
RAW_OBJECT_PATH="kyiv-air-alerts-grafana/data/alerts_in_ua_bridge_2026-09-07_16.csv.gz.b64"
RAW_OBJECT_GIT_BLOB_SHA="1ece234379381b4d7c0d10f851a86aa61aa958f6"
DECODED_CSV_SHA256="ba48bf85bd62e7f127dd1703bfcb9d38b4b960690adf1243175ce59366ec4d5a"
LVIV_ROWS_SHA256="2c9f256c75ac79c523ce826b3d48703bce2e83f0749b98092a1d8dc83c3f7e90"
SOURCE_KEY="alerts_in_ua"
SOURCE_RECORD_KEY_VERSION="alerts-in-ua-v1"
CANONICALIZATION_VERSION="alert-canonicalization-v1"
SCHEMA_VERSION="001_phase1_core"
REPAIR_NAME="lviv-production-boundary-reconciliation-2026-10-01"
EXPECTED_NON_TARGET_123_MD5="304ef1d8e5b62f8eebf27f4285b52669"
TARGET_UIDS=("575f370c-6e99-4623-8219-f8fbdfd6c978","c90e7b05-1982-461f-945f-53d8130c627b","451c8a2c-248a-41e5-b49e-31af3f44631f")

class RepairBlocked(RuntimeError): pass
class ForcedRepairFailure(RuntimeError): pass

@dataclass(frozen=True)
class RepairTarget:
    episode_uid:str; old_start:str; old_end:str; old_legacy_id:str
    new_start:str; new_end:str; new_legacy_id:str
    static_start:str; static_end:str; raw_local_start:str; raw_local_end:str
    ua_start_flag:bool; ua_end_flag:bool; static_start_flag:bool; static_end_flag:bool
    @property
    def source_identity(self):
        return alerts_in_ua_source_record_key({"city_key":"lviv","alert_type":"AIR","start_at":self.static_start,"end_at":self.static_end})

TARGETS=(
 RepairTarget("575f370c-6e99-4623-8219-f8fbdfd6c978","2026-09-12T22:00:05.398348Z","2026-09-12T22:14:23.315771Z","b3df9090f7264ddbd726e113","2026-09-12T22:00:05.398348Z","2026-09-12T22:14:27Z","7dd411c2a2587efc740a1a66","2026-09-12T22:00:06Z","2026-09-12T22:14:27Z","2026-09-13T01:00:06+03:00","2026-09-13T01:14:27+03:00",True,False,False,True),
 RepairTarget("c90e7b05-1982-461f-945f-53d8130c627b","2026-09-13T02:32:14.172141Z","2026-09-13T06:11:11.976953Z","202d8d1527183a6282ccf1e2","2026-09-13T02:32:14Z","2026-09-13T06:11:11.976953Z","c2cd9a96768756d84c250735","2026-09-13T02:32:14Z","2026-09-13T06:11:11Z","2026-09-13T05:32:14+03:00","2026-09-13T09:11:11+03:00",False,True,True,False),
 RepairTarget("451c8a2c-248a-41e5-b49e-31af3f44631f","2026-09-15T16:44:13.025549Z","2026-09-15T17:08:51.287249Z","b24ba103214a22f4d5e65ce4","2026-09-15T16:44:13Z","2026-09-15T17:09:02Z","94ce779cf047984e881bfdd5","2026-09-15T16:44:13Z","2026-09-15T17:09:02Z","2026-09-15T19:44:13+03:00","2026-09-15T20:09:02+03:00",False,False,True,True),
)
EXPECTED_SOURCE_RECORD_KEYS=("980d8771eb46bca4bc542aa98c987795f254e01ce4fc59d25b1e4cd0fb55c7e0","828e721a803eb19280ff3b20182314e3196dba48516a780fd050639136354664","9c827b4b944729c82daafc29b42acd7146752920e6871a6ff39962e18b785b91")

for t,k in zip(TARGETS,EXPECTED_SOURCE_RECORD_KEYS):
    assert t.source_identity[1]==k
    assert legacy_episode_id("lviv",t.new_start,t.new_end)==t.new_legacy_id

def _six(v):
    body=v[:-1]
    if "." not in body: return body+".000000Z"
    h,f=body.split(".",1); return h+"."+(f+"000000")[:6]+"Z"

def repair_plan():
    out=[]
    for t in TARGETS:
        pre,key=t.source_identity
        out.append({"episode_uid":t.episode_uid,"old":{"start_at":t.old_start,"end_at":t.old_end,"legacy_episode_id":t.old_legacy_id},"new":{"start_at":t.new_start,"end_at":t.new_end,"legacy_episode_id":t.new_legacy_id},"alerts_in_ua":{"source_key":SOURCE_KEY,"source_record_key_version":SOURCE_RECORD_KEY_VERSION,"source_record_key":key,"canonical_preimage":pre,"source_start_at":t.static_start,"source_end_at":t.static_end,"raw_local_start":t.raw_local_start,"raw_local_end":t.raw_local_end,"contributes_start_boundary":t.static_start_flag,"contributes_end_boundary":t.static_end_flag},"ukrainealarm_flags":{"contributes_start_boundary":t.ua_start_flag,"contributes_end_boundary":t.ua_end_flag}})
    return out

def _map(row,cols):
    return dict(row) if isinstance(row,Mapping) else dict(zip(cols,row))

def inspect_state(cursor,lock=False):
    lock_sql=" FOR UPDATE" if lock else ""
    u=TARGET_UIDS
    cursor.execute(f"""SELECT episode_uid::text,legacy_episode_id,to_char(start_at AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),to_char(end_at AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),city_key,alert_type,episode_state,canonicalization_version,created_by_run_id::text,to_char(created_at AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"') FROM alert_episodes WHERE episode_uid IN (%s,%s,%s) ORDER BY episode_uid{lock_sql}""",u)
    episodes=[_map(r,("episode_uid","legacy_episode_id","start_at","end_at","city_key","alert_type","episode_state","canonicalization_version","created_by_run_id","created_at")) for r in cursor.fetchall()]
    cursor.execute(f"""SELECT source_observation_id::text,episode_uid::text,source_key,source_record_key_version,source_record_key,to_char(source_start_at AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),to_char(source_end_at AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),binding_state,canonicalization_role,contributes_start_boundary,contributes_end_boundary,source_retrieved_at,last_seen_by_run_id::text,last_seen_at,raw_object_path,provenance FROM alert_episode_sources WHERE episode_uid IN (%s,%s,%s) ORDER BY episode_uid,source_key,source_record_key{lock_sql}""",u)
    sources=[_map(r,("source_observation_id","episode_uid","source_key","source_record_key_version","source_record_key","source_start_at","source_end_at","binding_state","canonicalization_role","contributes_start_boundary","contributes_end_boundary","source_retrieved_at","last_seen_by_run_id","last_seen_at","raw_object_path","provenance")) for r in cursor.fetchall()]
    cursor.execute("""SELECT md5(coalesce(string_agg(to_jsonb(t)::text,E'\\n' ORDER BY to_jsonb(t)::text),'')) FROM alert_episodes t WHERE episode_uid NOT IN (%s,%s,%s)""",u)
    return {"episodes":episodes,"sources":sources,"non_target_123_md5":cursor.fetchone()[0]}

def classify_state(state):
    if state.get("non_target_123_md5")!=EXPECTED_NON_TARGET_123_MD5: raise RepairBlocked("123 non-target Lviv episode fingerprint changed")
    episodes={str(x["episode_uid"]):x for x in state.get("episodes",[])}
    if set(episodes)!=set(TARGET_UIDS): raise RepairBlocked("target episode set mismatch")
    old_ok=repaired_ok=True
    for t in TARGETS:
        e=episodes[t.episode_uid]
        common=e.get("city_key")=="lviv" and e.get("alert_type")=="AIR" and e.get("episode_state")=="closed" and e.get("canonicalization_version")==CANONICALIZATION_VERSION
        old_ok &= common and e.get("legacy_episode_id")==t.old_legacy_id and e.get("start_at")==_six(t.old_start) and e.get("end_at")==_six(t.old_end)
        repaired_ok &= common and e.get("legacy_episode_id")==t.new_legacy_id and e.get("start_at")==_six(t.new_start) and e.get("end_at")==_six(t.new_end)
    by={uid:[] for uid in TARGET_UIDS}
    for s in state.get("sources",[]): by[str(s["episode_uid"])].append(s)
    if old_ok:
        for t in TARGETS:
            ss=by[t.episode_uid]
            if len(ss)!=1: raise RepairBlocked("pristine target has unexpected source observation count")
            s=ss[0]
            if not (s.get("source_key")=="ukrainealarm_region_history" and s.get("binding_state")=="bound" and s.get("canonicalization_role")=="canonical_input" and bool(s.get("contributes_start_boundary")) and bool(s.get("contributes_end_boundary"))): raise RepairBlocked("pristine source contract mismatch")
        return "pristine"
    if repaired_ok:
        for t,k in zip(TARGETS,EXPECTED_SOURCE_RECORD_KEYS):
            ss=by[t.episode_uid]
            if len(ss)!=2: raise RepairBlocked("repaired target has unexpected source observation count")
            ua=[s for s in ss if s.get("source_key")=="ukrainealarm_region_history"]
            st=[s for s in ss if s.get("source_key")==SOURCE_KEY and s.get("source_record_key")==k]
            if len(ua)!=1 or len(st)!=1: raise RepairBlocked("repaired source identity mismatch")
            if (bool(ua[0]["contributes_start_boundary"]),bool(ua[0]["contributes_end_boundary"]))!=(t.ua_start_flag,t.ua_end_flag): raise RepairBlocked("UkraineAlarm flags mismatch")
            if (bool(st[0]["contributes_start_boundary"]),bool(st[0]["contributes_end_boundary"]))!=(t.static_start_flag,t.static_end_flag): raise RepairBlocked("Alerts.in.ua flags mismatch")
            if st[0]["source_start_at"]!=_six(t.static_start) or st[0]["source_end_at"]!=_six(t.static_end): raise RepairBlocked("Alerts.in.ua interval mismatch")
        return "already_repaired"
    raise RepairBlocked("target state is neither exact pristine nor exact repaired state")

def _guard_collisions(c):
    c.execute("SELECT count(*) FROM alert_episode_sources WHERE source_key=%s AND source_record_key_version=%s AND source_record_key IN (%s,%s,%s)",(SOURCE_KEY,SOURCE_RECORD_KEY_VERSION,*EXPECTED_SOURCE_RECORD_KEYS))
    if c.fetchone()[0]: raise RepairBlocked("Alerts.in.ua source_record_key already exists")
    c.execute("SELECT count(*) FROM alert_episodes WHERE legacy_episode_id IN (%s,%s,%s)",tuple(t.new_legacy_id for t in TARGETS))
    if c.fetchone()[0]: raise RepairBlocked("candidate legacy_episode_id already exists")
    for t in TARGETS:
        c.execute("SELECT count(*) FROM alert_episodes WHERE city_key='lviv' AND alert_type='AIR' AND start_at=%s::timestamptz AND end_at=%s::timestamptz",(t.new_start,t.new_end))
        if c.fetchone()[0]: raise RepairBlocked("candidate exact parent interval already exists")

def _provenance(t,pre):
    return {"source_family":"alerts_in_ua_static_bridge","frozen_production_ref":FROZEN_PRODUCTION_REF,"raw_object_path":RAW_OBJECT_PATH,"git_blob_sha":RAW_OBJECT_GIT_BLOB_SHA,"decoded_csv_sha256":DECODED_CSV_SHA256,"lviv_rows_sha256":LVIV_ROWS_SHA256,"raw_local_start":t.raw_local_start,"raw_local_end":t.raw_local_end,"utc_normalized_start":t.static_start,"utc_normalized_end":t.static_end,"repair_reason":"production_boundary_supersedes_phase1","canonical_preimage":pre}

def repair(connection,dry_run=False,force_failure_after_first_source=False,inspector=inspect_state,db_branch=None):
    c=connection.cursor()
    try:
        c.execute("/* LVIV_BOUNDARY_REPAIR:BEGIN */ BEGIN")
        classification=classify_state(inspector(c,lock=True))
        if classification=="already_repaired":
            connection.rollback(); return {"status":"already_repaired","writes":0,"plan":repair_plan()}
        _guard_collisions(c)
        if dry_run:
            connection.rollback(); return {"status":"dry_run","writes":0,"plan":repair_plan()}
        if not db_branch: raise RepairBlocked("db_branch must be supplied explicitly")
        c.execute("""/* LVIV_BOUNDARY_REPAIR:RUN_INSERT */ INSERT INTO ingestion_runs(run_kind,source_key,city_key,db_branch,schema_version,canonicalization_version,status,started_at,parameters,stats) VALUES('canonical_boundary_repair',%s,'lviv',%s,%s,%s,'running',now(),%s::jsonb,'{}'::jsonb) RETURNING run_id""",(SOURCE_KEY,db_branch,SCHEMA_VERSION,CANONICALIZATION_VERSION,json.dumps({"repair":REPAIR_NAME,"frozen_production_ref":FROZEN_PRODUCTION_REF,"reconciliation_proof_head":RECONCILIATION_PROOF_HEAD,"affected_episode_count":3},sort_keys=True)))
        run_id=c.fetchone()[0]
        for i,(t,k) in enumerate(zip(TARGETS,EXPECTED_SOURCE_RECORD_KEYS)):
            pre,key=t.source_identity
            if key!=k: raise RepairBlocked("source identity drift")
            c.execute("""/* LVIV_BOUNDARY_REPAIR:SOURCE_INSERT */ INSERT INTO alert_episode_sources(episode_uid,source_key,source_record_key_version,source_record_key,source_native_id,city_key,alert_type,source_start_at,source_end_at,source_retrieved_at,binding_state,canonicalization_role,duplicate_of_observation_id,match_method,start_delta_ms,end_delta_ms,contributes_start_boundary,contributes_end_boundary,raw_sha256,raw_object_path,provenance,first_persisted_by_run_id,last_seen_by_run_id) VALUES(%s::uuid,%s,%s,%s,NULL,'lviv','AIR',%s::timestamptz,%s::timestamptz,NULL,'bound','canonical_input',NULL,'canonical_boundary_repair',NULL,NULL,%s,%s,NULL,%s,%s::jsonb,%s::uuid,%s::uuid)""",(t.episode_uid,SOURCE_KEY,SOURCE_RECORD_KEY_VERSION,key,t.static_start,t.static_end,t.static_start_flag,t.static_end_flag,RAW_OBJECT_PATH,json.dumps(_provenance(t,pre),sort_keys=True),run_id,run_id))
            if force_failure_after_first_source and i==0: raise ForcedRepairFailure("deterministic failure after first static source insert")
        for t in TARGETS:
            c.execute("""/* LVIV_BOUNDARY_REPAIR:UA_FLAGS */ UPDATE alert_episode_sources SET contributes_start_boundary=%s,contributes_end_boundary=%s WHERE episode_uid=%s::uuid AND source_key='ukrainealarm_region_history' AND binding_state='bound' AND canonicalization_role='canonical_input'""",(t.ua_start_flag,t.ua_end_flag,t.episode_uid))
            if c.rowcount!=1: raise RepairBlocked("UkraineAlarm contributor update count != 1")
            c.execute("""/* LVIV_BOUNDARY_REPAIR:PARENT_UPDATE */ UPDATE alert_episodes SET start_at=%s::timestamptz,end_at=%s::timestamptz,legacy_episode_id=%s,updated_by_run_id=%s::uuid,updated_at=now() WHERE episode_uid=%s::uuid AND legacy_episode_id=%s AND start_at=%s::timestamptz AND end_at=%s::timestamptz""",(t.new_start,t.new_end,t.new_legacy_id,run_id,t.episode_uid,t.old_legacy_id,t.old_start,t.old_end))
            if c.rowcount!=1: raise RepairBlocked("parent update count != 1")
        c.execute("""/* LVIV_BOUNDARY_REPAIR:RUN_FINALIZE */ UPDATE ingestion_runs SET status='succeeded',ingest_committed_at=now(),finished_at=now(),stats=%s::jsonb WHERE run_id=%s::uuid AND status='running'""",(json.dumps({"affected_episode_count":3,"inserted_source_observations":3,"checkpoint_changes":0},sort_keys=True),run_id))
        if c.rowcount!=1: raise RepairBlocked("repair ingestion_run finalize count != 1")
        connection.commit(); return {"status":"repaired","writes":1,"run_id":str(run_id),"plan":repair_plan()}
    except Exception:
        connection.rollback(); raise
    finally:
        close=getattr(c,"close",None)
        if callable(close): close()

def _connect(url):
    try:
        import psycopg; return psycopg.connect(url)
    except ImportError:
        import psycopg2; return psycopg2.connect(url)

def main():
    p=argparse.ArgumentParser(); p.add_argument("--dry-run",action="store_true"); p.add_argument("--force-failure-after-first-source",action="store_true"); p.add_argument("--db-branch",default=os.environ.get("DB_BRANCH")); a=p.parse_args()
    url=os.environ.get("DATABASE_URL")
    if not url: raise SystemExit("DATABASE_URL is required")
    conn=_connect(url)
    try: print(json.dumps(repair(conn,dry_run=a.dry_run,force_failure_after_first_source=a.force_failure_after_first_source,db_branch=a.db_branch),sort_keys=True,separators=(",",":")))
    finally: conn.close()
    return 0
if __name__=="__main__": raise SystemExit(main())
