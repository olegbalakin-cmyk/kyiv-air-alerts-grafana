#!/usr/bin/env python3
"""Frozen-source-only Kyiv 28 provenance audit. No classifier, source request or SQL."""
import argparse
import collections
import csv
import datetime as dt
import hashlib
import io
import json
import os
import pathlib
import subprocess
import sys
import urllib.request
import zipfile

PIN = "92d57bbbfad60e6c09bb92372b1e84f38fa6ced4"
RECEIPT_COMMIT = "2648aea950f489e5547869ca422e463dda84648d"
RECEIPT_PATH = "research/kyiv_live_29_semantic_audit_verified_receipt_2026-10-12.json"
RECEIPT_BLOB = "9df9e451b852a882f065e98bbb188f878eda6646"
PREFIX = "kyiv-air-alerts-grafana/data/"
FILES = {
 "state": ("explosion_candidate_monitor_state.json","b255f516a8598bbd28faaa1a651249f4064b5620","439fdc640603210a8aa1ffb72543b2837cc729a5618b809ede82b18b8b632a8c",4100971),
 "queue": ("explosion_review_queue.json","e7777b88bf1912572df10eb252f991ea6456feba","48db2aef4daab57a14fae3c533d1c0c2b6a5d81f0790fb09a86bc749e4de3573",54234970),
 "report": ("explosion_candidate_monitor_last_run.json","19d27d7b72afb52a235e6dfc0914f5aee7082ce2","b1e0fa30a72d72a29dfc02db0328351551878ad53a4004a201a9a653bed0e074",184821),
}
CODE_PATHS = {
 "monitor": "kyiv-air-alerts-grafana/scripts/monitor_explosion_candidates.py",
 "classifier": "kyiv-air-alerts-grafana/scripts/authoritative_classifier_71cb6f6f.py",
 "ordering": "kyiv-air-alerts-grafana/scripts/live_parent_ordering.py",
 "persistence": "kyiv-air-alerts-grafana/scripts/attack_event_canonical_persistence.py",
}
BLOBS = {
 "monitor":"95e0eb313c6c68016601f681ab5186bf147d6dd1",
 "classifier":"778469b74c2aa807d851cf2c2ee35cf4aa785589",
 "ordering":"d43ee3573d78e70e4d9fa3559e81cf950799db0b",
 "persistence":"0118ca9e5f1308173e657257f1b49fe91cc19fe1",
}
ARTIFACT = 11793023953
ARTIFACT_HASH = "f9b106535adc4bb3ef8c71ae0d043b432440dbf84681a521cca5e7fa47d72c5a"
READBACK_HASH = "61adf25c29fbf819e3823430f473032acc117cc3e2aa86d40a0b8860c7b9ff5a"
RECON_HASH = "8e7993bc2db623faf40971e0ef957e8d52127d4672c44203685fecf2474aaa16"
SNAPSHOT = "2026-10-11T05:56:28.255150Z"
LABELS = [("immediate",0),("24h",24),("72h",72),("7d",168)]
FAMILIES = ["explosion","impact_arrival","strike","attack_consequence","air_defense_action"]
TARGET = "191d71f593ca42db0c8f5ba4"
CONTROL = "176a083e264eec607cdb1ea6"

def sha(b): return hashlib.sha256(b).hexdigest()
def fmt(x): return json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(",",":"),default=str).encode()
def git(*args): return subprocess.check_output(["git",*args],stderr=subprocess.PIPE)
def iso(s): return dt.datetime.fromisoformat(str(s).replace("Z","+00:00")).astimezone(dt.timezone.utc)
def us(s): return iso(s).isoformat().replace("+00:00","Z")
def rowhash(x): return sha(fmt(x))
def write(out,name,value):
    (out/name).write_bytes(json.dumps(value,sort_keys=True,indent=2,ensure_ascii=False,default=str).encode("utf-8")+b"\n")

def download_snapshot(path):
    token=os.environ.get("GITHUB_TOKEN")
    if not token: raise RuntimeError("MISSING_ACTIONS_READ_TOKEN")
    url="https://api.github.com/repos/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/artifacts/"+str(ARTIFACT)+"/zip"
    req=urllib.request.Request(url,headers={"Authorization":"Bearer "+token,"Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28","User-Agent":"bounded-kyiv-28-audit"})
    with urllib.request.urlopen(req,timeout=90) as res: raw=res.read()
    if sha(raw)!=ARTIFACT_HASH: raise RuntimeError("ACCEPTED_ARTIFACT_ZIP_HASH_MISMATCH:"+sha(raw))
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(raw)
    print("FROZEN_ACCEPTED_SNAPSHOT_ZIP_VERIFIED",ARTIFACT,len(raw),ARTIFACT_HASH)

def read_snapshot(path):
    raw=path.read_bytes()
    # The Actions downloader provides decompressed accepted members; workflow repacks them for transport within this job. Original ZIP SHA is separately verified at source.
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        names=z.namelist()
        bybase={pathlib.PurePosixPath(x).name:x for x in names if not x.endswith("/")}
        manifest=json.loads(z.read(bybase["10_manifest.json"]))
        assert len(manifest["members"])==9, "SNAPSHOT_MEMBER_CARDINALITY"
        for name,meta in manifest["members"].items():
            data=z.read(bybase[name])
            assert sha(data)==meta["sha256"] and len(data)==meta["bytes"], ("MANIFEST_MEMBER_ERROR",name)
        rb=z.read(bybase["04_canonical_readback_redacted.json"])
        reconciliation=z.read(bybase["05_kyiv_29_reconciliation.json"])
        assert sha(rb)==READBACK_HASH and sha(reconciliation)==RECON_HASH
        return json.loads(rb),json.loads(reconciliation),{"artifact":ARTIFACT,"repacked_transport_zip_sha256":sha(raw),"original_artifact_zip_sha256_accepted":ARTIFACT_HASH,"raw_sha256":sha(rb),"reconciliation_sha256":sha(reconciliation),"manifest_verified_members":9,"zip_members":len(bybase),"captured_at":json.loads(rb)["snapshot"].get("utc_observed_at")}

def get_frozen():
    assert git("rev-parse",PIN+"^{commit}").decode().strip()==PIN
    obj={}; integrity={}
    for key,(name,blob,digest,length) in FILES.items():
        p=PREFIX+name
        assert git("rev-parse",PIN+":"+p).decode().strip()==blob
        b=git("cat-file","blob",blob)
        assert len(b)==length and sha(b)==digest,("INVALID_ORIGINAL_OBJECT",key)
        obj[key]=json.loads(b)
        integrity[key]={"path":p,"git_blob":blob,"bytes":len(b),"sha256":sha(b)}
    raw=git("show",RECEIPT_COMMIT+":"+RECEIPT_PATH)
    assert git("hash-object","--stdin",input=raw).decode().strip()==RECEIPT_BLOB
    receipt=json.loads(raw)
    assert len(receipt["episode_rows"])==29
    for k,p in CODE_PATHS.items():
        assert git("rev-parse",PIN+":"+p).decode().strip()==BLOBS[k],("WRONG_FROZEN_CODE",k)
    integrity["accepted_receipt"]={"commit":RECEIPT_COMMIT,"path":RECEIPT_PATH,"blob":RECEIPT_BLOB,"sha256":sha(raw)}
    integrity["frozen_code"]={k:{"path":p,"blob":BLOBS[k],"wip_blob":git("rev-parse","multicity-wip-2026-09-16:"+p).decode().strip() if have_ref("multicity-wip-2026-09-16") else "NOT_OBSERVABLE"} for k,p in CODE_PATHS.items()}
    return obj,receipt,integrity

def have_ref(ref):
    return subprocess.run(["git","rev-parse","--verify","--quiet",ref],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0

def history_reports(original):
    """Only exact committed historical reports reachable from the frozen original commit."""
    rel=PREFIX+FILES["report"][0]
    commits=git("log","--format=%H","--since=2026-10-07T00:00:00Z","--max-count=250",PIN,"--",rel).decode().splitlines()
    found={}
    for commit in commits:
        try:
            b=git("show",commit+":"+rel)
            j=json.loads(b)
            when=j.get("finished_at","")
            if not ("2026-10-07"<=when[:10]<="2026-10-11") or iso(when)>iso(SNAPSHOT): continue
            hash_=sha(b)
            found[hash_]={"git_commit":commit,"git_blob":git("hash-object","--stdin",input=b).decode().strip(),"report":j,"sha256":hash_}
        except Exception: continue
    b=git("cat-file","blob",FILES["report"][1])
    h=sha(b)
    found[h]={"git_commit":PIN,"git_blob":FILES["report"][1],"report":original,"sha256":h}
    return sorted(found.values(),key=lambda a:(a["report"]["followup_cutoff_at"],a["git_commit"]))

def findref(x,ids,path="$"):
    if isinstance(x,dict):
        for k,v in x.items(): yield from findref(v,ids,path+"."+str(k))
    elif isinstance(x,list):
        for i,v in enumerate(x): yield from findref(v,ids,path+"["+str(i)+"]")
    elif isinstance(x,str) and x in ids: yield path,x

def refkind(path):
    if path in ("$.classification_evidence.classification_episode_id","$.composition_provenance.target_episode_id","$.classification_evidence.episode_level_composition.target_episode_id"):return "classifier_target"
    if path=="$.matched_episode_id" or path.endswith(".candidate_matching.matched_episode_id"):return "matched"
    if path.startswith("$.matched_episode_ids[") or path.startswith("$.matching_logical_episode_groups[") or ".candidate_matching.matched_episode_ids[" in path:return "matched"
    if path.startswith("$.trigger_episode_ids["):return "trigger"
    return "other"

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--fetch-snapshot",action="store_true")
    ap.add_argument("--snapshot",type=pathlib.Path,required=True)
    ap.add_argument("--out",type=pathlib.Path)
    args=ap.parse_args()
    if args.fetch_snapshot:
        download_snapshot(args.snapshot);return
    if args.out is None: raise RuntimeError("MISSING_OUTPUT_DIRECTORY")
    out=args.out;out.mkdir(parents=True,exist_ok=True)
    frozen,receipt,integrity=get_frozen()
    db,db_summary,snapshot_integrity=read_snapshot(args.snapshot)
    integrity["canonical_snapshot"]=snapshot_integrity
    integrity["frozen_original_commit"]=PIN
    integrity["current_canonical_is_historical_asof"]="NOT_PROVEN"
    state,queue,run=frozen["state"],frozen["queue"],frozen["report"]
    assert run["finished_at"]==SNAPSHOT and run["production_persistence_canary_max_episodes"]==10
    assert len(queue)==4442 and len(db_summary["episodes"])==29
    erows={x["episode_id"]:x for x in receipt["episode_rows"]}
    drows={x["episode_id"]:x for x in db_summary["episodes"]}
    assert set(erows)==set(drows) and len(erows)==29
    control=[x for x in drows.values() if x["current_tip_count"]==1]
    unclassified=[x for x in drows.values() if x["current_tip_count"]==0]
    assert len(control)==1 and control[0]["episode_id"]==CONTROL and len(unclassified)==28
    assert all(x["canonical_exact_parent_count"]==1 for x in drows.values())
    episodes={x["episode_id"]:x for x in state["cities"]["kyiv"]["episodes"] if x.get("episode_id") in erows}
    assert len(episodes)==29
    for eid,x in episodes.items():
        e=erows[eid]
        assert x["alert_start"]==e["alert_start"] and x["alert_end"]==e["alert_end"]
    hist=history_reports(run)
    by_cutoff=collections.defaultdict(list)
    for h in hist:by_cutoff[h["report"].get("followup_cutoff_at")].append(h)
    hist_receipts=[{"git_commit":h["git_commit"],"git_blob":h["git_blob"],"report_sha256":h["sha256"],"started_at":h["report"].get("started_at"),"finished_at":h["report"].get("finished_at"),"cutoff":h["report"].get("followup_cutoff_at"),"kyiv_search_reported":"kyiv" in h["report"].get("searches",{}),"kyiv_google_error":(h["report"].get("searches",{}).get("kyiv") or {}).get("google_error"),"kyiv_query_families":list((h["report"].get("searches",{}).get("kyiv") or {}).get("query_family_result_counts",{}))} for h in hist]
    cutoff=iso(SNAPSHOT);followup_ledger={};total=collections.Counter()
    for eid,e in sorted(episodes.items(),key=lambda kv:(kv[1]["alert_start"],kv[0])):
        entries=[]
        assert len(e.get("checks") or [])==4
        for (label,hours),ch in zip(LABELS,e["checks"]):
            due=iso(e["alert_end"])+dt.timedelta(hours=hours)
            assert label==ch["label"] and us(ch["due_at"])==us(due)
            is_due=due<=cutoff
            checked=bool(ch.get("checked_at"))
            if checked: assert is_due and iso(ch["checked_at"])<=cutoff
            status="NOT_DUE_AT_SNAPSHOT" if not is_due else ("DUE_NOT_EXECUTED" if not checked else "MARKED_CHECKED_ONLY")
            linked=[]; confirmed=False; failed=False;attempt=False
            if checked:
                for h in by_cutoff.get(ch["checked_at"],[]):
                    jr=h["report"];sr=jr.get("searches",{}).get("kyiv") or {}
                    if sr:
                        family_counts=sr.get("query_family_result_counts") or {}
                        family_urls=sr.get("query_urls") or {}
                        good=all(k in family_counts and k in family_urls for k in FAMILIES) and sr.get("google_error") is None and not jr.get("errors",{}).get("search:kyiv")
                        error=bool(sr.get("google_error") or jr.get("errors",{}).get("search:kyiv"))
                        attempt=attempt or bool(sr.get("query_url") or family_urls or error)
                        confirmed=confirmed or good
                        failed=failed or error
                        linked.append({"report_git_commit":h["git_commit"],"report_git_blob":h["git_blob"],"report_sha256":h["sha256"],"reported_due_city_checks":sr.get("due_checks"),"query_families_recorded":sorted(family_counts),"query_family_result_counts":{k:family_counts.get(k) for k in FAMILIES if k in family_counts},"google_error":sr.get("google_error"),"telegram_results":sr.get("telegram_results"),"new_candidates_city_batch":sr.get("new_candidates"),"run_started_at":jr.get("started_at"),"run_followup_cutoff_at":jr.get("followup_cutoff_at"),"google_batch_return_confirmed":good,"source_packet_capture_present":False})
            if failed:status="SEARCH_EXECUTION_FAILED"
            elif confirmed:status="PARTIAL_SOURCE_COVERAGE_CONFIRMED"
            elif attempt:status="SEARCH_ATTEMPT_RECORDED"
            total[status]+=1
            entries.append({"label":label,"hours_after_alert_end":hours,"scheduled_utc":us(due),"snapshot_cutoff":SNAPSHOT,"due_at_snapshot":is_due,"checked_at":ch.get("checked_at"),"new_candidates_stored":ch.get("new_candidates"),"status":status,"google_execution_confirmed_by_complete_success_report":confirmed,"google_attempt_recorded":attempt,"google_execution_failed_in_report":failed,"city_search_reports":linked,"telegram_cache_evidence":"LAST_SNAPSHOT_CACHE_ONLY; NO PER-FOLLOWUP RAW_RESPONSE","specific_required_coverage_complete":False,"missing":["ORIGINAL_GOOGLE_NEWS_HTTP_RESPONSE_AND_PER_FAMILY_SOURCE_RECEIPTS","ORIGINAL_TELEGRAM_PAGE_FETCH_RESPONSE_AND_HISTORICAL_PAGINATION_PROOF","PUBLISHER_ORIGINAL_CONTENT_AND_VERSION_WHERE_REQUIRED","EPISODE_SPECIFIC_SOURCE_BATCH_MEMBERSHIP_AND_COMPLETENESS"] if is_due else []})
        followup_ledger[eid]=entries
    assert sum(total.values())==116
    assert total["NOT_DUE_AT_SNAPSHOT"]==61
    assert sum(x["due_at_snapshot"] for checks in followup_ledger.values() for x in checks)==55
    assert sum(bool(x["checked_at"]) for checks in followup_ledger.values() for x in checks)==55
    assert sum(x["due_at_snapshot"] for eid,checks in followup_ledger.items() if eid!=CONTROL for x in checks)==52
    assert sum(bool(x["checked_at"]) for eid,checks in followup_ledger.items() if eid!=CONTROL for x in checks)==52
    # Independently reconstruct the exact GLOBAL earliest-ten ordering, not only Kyiv order.
    order=[];seen=set();cutoff_start=iso(run["production_persistence_canary_cutoff"])
    for city,cs in state["cities"].items():
        for x in cs.get("episodes") or []:
            eid=str(x.get("episode_id") or "")
            if not eid or x.get("identity_superseded_by_episode_id") or not x.get("alert_end") or iso(x["alert_end"])<cutoff_start:continue
            key=(city,eid)
            if key in seen:continue
            seen.add(key)
            order.append((iso(x["alert_end"]),iso(x["alert_start"]),city,eid))
    order.sort();positions={(x[2],x[3]):i+1 for i,x in enumerate(order)}
    selected=[(x.get("city"),x.get("episode_id")) for x in run["parent_ordering"]["records"]]
    assert len(order)==run["parent_ordering"]["eligible_post_cutoff_live_episodes"]==479
    assert selected==[(x[2],x[3]) for x in order[:10]],"FROZEN_GATE_ORDER_DIFFERS_FROM_REPORT"
    assert len(selected)==10 and (("kyiv",CONTROL) in selected)
    assert run["canonical_persistence"]["episodes_considered"]==0 and run["canonical_persistence"]["records"]==[]
    # Exact-original-queue candidate relationships. No classification rerun.
    idset=set(erows);matches=collections.defaultdict(lambda:collections.defaultdict(set))
    qlinks=collections.defaultdict(list)
    for idx,q in enumerate(queue):
        if not isinstance(q,dict):continue
        cid=str(q.get("candidate_id") or "MISSING_CANDIDATE_"+str(idx))
        found=list(findref(q,idset))
        for path,eid in found:
            matches[eid]["any"].add(cid)
            kind=refkind(path)
            if kind in ("matched","classifier_target"):matches[eid]["stored_match_or_classifier"].add(cid)
            if kind=="classifier_target":matches[eid]["classifier_target"].add(cid)
            if kind=="matched":matches[eid]["matched"].add(cid)
            if kind=="trigger":matches[eid]["trigger"].add(cid)
            if kind=="other":matches[eid]["other"].add(cid)
            if eid in (TARGET,CONTROL):
                qlinks[eid].append({"candidate_id":cid,"queue_index":idx,"json_path":path,"relation_type":kind,"row_sha256":rowhash(q),"status":q.get("status"),"published_at":q.get("published_at"),"source":q.get("source"),"publisher":q.get("publisher"),"observation_id":q.get("observation_id"),"matched_episode_id":q.get("matched_episode_id"),"classification_reason_codes":q.get("classification_reason_codes"),"classification_evidence_reason_codes":(q.get("classification_evidence") or {}).get("reason_codes") if isinstance(q.get("classification_evidence"),dict) else None,"classification_evidence_sha256":rowhash(q.get("classification_evidence")) if q.get("classification_evidence") is not None else None,"review_disposition_present":q.get("review_disposition") is not None,"review_history_present":bool(q.get("review_history"))})
    for eid,e in erows.items():
        assert len(matches[eid]["any"])==e["unique_candidates_any"],("ANY_CANDIDATE_COUNT_MISMATCH",eid)
        assert len(matches[eid]["stored_match_or_classifier"])==e["unique_candidates_with_stored_match_or_classifier"],("EXPLICIT_MATCH_COUNT_MISMATCH",eid)
        assert len(matches[eid]["classifier_target"])==e["unique_candidates_with_final_classifier_binding"],("TARGET_COUNT_MISMATCH",eid)
    assert len(matches[TARGET]["classifier_target"])==1
    assert len(matches[CONTROL]["classifier_target"])==0
    raw_db=db["tables"]
    cls_by=collections.defaultdict(list)
    for c in raw_db["attack_event_classifications"]:cls_by[str(c["historical_episode_id"])].append(c)
    links_by=collections.defaultdict(list)
    for l in raw_db["attack_event_sources"]:links_by[str(l["classification_uid"])].append(l)
    def class_summary(eid):
        cs=sorted(cls_by[eid],key=lambda c:str(c.get("created_at")))
        out=[]
        for c in cs:
            ls=links_by[str(c["classification_uid"])]
            out.append({"classified_at":c.get("classified_at"),"created_at":c.get("created_at"),"verdict":c.get("verdict"),"revision_reason":c.get("revision_reason"),"supersedes_previous":bool(c.get("supersedes_classification_uid")),"origin_kind":c.get("origin_kind"),"origin_provenance_sha256":c.get("origin_provenance_sha256"),"origin_provenance_content_sha256":c.get("origin_provenance_content_sha256"),"classifier_blob_sha":c.get("classifier_blob_sha"),"classifier_methodology_version":c.get("classifier_methodology_version"),"classification_key_sha256":sha(str(c.get("classification_key")).encode()),"sources_count":len(ls),"sources_sanitized":[{"source_family":l.get("source_family"),"source_type":l.get("source_type"),"source_timestamp":l.get("source_timestamp"),"observation_id_sha256":sha(str(l.get("observation_id")).encode()) if l.get("observation_id") else None,"content_sha256":l.get("content_sha256")} for l in ls]})
        return out
    assessment=[];traces=[];coverage=[];nexts=[]
    ordered_ids=sorted((eid for eid in erows if eid!=CONTROL),key=lambda eid:(erows[eid]["alert_start"],eid))
    for eid in ordered_ids+[CONTROL]:
        er=erows[eid];dr=drows[eid];c=collections.Counter(x["status"] for x in followup_ledger[eid])
        rank=positions.get(("kyiv",eid))
        assert rank is not None and (rank<=10)==(eid==CONTROL),("UNEXPECTED_KYIV_POSITION",eid,rank)
        search_success=sum(x["google_execution_confirmed_by_complete_success_report"] for x in followup_ledger[eid])
        search_failed=sum(x["google_execution_failed_in_report"] for x in followup_ledger[eid])
        source_ok=False
        flags=["SOURCE_COVERAGE_INCOMPLETE_OR_UNVERIFIABLE"]
        if eid!=CONTROL:flags+=["QUEUE_STARVATION_EPISODE_PROVEN","PERSISTENCE_NOT_SELECTED_PROVEN"]
        row={"episode_id":eid,"alert_start":er["alert_start"],"alert_end":er["alert_end"],"control":eid==CONTROL,"canonical_snapshot_disposition":dr["disposition"],"canonical_parent_exact":dr["canonical_exact_parent_count"]==1,"canonical_classification_revisions":dr["classification_revisions"],"canonical_current_tip_verdicts":dr["current_tip_verdicts"],"canonical_source_links":dr["source_links_count"],"canonical_event_count":dr["event_count"],"followup_states":[{"label":x["label"],"due_at_utc":x["scheduled_utc"],"state":x["status"],"checked_at":x["checked_at"]} for x in followup_ledger[eid]],"due_followups":sum(x["due_at_snapshot"] for x in followup_ledger[eid]),"marked_checked_followups":sum(bool(x["checked_at"]) for x in followup_ledger[eid]),"confirmed_google_execution_followups":search_success,"reported_failed_google_execution_followups":search_failed,"required_source_coverage_confirmed":source_ok,"candidate_any_count":len(matches[eid]["any"]),"candidate_stored_matching_or_classifier_count":len(matches[eid]["stored_match_or_classifier"]),"candidate_matched_count":len(matches[eid]["matched"]),"classifier_target_count":len(matches[eid]["classifier_target"]),"queue_global_rank_at_frozen_run":rank,"within_parent_canary_ten":rank<=10,"frozen_run_parent_gate_selected":("kyiv",eid) in selected,"frozen_run_persistence_selected":False,"frozen_run_persistence_attempt_confirmed":False,"frozen_run_persistence_failure_confirmed":False,"supported_blockers":flags,"required_missing_evidence":["EPISODE_SPECIFIC_RAW_SOURCE_RESPONSE_AND_SOURCE_COMPLETENESS","HISTORICALLY_CORRELATED_SUCCESSFUL_RUN_RECEIPTS_FOR_ALL_DUE_CHECKS","ORIGINAL_PUBLISHER_VERSIONS_WHERE_REQUIRED","PER_EPISODE_PERSISTENCE_ACK_HISTORY_BEFORE_FROZEN_RUN"],"future_prospective_capture_required_to_ESTABLISH_FUTURE_NOT_HISTORICAL_COVERAGE":True,"ready_for_canonical_processing":False,"recovery_readiness":"RECOVERY_READINESS_NOT_PROVEN","smallest_next_action":"RECOVER_EXISTING_HISTORICAL_RUN_AND_SOURCE_RESPONSE_RECEIPTS; NO RETROSPECTIVE_SOURCE_REPLAY"}
        assessment.append(row)
        coverage.append({"episode_id":eid,"control":eid==CONTROL,"followup_summary":dict(sorted(c.items())),"confirmed_google_run_followups":search_success,"google_execution_failures":search_failed,"telegram_original_page_responses_retained":False,"original_google_news_http_responses_retained":False,"required_source_coverage_confirmed":False,"source_discovery_triggers_are_confirmation":False,"run_reports":[{"check":x["label"],"report_git_commits":[y["report_git_commit"] for y in x["city_search_reports"]]} for x in followup_ledger[eid]]})
        traces.append({"episode_id":eid,"control":eid==CONTROL,"eligible_at_frozen_run":True,"global_rank":rank,"parent_gate_selected":rank<=10,"parent_report_records_exact":sorted([x for x in run["parent_ordering"]["records"] if x.get("city")=="kyiv" and x.get("episode_id")==eid],key=lambda x:fmt(x)),"persistence_selection_at_frozen_run":False,"persistence_report_episodes_considered":0,"persistence_attempt_confirmed":False,"persistence_failure_confirmed":False,"candidate_classifier_target_count":len(matches[eid]["classifier_target"]),"past_run_evidence_caveat":"Current run proves excluded by parent gate, not the absence of attempts in all previous executions.","supported_causes":flags})
        if eid!=CONTROL:nexts.append({"episode_id":eid,"source_gap":"REQUIRED_SOURCE_COVERAGE_NOT_PROVEN","historical_run_receipts_with_confirmed_kyiv_search":search_success,"historical_run_receipts_with_failed_kyiv_search":search_failed,"queue_gate":"EXCLUDED_FROM_OLDest_TEN_AT_2026_10_11_FROZEN_RUN","persistence_attempt":"NOT_SELECTED_IN_FROZEN_RUN; PRIOR_HISTORY_NOT_EXHAUSTIVELY_PROVEN","next_action":"Seek exact immutable run-level source receipts and original source-response archives; if absent, future controlled prospective capture cannot certify historical coverage."})
    assert len(assessment)==29 and len(nexts)==28
    cross={
      TARGET:{"episode_id":TARGET,"interval":[erows[TARGET]["alert_start"],erows[TARGET]["alert_end"]],"frozen_queue_classifier_target_references":[q for q in qlinks[TARGET] if q["relation_type"]=="classifier_target"],"all_frozen_queue_references_summary":dict(collections.Counter(q["relation_type"] for q in qlinks[TARGET])),"original_record_locator":{"git_commit":PIN,"queue_git_blob":FILES["queue"][1],"json_pointer":"$[INDEX_IN_REFERENCES_ABOVE]","full_original_row_bytes_not_republished":True},"canonical_classification_revisions":len(cls_by[TARGET]),"persistence_selection_on_frozen_run":False,"persistence_attempt_confirmed":False,"outcome":"CLASSIFIER_DECISION_WITHOUT_PROVEN_PERSISTENCE_ATTEMPT" if matches[TARGET]["classifier_target"] else "CLASSIFIER_TARGET_ONLY","persistence_cause":"PERSISTENCE_SKIPPED_PROVEN_ON_FROZEN_RUN; PREVIOUS_HISTORY_NOT_OBSERVABLE","lost_committed_write_proven":False},
      CONTROL:{"episode_id":CONTROL,"interval":[erows[CONTROL]["alert_start"],erows[CONTROL]["alert_end"]],"frozen_queue_classifier_target_references":[q for q in qlinks[CONTROL] if q["relation_type"]=="classifier_target"],"all_frozen_queue_references_summary":dict(collections.Counter(q["relation_type"] for q in qlinks[CONTROL])),"accepted_canonical_revision_provenance_sanitized":class_summary(CONTROL),"frozen_run_parent_gate_selected":True,"frozen_run_persistence_selected":False,"source_link_count":dr["source_links_count"] if False else drows[CONTROL]["source_links_count"],"explanation_from_original_persistence_code":"_episode_refs reads matched_episode_id(s) and classification_evidence.classification_episode_id; no surviving frozen classifier_target field is necessary for a prior canonical classification.","origin_reconstruction":"ORIGIN_KIND_AND_REVISION_TIMES_AS_REDACTED; FULL_SOURCE_PROVENANCE_IF_NOT_RETAINED_UNRESOLVED","outcome":"CANONICAL_CLASSIFICATION_PROVEN; FROZEN_TARGET_FIELD_NOT_REQUIRED"}}
    assert len(cross[TARGET]["frozen_queue_classifier_target_references"])==1
    assert len(cross[CONTROL]["accepted_canonical_revision_provenance_sanitized"])==2
    summarized={"unclassified_episodes":28,"classified_control":1,"canonical_parents":29,"four_checks_all":116,"followups_due":55,"followups_marked_checked":55,"unclassified_followups_scheduled":112,"unclassified_followups_due":52,"unclassified_followups_checked":52,"followup_execution_statuses_all":dict(sorted(total.items())),"followup_execution_statuses_unclassified":dict(sorted(collections.Counter(x["status"] for eid in ordered_ids for x in followup_ledger[eid]).items())),"required_source_coverage_confirmed_episodes":0,"source_coverage_partial_google_run_proven_episodes":sum(x["confirmed_google_execution_followups"]>0 for x in assessment if not x["control"]),"source_execution_failure_proven_episodes":sum(x["reported_failed_google_execution_followups"]>0 for x in assessment if not x["control"]),"insufficient_source_execution_or_coverage_evidence_episodes":28,"queue_starvation_episode_proven_in_frozen_run":28,"persistence_not_selected_episode_proven_in_frozen_run":28,"persistence_attempts_proven_unclassified":0,"persistence_failures_proven_unclassified":0,"historical_any_attempt_prior_to_frozen_run":"NOT_EXHAUSTIVELY_OBSERVABLE","processing_causes_unresolved_historically":28,"ready_for_canonical_processing":0,"original_queue_total_candidates":len(queue),"original_report_parent_gate_selected_total":len(selected),"original_report_parent_gate_eligible_total":len(order),"original_report_persistence_episodes_considered":run["canonical_persistence"]["episodes_considered"],"historical_git_run_receipts_found":len(hist),"control_db_revision_count":2,"cross_layer_classifier_target_rows":1}
    contract={"frozen_git_commit":PIN,"current_wip_is_not_retroactive_authority":True,"code_git_blobs":BLOBS,"schedule_hours":[x[1] for x in LABELS],"schedule_anchor":"alert_end UTC; due selection at monitor end of polling; last-run followup_cutoff_at","source_families":{"google_news":FAMILIES,"telegram":["suspilne","ukrpravda"],"publisher_fulltext_fetch_cap_per_city":8},"google_contract":"5 query families sequential; request + raise_for_status + XML parse; function can throw; family counts reported only for completed loop; raw responses not durably captured here","telegram_contract":"Cached posts retained max 9 days; page retrieval failures recorded per source, but no historic HTTP response archive.","due_contract":"due if due_at <= followup_cutoff and checked_at absent; city-batched; checked_at assigned after search attempt even if google_error.","search_flags":"checked_at != HTTP success; query_url != HTTP proof; zero candidates != no attack; city-batch success != episode-specific complete coverage","global_parent_gate":"all eligible 23-city closed episodes sorted by (alert_end,alert_start,city_key,episode_id); max 10; oldest selected on every run; no skip of already synced/classified","persistence_gate":"parent-ready due only; coverage_by_city is runtime boolean; classification builder examines matched refs from stored queue, not all trigger refs; per-episode transaction and response records","frozen_run_correlated_kyiv_search":{"started_at":run["started_at"],"cutoff_at":run["followup_cutoff_at"],"google_error":run["searches"]["kyiv"]["google_error"],"query_family_result_counts":run["searches"]["kyiv"]["query_family_result_counts"],"city_due_checks":run["searches"]["kyiv"]["due_checks"],"telegram_results":run["searches"]["kyiv"]["telegram_results"],"record_identity":FILES["report"][1]},"historical_git_reports":hist_receipts,"original_source_raw_archives_present":"NOT_ESTABLISHED_FROM_ANY_FROZEN_MONITOR_CONTRACT","no_network_source_fetch":True,"no_classifier_execution":True,"no_neon_sql":True,"no_db_write":True}
    write(out,"01_frozen_input_integrity.json",integrity)
    write(out,"02_frozen_source_execution_contract.json",contract)
    write(out,"03_kyiv_28_followup_execution_ledger.json",{"unclassified":{k:followup_ledger[k] for k in ordered_ids},"classified_control":{CONTROL:followup_ledger[CONTROL]},"counts":dict(sorted(total.items()))})
    write(out,"04_kyiv_28_source_coverage_matrix.json",{"unclassified":[x for x in coverage if not x["control"]],"classified_control":next(x for x in coverage if x["control"])})
    write(out,"05_kyiv_28_queue_selection_and_persistence_trace.json",{"unclassified":[x for x in traces if not x["control"]],"classified_control":next(x for x in traces if x["control"]),"global_eligible_count":len(order),"global_selected_oldest_ten":selected,"persistence_considered_in_frozen_run":0})
    write(out,"06_two_episode_cross_layer_provenance.json",cross)
    write(out,"07_kyiv_28_recovery_assessment.json",{"verdict_scope":"FROZEN_EVIDENCE_BOUNDS_ONLY_NOT_CLASSIFIER_OR_PRODUCTION_ACCEPTANCE","summary":summarized,"unclassified":[x for x in assessment if not x["control"]],"classified_control":next(x for x in assessment if x["control"])})
    with (out/"08_kyiv_28_recovery_assessment.csv").open("w",encoding="utf-8",newline="") as f:
        fields=["episode_id","alert_start","alert_end","canonical_snapshot_disposition","due_followups","marked_checked_followups","confirmed_google_execution_followups","reported_failed_google_execution_followups","candidate_any_count","candidate_stored_matching_or_classifier_count","classifier_target_count","queue_global_rank_at_frozen_run","frozen_run_parent_gate_selected","frozen_run_persistence_selected","required_source_coverage_confirmed","recovery_readiness","followup_states","supported_blockers","smallest_next_action"]
        w=csv.DictWriter(f,fieldnames=fields,lineterminator="\n");w.writeheader()
        for x in sorted(assessment,key=lambda x:x["control"]):
            w.writerow({k:json.dumps(x[k],ensure_ascii=False,sort_keys=True) if isinstance(x[k],(list,dict)) else x.get(k) for k in fields})
    write(out,"09_unresolved_evidence_and_next_actions.json",{"unclassified":nexts,"snapshot_artifact_retention_days":30,"approximate_expiry_date_utc":"2026-11-12","risk":"Accepted original 29-row canonical readback remains solely in GitHub Actions artifact; this output does not duplicate it.","prospective_collection_cannot_restore_historical_http_bytes":True,"next_separate_tasks":["Recover extant immutable historical search/source-response/transaction-ack receipts by exact run and episode if any","If historical raw evidence truly absent, design separately authorized prospective source-HTTP capture with access/retention contract; do not fabricate retrospective coverage","Perform isolated full 23-city queue integration, regression and deployment acceptance after distinct authorization"],"activation_status":"KYIV LIVE CANONICAL QUEUE INTEGRATION = PARTIAL"})
    print("AUDIT_PRIMARY_COMPLETE",json.dumps(summarized,sort_keys=True))
if __name__=="__main__": main()
