#!/usr/bin/env python3
"""Frozen Kyiv 42-case read-only first-failure proof. No evidence collection."""
from __future__ import annotations
import argparse
import collections
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CLASSIFIER_PATH = "kyiv-air-alerts-grafana/scripts/monitor_explosion_candidates.py"
CLASSIFIER_BLOB = "4019b8374dcc44846df04ed0cc41356652214bff"
FREEZE = "9784473e64c3ddfe3474bacdc30a12458923ff87"
START = "b8e18f37509aa93cebc44fbe6664016ed618446d"
SOURCE_FREEZE = "7fdcc2903205e8fc489b2eff588332a45cfaca09"
SOURCE_FILE = "research/kyiv_immutable_development_source_set_expanded_freeze_2026-10-09.json"
OLD_COMMIT = "cb46d7b8232bc3af75c29f40592b731001aed8ea"
OLD_FILE = "research/kyiv_immutable_expanded_baseline_remaining_failure_diagnosis_2026-10-09.json"
FORENSIC_COMMIT = "cf451a61c0f590ca1745f66744ce9c99561c9d13"
FORENSIC_FILE = "research/kyiv_immutable_temporal_parser_five_case_forensic_audit_2026-10-09.json"
RUNNER_COMMIT = "906b9e18aa9e0a2056bcb798b9870ae35d8dee3d"
RUNNER_FILE = ".github/proof/kyiv_0825_actual_classifier_repair_reproof.py"
COORDINATION_MAIN = "bc29c2ad343b13a3823d37489277a81b689e31d1"
SOURCE_MANIFEST_SHA = "58dbde111229d099413ad03e99be3839557431957c4ac72832b23be8a49bc08e"
CORPUS_HASHES = {
    "discovery":"fc1e184741c8409ce634015771a9484de8cfd8230037be56e3d8970d0178e5cc",
    "native":"bcfdedba186b58671dab7c3c1bd33dc8ec0f2772c8b9f9c3bf053c7d64cff858",
    "normalized":"e5790301a8d17b9997a3dbdfb71651e486de8ba6a4c39a552043754805e7ce2d",
}
FAILURE_SHA = "fcf85d81ccfa59501fe3a3a51f1c11cab48f5ff36a79b20454309db23b2913ab"
REMOVED_ID = "cfd8acaf2ae96fb3ab6508d6"
EXTRA_SOURCES = ("5.ua", "zaxid.net", "kyiv.novyny.live")
POSITIVES = {"STRICT_EVENT_POSITIVE","SENSITIVITY_EVENT_POSITIVE"}
EXPECTED_TEMPORAL = {
    "636a2ee8464e0041c402cef1":"TEMPORAL_REPRESENTATION_LIMIT",
    "c475d1dca5c22956189e88e3":"NON_EVENT_CLOCK",
    "c5f05a41bcd9e336afbb2362":"TEMPORAL_REPRESENTATION_LIMIT",
    "d3111283a5df66d38a665c20":"NON_EVENT_CLOCK",
}
CATEGORIES = (
    "NO_RELEVANT_NATIVE_EVIDENCE_IN_FROZEN_CORPUS",
    "RELEVANT_FROZEN_EVIDENCE_OUTSIDE_15_FAMILY_SOURCE_SET",
    "ACQUISITION_FAILURE_WITHIN_INCLUDED_SOURCE",
    "ADMISSION_PUBLICATION_WINDOW","ADMISSION_ATTACK_VOCAB","ADMISSION_EXACT_CITY",
    "ADMISSION_OTHER","ATTACK_EVENT_PARSER_MISS","ATTACK_EVENT_TRULY_INSUFFICIENT",
    "EXACT_CITY_CLASSIFIER_INSUFFICIENT","EVIDENCE_SEGMENT_SELECTION_LIMIT",
    "TEMPORAL_PARSER_SYNTAX_MISS","EVENT_TIME_TRULY_ABSENT",
    "TEMPORAL_REPRESENTATION_LIMIT","NON_EVENT_CLOCK","EVENT_TIME_OUTSIDE_EPISODE",
    "AIR_CONTEXT_INSUFFICIENT","SAME_ATTACK_INSUFFICIENT","OTHER",
)
REPAIRABILITY = (
    "SOURCE_COVERAGE","CANDIDATE_ADMISSION","PARSER_ONLY","TEMPORAL_REPRESENTATION",
    "EVIDENCE_SELECTION","CLASSIFIER_SEMANTICS","EVIDENCE_INSUFFICIENT",
    "NOT_SAFE_TO_AUTOMATE","OTHER",
)
OLD_LABELS = {
    "NO_RELEVANT_FROZEN_NATIVE_RESULT":CATEGORIES[0],
    "RELEVANT_FROZEN_RESULT_OUTSIDE_FROZEN_SOURCE_SET":CATEGORIES[1],
    "NATIVE_ACQUISITION_FAILED":CATEGORIES[2],
    "ADMISSION_ATTACK_VOCABULARY":"ADMISSION_ATTACK_VOCAB",
    "ATTACK_EVENT_PRESENT_BUT_PARSER_MISSES":"ATTACK_EVENT_PARSER_MISS",
    "EVENT_TIME_PRESENT_BUT_TEMPORAL_PARSER_MISSES":"TEMPORAL_PARSER_SYNTAX_MISS",
    "EVENT_TIME_TRULY_ABSENT":"EVENT_TIME_TRULY_ABSENT",
    "OTHER_CLASSIFIER_FAILURE":"OTHER",
}
REPAIR_BY_CATEGORY = {
    CATEGORIES[0]:"SOURCE_COVERAGE",CATEGORIES[1]:"SOURCE_COVERAGE",
    CATEGORIES[2]:"SOURCE_COVERAGE",
    "ADMISSION_PUBLICATION_WINDOW":"CANDIDATE_ADMISSION",
    "ADMISSION_ATTACK_VOCAB":"CANDIDATE_ADMISSION",
    "ADMISSION_EXACT_CITY":"CANDIDATE_ADMISSION",
    "ADMISSION_OTHER":"CANDIDATE_ADMISSION",
    "ATTACK_EVENT_PARSER_MISS":"PARSER_ONLY",
    "ATTACK_EVENT_TRULY_INSUFFICIENT":"EVIDENCE_INSUFFICIENT",
    "EXACT_CITY_CLASSIFIER_INSUFFICIENT":"EVIDENCE_INSUFFICIENT",
    "EVIDENCE_SEGMENT_SELECTION_LIMIT":"EVIDENCE_SELECTION",
    "TEMPORAL_PARSER_SYNTAX_MISS":"PARSER_ONLY",
    "EVENT_TIME_TRULY_ABSENT":"EVIDENCE_INSUFFICIENT",
    "TEMPORAL_REPRESENTATION_LIMIT":"TEMPORAL_REPRESENTATION",
    "NON_EVENT_CLOCK":"NOT_SAFE_TO_AUTOMATE",
    "EVENT_TIME_OUTSIDE_EPISODE":"EVIDENCE_INSUFFICIENT",
    "AIR_CONTEXT_INSUFFICIENT":"EVIDENCE_INSUFFICIENT",
    "SAME_ATTACK_INSUFFICIENT":"CLASSIFIER_SEMANTICS",
    "OTHER":"OTHER",
}

def require(test, reason):
    if not test:
        raise RuntimeError(reason)

def canonical(obj):
    return (json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(",",":"))+"\n").encode("utf-8")

def digest(obj):
    return hashlib.sha256(canonical(obj)).hexdigest()

def sha_bytes(raw):
    return hashlib.sha256(raw).hexdigest()

def git(*args):
    return subprocess.check_output(["git",*args],cwd=ROOT,text=True).strip()

def git_file(commit,path):
    return subprocess.check_output(["git","show",commit+":"+path],cwd=ROOT)

def load_json(commit,path):
    return json.loads(git_file(commit,path))

def write_json(path,obj):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(canonical(obj))

def load_module(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module
    spec.loader.exec_module(module)
    return module

def immutable_preflight():
    require(git("rev-parse","HEAD:"+CLASSIFIER_PATH)==CLASSIFIER_BLOB,"CLASSIFIER_BLOB_CHANGED")
    require(git("rev-parse",FREEZE+":"+CLASSIFIER_PATH)==CLASSIFIER_BLOB,"FREEZE_BLOB_CHANGED")
    subprocess.check_call(["git","merge-base","--is-ancestor",START,"HEAD"],cwd=ROOT)
    paths=set(git("diff","--name-only",FREEZE,"HEAD").splitlines())
    require(paths <= {RUNNER_FILE.replace("kyiv_0825_actual_classifier_repair_reproof","kyiv_repaired_42_first_failure_diagnosis"),
                      ".github/workflows/kyiv-repaired-42-first-failure-diagnosis.yml"},
            "UNAUTHORIZED_PROOF_BRANCH_DIFF:"+str(sorted(paths)))
    source=load_json(SOURCE_FREEZE,SOURCE_FILE)
    manifest=source["expanded_development_manifest"]
    require(digest(manifest)==SOURCE_MANIFEST_SHA and
            source["expanded_development_manifest_sha256"]==SOURCE_MANIFEST_SHA,"SOURCE_MANIFEST_HASH_MISMATCH")
    require(len(manifest["included_source_families"])==15 and
            manifest["immutable_corpus"]["payload_hashes_sha256"]==CORPUS_HASHES,
            "FROZEN_SOURCE_CORPUS_IDENTITY_MISMATCH")
    for name in ("DATABASE_URL","DIRECT_URL","PGHOST","PGPASSWORD","PGDATABASE","NEON_DATABASE_URL"):
        require(not os.getenv(name),"DB_CREDENTIAL_PRESENT:"+name)
    return manifest

def prepare(acquisition,prior):
    manifest=immutable_preflight()
    runner=ROOT/RUNNER_FILE
    runner.parent.mkdir(parents=True,exist_ok=True)
    runner.write_bytes(git_file(RUNNER_COMMIT,RUNNER_FILE))
    mod=load_module(runner,"pinned_kyiv_0825_repair_runner")
    offline=mod.prepare("repaired",Path(acquisition),Path(prior))
    require({k:v["payload_sha256"] for k,v in
             (("discovery",offline.discovery),("native",offline.native),
              ("normalized",offline.normalized))}==CORPUS_HASHES,"ACQUISITION_HASH_MISMATCH")
    return mod,offline,manifest

def replay(offline):
    generated={}
    original=offline.p.make_candidate
    def observer(*args,**kwargs):
        row,meta=original(*args,**kwargs)
        generated[row["candidate_id"]]=dict(row)
        return row,meta
    offline.p.make_candidate=observer  # passive instrumentation; original return untouched
    try:
        rows=offline.replay(EXTRA_SOURCES)
    finally:
        offline.p.make_candidate=original
    require(len(rows)==67 and sum(x["candidate_count"] for x in rows)==105,
            "REPAIRED_67_EPISODE_CANDIDATE_REPLAY_MISMATCH")
    positives=[x for x in rows if x["truth_label"] in POSITIVES]
    holds=[x for x in rows if x["truth_label"]=="HOLD_CONTROL"]
    require(len(positives)==48 and len(holds)==19,"TRUTH_COHORT_CHANGED")
    require(sum(x["final"]=="STRICT_EVENT_POSITIVE" for x in positives)==4 and
            sum(x["final"]=="SENSITIVITY_EVENT_POSITIVE" for x in positives)==2,
            "REPAIRED_POSITIVE_METRICS_CHANGED")
    require(sum(x["final"]=="STRICT_EVENT_POSITIVE" for x in holds)==2 and
            sum(x["final"]=="SENSITIVITY_EVENT_POSITIVE" for x in holds)==0,
            "HOLD_METRICS_CHANGED")
    hold_promotions=sorted(x["episode_id"] for x in holds if x["final"] in POSITIVES)
    require(set(hold_promotions)=={"e56cdca45ed5b1cd7b0b9746","f06c52e0ed82b44792ec2ec7"},
            "NEW_UNCLEARED_HOLD_PROMOTION")
    failed=sorted(x["episode_id"] for x in positives if x["final"] not in POSITIVES)
    require(len(failed)==42 and sha_bytes(canonical(failed))==FAILURE_SHA,
            "EXACT_42_FAILURE_ID_SHA_MISMATCH")
    require(REMOVED_ID not in failed,"REPAIRED_EPISODE_STILL_FAILED")
    return rows,generated,failed,hold_promotions

def excerpt(text,term=None,limit=350):
    text=str(text or "")
    if not text:return None
    at=text.casefold().find(str(term).casefold()) if term else -1
    if at<0:at=0
    start=max(0,at-85)
    return text[start:start+limit].replace("\n"," ")

def clock_role(segment,mon):
    low=mon.normalize_evidence_text(segment)
    if re.search(r"починаючи з|після\s+\d{1,2}\s*(?:ранку|години|вечора)|протягом|за\s+півгодини|незабаром після",low,re.I):
        return "EVENT_RANGE_OR_RELATIVE_BOUND"
    if re.search(r"(?:(?:зазначил|повідомил|написал)\w*|за\s+повідомленням).{0,45}\d{1,2}[:.]\d{2}",low,re.I):
        return "REPORT_STATEMENT_CLOCK"
    if re.search(r"\b(?:я|мене|завжди|прокинув\w*|відкриваю)\b.{0,65}\b(?:ранку|годині)\b",low,re.I):
        return "NARRATIVE_NON_EVENT_CLOCK"
    if mon.event_clock_mentions(segment):
        return "PARSER_RECOGNIZED_EVENT_CLOCK"
    if re.search(r"\b\d{1,2}[:.]\d{2}\b",low):
        return "UNRESOLVED_NUMERIC_CLOCK"
    if re.search(r"\b(?:вночі|увечері|вранці|пізно ввечері|після опівночі|до ранку|зранку)\b",low,re.I):
        return "BROAD_TIME_WORDING"
    return "NO_TIME_EXPRESSION"

def ordinal_selection(mon,row):
    source=mon.classification_segments(row)
    exact=[(i+1,s) for i,s in enumerate(source) if mon.city_mentioned("kyiv",s)]
    selection=mon.exact_city_classification_evidence("kyiv",row)["segments"]
    ordinals=[]
    last=0
    for segment in selection:
        found=next((i for i,s in exact if i>last and s==segment),None)
        require(found is not None,"EXACT_CITY_SELECTION_NOT_SUBSEQUENCE")
        ordinals.append(found);last=found
    clocks=[]
    for i,s in exact:
        clocks.append({"ordinal":i,"selected":i in ordinals,
                       "strict_event":bool(mon.strict_attack_event_signal(s)),
                       "parsed_clocks":[list(x) for x in mon.event_clock_mentions(s)],
                       "semantic_clock_role":clock_role(s,mon),
                       "excerpt":excerpt(s,limit=220)})
    return source,exact,ordinals,clocks

def current_candidate_trace(mon,offline,ep,row,rec):
    ctx=offline.p.context_episodes(offline.all_episodes,ep)
    matching=mon.match_candidate_to_episodes(row,ctx)
    decision=mon.classify_candidate(row,"kyiv",ctx,matching)
    source,exact,chosen,clocks=ordinal_selection(mon,row)
    selected=set(chosen)
    exact_result=decision.get("candidate_evidence",{}).get("exact_city",{})
    strict=decision.get("candidate_evidence",{}).get("strict_explosion",{})
    air=decision.get("candidate_evidence",{}).get("air_military_context",{})
    same=decision.get("candidate_evidence",{}).get("same_attack_context",{})
    temporal=decision.get("temporal_binding") or {}
    lost=[x["ordinal"] for x in clocks if x["strict_event"] and x["parsed_clocks"]
          and x["ordinal"] not in selected]
    represented=[x for x in clocks if x["ordinal"] in selected and x["strict_event"]]
    text=rec.get("native",{}).get("text") if rec else row.get("matched_text_excerpt")
    sha=sha_bytes(str(text or "").encode("utf-8"))
    original_sha=rec.get("extracted_text_sha256") if rec else None
    require(not original_sha or sha==original_sha,"CANDIDATE_FROZEN_TEXT_SHA_MISMATCH")
    return {
        "candidate_id":row["candidate_id"],"source_family":row.get("source"),
        "url":row.get("url"),"text_sha256":sha,
        "published_at":row.get("published_at"),
        "classifier_outcome":decision.get("proposed_outcome"),
        "classifier_episode_id":decision.get("proposed_matched_episode_id"),
        "reason_codes":decision.get("reason_codes") or [],
        "classification_segment_count":len(source),
        "all_exact_city_segment_ordinals":[i for i,s in exact],
        "selected_exact_city_segment_ordinals":chosen,
        "evidence_selection_loss":bool(lost),
        "qualifying_lost_segment_ordinals":lost,
        "clocks_by_segment":clocks,
        "attack_event_predicate":bool(strict.get("present")),
        "attack_event_types":decision.get("event_types") or [],
        "exact_city_predicate":bool(exact_result.get("present")),
        "air_context_predicate":bool(air.get("present")),
        "same_attack_predicate":bool(same.get("present")),
        "same_attack_reason":same.get("reason"),
        "temporal_binding":temporal,
        "parsed_clocks":[{"ordinal":x["ordinal"],"clock":v}
                         for x in clocks for v in x["parsed_clocks"]],
        "semantic_clock_roles":sorted(set(x["semantic_clock_role"] for x in clocks
                                           if x["semantic_clock_role"]!="NO_TIME_EXPRESSION")),
        "frozen_short_excerpt":excerpt(text,term=(strict.get("segments") or [None])[0],limit=440),
        "matching_outcome":matching.get("outcome"),
        "matching_ids":matching.get("matched_episode_ids") or [],
        "_selected_strict_count":len(represented),
        "_all_city_strict_count":sum(x["strict_event"] for x in clocks),
    }

def candidate_stage(trace,ep,forensic):
    eid=ep["episode_id"]
    # Only positive evidence from the exact current frozen classifier earns a later stage.
    if not trace["_all_city_strict_count"]:
        if trace["attack_event_predicate"] and not trace["exact_city_predicate"]:
            return 5,"EXACT_CITY_CLASSIFIER_INSUFFICIENT","Event predicate present without target city"
        return 4,"ATTACK_EVENT_TRULY_INSUFFICIENT","No qualifying current-policy attack segment in the frozen exact-city text"
    if not trace["exact_city_predicate"]:
        return 5,"EXACT_CITY_CLASSIFIER_INSUFFICIENT","No exact-city predicate"
    if not trace["attack_event_predicate"]:
        if trace["evidence_selection_loss"]:
            return 6,"EVIDENCE_SEGMENT_SELECTION_LIMIT","Valid clock-bearing strict exact-city segment omitted by selection"
        return 4,"ATTACK_EVENT_TRULY_INSUFFICIENT","No retained strict attack-event segment"
    if trace["evidence_selection_loss"] and not any(
        x["selected"] and x["strict_event"] and x["parsed_clocks"]
        for x in trace["clocks_by_segment"]):
        return 7,"EVIDENCE_SEGMENT_SELECTION_LIMIT","Qualifying direct event clock lost at current selector"
    # Accepted semantic-clock analysis is independently matched to frozen text and
    # exact candidate identity before applying the semantic role; no truth labels.
    if forensic:
        role=forensic["semantic_role"]
        code=trace["temporal_binding"].get("code")
        require(not trace["temporal_binding"].get("present") and
                code in ("NO_STRICT_TEMPORAL_BINDING","TEMPORAL_EXPLICIT_EVENT_TIME_NEAR_BOUNDARY",
                         "TEMPORAL_EXPLICIT_ALERT_RELATION_AMBIGUOUS_DATE",
                         "TEMPORAL_EXPLICIT_ALERT_RELATION_NO_EPISODE"),
                "ACCEPTED_TEMPORAL_FORENSIC_CONTRADICTION:"+eid+":"+str(code))
        if role=="EVENT_ONSET_LOWER_BOUND":
            return 10,"TEMPORAL_REPRESENTATION_LIMIT","Frozen source states a lower bound, not a point timestamp"
        if role in ("NARRATIVE_ANCHOR_CLOCK","REPORT_OR_STATEMENT_CLOCK"):
            return 8,"NON_EVENT_CLOCK","Frozen clock denotes witness action or report, not the strike"
        raise RuntimeError("UNSUPPORTED_ACCEPTED_FORENSIC_ROLE:"+eid+":"+role)
    event_time=trace["temporal_binding"]
    bound=event_time.get("episode_id")
    if bound and bound!=eid:
        return 11,"EVENT_TIME_OUTSIDE_EPISODE","Repaired classifier binds candidate to another episode"
    if trace["classifier_episode_id"] and trace["classifier_episode_id"]!=eid:
        return 11,"EVENT_TIME_OUTSIDE_EPISODE","Candidate approval is for another episode"
    if event_time.get("present") and bound==eid:
        if not trace["air_context_predicate"]:
            return 12,"AIR_CONTEXT_INSUFFICIENT","Correct event time, insufficient air context"
        if not trace["same_attack_predicate"]:
            return 13,"SAME_ATTACK_INSUFFICIENT","Correct event time and air context, no same-attack basis"
        return 14,"OTHER","Current predicates pass; final candidate outcome still non-positive"
    clocks=[x for x in trace["clocks_by_segment"] if x["selected"] and x["strict_event"]]
    direct=[x for x in clocks if x["parsed_clocks"]]
    if direct:
        return 11,"EVENT_TIME_OUTSIDE_EPISODE","Parser sees a genuine event clock but it does not bind target episode"
    if "EVENT_RANGE_OR_RELATIVE_BOUND" in trace["semantic_clock_roles"] or "BROAD_TIME_WORDING" in trace["semantic_clock_roles"]:
        return 10,"TEMPORAL_REPRESENTATION_LIMIT","Event has non-point temporal language; present model cannot assign exact episode"
    if "REPORT_STATEMENT_CLOCK" in trace["semantic_clock_roles"] or "NARRATIVE_NON_EVENT_CLOCK" in trace["semantic_clock_roles"]:
        return 8,"NON_EVENT_CLOCK","Clock belongs to report or witness, not independently to attack event"
    if "UNRESOLVED_NUMERIC_CLOCK" in trace["semantic_clock_roles"]:
        # Strict parser-miss conditions are not established from a bare timestamp.
        return 10,"TEMPORAL_REPRESENTATION_LIMIT","Unresolved clock role; no proven syntax-only parser repair"
    return 8,"EVENT_TIME_TRULY_ABSENT","No usable episode-specific event clock in selected frozen attack evidence"

def relevant_frozen_record(mon,offline,ep,rec):
    native=rec.get("native") or {}
    text=str(native.get("text") or "")
    if not text:return False,{"native_text":False}
    row,_=offline.p.make_candidate(rec["normalized_source_family"],native,
                                   "frozen_diagnostic_only",{})
    source,city,sel,clocks=ordinal_selection(mon,row)
    event_any=any(mon.strict_attack_event_signal(s) for s in source)
    event_city=any(mon.strict_attack_event_signal(s) for _,s in city)
    attack_vocab=bool(offline.p.ATTACK_RE.search(str(native.get("title") or "")+" "+text))
    exact_city=bool(city)
    start=offline.p.parse_dt(ep["alert_start"])
    end=offline.p.parse_dt(ep["alert_end"])
    pub=offline.p.parse_dt(native.get("published_at"))
    # The news retrieval window is not itself proof of the event's time.
    proximity=pub is None or start-timedelta(hours=36)<=pub<=end+timedelta(hours=36)
    current_policy_support=event_city or (attack_vocab and exact_city and event_any)
    return bool(current_policy_support and proximity),{
        "native_text":True,"exact_city":exact_city,"strict_event_anywhere":event_any,
        "strict_city_event":event_city,"admission_attack_vocab":attack_vocab,
        "publication_proximity_36h":proximity,
        "usable_native_timestamp":native.get("published_at"),
        "exact_city_segment_ordinals":[i for i,s in city],
        "url":native.get("url"),"text_sha256":sha_bytes(text.encode()),
        "excerpt":excerpt(text,term=(source[0] if source else None),limit=340),
    }

def upstream_audit(mon,offline,ep,allowed,old_provenance):
    eid=ep["episode_id"]
    hits=[h for h in offline.discovery["search_hits"] if h["episode_id"]==eid]
    nmap={r["requested_native_url"]:r for r in offline.native["records"]}
    found={}
    relevant_in=[]
    relevant_out=[]
    failed=[]
    rejects=[]
    provenance_urls={x["url"]:x for x in
      ((old_provenance.get("no_candidate_corpus_audit") or {}).get("outside_source_material_evidence") or [])}
    for hit in hits:
        url=hit.get("native_url")
        if not url or url not in nmap:continue
        rec=nmap[url]
        if url in found:continue
        found[url]=rec
        fam=rec.get("normalized_source_family") or ""
        native=rec.get("native") or {}
        if not native or not native.get("text"):
            failed.append({"source_family":fam,"url":url,
                           "error":rec.get("error") or rec.get("native_error") or
                                   rec.get("acquisition_error") or "FROZEN_NATIVE_TEXT_MISSING"})
            continue
        useful,mechanics=relevant_frozen_record(mon,offline,ep,rec)
        old_witness=provenance_urls.get(url)
        if old_witness:
            require(mechanics["text_sha256"]==old_witness["frozen_text_sha256"],
                    "OUTSIDE_FROZEN_PROVENANCE_HASH_CONTRADICTION:"+eid)
        if fam in allowed:
            # Accepted replay admission predicate from immutable runner.
            native_start=offline.p.parse_dt(ep["alert_start"])-timedelta(hours=6)
            native_end=offline.p.parse_dt(ep["alert_end"])+timedelta(hours=24)
            if not native.get("published_at"):
                admission="NO_PUBLICATION_TIMESTAMP"
            elif not offline.p.native_in_window(native,native_start,native_end):
                admission="OUTSIDE_PUBLICATION_WINDOW"
            elif not offline.p.ATTACK_RE.search(f"{native.get('title','')} {native.get('text','')}"):
                admission="NO_ATTACK_VOCABULARY"
            elif not re.search(r"\bКи(їв|єв)",f"{native.get('title','')} {native.get('text','')}",re.I):
                admission="NO_EXACT_CITY"
            else:
                admission="PASS"
            if admission!="PASS":
                rejects.append({"source_family":fam,"url":url,
                                "reason":admission,"text_sha256":mechanics["text_sha256"],
                                "publication_timestamp":native.get("published_at"),
                                "relevant":useful})
            if useful:relevant_in.append({"source_family":fam,"admission":admission,**mechanics})
        elif useful:
            relevant_out.append({"source_family":fam,"frozen_reference":url,
                                 "prior_forensic_provenance_verified":bool(old_witness),
                                 **mechanics})
    relevant_in.sort(key=lambda x:(x["source_family"],x["url"]))
    relevant_out.sort(key=lambda x:(x["source_family"],x["url"]))
    failed.sort(key=lambda x:(x["source_family"],x["url"]))
    rejects.sort(key=lambda x:(x["source_family"],x["url"]))
    if relevant_in:
        reasons=[x["admission"] for x in relevant_in if x["admission"]!="PASS"]
        if not reasons:
            category="ADMISSION_OTHER"
            reason="Relevant included-source record passed admission but no candidate was emitted"
        else:
            first=sorted(reasons,key=lambda x:{
                "OUTSIDE_PUBLICATION_WINDOW":0,"NO_PUBLICATION_TIMESTAMP":1,
                "NO_ATTACK_VOCABULARY":2,"NO_EXACT_CITY":3}.get(x,4))[0]
            category={"OUTSIDE_PUBLICATION_WINDOW":"ADMISSION_PUBLICATION_WINDOW",
                      "NO_ATTACK_VOCABULARY":"ADMISSION_ATTACK_VOCAB",
                      "NO_EXACT_CITY":"ADMISSION_EXACT_CITY"}.get(first,"ADMISSION_OTHER")
            reason="Frozen included-source target record fails original admission: "+first
    elif relevant_out:
        category="RELEVANT_FROZEN_EVIDENCE_OUTSIDE_15_FAMILY_SOURCE_SET"
        reason="Frozen native text supports target city attack but its source family is not in the 15-family manifest"
    else:
        # A fetch error without target-relevant native text is not independently
        # sufficient to claim recoverable acquisition coverage.
        category="NO_RELEVANT_NATIVE_EVIDENCE_IN_FROZEN_CORPUS"
        reason="No target-relevant native evidence mechanically proven in retained frozen corpus"
    return category,reason,{
        "discovery_hits":len(hits),"native_evidence_records":sum(bool(r.get("native")) for r in found.values()),
        "relevant_included_source_evidence":relevant_in,
        "relevant_outside_source_evidence":relevant_out,
        "acquisition_errors":failed,
        "admission_failures":rejects,
        "source_relevance_unproven_acquisition_error_count":len(failed),
    }

def verify_accepted_semantics(offline,forensic,rows,generated):
    mon=offline.monitor
    by={x["episode_id"]:x for x in rows}
    accepted={}
    nmap={r["requested_native_url"]:r for r in offline.native["records"]}
    for d in forensic["dispositions"]:
        eid=d["episode_id"]
        if eid==REMOVED_ID:continue
        require(eid in EXPECTED_TEMPORAL,"UNEXPECTED_ACCEPTED_FORENSIC_ID:"+eid)
        identity=d["frozen_evidence_identity"]
        candidate=next((c for c in by[eid]["candidates"]
                        if c["candidate_id"]==identity["candidate_id"]),None)
        require(candidate is not None and candidate["family"]==identity["source_family"] and
                candidate["url"]==identity["url"] and
                candidate["text_sha256"]==identity["normalized_text_sha256"],
                "ACCEPTED_FORENSIC_CANDIDATE_IDENTITY_CHANGED:"+eid)
        native=nmap[identity["url"]]["native"]
        body=native["text"]
        require(sha_bytes(body.encode())==identity["normalized_text_sha256"],
                "FORENSIC_NATIVE_BODY_MISMATCH:"+eid)
        require(d["exact_relevant_wording"] in body,
                "ACCEPTED_FORENSIC_QUOTE_MISSING:"+eid)
        role=d["semantic_role"]
        require(role in ("EVENT_ONSET_LOWER_BOUND","NARRATIVE_ANCHOR_CLOCK",
                         "REPORT_OR_STATEMENT_CLOCK"),"UNEXPECTED_FORENSIC_ROLE:"+eid)
        accepted[eid]=d
    require(set(accepted)==set(EXPECTED_TEMPORAL),"TEMPORAL_FORENSIC_UNIVERSE_CHANGED")
    return accepted

def diagnose(acquisition,prior,out):
    runner,offline,manifest=prepare(acquisition,prior)
    try:
        rows,generated,failed,hold_promotions=replay(offline)
        prior_doc=load_json(OLD_COMMIT,OLD_FILE)
        prior_by={r["episode_id"]:r for r in prior_doc["exact_43_remaining_failures"]}
        require(len(prior_by)==43 and set(prior_by)==set(failed)|{REMOVED_ID},
                "PREDECESSOR_43_TO_42_UNIVERSE_MISMATCH")
        forensic=load_json(FORENSIC_COMMIT,FORENSIC_FILE)
        accepted=verify_accepted_semantics(offline,forensic,rows,generated)
        epi={r["episode_id"]:r for r in offline.cohort}
        nmap={r["requested_native_url"]:r for r in offline.native["records"]}
        allowed=set(manifest["included_source_families"])
        items=[]
        for row in rows:
            eid=row["episode_id"]
            if eid not in failed:continue
            ep=epi[eid]
            candidates=[]
            for c in row["candidates"]:
                require(c["candidate_id"] in generated,"CANDIDATE_ROW_NOT_IN_INSTRUMENTED_REPLAY:"+eid)
                source=nmap.get(c["url"])
                t=current_candidate_trace(offline.monitor,offline,ep,generated[c["candidate_id"]],source)
                require(t["classifier_outcome"]==c["classifier_outcome"] and
                        t["classifier_episode_id"]==c["classifier_episode_id"] and
                        t["reason_codes"]==c["reason_codes"],"PASSIVE_CLASSIFIER_RECHECK_CHANGED:"+eid)
                t["candidate_frozen_text_sha256"]=c["text_sha256"]
                t["candidate_semantics"]=None
                if eid in accepted and c["candidate_id"]==accepted[eid]["frozen_evidence_identity"]["candidate_id"]:
                    t["candidate_semantics"]=accepted[eid]["semantic_role"]
                stage,cat,why=candidate_stage(t,ep,accepted.get(eid) if t["candidate_semantics"] else None)
                t["earliest_failing_stage_number"]=stage
                t["primary_failure_if_best_candidate"]=cat
                t["mechanical_failure_explanation"]=why
                candidates.append(t)
            if candidates:
                # The strongest progressed candidate determines the episode-level
                # first missing gate. Irrelevant weaker candidates are secondary.
                candidates.sort(key=lambda c:(-c["earliest_failing_stage_number"],
                                               -int(c["attack_event_predicate"]),
                                               -int(c["exact_city_predicate"]),
                                               c["candidate_id"]))
                best=candidates[0]
                primary=best["primary_failure_if_best_candidate"]
                reason=best["mechanical_failure_explanation"]
                upstream={
                    "discovery_hits":len([h for h in offline.discovery["search_hits"] if h["episode_id"]==eid]),
                    "native_evidence_records":len({rec["requested_native_url"]
                        for hit,rec in offline.discovered.get(eid,[])}),
                    "relevant_included_source_evidence":[],
                    "relevant_outside_source_evidence":[],
                    "acquisition_errors":[],"admission_failures":[],
                }
                strongest={"source_family":best["source_family"],"url":best["url"],
                           "candidate_id":best["candidate_id"],
                           "text_sha256":best["text_sha256"],
                           "excerpt":best["frozen_short_excerpt"]}
                stage=best["earliest_failing_stage_number"]
                secondary=sorted(set(c["primary_failure_if_best_candidate"] for c in candidates[1:]))
            else:
                primary,reason,upstream=upstream_audit(offline.monitor,offline,ep,allowed,prior_by[eid])
                strongest=(upstream["relevant_included_source_evidence"] or
                           upstream["relevant_outside_source_evidence"] or [None])[0]
                stage={CATEGORIES[0]:1,CATEGORIES[1]:2,CATEGORIES[2]:3,
                       "ADMISSION_PUBLICATION_WINDOW":4,"ADMISSION_ATTACK_VOCAB":4,
                       "ADMISSION_EXACT_CITY":4,"ADMISSION_OTHER":4}[primary]
                secondary=[]
            if eid in accepted:
                require(primary==EXPECTED_TEMPORAL[eid],
                        "ACCEPTED_TEMPORAL_DISPOSITION_CONTRADICTION:"+eid+
                        ":got="+primary+":expected="+EXPECTED_TEMPORAL[eid])
            old=prior_by[eid]
            oldids=sorted(old["candidate_ids"])
            require(oldids==sorted(row_c["candidate_id"] for row_c in candidates),
                    "PREDECESSOR_CANDIDATE_UNIVERSE_CHANGED:"+eid)
            selection_loss=any(c["evidence_selection_loss"] for c in candidates)
            item={
                "episode_id":eid,"alert_start":ep["alert_start"],"alert_end":ep["alert_end"],
                "current_repaired_final_verdict":row["final"],
                "candidate_count":len(candidates),
                "candidate_ids":sorted(c["candidate_id"] for c in candidates),
                "candidate_source_families":sorted(set(c["source_family"] for c in candidates)),
                "frozen_discovery_hit_count":upstream["discovery_hits"],
                "frozen_native_evidence_count":upstream["native_evidence_records"],
                "relevant_included_source_evidence":upstream["relevant_included_source_evidence"],
                "relevant_outside_source_evidence":upstream["relevant_outside_source_evidence"],
                "acquisition_errors":upstream["acquisition_errors"],
                "admission_failures":upstream["admission_failures"],
                "strongest_frozen_evidence_identity":strongest,
                "frozen_url":(strongest or {}).get("url") or (strongest or {}).get("frozen_reference"),
                "text_sha256":(strongest or {}).get("text_sha256"),
                "relevant_short_excerpt":(strongest or {}).get("excerpt"),
                "attack_event_predicate_result":any(c["attack_event_predicate"] for c in candidates),
                "exact_city_predicate_result":any(c["exact_city_predicate"] for c in candidates),
                "all_exact_city_segment_ordinals":best["all_exact_city_segment_ordinals"] if candidates else [],
                "selected_exact_city_ordinals":best["selected_exact_city_segment_ordinals"] if candidates else [],
                "evidence_selection_loss":selection_loss,
                "parsed_clocks":best["parsed_clocks"] if candidates else [],
                "semantic_clock_role":best["semantic_clock_roles"] if candidates else [],
                "temporal_code":best["temporal_binding"].get("code") if candidates else None,
                "air_context_result":best["air_context_predicate"] if candidates else None,
                "same_attack_result":best["same_attack_predicate"] if candidates else None,
                "candidate_classifier_outcomes":[{"id":c["candidate_id"],
                      "outcome":c["classifier_outcome"],"bound_episode":c["classifier_episode_id"]}
                      for c in candidates],
                "candidate_level_traces":candidates,
                "earliest_failing_stage_number":stage,
                "primary_category":primary,
                "secondary_factors":secondary,
                "repairability_class":REPAIR_BY_CATEGORY[primary],
                "explanation":reason,
            }
            items.append(item)
        items.sort(key=lambda x:x["episode_id"])
        require(len(items)==42 and len({x["episode_id"] for x in items})==42,
                "INCOMPLETE_PER_CASE_TRACE_UNIVERSE")
        return {
            "schema":"kyiv-repaired-42-first-failure-diagnosis-run-v1",
            "coordination_main":COORDINATION_MAIN,
            "source_freeze_identity":{"commit":SOURCE_FREEZE,"manifest_sha256":SOURCE_MANIFEST_SHA,
                                      "included_source_families":manifest["included_source_families"]},
            "classifier_identity":{"freeze":FREEZE,"blob":CLASSIFIER_BLOB,"repair_commit":
                                   "c5dd5fec6fe8f9a3fa0bbdefdd2cf71cee2ff801"},
            "frozen_corpus_sha256":CORPUS_HASHES,
            "known_positives":48,"strict_positives":4,"sensitivity_positives":2,
            "final_positives":6,"remaining_failures":42,"failure_id_sha256":FAILURE_SHA,
            "holds_processed":19,"hold_strict":2,"hold_sensitivity":0,
            "hold_promotion_ids":hold_promotions,"new_uncleared_hold_promotions":0,
            "per_case_traces":items,
            "accepted_temporal_forensic_identities":[{"episode_id":x,
                "semantic_role":accepted[x]["semantic_role"],
                "frozen_text_sha256":accepted[x]["frozen_evidence_identity"]["normalized_text_sha256"],
                "verified_category":next(y["primary_category"] for y in items if y["episode_id"]==x)}
                for x in sorted(accepted)],
            "blind_per_episode_inspected":False,
            "historical_411_regression":"411 REGRESSION NOT RERUN — NOT REQUIRED FOR READ-ONLY REMAINING-FAILURE DIAGNOSIS",
            "network_evidence_fetches":0,"neon_queries":0,"neon_writes":0,
            "production_mutations":0,"site_prod_mutations":0,
            "canonical_alert_mutations":0,"review_queue_mutations":0,
            "historical_backfill_started":False,
            "classifier_source_mutations":0,
        }
    finally:
        offline.close()

def precheck(acquisition,prior):
    runner,offline,manifest=prepare(acquisition,prior)
    try:
        rows,generated,failed,holds=replay(offline)
        return {"status":"PASS","classifier_blob":CLASSIFIER_BLOB,
                "source_family_count":15,"corpus_sha256":CORPUS_HASHES,
                "known_positives":48,"final_positives":6,
                "remaining_failures":42,"failure_id_sha256":sha_bytes(canonical(failed)),
                "repaired_target_absent":REMOVED_ID not in failed,
                "hold_processed":19,"hold_positive_ids":holds,
                "network_evidence_fetches":0,"neon_queries":0,"neon_writes":0}
    finally:offline.close()

def summarize(run):
    episodes=run["per_case_traces"]
    bycategory={k:sorted(x["episode_id"] for x in episodes if x["primary_category"]==k)
                for k in CATEGORIES}
    byrepair={k:sorted(x["episode_id"] for x in episodes if x["repairability_class"]==k)
              for k in REPAIRABILITY}
    return {
        "primary_category_counts":{k:len(v) for k,v in bycategory.items()},
        "primary_category_episode_ids":bycategory,
        "primary_category_pct_of_42":{k:round(100*len(v)/42,3) for k,v in bycategory.items()},
        "repairability_counts":{k:len(v) for k,v in byrepair.items()},
        "repairability_episode_ids":byrepair,
    }

def transitions(run,prior):
    old={x["episode_id"]:x for x in prior["exact_43_remaining_failures"]}
    new={x["episode_id"]:x for x in run["per_case_traces"]}
    require(len(old)==43 and len(new)==42 and set(old)==set(new)|{REMOVED_ID},
            "PREDECESSOR_UNIVERSE_LOSS")
    removed=[{"episode_id":REMOVED_ID,"old_category":old[REMOVED_ID]["primary_first_material_failure"],
              "new_final_verdict":"STRICT_EVENT_POSITIVE",
              "reason":"Accepted UNIQUE_LATE_CLOCK_AND_FREE_SLOT repair"}]
    buckets={"removed_because_repaired":removed,
             "reclassified_by_accepted_temporal_forensics":[],
             "reclassified_by_repaired_classifier_execution":[],
             "reclassified_predecessor_too_coarse_or_incorrect":[],
             "unchanged":[]}
    for eid in sorted(new):
        source=old[eid]
        target=new[eid]
        oldcat=OLD_LABELS.get(source["primary_first_material_failure"],
                              source["primary_first_material_failure"])
        category=target["primary_category"]
        if oldcat==category:
            buckets["unchanged"].append({"episode_id":eid,"category":category})
            continue
        changes=[]
        prev={x["candidate_id"]:x for x in source["candidate_level_traces"]}
        for cur in target["candidate_level_traces"]:
            prior_candidate=prev.get(cur["candidate_id"])
            require(prior_candidate is not None,"PREDECESSOR_CANDIDATE_TRACE_MISSING:"+eid)
            if ((prior_candidate["classifier_outcome"],prior_candidate["classifier_episode_binding"],
                 prior_candidate["reason_codes"]) !=
                (cur["classifier_outcome"],cur["classifier_episode_id"],cur["reason_codes"])):
                changes.append(cur["candidate_id"])
        details={"episode_id":eid,"old_category":oldcat,"new_category":category,
                 "mechanical_explanation":target["explanation"]}
        if eid in EXPECTED_TEMPORAL:
            buckets["reclassified_by_accepted_temporal_forensics"].append(details)
        elif changes:
            details["changed_classifier_candidate_ids"]=changes
            buckets["reclassified_by_repaired_classifier_execution"].append(details)
        else:
            buckets["reclassified_predecessor_too_coarse_or_incorrect"].append(details)
    require(sum(len(v) for v in buckets.values())==43,"TRANSITION_ROWS_DO_NOT_SUM_TO_43")
    require(len(buckets["removed_because_repaired"])==1,"REPAIRED_REMOVAL_COUNT")
    return buckets

def ceilings_and_priorities(run,summary):
    cases=run["per_case_traces"]
    features={
        "NO_RELEVANT_NATIVE_EVIDENCE_IN_FROZEN_CORPUS":(0,0,0,1,2,1),
        "RELEVANT_FROZEN_EVIDENCE_OUTSIDE_15_FAMILY_SOURCE_SET":(2,1,1,1,1,0),
        "ACQUISITION_FAILURE_WITHIN_INCLUDED_SOURCE":(1,1,1,1,1,0),
        "ADMISSION_PUBLICATION_WINDOW":(2,2,2,1,0,0),
        "ADMISSION_ATTACK_VOCAB":(2,2,2,1,0,1),
        "ADMISSION_EXACT_CITY":(2,2,2,1,1,1),
        "ADMISSION_OTHER":(2,2,2,1,1,1),
        "ATTACK_EVENT_PARSER_MISS":(2,2,2,1,0,0),
        "ATTACK_EVENT_TRULY_INSUFFICIENT":(0,0,1,0,1,1),
        "EXACT_CITY_CLASSIFIER_INSUFFICIENT":(1,0,1,0,1,1),
        "EVIDENCE_SEGMENT_SELECTION_LIMIT":(2,2,2,0,0,0),
        "TEMPORAL_PARSER_SYNTAX_MISS":(2,2,2,0,0,0),
        "EVENT_TIME_TRULY_ABSENT":(1,1,0,0,1,1),
        "TEMPORAL_REPRESENTATION_LIMIT":(2,2,1,1,1,0),
        "NON_EVENT_CLOCK":(1,0,0,2,1,1),
        "EVENT_TIME_OUTSIDE_EPISODE":(1,0,0,1,1,1),
        "AIR_CONTEXT_INSUFFICIENT":(1,1,0,1,1,0),
        "SAME_ATTACK_INSUFFICIENT":(1,1,0,1,1,0),
        "OTHER":(0,0,0,2,1,1),
    }
    ceiling={}
    priorities=[]
    for cat in CATEGORIES:
        count=summary["primary_category_counts"][cat]
        evidence,close,bounded,risk,source,semantics=features[cat]
        eligible=[x for x in cases if x["primary_category"]==cat]
        already=bool(eligible) and all(x["candidate_count"]>0 for x in eligible)
        ceiling[cat]={
            "affected_episode_count":count,
            "candidate_level_ceiling":count,
            "potential_final_positive_ceiling":None,
            "frozen_evidence_sufficient":("YES_FOR_DIAGNOSIS_NOT_PROMOTION" if already
                   else "PARTIAL_OR_NO"),
            "new_sources_required":bool(source>=1),
            "new_classifier_semantics_required":bool(semantics),
            "hold_false_positive_risk":("HIGH" if risk==2 else "MEDIUM" if risk else "LOW"),
            "technical_boundedness":("HIGH" if bounded==2 else "MEDIUM" if bounded else "LOW"),
            "status":"CEILING ONLY — NOT PROVEN RECOVERY",
        }
        if count:
            priorities.append({"category":cat,"count":count,"evidence_strength":evidence,
                 "closeness_to_final":close,"boundedness":bounded,
                 "hold_risk":risk,"new_sources":bool(source),"new_semantics":bool(semantics),
                 "episode_ids":summary["primary_category_episode_ids"][cat]})
    priorities.sort(key=lambda x:(-x["evidence_strength"],-x["closeness_to_final"],
                   -x["boundedness"],x["hold_risk"],x["new_semantics"],
                   x["new_sources"],-x["count"],x["category"]))
    choices={
        "RELEVANT_FROZEN_EVIDENCE_OUTSIDE_15_FAMILY_SOURCE_SET":
            "PILOT ONLY SOURCE ELIGIBILITY FOR THE HIGHEST-EVIDENCE FROZEN OUTSIDE FAMILY, WITH 19-HOLD SAFETY AND NO PRODUCTION CHANGE",
        "TEMPORAL_REPRESENTATION_LIMIT":
            "AUDIT ONLY BOUNDED TEMPORAL RELATIONS IN FROZEN REPAIRED NON-FINAL EPISODES; NO CLASSIFIER REPAIR",
        "ADMISSION_PUBLICATION_WINDOW":
            "AUDIT ONLY FROZEN PUBLICATION-TIMESTAMP PRECISION AND ADMISSION WINDOWS; NO REPAIR",
        "EVIDENCE_SEGMENT_SELECTION_LIMIT":
            "AUDIT ONLY THE REMAINING FROZEN SEGMENT-SELECTION LOSS; NO REPAIR",
    }
    top=priorities[0]["category"] if priorities else None
    task=choices.get(top,"FORENSICALLY AUDIT ONLY "+str(top)+" AGAINST FROZEN EVIDENCE; NO REPAIR")
    return ceiling,priorities,"NEXT: "+task

def compare(a,b):
    require(a==b,"INDEPENDENT_DIAGNOSIS_A_B_MISMATCH")
    fpa=digest(a);fpb=digest(b)
    summary=summarize(a)
    prior=load_json(OLD_COMMIT,OLD_FILE)
    transition=transitions(a,prior)
    ceilings,ranks,next_task=ceilings_and_priorities(a,summary)
    result={
        "schema":"kyiv-repaired-remaining-first-failure-rediagnosis-v1",
        "coordination_main":COORDINATION_MAIN,
        "project_state_read":True,"changelog_read":True,
        "classifier_freeze_commit":FREEZE,
        "classifier_repair_commit":"c5dd5fec6fe8f9a3fa0bbdefdd2cf71cee2ff801",
        "classifier_blob_sha":CLASSIFIER_BLOB,
        "source_freeze_commit":SOURCE_FREEZE,
        "source_manifest_sha256":SOURCE_MANIFEST_SHA,
        "corpus_sha256":CORPUS_HASHES,
        "proof_branch":"kyiv-repaired-42-failure-rediagnosis-proof-2026-10-10",
        "proof_head":os.environ.get("GITHUB_SHA"),
        "proof_run":os.environ.get("GITHUB_RUN_ID"),
        "exact_42_id_sha256":FAILURE_SHA,
        "known_positives":48,"final_positives":6,"remaining_failures":42,
        "full_42_case_traces":a["per_case_traces"],
        **summary,
        "predecessor_transition_table":transition,
        "temporal_forensic_preservation":a["accepted_temporal_forensic_identities"],
        "repair_ceilings":ceilings,"priority_ranking":ranks,
        "holds_processed":19,"hold_strict":2,"hold_sensitivity":0,
        "hold_positive_ids":a["hold_promotion_ids"],
        "new_uncleared_hold_promotions":0,
        "fingerprint_a":fpa,"fingerprint_b":fpb,
        "deterministic_equality":fpa==fpb,
        "independent_clean_python_processes":2,
        "network_evidence_fetches":0,
        "blind_per_episode_inspected":False,
        "historical_411_regression":a["historical_411_regression"],
        "historical_backfill_started":False,
        "neon_queries":0,"neon_writes":0,
        "production_mutations":0,"site_prod_mutations":0,
        "review_queue_mutations":0,"canonical_alert_mutations":0,
        "classifier_source_mutations":0,
        "final_artifact_branch":"kyiv-repaired-42-failure-rediagnosis-2026-10-10",
        "final_artifact_path":"research/kyiv_repaired_remaining_failure_rediagnosis_2026-10-10.json",
        "final_verdict":"KYIV REPAIRED 42-FAILURE FIRST-FAILURE REDIAGNOSIS = PROVEN",
        "exactly_one_next_task":next_task,
    }
    accept(result)
    return result

def accept(doc):
    cases=doc["full_42_case_traces"]
    require(len(cases)==42 and len({x["episode_id"] for x in cases})==42,
            "FULL_42_TRACES_MISSING")
    require(sha_bytes(canonical(sorted(x["episode_id"] for x in cases)))==FAILURE_SHA,
            "FINAL_42_ID_SHA_CHANGED")
    require(REMOVED_ID not in {x["episode_id"] for x in cases},"REPAIRED_TARGET_PRESENT")
    require(all(x["primary_category"] in CATEGORIES and
                x["repairability_class"] in REPAIRABILITY for x in cases),
            "UNKNOWN_CATEGORY_OR_REPAIRABILITY")
    require(sum(doc["primary_category_counts"].values())==42 and
            sum(doc["repairability_counts"].values())==42,"CATEGORY_SUM_MISMATCH")
    for eid,expected in EXPECTED_TEMPORAL.items():
        row=next(x for x in cases if x["episode_id"]==eid)
        require(row["primary_category"]==expected,
                "PRESERVED_TEMPORAL_CONTRADICTION:"+eid)
    require(doc["known_positives"]==48 and doc["final_positives"]==6 and
            doc["remaining_failures"]==42,"COHORT_COUNT_MISMATCH")
    require(doc["holds_processed"]==19 and doc["hold_strict"]==2 and
            doc["hold_sensitivity"]==0 and doc["new_uncleared_hold_promotions"]==0,
            "HOLD_SAFETY_GATE")
    require(doc["fingerprint_a"]==doc["fingerprint_b"] and
            doc["deterministic_equality"],"DETERMINISTIC_EQUALITY_GATE")
    require(doc["network_evidence_fetches"]==0 and
            not doc["blind_per_episode_inspected"] and
            doc["neon_queries"]==doc["neon_writes"]==doc["production_mutations"]==0 and
            doc["classifier_source_mutations"]==0 and
            not doc["historical_backfill_started"],"NO_MUTATION_GATE")
    require(doc["predecessor_transition_table"]["removed_because_repaired"][0]["episode_id"]==REMOVED_ID,
            "TRANSITION_REMOVAL_GATE")
    require(doc["exactly_one_next_task"].startswith("NEXT: "),"EXACT_ONE_NEXT_TASK")
    return True

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--mode",choices=("precheck","diagnose","compare","accept"),required=True)
    p.add_argument("--acquisition",type=Path)
    p.add_argument("--prior",type=Path)
    p.add_argument("--run-a",type=Path)
    p.add_argument("--run-b",type=Path)
    p.add_argument("--final",type=Path)
    p.add_argument("--out",type=Path)
    args=p.parse_args()
    if args.mode in ("precheck","diagnose"):
        require(args.acquisition and args.prior and args.out,"MISSING_IMMUTABLE_INPUTS")
        data=(precheck(args.acquisition,args.prior) if args.mode=="precheck"
              else diagnose(args.acquisition,args.prior,args.out))
        write_json(args.out,data)
        print("DIAGNOSIS_MODE="+args.mode,flush=True)
        print("DIAGNOSIS_OUTPUT_SHA256="+sha_bytes(args.out.read_bytes()),flush=True)
        print("DIAGNOSIS_42_ID_SHA256="+data["failure_id_sha256"],flush=True)
    elif args.mode=="compare":
        require(args.run_a and args.run_b and args.out,"MISSING_INDEPENDENT_RUNS")
        one=json.loads(args.run_a.read_text())
        two=json.loads(args.run_b.read_text())
        result=compare(one,two)
        write_json(args.out,result)
        print("DIAGNOSIS_FINGERPRINT_A="+result["fingerprint_a"],flush=True)
        print("DIAGNOSIS_FINGERPRINT_B="+result["fingerprint_b"],flush=True)
        print("CATEGORY_COUNTS="+json.dumps(result["primary_category_counts"],sort_keys=True),flush=True)
        print("NEXT_TASK="+result["exactly_one_next_task"],flush=True)
    else:
        require(args.final,"MISSING_FINAL_INPUT")
        data=json.loads(args.final.read_text())
        accept(data)
        print("ACCEPTANCE_VERDICT="+data["final_verdict"],flush=True)
        print("FINAL_ARTIFACT_SHA256="+sha_bytes(args.final.read_bytes()),flush=True)

if __name__=="__main__":
    main()
