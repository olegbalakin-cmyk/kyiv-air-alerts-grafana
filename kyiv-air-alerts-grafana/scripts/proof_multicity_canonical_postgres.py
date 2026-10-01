#!/usr/bin/env python3
from __future__ import annotations
import argparse, copy, json, os, sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import psycopg
from psycopg.rows import dict_row

sys.path.insert(0, str(Path(__file__).resolve().parent))
import multicity_canonical_postgres as mc

CORPUS="8e9f3660039de4e0490db25229fe1760f5926b6b73490c8a325b9abc7555971b"
TARGET="br-icy-forest-b5mfyezq"
REPAIRED={
"575f370c-6e99-4623-8219-f8fbdfd6c978":"7dd411c2a2587efc740a1a66",
"c90e7b05-1982-461f-945f-53d8130c627b":"c2cd9a96768756d84c250735",
"451c8a2c-248a-41e5-b49e-31af3f44631f":"94ce779cf047984e881bfdd5"}

def utc(v):
    if isinstance(v,datetime): d=v
    else:
        s=str(v); s=s[:-1]+"+00:00" if s.endswith("Z") else s; d=datetime.fromisoformat(s)
    return d.astimezone(timezone.utc).isoformat().replace("+00:00","Z")

def q1(cur,sql):
    cur.execute(sql); return cur.fetchone()[0]

def fp(cur,table,order,where=""):
    cur.execute(f"SELECT md5(coalesce(string_agg(to_jsonb(x)::text,E'\\n' ORDER BY {order}),'')) FROM (SELECT * FROM {table} {where}) x")
    return cur.fetchone()[0]

def snap(conn):
    with conn.cursor() as c:
        counts={
        "ingestion_runs":q1(c,"SELECT count(*) FROM ingestion_runs"),
        "alert_episodes":q1(c,"SELECT count(*) FROM alert_episodes"),
        "alert_episode_sources":q1(c,"SELECT count(*) FROM alert_episode_sources"),
        "ingestion_checkpoints":q1(c,"SELECT count(*) FROM ingestion_checkpoints"),
        "max_checkpoint_seq":q1(c,"SELECT coalesce(max(checkpoint_seq),0) FROM ingestion_checkpoints"),
        "alert_state_snapshots":q1(c,"SELECT count(*) FROM alert_state_snapshots"),
        "alert_threat_observations":q1(c,"SELECT count(*) FROM alert_threat_observations"),
        "non_lviv_episodes":q1(c,"SELECT count(*) FROM alert_episodes WHERE city_key<>'lviv'")}
        f={
        "lviv":fp(c,"alert_episodes","x.episode_uid::text","WHERE city_key='lviv'"),
        "sources":fp(c,"alert_episode_sources","x.source_observation_id::text"),
        "checkpoints":fp(c,"ingestion_checkpoints","x.checkpoint_id::text"),
        "snapshots":fp(c,"alert_state_snapshots","x.snapshot_uid::text"),
        "threats":fp(c,"alert_threat_observations","x.threat_observation_uid::text"),
        "repair_run":fp(c,"ingestion_runs","x.run_id::text","WHERE run_id='2dad3093-0600-4de3-9dc1-5f578140c47e'::uuid")}
    conn.rollback(); return {"counts":counts,"fingerprints":f}

def prov():
    return {"run_kind":"multicity_canonical_bootstrap_proof",
    "workflow_repository":os.environ.get("GITHUB_REPOSITORY"),
    "workflow_name":os.environ.get("GITHUB_WORKFLOW"),
    "workflow_ref":os.environ.get("GITHUB_REF"),"workflow_sha":os.environ.get("GITHUB_SHA"),
    "input_repository":"olegbalakin-cmyk/kyiv-air-alerts-grafana","input_ref":"site-prod",
    "input_sha":"928a566b7a8dc7916c93810eaafe319da3b28ee4",
    "github_run_id":int(os.environ["GITHUB_RUN_ID"]),"github_run_attempt":int(os.environ["GITHUB_RUN_ATTEMPT"]),
    "schema_version":"001_phase1_core","canonicalization_version":"alert-canonicalization-v1",
    "parameters":{"production_city_count":23,"canonical_episode_count":27866,"corpus_sha256":CORPUS,
    "source_provenance_coverage":"partial","preexisting_lviv_episode_count":126}}

def validate_boundary(path):
    b=json.load(open(path,encoding="utf-8"))
    assert b["boundary_proven"] is True and b["city_count"]==23 and b["total_episode_count"]==27866
    assert b["open_episode_count"]==0 and not b["boundary_errors"] and b["corpus_sha256"]==CORPUS
    counts={k:v["episode_count"] for k,v in b["per_city"].items()}
    assert counts["kropyvnytskyi"]==1268
    return b,counts

def prove(boundary,result):
    b,expected_counts=validate_boundary(boundary); episodes=b["episodes"]
    with psycopg.connect(os.environ["CHILD_DATABASE_URL"],row_factory=dict_row) as conn:
        pre=snap(conn)
        assert pre["counts"]=={"ingestion_runs":2,"alert_episodes":126,"alert_episode_sources":143,"ingestion_checkpoints":1,"max_checkpoint_seq":1,"alert_state_snapshots":13,"alert_threat_observations":14,"non_lviv_episodes":0}
        frozen={(x["city_key"],x["alert_type"],utc(x["start_at"]),utc(x["end_at"]),x["episode_state"],x["legacy_episode_id"]) for x in episodes if x["city_key"]=="lviv"}
        with conn.cursor() as c:
            c.execute("SELECT episode_uid,legacy_episode_id,city_key,alert_type,start_at,end_at,episode_state FROM alert_episodes WHERE city_key='lviv'"); db=list(c.fetchall())
        conn.rollback()
        actual={(x["city_key"],x["alert_type"],utc(x["start_at"]),utc(x["end_at"]),x["episode_state"],x["legacy_episode_id"]) for x in db}
        mappings={str(x["episode_uid"]):x["legacy_episode_id"] for x in db if str(x["episode_uid"]) in REPAIRED}
        assert len(frozen)==126 and len(db)==126 and frozen==actual and mappings==REPAIRED
        pf=mc.preflight(conn,episodes)
        summary={k:pf[k] for k in ("exact_existing","missing_to_insert","conflicting_legacy_id","conflicting_exact_interval","semantic_conflict","duplicate_candidate_legacy_id","duplicate_candidate_interval")}
        assert summary=={"exact_existing":126,"missing_to_insert":27740,"conflicting_legacy_id":0,"conflicting_exact_interval":0,"semantic_conflict":0,"duplicate_candidate_legacy_id":0,"duplicate_candidate_interval":0}
        assert {x["city_key"] for x in pf["exact_existing_rows"]}=={"lviv"}
        try: mc.persist_canonical_episodes(conn,episodes,provenance=prov(),db_branch=TARGET,force_failure_after_new=100)
        except mc.ForcedMulticityFailure: pass
        else: raise AssertionError("forced rollback did not fire")
        assert snap(conn)==pre
        out=mc.persist_canonical_episodes(conn,episodes,provenance=prov(),db_branch=TARGET)
        assert (out["episodes_inserted"],out["episodes_existing"],out["episodes_updated"])==(27740,126,0)
        post=snap(conn)
        assert post["counts"]=={"ingestion_runs":3,"alert_episodes":27866,"alert_episode_sources":143,"ingestion_checkpoints":1,"max_checkpoint_seq":1,"alert_state_snapshots":13,"alert_threat_observations":14,"non_lviv_episodes":27740}
        assert pre["fingerprints"]==post["fingerprints"]
        with conn.cursor() as c:
            c.execute("SELECT city_key,alert_type,start_at,end_at,episode_state,legacy_episode_id,canonicalization_version FROM alert_episodes"); rows=list(c.fetchall())
        conn.rollback()
        def rec(x): return (x["city_key"],x["alert_type"],utc(x["start_at"]),utc(x["end_at"]),x["episode_state"],x["legacy_episode_id"],x["canonicalization_version"])
        assert {rec(x) for x in episodes}=={rec(x) for x in rows}
        assert dict(Counter(x["city_key"] for x in rows))==expected_counts
        retry=mc.persist_canonical_episodes(conn,episodes,provenance=prov(),db_branch=TARGET)
        assert retry["status"]=="already_persisted" and retry["writes"]==0 and snap(conn)==post
        cases=[]
        a=copy.deepcopy(episodes[0]); a["end_at"]="2030-01-01T00:00:00Z"; cases.append(("legacy_changed_boundary",[a]))
        a=copy.deepcopy(episodes[0]); a["legacy_episode_id"]="0"*24; cases.append(("interval_different_legacy",[a]))
        a=copy.deepcopy(episodes[:1]); a.append(copy.deepcopy(a[0])); cases.append(("duplicate_input",a))
        for name,field,value in [("invalid_interval","end_at",episodes[0]["start_at"]),("empty_city","city_key",""),("empty_type","alert_type",""),("unsupported_version","canonicalization_version","v2")]:
            a=copy.deepcopy(episodes[0]); a[field]=value; cases.append((name,[a]))
        rejected={}
        for name,candidate in cases:
            try: mc.persist_canonical_episodes(conn,candidate,provenance=prov(),db_branch=TARGET)
            except Exception as e: assert snap(conn)==post; rejected[name]=type(e).__name__
            else: raise AssertionError(name)
    o={"runtime_verdict":"MULTICITY CANONICAL ALERTS NEON PERSISTENCE PROVEN","proof_branch":"multicity-canonical-alerts-neon-persistence-proof-v2-2026-10-01",
    "runtime_head":os.environ["GITHUB_SHA"],"workflow_run_id":int(os.environ["GITHUB_RUN_ID"]),
    "predecessor_repair_head":"299bb5dd2101facae9f70dc7c885851575505212","original_blocked_proof_head":"8b6dff2bcf813b13f09bf5efd6078f393e76c494",
    "frozen_production_ref":"928a566b7a8dc7916c93810eaafe319da3b28ee4","frozen_vadimkin_ref":"58ee75bc20113181b9ddf8029d4cbf3a62d8cd10","canonical_corpus_sha256":CORPUS,
    "city_count":23,"total_episode_count":27866,"open_episode_count":0,"per_city_counts":expected_counts,
    "lviv_compatibility":{"frozen":126,"db":126,"mismatches":0,"repaired_mappings":REPAIRED},"preflight":summary,
    "forced_rollback":{"after_new":100,"exact_pre_state_restored":True,"residue":0},"successful_ingestion_run_id":out["run_id"],
    "successful_import":{"episodes_inserted":27740,"episodes_existing":126,"episodes_updated":0},"post_state":post,
    "full_db_parity":{"exact":True,"rows":27866,"cities":23,"missing":0,"extra":0},"lviv_fingerprint_preserved":True,
    "source_fingerprint_preserved":True,"checkpoint_fingerprint_preserved":True,"differentiated_fingerprints_preserved":True,
    "exact_replay":{"status":"already_persisted","writes":0},"fresh_process_replay":"pending","conflict_rejection":rejected,
    "source_provenance_coverage":"partial","attack_events_in_neon":False,"db_cutover":False,"credentials_exposed":False}
    json.dump(o,open(result,"w",encoding="utf-8"),indent=2,sort_keys=True)
    print("PROOF PASS ingestion_run="+out["run_id"])

def retry(boundary,result):
    b,_=validate_boundary(boundary)
    with psycopg.connect(os.environ["CHILD_DATABASE_URL"],row_factory=dict_row) as conn:
        before=snap(conn); out=mc.persist_canonical_episodes(conn,b["episodes"],provenance=prov(),db_branch=TARGET); after=snap(conn)
        assert out["status"]=="already_persisted" and out["writes"]==0 and before==after
        assert after["counts"]["ingestion_runs"]==3 and after["counts"]["alert_episodes"]==27866
    o=json.load(open(result,encoding="utf-8")); o["fresh_process_replay"]={"status":"already_persisted","writes":0,"state_unchanged":True}
    json.dump(o,open(result,"w",encoding="utf-8"),indent=2,sort_keys=True)
    print("FRESH PROCESS REPLAY PASS writes=0")

if __name__=="__main__":
    p=argparse.ArgumentParser(); p.add_argument("mode",choices=["prove","retry"]); p.add_argument("--boundary",required=True); p.add_argument("--result",required=True); a=p.parse_args()
    (prove if a.mode=="prove" else retry)(a.boundary,a.result)
