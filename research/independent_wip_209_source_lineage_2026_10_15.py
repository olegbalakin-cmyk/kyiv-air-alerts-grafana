#!/usr/bin/env python3
"""Independent read-only audit of the frozen 209 WIP identity manifest.

Inputs are pinned Git checkouts and the original GitHub Actions ZIP. No live
source clients, classifier imports, database connections or data mutations.
Observations about temporal similarity never constitute identity equivalence.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import zipfile

WIP = "567c0aab3aaf98a5b8dd788021a26ece41f083e3"
PROD = "97ec99389259f8d0cfcecc17a2ff77302bb0615f"
MANIFEST_SHA = "54ce8c9800739b294a83991f71130ab3c6096742ed861b469c1df2ecf2ec9d76"
MANIFEST_LEN = 44645890
ZIP_SHA = "0d10cceb48b6266a67faab90bad27201b7be8537bb244d7008824ffc3227e486"
MFILE = "wip_cached_209_identity_manifest_2026-10-15.json"
D = "kyiv-air-alerts-grafana/data/"
MON = "kyiv-air-alerts-grafana/scripts/monitor_explosion_candidates.py"
WF = ".github/workflows/explosion-monitor-wip.yml"
EXPECTED_CITY = {"kyiv":185, "mykolaiv":12, "sumy":9, "kharkiv":3}
EXPECTED_BLOBS = {
    "wip:explosion_candidate_monitor_state.json": "fe8ffd3301834f52d42cd6586b04baf0657bdb91",
    "wip:explosion_review_queue.json": "aacda53916d54cbb1e18c26915cf0c1dc79d7725",
    "wip:alerts_combined.json": "ab9babd3527055256017867869bc62b96a6ebffc",
    "wip:ukrainealarm_bridge.json": "9b2922b0863ff6f3dba6e84f2348ad0e4b111d41",
    "wip:sevastopol_events.json": "ae324c63b390fc800472bd97c35816daca8dd6c3",
    "prod:alerts_combined.json": "e91eff537de69156a9bebd55cec1e1ea160d7b58",
    "prod:ukrainealarm_bridge.json": "31ca616c0c6bd103cb1f042f2852d2ca1f266a8d",
    "prod:sevastopol_events.json": "afc8ff3a6f5ed3f0fcd2c7da4298da2258fac10c",
}
REPAIR = "e325e1f7bde398e7267098f1e5d565aa78dc43ac"

def digest(x):
    return hashlib.sha256(x).hexdigest()

def git(root, *args, binary=False, optional=False):
    proc = subprocess.run(["git", "-C", str(root), *args], stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE)
    if proc.returncode:
        if optional:
            return None
        raise AssertionError(("git",args,proc.stderr.decode("utf-8","replace")[-500:]))
    return proc.stdout if binary else proc.stdout.decode("utf-8").strip()

def load(path):
    return json.loads(Path(path).read_bytes())

def dt(x):
    return datetime.fromisoformat(str(x).replace("Z","+00:00")).astimezone(timezone.utc)

def iso(x):
    return dt(x).isoformat().replace("+00:00","Z")

def ep_id(city,start,end):
    return digest((city+"|"+start+"|"+end).encode())[:24]

def seconds(a,b):
    return round((dt(a)-dt(b)).total_seconds(),6)

def pointer(obj,ptr):
    current=obj
    for section in ptr.strip("/").split("/"):
        if not section:
            continue
        key=section.replace("~1","/").replace("~0","~")
        current=current[int(key)] if isinstance(current,list) else current[key]
    return current

def as_json_bytes(obj):
    return (json.dumps(obj,sort_keys=True,ensure_ascii=False,indent=2)+"\n").encode("utf-8")

def save(folder,name,obj):
    b=as_json_bytes(obj)
    (folder/name).write_bytes(b)
    return {"file":name,"bytes":len(b),"sha256":digest(b)}

def src_rows_from(root, commit, path):
    raw=git(root,"show",commit+":"+path,binary=True,optional=True)
    if raw is None:
        return None
    return json.loads(raw)

def array_pairs(arr):
    result=defaultdict(list)
    if not isinstance(arr,list):
        return result
    for i,r in enumerate(arr):
        if isinstance(r,dict) and r.get("start") and r.get("end"):
            try:
                result[(iso(r["start"]),iso(r["end"]))].append({"index":i,"record":r})
            except (TypeError,ValueError):
                pass
    return result

def source_versions(wip, orig_pairs, candidate_pairs):
    path=D+"alerts_combined.json"
    commits=git(wip,"log","--reverse","--format=%H",WIP,"--",path).splitlines()
    changes=[]
    lastblob=None
    for commit in commits:
        blob=git(wip,"rev-parse",commit+":"+path,optional=True)
        if not blob or blob==lastblob:
            continue
        lastblob=blob
        raw=git(wip,"cat-file","blob",blob,binary=True)
        data=json.loads(raw)
        idx=array_pairs(data)
        old={key:[{"index":r["index"],"record":r["record"]} for r in idx[key]]
             for key in orig_pairs if key in idx}
        new={key:[{"index":r["index"],"record":r["record"]} for r in idx[key]]
             for key in candidate_pairs if key in idx}
        changes.append({"commit":commit,"blob":blob,"rows":len(data),
                        "old_matches":old,"candidate_matches":new})
    return changes

def index_prod(proddata):
    out=defaultdict(dict)
    regions=proddata["ukrainealarm_bridge.json"]["regions"]
    bycity=defaultdict(list)
    for i,r in enumerate(proddata["ukrainealarm_bridge.json"]["events"]):
        if r.get("city_key") in EXPECTED_CITY:
            bycity[r["city_key"]].append((dt(r["start"]),dt(r["end"]),f"/events/{i}"))
    for city in EXPECTED_CITY:
        if city=="kyiv":
            for i,r in enumerate(proddata["alerts_combined.json"]):
                s,e=iso(r["start"]),iso(r["end"])
                if dt(e)<=dt(s):
                    continue
                idv=ep_id(city,s,e)
                out[city][idv]={"start":s,"end":e,"members":[(D+"alerts_combined.json",f"/{i}")],
                               "family":"Kyiv exact-city"}
        elif regions[city]["kind"]=="proxy":
            groups=[]
            for s,e,ptr in sorted(bycity[city]):
                if not groups or s>groups[-1]["end"]:
                    groups.append({"start":s,"end":e,"members":[(D+"ukrainealarm_bridge.json",ptr)]})
                else:
                    groups[-1]["end"]=max(e,groups[-1]["end"])
                    groups[-1]["members"].append((D+"ukrainealarm_bridge.json",ptr))
            for g in groups:
                s= g["start"].isoformat().replace("+00:00","Z")
                e= g["end"].isoformat().replace("+00:00","Z")
                out[city][ep_id(city,s,e)]={"start":s,"end":e,"members":g["members"],
                    "family":"UkraineAlarm raion-proxy"}
        else:
            for s,e,ptr in bycity[city]:
                ss=s.isoformat().replace("+00:00","Z")
                ee=e.isoformat().replace("+00:00","Z")
                out[city][ep_id(city,ss,ee)]={"start":ss,"end":ee,
                    "members":[(D+"ukrainealarm_bridge.json",ptr)],
                    "family":"UkraineAlarm exact"}
    return out

def plausible(old,cand):
    os,oe=dt(old["original_alert_start_exact"]),dt(old["original_alert_end_exact"])
    cs,ce=dt(cand["start"]),dt(cand["end"])
    overlap=max(0.,(min(oe,ce)-max(os,cs)).total_seconds())
    gap=max(0.,(cs-oe).total_seconds(),(os-ce).total_seconds())
    return overlap>0 or (gap<=900 and min(abs((cs-os).total_seconds()),
                                           abs((ce-oe).total_seconds()))<=900)

def walk(v,target,path="",depth=0):
    if depth>35:
        raise AssertionError("queue nesting beyond frozen verifier bound")
    if isinstance(v,str):
        if v in target:
            yield v,path
    elif isinstance(v,dict):
        for k,x in v.items():
            q=str(k).replace("~","~0").replace("/","~1")
            yield from walk(x,target,path+"/"+q,depth+1)
    elif isinstance(v,list):
        for i,x in enumerate(v):
            yield from walk(x,target,path+"/"+str(i),depth+1)

def queue_audit(queue,rows):
    ids={r["original_episode_id"] for r in rows}
    linked=defaultdict(dict)
    total_occurrences=0
    decision_field=0
    classification_field=0
    unique_item_ids=set()
    for idx,item in enumerate(queue):
        members=defaultdict(list)
        for key,p in walk(item,ids):
            members[key].append(p)
            total_occurrences+=1
        if members:
            unique_item_ids.add(idx)
            if isinstance(item,dict):
                if item.get("review_decision") is not None or item.get("reviewed_at") or item.get("approved_by"):
                    decision_field+=1
                if item.get("classification") is not None:
                    classification_field+=1
        for idv,paths in members.items():
            linked[idv][idx]=sorted(set(paths))
    total_links=sum(map(len,linked.values()))
    assert total_links==85569,(total_links,85569)
    assert len(linked)==209
    for row in rows:
        idv=row["original_episode_id"]
        wanted={}
        for q in row["review_classification_references"]:
            ix=int(q["json_pointer"].strip("/"))
            assert ix not in wanted,(idv,ix)
            wanted[ix]=sorted(q["exact_id_reference_paths"])
            assert q["commit"]==WIP and q["blob"]==EXPECTED_BLOBS["wip:explosion_review_queue.json"]
        assert wanted==linked[idv],(idv,len(wanted),len(linked[idv]))
        assert row["review_reference_count"]==len(wanted)
    return {"exact_id_queue_entry_links":total_links,
            "unique_queue_entries_with_target_ids":len(unique_item_ids),
            "nested_exact_string_occurrences":total_occurrences,
            "nested_repeat_occurrences":total_occurrences-total_links,
            "entries_with_review_shaped_metadata":decision_field,
            "entries_with_classification_field":classification_field,
            "independently_accepted_review_decision_count":None,
            "warning":"References and fields alone do not prove approved decisions."}

def first_state_appearances(wip, rows):
    path=D+"explosion_candidate_monitor_state.json"
    byid={r["original_episode_id"]:r["city"] for r in rows}
    commits=git(wip,"log","--reverse","--format=%H",WIP,"--",path).splitlines()
    first={}
    seen=set()
    checked=0
    needle=re.compile(rb'"episode_id"\s*:\s*"([0-9a-f]{24})"')
    for commit in commits:
        blob=git(wip,"rev-parse",commit+":"+path,optional=True)
        if not blob or blob in seen:
            continue
        seen.add(blob)
        b=git(wip,"cat-file","blob",blob,binary=True)
        found={v.decode() for v in needle.findall(b)}.intersection(byid).difference(first)
        checked+=1
        if not found:
            continue
        state=json.loads(b)
        for idv in found:
            city=byid[idv]
            for i,ep in enumerate(state["cities"].get(city,{}).get("episodes",[])):
                if ep.get("episode_id")==idv:
                    first[idv]={"commit":commit,"state_blob":blob,
                                "json_pointer":f"/cities/{city}/episodes/{i}",
                                "source_at_first_persist":ep.get("alert_source"),
                                "first_exact_start":ep.get("alert_start"),
                                "first_exact_end":ep.get("alert_end")}
                    break
        if len(first)==len(rows):
            break
    assert len(first)==len(rows),(len(first),len(rows))
    return first,{"state_git_revisions_scanned":checked,
                  "distinct_state_blobs_scanned":len(seen),"found":len(first)}

def repair_probe(repair_root,original_pairs,candidate_pairs):
    path=D+"alerts_combined.json"
    if repair_root is None:
        return {"available":False}
    assert git(repair_root,"rev-parse","HEAD")==REPAIR
    parent=git(repair_root,"rev-parse","HEAD^",optional=True)
    before=src_rows_from(repair_root,parent,path) if parent else None
    after=src_rows_from(repair_root,REPAIR,path)
    def stable_counts(rows):
        arr=array_pairs(rows or [])
        return {
            "original_pairs_present":sum(pair in arr for pair in original_pairs),
            "production_candidate_pairs_present":sum(pair in arr for pair in candidate_pairs),
        }
    return {"available":True,"commit":REPAIR,"parent_commit":parent,
            "before_blob":git(repair_root,"rev-parse",str(parent)+":"+path) if parent else None,
            "after_blob":git(repair_root,"rev-parse",REPAIR+":"+path),
            "before_rows":len(before or []),"after_rows":len(after or []),
            "before":stable_counts(before),"after":stable_counts(after),
            "new_records_in_patch":len(after or [])-len(before or [])}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--wip",type=Path,required=True)
    ap.add_argument("--prod",type=Path,required=True)
    ap.add_argument("--repair",type=Path,required=True)
    ap.add_argument("--manifest",type=Path,required=True)
    ap.add_argument("--archive",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    for forbidden in ("UKRAINEALARM_API_TOKEN","ATTACK_EVENT_DATABASE_URL",
                      "DATABASE_URL","NETLIFY_AUTH_TOKEN"):
        assert not os.environ.get(forbidden),forbidden
    assert git(a.wip,"rev-parse","HEAD")==WIP
    assert git(a.prod,"rev-parse","HEAD")==PROD
    raw=a.manifest.read_bytes()
    assert len(raw)==MANIFEST_LEN and digest(raw)==MANIFEST_SHA
    archive=a.archive.read_bytes()
    assert digest(archive)==ZIP_SHA
    with zipfile.ZipFile(a.archive) as z:
        files=[n for n in z.namelist() if n.endswith(MFILE)]
        assert len(files)==1,files
        assert z.read(files[0])==raw,"original artifact and frozen Git blob differ"
        artifact_members=sorted(z.namelist())
    manifest=json.loads(raw)
    rows=manifest["rows"]
    assert len(rows)==209 and manifest["count"]==209
    assert Counter(r["city"] for r in rows)==EXPECTED_CITY
    ids=[r["original_episode_id"] for r in rows]
    assert len(set(ids))==209
    assert manifest["wip_commit"]==WIP and manifest["site_prod_commit"]==PROD
    assert manifest["source_blobs"]==EXPECTED_BLOBS

    paths={"state":a.wip/D/"explosion_candidate_monitor_state.json",
           "queue":a.wip/D/"explosion_review_queue.json"}
    for label,root in (("wip",a.wip),("prod",a.prod)):
        for name in ("alerts_combined.json","ukrainealarm_bridge.json","sevastopol_events.json"):
            paths[label+":"+name]=root/D/name
    input_hash={}
    git_sha={}
    for label,path in paths.items():
        kind,filename=(("wip",label) if label in ("state","queue")
                       else label.split(":"))
        filename={"state":"explosion_candidate_monitor_state.json",
                  "queue":"explosion_review_queue.json"}.get(filename,filename)
        key=kind+":"+filename
        input_hash[key]=digest(path.read_bytes())
        git_sha[key]=git(a.wip if kind=="wip" else a.prod,
                         "rev-parse","HEAD:"+D+filename)
        assert git_sha[key]==EXPECTED_BLOBS[key],(key,git_sha[key])
    assert input_hash["prod:alerts_combined.json"]=="cb18e0c7a2cbcb7bdcd5ef5d5a2009029346ed27523642c59f03a6bdb1fb6cda"
    assert input_hash["prod:ukrainealarm_bridge.json"]=="7194d5089fbb68165366bea0045660c9c5365cff4457e652d7a18e31b6793f75"
    assert input_hash["prod:sevastopol_events.json"]=="1b0a92690c9bd79878c0c7802fb20cb4dca2f5cef59992ca435fc661877d6f1f"
    prod_data={k:load(paths["prod:"+k]) for k in
               ("alerts_combined.json","ukrainealarm_bridge.json","sevastopol_events.json")}
    assert len(prod_data["ukrainealarm_bridge.json"]["regions"])==21
    candidates=index_prod(prod_data)
    state=load(paths["state"])
    queue=load(paths["queue"])
    state_index={}
    for city in EXPECTED_CITY:
        for i,entry in enumerate(state["cities"][city]["episodes"]):
            if entry.get("episode_id") in ids:
                assert entry["episode_id"] not in state_index
                state_index[entry["episode_id"]]=(city,i,entry)
    assert len(state_index)==209
    ccard=Counter()
    cats=Counter()
    candidate_to_ids=defaultdict(set)
    for row in rows:
        city=row["city"]
        idv=row["original_episode_id"]
        c,ix,original=state_index[idv]
        assert city==c
        assert row["original_git_location"]=={
            "path":D+"explosion_candidate_monitor_state.json","commit":WIP,
            "blob":EXPECTED_BLOBS["wip:explosion_candidate_monitor_state.json"],
            "json_pointer":f"/cities/{c}/episodes/{ix}"}
        assert row["original_episode_state_complete"]==original
        s,e=original["alert_start"],original["alert_end"]
        assert (s,e)==(row["original_alert_start_exact"],row["original_alert_end_exact"])
        assert ep_id(city,s,e)==idv
        assert row["hash_contract"]["matches_original"] is True
        assert row["hash_contract"]["recomputed_id"]==idv
        expected={idc for idc,info in candidates[city].items() if plausible(row,info)}
        got={c["production_id"] for c in row["candidate_production_episodes"]}
        assert expected==got,(city,idv,expected,got)
        assert row["candidate_count"]==len(got)
        for cand in row["candidate_production_episodes"]:
            cid=cand["production_id"]
            cc=candidates[city][cid]
            assert cand["production_start"]==cc["start"]
            assert cand["production_end"]==cc["end"]
            assert cand["candidate_hash_valid"] and cand["candidate_hash_recomputed"]==cid
            assert cand["source_family"]==cc["family"]
            locs=[(z["path"],z["json_pointer"]) for z in cand["candidate_source_locations"]]
            assert sorted(locs)==sorted(cc["members"]),(idv,cid)
            ds=seconds(cc["start"],s)
            de=seconds(cc["end"],e)
            assert ds==cand["start_delta_seconds_signed"] and de==cand["end_delta_seconds_signed"]
            for loc in cand["candidate_source_locations"]:
                assert loc["commit"]==PROD
                f=loc["path"][len(D):]
                assert loc["blob"]==EXPECTED_BLOBS["prod:"+f]
                src=pointer(prod_data[f],loc["json_pointer"])
                assert src["start"]==loc["source_fields"]["start"]
                assert src["end"]==loc["source_fields"]["end"]
                assert src.get("city_key",city)==city
            candidate_to_ids[cid].add(idv)
        assert row["historical_raw_record_observed"]==bool(row["original_raw_source_records"])
        assert not row["original_raw_source_records"],"prior zero-raw finding contradicted"
        cats[row["root_cause_category"]]+=1
    assert cats=={"G":194,"A":15}
    for row in rows:
        names=[x["production_id"] for x in row["candidate_production_episodes"]]
        cardinality=("unmatched" if not names else "one_to_many_candidates" if len(names)>1
                     else "many_to_one_candidates" if len(candidate_to_ids[names[0]])>1
                     else "one_to_one_candidate")
        assert cardinality==row["candidate_cardinality"]
        ccard[cardinality]+=1
    assert ccard=={"one_to_one_candidate":206,"one_to_many_candidates":1,
                  "many_to_one_candidates":2}
    queue_result=queue_audit(queue,rows)
    first,first_stats=first_state_appearances(a.wip,rows)
    original_pairs={ (iso(r["original_alert_start_exact"]),iso(r["original_alert_end_exact"]))
                    for r in rows if r["city"]=="kyiv" }
    cand_pairs={ (c["production_start"],c["production_end"])
                 for r in rows if r["city"]=="kyiv" for c in r["candidate_production_episodes"]}
    versions=source_versions(a.wip,original_pairs,cand_pairs)
    repair=repair_probe(a.repair,original_pairs,cand_pairs)
    source_at_appearance_cache={}
    producer_cache={}
    kyiv=[]
    proxy=[]
    precision=[]
    all_unresolved=[]
    proven=Counter()
    for r in rows:
        idv=r["original_episode_id"]; city=r["city"]
        firstrec=first[idv]
        producer_commit=firstrec["commit"]
        if producer_commit not in producer_cache:
            script_sha=git(a.wip,"rev-parse",producer_commit+":"+MON,optional=True)
            wf_sha=git(a.wip,"rev-parse",producer_commit+":"+WF,optional=True)
            producer_cache[producer_commit]={
                "script_path":MON,"script_git_blob":script_sha,
                "workflow_path":WF,"workflow_git_blob":wf_sha,
                "producer_code_commit_assumption":producer_commit,
                "executed_runtime_receipt":"NOT RECOVERED; checked-in code is not a job execution proof"}
        if city=="kyiv":
            old_pair=(iso(r["original_alert_start_exact"]),iso(r["original_alert_end_exact"]))
            if producer_commit not in source_at_appearance_cache:
                source_at_appearance_cache[producer_commit]={
                    "blob":git(a.wip,"rev-parse",producer_commit+":"+D+"alerts_combined.json",optional=True),
                    "pairs":array_pairs(src_rows_from(a.wip,producer_commit,D+"alerts_combined.json") or [])}
            src_on_first=source_at_appearance_cache[producer_commit]
            match_first=src_on_first["pairs"].get(old_pair,[])
            all_history=[{"commit":v["commit"],"blob":v["blob"],
                          "rows":v["old_matches"][old_pair]}
                         for v in versions if old_pair in v["old_matches"]]
            new_candidate_records=[{
                "production_id":c["production_id"],
                "time_delta_seconds_signed":{"start":c["start_delta_seconds_signed"],
                                             "end":c["end_delta_seconds_signed"]},
                "source_records":c["candidate_source_locations"],
                "whole_second_equal":c["precision_only_whole_second_match"],
                "same_minute_not_instant":c["same_minute_but_not_same_instant"],
            } for c in r["candidate_production_episodes"]]
            # A historical file-version difference is not evidence of row identity:
            # neither the old WIP state nor Kyiv combined rows carry a stable source ID.
            if match_first or all_history:
                disposition="AMBIGUOUS_RELATIONSHIP"
                uncertainty="Historical combined-source record found, but no stable upstream record ID/raw publisher response proves its relation to the production candidate"
            else:
                disposition="SOURCE_PROVENANCE_NOT_RECOVERABLE"
                uncertainty="Original WIP timestamp pair absent from searched historical WIP combined-source revisions; no raw publisher response"
            record={
                "city":"kyiv","original_episode_id":idv,
                "original_times_exact":[r["original_alert_start_exact"],r["original_alert_end_exact"]],
                "original_state_git_location":r["original_git_location"],
                "first_persisted_git":firstrec,
                "possible_producer_code_revision":producer_cache[producer_commit],
                "source_contract_at_frozen_wip":"load_kyiv_alert_episodes -> parse_dt -> make_episode -> event_id",
                "combined_source_blob_at_first_persistence":src_on_first["blob"],
                "raw_combined_rows_at_first_persistence":match_first,
                "other_historical_combined_row_occurrences":all_history,
                "original_upstream_HTTP_bytes_recovered":False,
                "production_candidates":new_candidate_records,
                "proven_transformation":None,
                "supported_identity_disposition":disposition,
                "remaining_uncertainty":uncertainty,
            }
            kyiv.append(record)
            proven[disposition]+=1
        elif r["root_cause_category"]=="G":
            evidence=[]
            for can in r["candidate_production_episodes"]:
                evidence.append({
                    "id":can["production_id"],
                    "start_signed_delta_s":can["start_delta_seconds_signed"],
                    "end_signed_delta_s":can["end_delta_seconds_signed"],
                    "member_count":can["candidate_member_count"],
                    "members":can["candidate_source_locations"],
                    "wip_raw_intervals":r["original_grouping"].get("raw_intervals"),
                    "original_is_production_member":can["wip_interval_is_raw_production_member"],
                    "candidate_relationship_not_authorized":True})
            proxy.append({"city":city,"original_episode_id":idv,
                          "original_exact":[r["original_alert_start_exact"],r["original_alert_end_exact"]],
                          "first_persisted_git":firstrec,
                          "producer_code":producer_cache[producer_commit],
                          "grouping":"touching_or_overlapping_union",
                          "candidate_cardinality":r["candidate_cardinality"],
                          "candidate_comparisons":evidence,
                          "supported_identity_disposition":"AMBIGUOUS_RELATIONSHIP",
                          "material_boundary_differences_observed":
                              any(c["start_delta_seconds_signed"] or c["end_delta_seconds_signed"]
                                  for c in r["candidate_production_episodes"]),
                          "equivalence_proven":False})
        else:
            assert r["root_cause_category"]=="A"
            c=r["candidate_production_episodes"][0]
            assert c["precision_only_whole_second_match"] is True
            precision.append({"city":city,"original_episode_id":idv,
                              "candidate_id":c["production_id"],
                              "original_exact":[r["original_alert_start_exact"],r["original_alert_end_exact"]],
                              "production_exact":[c["production_start"],c["production_end"]],
                              "start_signed_delta_s":c["start_delta_seconds_signed"],
                              "end_signed_delta_s":c["end_delta_seconds_signed"],
                              "mechanical_whole_second_match":True,
                              "proven_source_transformation":False,
                              "new_identity_authorized":False})
        if r["root_cause_category"]=="G":
            all_unresolved.append({"city":city,"original_episode_id":idv,
                                   "source_disposition":
                                   (kyiv[-1]["supported_identity_disposition"] if city=="kyiv" else
                                    "AMBIGUOUS_RELATIONSHIP"),
                                   "candidate_ids":[c["production_id"] for c in r["candidate_production_episodes"]],
                                   "original_start_exact":r["original_alert_start_exact"],
                                   "original_end_exact":r["original_alert_end_exact"],
                                   "first_git_commit":firstrec["commit"],
                                   "root_cause_frozen":r["root_cause_category"]})
    assert len(kyiv)==185 and len(proxy)==9 and len(precision)==15
    assert len(all_unresolved)==194
    expected_rpt=load(Path(a.manifest).with_name("wip_cached_209_reconciliation_report_2026-10-15.json"))
    assert expected_rpt["category_counts"]=={"A":15,"G":194}
    assert expected_rpt["candidate_cardinality_counts"]==dict(ccard)
    assert expected_rpt["total_exact_queue_item_links"]==queue_result["exact_id_queue_entry_links"]
    before_hash=dict(input_hash)
    after_hash={k:digest(v.read_bytes()) for k,v in paths.items() for k in
                ([("wip:" if k in ("state","queue") else "")+("explosion_candidate_monitor_state.json" if k=="state" else
                   "explosion_review_queue.json" if k=="queue" else k)] )}
    assert before_hash==after_hash
    assert git(a.wip,"status","--porcelain")=="" and git(a.prod,"status","--porcelain")==""
    receipt={
        "checkpoint":"INDEPENDENT_MANIFEST_INTEGRITY_PASS_WITH_GIT_ARCHIVE_PARITY",
        "209_manifest_integrity":"PASS",
        "rows":209,"unique_original_ids":209,"original_hashes_correct":209,
        "geography":EXPECTED_CITY,"original_source_blob_pointer_checks":"PASS",
        "production_candidate_reconstruction":"PASS",
        "candidate_cardinality":dict(ccard),"frozen_categories":dict(cats),
        "queue_reference_audit":queue_result,
        "manifest_bytes":MANIFEST_LEN,"manifest_sha256":MANIFEST_SHA,
        "original_artifact_zip_sha256":ZIP_SHA,"original_artifact_members":artifact_members,
        "raw_provenance_current_frozen_wip_cases":0,
        "history_scan":first_stats,
        "historical_combined_source_versions_scanned":len(versions),
        "repair_e325_git_check":repair,
        "source_version_evidence_is_not_automatic_identity_proof":True}
    ledger={"city":"kyiv","count":185,"rows":kyiv}
    diagnosis={"cities":{"mykolaiv":4,"sumy":5},"count":9,"rows":proxy}
    matrix={"city_frozen_categories":{
        city:dict(Counter(r["root_cause_category"] for r in rows if r["city"]==city))
        for city in EXPECTED_CITY},
        "kyiv_source_dispositions":dict(proven),
        "source_transformations_proven":0,
        "material_boundary_observations_not_identity_proofs":sum(
            r["material_boundary_differences_observed"] for r in proxy),
        "proxy_identity_equivalences_proven":0,
        "precision_only_mechanical_pass":len(precision),
        "precision_only_source_transformations_proven":0,
        "still_unresolved_194":194,
        "precision_only_cases":precision,
        "historical_source_repair":repair,
        "unique_historical_kyiv_source_records_at_first_persistence":
            sum(bool(r["raw_combined_rows_at_first_persistence"]) for r in kyiv),
        "kyiv_cases_with_any_historical_combined_source_match":
            sum(bool(r["other_historical_combined_row_occurrences"]) for r in kyiv),
        "provisional_only":True}
    safety={"wip_sha":WIP,"prod_sha":PROD,
            "initial_input_sha256":before_hash,"final_input_sha256":after_hash,
            "git_sha":git_sha,"original_archive_sha256":ZIP_SHA,
            "original_manifest_sha256":MANIFEST_SHA,
            "production_credentials_present":False,
            "source_request_count":0,"database_connection_count":0,
            "publisher_request_count":0,"classifier_runs":0,
            "production_writes":0,"wip_writes":0,
            "historical_review_decisions_modified":0,
            "identity_mapping_authorized":False,
            "wip_activation":"NO-GO",
            "output_determinism":"to be independently checked by A/B workflow"}
    a.out.mkdir(parents=True,exist_ok=True)
    artifacts=[
        save(a.out,"independent_209_manifest_receipt_2026-10-15.json",receipt),
        save(a.out,"kyiv_185_source_time_lineage_2026-10-15.json",ledger),
        save(a.out,"proxy_9_boundary_diagnosis_2026-10-15.json",diagnosis),
        save(a.out,"reconciliation_matrix_2026-10-15.json",matrix),
        save(a.out,"unresolved_194_register_2026-10-15.json",{"count":194,"rows":all_unresolved}),
        save(a.out,"safety_reproducibility_2026-10-15.json",safety)]
    print(json.dumps({"manifest_integrity":"PASS","kyiv":dict(proven),
                      "historical_matches":matrix["kyiv_cases_with_any_historical_combined_source_match"],
                      "original_first_matches":matrix["unique_historical_kyiv_source_records_at_first_persistence"],
                      "proven_identity_links":0,"proxy":len(proxy),"precision":len(precision),
                      "queue":queue_result,"historical_versions":len(versions),
                      "output_artifacts":artifacts},sort_keys=True))

if __name__=="__main__":
    main()
