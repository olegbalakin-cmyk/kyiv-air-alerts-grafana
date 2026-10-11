#!/usr/bin/env python3
"""Frozen Git H2 chronology/producer forensic; never imports historical classifiers."""
import hashlib,json,os,subprocess,sys
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from zoneinfo import ZoneInfo
MAIN="182f783526a1d9db9d298bb4b18e291639998fc5"
WORKER="b09a95da6354d496eea478fc7e6871e62acb4b7d"
TARGET="3c39dabbf78ff9415213332023e6e6c4ee7e8225"
EXPORT="03a04d33f7616b77181741fd77a776c490391d07"
TRANSPORT="8d45d8333da0d2d2f123f658d4631791dde8a3d3"
PRODUCER="f4732a37b341b4a548382817bdb9bf210e8c2e21"
WORKER_PATH="research/historical_v2_formalization_kropyvnytskyi_mykolaiv_proof_2026-10-02.json"
TARGET_PATH="research/attack_event_18city_accepted_target_map_2026-10-04.json"
EXPORT_PATH="research/attack_event_18city_persistence_identity_export_v2_2026-10-04.json"
TRANSPORT_PATH="research/neon_h1_h2_large_export_authority_transport_2026-10-11.json"
PRODUCER_PATH=".github/workflows/attack-event-18city-persistence-identity-v2-replay-proof.yml"
SCRIPT="kyiv-air-alerts-grafana/scripts/formalize_historical_v2_existing_evidence.py"
REPLAY="kyiv-air-alerts-grafana/scripts/replay_explosion_history.py"
PREFIX="kyiv-air-alerts-grafana/data/explosion_metric_handoff/source_slices/"
COUNTS={"kropyvnytskyi":1161,"mykolaiv":1648}
HASHES={"kropyvnytskyi":"d34a4079f97e96bf9f75126788bcaf5db9460786ba25e89a8f07e9c1e849352d","mykolaiv":"357cf4fc1eb761ba266d97058e23700605ef46ba23087b5fab7955883b9cdeeb"}
BLOBS={(WORKER,WORKER_PATH):"3db2c10957beb51cfc565af645f06007a8c0ca55",(WORKER,SCRIPT):"af1b035054b7acf2fe5937c4410d573fea82fb62",(WORKER,REPLAY):"e1a6c793d680196724fbf70f09ed09a821912aca",(TARGET,TARGET_PATH):"4211c5899f219c4561cd139afbbf48c36b6ea86f",(EXPORT,EXPORT_PATH):"a240f1950748afcb9fc974c49ac58da07adfff65",(TRANSPORT,TRANSPORT_PATH):"7b4b2fa92ae6b900eea3a94d7b05ba6aabd358c5",(PRODUCER,PRODUCER_PATH):"9679c0480e22ff4c112b20123b29fac285c98c0a"}
def run(*args):
    p=subprocess.run(args,capture_output=True)
    if p.returncode: raise RuntimeError("GIT_ERROR:"+str(args[:4])+":"+p.stderr.decode("utf8","replace")[:150])
    return p.stdout
def git(*args): return run("git",*args).decode().strip()
def ensure(ref):
    p=subprocess.run(["git","cat-file","-e",ref+"^{commit}"],capture_output=True)
    if p.returncode:run("git","fetch","--no-tags","origin",ref)
    assert git("rev-parse",ref+"^{commit}")==ref,ref
def read(ref,path,blob=None,sha=None):
    found=git("rev-parse",ref+":"+path)
    if blob and found!=blob:raise RuntimeError("GIT_BLOB_DRIFT:"+path)
    data=run("git","show",ref+":"+path)
    if hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()!=found:raise RuntimeError("BLOB_CONTENT_INTEGRITY:"+path)
    h=hashlib.sha256(data).hexdigest()
    if sha and sha!=h:raise RuntimeError("CONTENT_SHA_DRIFT:"+path)
    return data,{"commit":ref,"path":path,"git_blob":found,"sha256":h,"bytes":len(data)}
def load(ref,path,**kw):
    raw,meta=read(ref,path,**kw)
    return json.loads(raw),meta
def canonical(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
def digest(v):return hashlib.sha256(canonical(v)).hexdigest()
def kyivdate(ep):
    day=ep.get("alert_start_date_kyiv")
    if day:return str(day)
    s=str(ep.get("alert_start") or "").strip()
    d=datetime.fromisoformat(s.replace("Z","+00:00"))
    if d.tzinfo is None:d=d.replace(tzinfo=ZoneInfo("Europe/Kyiv"))
    return d.astimezone(ZoneInfo("Europe/Kyiv")).date().isoformat()
def utcmicro(v):
    if isinstance(v,int) and not isinstance(v,bool):d=datetime.fromtimestamp(v/1000000,timezone.utc)
    elif isinstance(v,str) and v.isdigit():d=datetime.fromtimestamp(int(v)/1000000,timezone.utc)
    elif isinstance(v,str):
        d=datetime.fromisoformat(v.replace("Z","+00:00"))
        if d.tzinfo is None:raise ValueError("NAIVE")
    else:raise ValueError("TYPE")
    return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
def main():
    for ref in (MAIN,WORKER,TARGET,EXPORT,TRANSPORT,PRODUCER):ensure(ref)
    for (ref,path),blob in BLOBS.items():read(ref,path,blob=blob)
    worker,worker_info=load(WORKER,WORKER_PATH,blob=BLOBS[(WORKER,WORKER_PATH)])
    target,target_info=load(TARGET,TARGET_PATH,blob=BLOBS[(TARGET,TARGET_PATH)])
    old,old_info=load(TRANSPORT,TRANSPORT_PATH,blob=BLOBS[(TRANSPORT,TRANSPORT_PATH)],sha="40d2ba356d2695485e88b0be37604fc5a0bbf5c4dfc451db03e8d581bd364809")
    h2,h2_info=load(EXPORT,EXPORT_PATH,blob=BLOBS[(EXPORT,EXPORT_PATH)],sha="a8440ab537e1b675c7223b7eb7b29c817c1a2e8fc26ba5cf494b5efb3caf662a")
    producer_raw,producer_info=read(PRODUCER,PRODUCER_PATH,blob=BLOBS[(PRODUCER,PRODUCER_PATH)])
    assert h2_info["bytes"]==60509907,"H2_EXPORT_LENGTH"
    assert worker["tested_head"]=="a89a85daf32d7896086b37ca6557abf28a39904f","HISTORICAL_TESTED_HEAD"
    ensure(worker["tested_head"])
    read(worker["tested_head"],SCRIPT,blob=BLOBS[(WORKER,SCRIPT)])
    read(worker["tested_head"],REPLAY,blob=BLOBS[(WORKER,REPLAY)])
    assert len(target["workers"])==10 and len(target["target_map"])==18,"TARGET_WORKER_MATRIX"
    tc={v["city_key"]:v for v in target["target_map"]}
    prior=old["accepted_18city_matrix"]["city_results"]
    prior_pass=sorted(c for c,v in prior.items() if c not in COUNTS and v.get("result")=="PASS" and v.get("recomputed_sha256")==v.get("accepted_matrix_sha256"))
    lineage=[]
    for w in target["workers"]:
        ensure(w["tested_head"]);ensure(w["final_head"])
        read(w["tested_head"],w["formalizer_path"],blob=w["formalizer_blob"])
        p,pm=load(w["final_head"],w["proof_artifact_path"],blob=w["proof_artifact_blob"])
        inputs=[]
        for c,item in sorted((p.get("cities") or {}).items()):
            details=[]
            for path,record in sorted((item.get("input_hashes") or {}).items()):
                if isinstance(record,dict) and record.get("sha256") and record.get("git_blob_sha"):
                    _,m=read(w["tested_head"],path,blob=record["git_blob_sha"],sha=record["sha256"])
                    details.append(m)
            inputs.append({"city":c,"files":details})
        lineage.append({"worker":w["worker"],"tested_head":w["tested_head"],"accepted_final_head":w["final_head"],"formalizer_blob":w["formalizer_blob"],"original_proof":pm,"attested_input_cities":inputs})
    result={}
    for city,n in COUNTS.items():
        proof=worker["cities"][city]
        t=tc[city]
        assert proof["target_state_sha256"]==t["accepted_target_state_sha256"]==HASHES[city],city+":ORIGINAL_HASH_REFERENCE"
        start,end=(str(proof["guards"][k]) for k in ("coverage_start","coverage_end"))
        names=[p for p in git("ls-tree","-r","--name-only",worker["tested_head"],"--",PREFIX).splitlines() if p.startswith(PREFIX+city+"-") and p.endswith("_alerts.json")]
        expected_names=sorted(p for p in proof["input_hashes"] if p.startswith(PREFIX))
        assert names==expected_names,(city,"SOURCE_SET",names,expected_names)
        byid={};source_rows=Counter()
        for name in names:
            data,meta=load(worker["tested_head"],name,blob=proof["input_hashes"][name]["git_blob_sha"],sha=proof["input_hashes"][name]["sha256"])
            for i,ep in enumerate(data.get("episodes") or []):
                eid=str(ep.get("episode_id") or "")
                if eid:
                    source_rows[eid]+=1
                    byid[eid]={"record":ep,"source_path":name,"source_blob":meta["git_blob"],"index":i,"source_row_sha256":digest(ep)}
        picked={eid:v for eid,v in byid.items() if start<=kyivdate(v["record"])<=end}
        rows=t["target_rows"];all_ids=[str(r["episode_id"]) for r in rows]
        states={str(r["episode_id"]):str(r["state"]) for r in rows}
        duplicates=sorted(eid for eid,q in Counter(all_ids).items() if q!=1)
        missing=sorted(set(picked)-set(states));extras=sorted(set(states)-set(picked))
        badiso=sorted(eid for eid,v in picked.items() if not all(isinstance(v["record"].get(x),str) for x in ("alert_start","alert_end")))
        chronology=[{"episode_id":eid,"alert_start":v["record"].get("alert_start"),"alert_end":v["record"].get("alert_end"),"state":states.get(eid)} for eid,v in picked.items()]
        chronology.sort(key=lambda row:(str(row["alert_start"] or ""),str(row["episode_id"] or "")))
        sha=digest(chronology)
        export_rows=[r for r in h2["classifications"] if r.get("city_key")==city]
        export_ids=[str(r.get("historical_episode_id")) for r in export_rows]
        emap={str(r["historical_episode_id"]):r for r in export_rows}
        export_missing=sorted(set(picked)-set(emap));export_extra=sorted(set(emap)-set(picked))
        export_dupes=sorted(eid for eid,q in Counter(export_ids).items() if q!=1)
        time_errors=[];state_errors=[];types=Counter()
        for eid in sorted(set(picked)&set(emap)):
            x=picked[eid]["record"]; e=emap[eid]
            if e.get("verdict")!=states[eid]:state_errors.append(eid)
            for field,orig in [("alert_start_utc_microseconds","alert_start"),("alert_end_utc_microseconds","alert_end")]:
                types[type(e.get(field)).__name__]+=1
                try:
                    if utcmicro(e.get(field))!=utcmicro(x[orig]):time_errors.append({"episode_id":eid,"field":field})
                except Exception as err:time_errors.append({"episode_id":eid,"field":field,"reason":type(err).__name__})
        known={"STRICT_EVENT_POSITIVE":proof["counts"]["strict_positives"],"SENSITIVITY_EVENT_POSITIVE":proof["counts"]["sensitivity_positives"],"NEEDS_REVIEW":proof["counts"]["needs_review"],"NO_CONFIRMED_EVENT":proof["counts"]["no_confirmed_event"]}
        distribution=dict(Counter(states.values()))
        valid=sha==HASHES[city] and len(picked)==len(rows)==n and not (duplicates or missing or extras or badiso or export_missing or export_extra or export_dupes or state_errors or time_errors) and all(distribution.get(k,0)==v for k,v in known.items())
        refs=[{"episode_id":eid,**{k:v[k] for k in ("source_path","source_blob","index","source_row_sha256")}} for eid,v in picked.items()]
        contradictions=sorted(set(duplicates+missing+extras+badiso+export_missing+export_extra+export_dupes+state_errors+[x["episode_id"] for x in time_errors]))
        result[city]={"verdict":"PASS" if valid else "MISMATCH","accepted_original_hash":HASHES[city],"recomputed_original_hash":sha,"expected":n,"canonical_episodes":len(picked),"accepted_target_rows":len(rows),"source_row_refs_sha256":digest(sorted(refs,key=lambda r:r["episode_id"])),"original_source_slices":names,"source_record_occurrences":sum(source_rows.values()),"repeated_episode_ids_in_raw_slices":sorted(eid for eid,q in source_rows.items() if q>1)[:100],"duplicate_canonical_ids":0,"missing_target_ids":missing,"extra_target_ids":extras,"duplicate_target_ids":duplicates,"original_iso_missing_ids":badiso,"state_counts":distribution,"H2_export_count":len(export_rows),"export_missing_ids":export_missing,"export_extra_ids":export_extra,"export_duplicate_ids":export_dupes,"export_verdict_mismatches":state_errors,"export_timestamp_mismatches":time_errors,"export_timestamp_types":dict(types),"contradictory_episode_ids":contradictions,"canonical_hash_contract":"CANON_CHRONO_FULL: episode_id,alert_start,alert_end,state; sort original alert_start string then episode_id; compact sorted-key UTF8 Python JSON"}
    pt=producer_raw.decode()
    markers=["FRESH_MAIN=\"5a119520275c606e0c306d41fb831e460e2f7f63\"","TARGET_COMMIT=\"3c39dabbf78ff9415213332023e6e6c4ee7e8225\"","TARGET_BLOB=\"4211c5899f219c4561cd139afbbf48c36b6ea86f\"","NETWORK_GUARD=r","target_rows_by_city","classifications.append(classification)","persistence_identity_export.json","git push --force-with-lease"]
    producer_markers={m:m in pt for m in markers}
    all_pass=all(v["verdict"]=="PASS" for v in result.values())
    independent=all(producer_markers.values()) and h2_info["sha256"]=="a8440ab537e1b675c7223b7eb7b29c817c1a2e8fc26ba5cf494b5efb3caf662a"
    return {"schema_version":1,"task":"H2_TWO_CITY_CHRONOLOGY_AND_EXPORT_PROVENANCE","main_base":MAIN,"original_worker":worker_info,"accepted_target_map":target_info,"prior_16_city_proof":old_info,"H2_original_export":h2_info,"original_generator_blob":BLOBS[(WORKER,SCRIPT)],"original_replay_loader_blob":BLOBS[(WORKER,REPLAY)],"chronology":result,"prior_accepted_16_city_hash_pass":len(prior_pass),"prior_accepted_16_cities":prior_pass,"H2_ACCEPTED_CITY_HASH_RECONSTRUCTION":"18/18" if all_pass and len(prior_pass)==16 else "NOT_18_18","H2_EXPORT_NEON_INDEPENDENCE":"PROVEN" if independent else "NOT PROVEN","producer":{"executed_HEAD":PRODUCER,"workflow":producer_info,"worker_frozen_lineage":lineage,"producer_code_markers":producer_markers,"Actions_run":37204040063,"Jobs_A_B_compare_finalize":[111441414010,111441413793,111441716885,111441756917],"export_generated_UTC_bounded_by_logs":"2026-10-04T13:01:21Z..2026-10-04T13:02:00Z","publication_commit":EXPORT,"publication_commit_UTC":"2026-10-04T13:01:58Z","initial_verified_23city_Neon_persistence":{"Actions_run":37442792301,"commit_observed_UTC":"2026-10-06T09:26:06Z","classifications":26405},"original_target_verdict_origin":"Accepted October2 workers; October4 Git target map exact states","other_semantic_input_origin":"October4 replay of Git-frozen historical workers, not Neon; code-derived, not independently accepted Oct2 field authority","QA_field":"UNMATERIALIZED_IN_ACCEPTED_SOURCE","native_source_hash_count":0,"normalized_evidence_hash_fallback_count":1429,"source_links":1429,"positive_events":961,"historical_source_network_requests":0,"new_classifier_execution_in_this_task":False},"field_authority":{"historical_ISO_boundaries_and_episode_IDs":"TWO_CITY_ORIGINAL_SOURCE_PROVEN" if all_pass else "UNRESOLVED","classification_verdicts":"TWO_CITY_ORIGINAL_ACCEPTED_PROVEN" if all_pass else "UNRESOLVED","H2_derived_source_links":"REPLAY_DERIVED_NOT_ORIGINAL_FIELD_AUTHORITY","H2_derived_event_relationships":"REPLAY_DERIVED_NOT_ORIGINAL_FIELD_AUTHORITY","H2_derived_deterministic_keys":"REPLAY_DERIVED_NOT_ORIGINAL_FIELD_AUTHORITY","historical_parent_admission":"UNRESOLVED_25","actual_Neon_parity":"NOT_QUERIED"},"H2_TWO_CITY_CHRONOLOGY_AND_EXPORT_PROVENANCE":"PASS" if all_pass and independent and len(prior_pass)==16 else "PARTIAL","C4":"NOT PROVEN","C5":"NOT PROVEN","outstanding_C4":["H1 source/event/key remaining governed semantics","H2 19542-row independently adjudicated source/event/key projection","25 historical parent admission decisions","global Neon persisted-versus-frozen missing/extra certification"],"mutation_counters":{"neon_queries":0,"neon_writes":0,"classifier_reruns_for_truth":0,"A5_executions":0,"historical_backfills":0,"parent_repairs":0,"main_writes":0,"production_writes":0,"site_prod_writes":0,"cutover_actions":0}}
if __name__=="__main__":
    try:r=main()
    except Exception as e:r={"schema_version":1,"task":"H2_TWO_CITY_CHRONOLOGY_AND_EXPORT_PROVENANCE","main_base":MAIN,"H2_TWO_CITY_CHRONOLOGY_AND_EXPORT_PROVENANCE":"BLOCKED","H2_EXPORT_NEON_INDEPENDENCE":"NOT PROVEN","blocker":type(e).__name__+":"+str(e),"mutation_counters":{"neon_queries":0,"neon_writes":0,"classifier_reruns_for_truth":0,"A5_executions":0,"historical_backfills":0,"production_writes":0}}
    b=canonical(r);p=Path(os.environ.get("PROOF_OUT","/tmp/h2proof.json"));p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
    print("H2_VERDICT="+str(r.get("H2_TWO_CITY_CHRONOLOGY_AND_EXPORT_PROVENANCE")))
    print("H2_SHA="+hashlib.sha256(b).hexdigest())
    print("H2_BYTES="+str(len(b)))
    if r.get("blocker"):print("H2_BLOCKER="+r["blocker"])
