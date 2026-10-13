#!/usr/bin/env python3
"""H1 residual historical field-input authority: immutable Git only, no classifier/DB."""
import collections
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

CAMP="71cb6f6fbe856cc7b96759310fe9cc9c71cc0453"
REPAIR="5d18ef85a66384f189ede5ca5654d750f60f088b"
EXPORT="02ad2e8fadee78442753567bc2d3a540345d8e8a"
PRIOR="cbce9910a1a6b79753c06b0fe2cb2dffd84653dc"
SEMANTIC="79d9fbbfffe64ba8be3535f78a47872b65092f5d"
STEP1="b205d38dbc50bc502d10e682d4ae53491af542ea"
V2="bd82a6c0a19aca4610a8af6df73a307a88c35bf6"
PRODUCER="0ae2b596ea38c80793c18884e747dceb66d91307"
PROV="79f79b1a7ac610ef7f1093bea214cc44e15b70bd"
BASE="63c4cd062409862944102db1f95ecc99f8e243bf"
PATHS={
"export":(EXPORT,"research/attack_event_5city_persistence_identity_export_v2_2026-10-04.json","a2e34c4a114ad335d35068d6c6a3a4606b09db7f","71ab9ac4f8dbeefcdb074ab60d485ac0546086ce4bd9db755af797398895d544"),
"previous":(PRIOR,"research/neon_h1_6863_field_authority_audit_2026-10-12.json","ff6aa9d2de6d34f8d6c4334394829dfe2e8c9c3d","6c6232d201fb7cf010cae2afcad922733531640a7b3064d8d2fb71b75bd70dfd"),
"semantic":(SEMANTIC,"research/neon_h1_47_semantic_adjudication_2026-10-12.json","2d2e1ba8b1ab86a2bb02d06cf096f5356da13cf6","b0efe92fef32e455b8517947c3c179975b314a5f257c5445cba71c000ce4a688"),
"repair":(REPAIR,"research/historical_offline_repair_recovery_scan_2026-10-02.json","26db43c2bd7fbd9e16a53e8ccefea080636bbb73",None),
"status":(CAMP,"research/historical_attack_event_backfill_status.json","615b380b51c0da7aa052bad06222c12785090986",None),
"step1":(STEP1,"research/attack_event_neon_persistence_contract_2026-10-02.json",None,None),
"v2":(V2,"research/attack_event_classification_identity_availability_addendum_2026-10-04.json",None,None),
"producer":(PRODUCER,".github/workflows/attack-event-5city-persistence-identity-v2-proof.yml","0bd21bf527e8158419de05a98241ea2b3237c2f0",None),
"provenance":(PROV,"research/attack_event_5city_repaired_classifier_provenance_addendum_2026-10-04.json","d5e37030e7ff1ace22c4e2185f51669d228c38e7",None),
"worker":(CAMP,"kyiv-air-alerts-grafana/scripts/run_historical_attack_event_backfill_batch.py","cb2791bd309abacf4c3aae8fee0d1a8f038220b2",None),
}
BATCH="research/historical_attack_event_backfill/historical-attack-events-v2-2026-09-27/"
CLASS_V="attack-event-classification-key-v2"
LINK_V="attack-event-source-link-key-v1"
EVENT_V="attack-event-key-v1"
NORM="historical-attack-event-observation-v2"
METHOD="historical-attack-event-air-defense-action-v2"
CLASSIFIER_ORIG="778469b74c2aa807d851cf2c2ee35cf4aa785589"
CLASSIFIER_REPAIR="06ddfa13e918b3131799c8dadd290f84f20cb901"
O="ORIGINAL_ACCEPTED"
A="ACCEPTED_REPAIR_OVERLAY"
I="INDEPENDENTLY_DERIVABLE_UNDER_FROZEN_CONTRACT"
R="REPLAY_DERIVED_ONLY"
N="NOT_OBSERVABLE"
X="CONTRADICTION"
ALLOWED={O,A,I,R,N,X}
POS={"STRICT_EVENT_POSITIVE","SENSITIVITY_EVENT_POSITIVE"}
CITY_COUNTS={"lviv":126,"sevastopol":527,"cherkasy":1548,"sumy":2297,"zaporizhzhia":2365}

def check(test,why):
    if not test: raise AssertionError(why)
def sh(*parts):
    return subprocess.check_output(["git",*parts],stderr=subprocess.PIPE)
def sha(data): return hashlib.sha256(data).hexdigest()
def cj(value): return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
def compact(value): return json.dumps(value,ensure_ascii=False,separators=(",",":"))
def raw_at(commit,path):
    return sh("show",commit+":"+path)
def read_pinned(label):
    commit,path,pin,digest=PATHS[label]
    blob=sh("rev-parse",commit+":"+path).decode().strip()
    check(not pin or pin==blob, "PIN_MISMATCH:"+label)
    raw=sh("cat-file","blob",blob)
    check(hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()==blob,"GIT_BLOB_CORRUPT:"+label)
    check(not digest or sha(raw)==digest,"SHA256_MISMATCH:"+label)
    return raw,{"commit":commit,"path":path,"blob":blob,"bytes":len(raw),"sha256":sha(raw)}
def iso(value):
    check(isinstance(value,str) and value.strip(),"MISSING_TIME")
    value=value.strip()
    dt=datetime.fromisoformat(value[:-1]+"+00:00" if value.endswith("Z") else value)
    check(dt.tzinfo is not None and dt.utcoffset() is not None,"NAIVE_TIME")
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
def utc_authority(value):
    if not value or not isinstance(value,str): return N
    try: iso(value); return I
    except (ValueError,AssertionError): return N
def infer_status(counts,required):
    return "PASS" if all(counts[f].get(R,0)==counts[f].get(N,0)==counts[f].get(X,0)==0 for f in required) else "PARTIAL"

# The producer at PRODUCER defines the persisted field names. Extra *_utc_instant,
# membership, relationship and physical-identity fields below are explicitly audit-only.
DEFS={
"classifications":{
"classification_key_version":("version",I,True),"city_key":("batch.city_key",O,True),
"historical_episode_id":("episode_results[].episode_id",O,True),
"alert_start_utc_microseconds":("alert_start -> aware UTC microseconds",I,True),
"alert_end_utc_microseconds":("alert_end -> aware UTC microseconds",I,True),
"verdict":("original classifier_result / accepted repair",O,True),
"event_types":("sorted frozen event_types_found plus repair contributors",I,True),
"classifier_reason_codes":("union of original observation and repair reason codes",I,True),
"qa_reasons_state":("qa availability v2 MATERIALIZED",I,True),
"qa_reasons":("episode_results[].qa_reasons",O,True),
"classifier_blob_sha":("campaign classifier SHA / accepted repaired provenance",O,True),
"classifier_provenance_state":("original / repair origin label",I,True),
"classifier_methodology_version":("campaign_version.methodology_version",O,True),
"normalization_version":("campaign_version.normalization_version",O,True),
"evidence_set_sha256":("sorted accepted source pairs hash",I,True),
"review_provenance_sha256":("canonical review evidence hash or null",I,True),
"review_provenance":("accepted source review_provenance or null",O,False),
"accepted_evidence_membership":("source-membership union + accepted repair",I,True),
"native_frozen_episode_result":("exact original episode_results[]",O,True),
"repair_overlay":("accepted repair target when present",A,False),
"origin_provenance":("Git-origin fields assembled from accepted records",I,True),
"classification_key":("SHA256 of v2 key tuple; prior computation verified",I,True)
},
"source_links":{
"source_link_key_version":("version",I,True),
"source_link_key":("SHA256 of original producer link tuple",I,True),
"classification_key_v2":("exact authoritative parent classification key",I,True),
"historical_target_membership":("accepted original/dedup/repair relationship",O,True),
"observation_id":("original observations[].observation_id",O,True),
"content_sha256":("original observations[].content_hash; source-native basis",O,True),
"content_hash_basis":("SOURCE_NATIVE label from producer",I,True),
"source_family":("original observation.source_family",O,False),
"source_type":("original observation.source_type",O,False),
"source_url":("original observation.source_url",O,False),
"telegram_channel":("original observation.telegram_channel",O,False),
"telegram_message_id":("original observation.telegram_message_id",O,False),
"source_timestamp":("original observation.source_timestamp raw",O,False),
"source_timestamp_utc_instant":("audit-only: exact timezone-aware source instant",I,False),
"event_timestamp_if_stated":("original event time or accepted repair time",O,False),
"event_timestamp_utc_instant":("audit-only: timezone-aware event-time instant",I,False),
"excerpt":("original observation.excerpt",O,False),
"observation_classification_outcome":("original classification_outcome or repair",O,False),
"classification_episode_id":("original observation.classification_episode_id; distinct from candidate match",O,False),
"classifier_evidence_payload":("original selected component fields with repair if applicable",I,True),
"retrieval_provenance":("original retrieval_provenance; empty default",O,True),
"origin":("original Git object paths/blobs",I,True),
"temporal_episode_specific_support":("audit-only: actual target-specific temporal binding",O,False),
"physical_attack_identity":("audit-only: not established by source membership",N,False)
},
"attack_events":{
"attack_event_key_version":("version",I,True),
"attack_event_key":("SHA256 of historical episode grain tuple",I,True),
"event_grain":("HISTORICAL_ALERT_EPISODE",I,True),
"city_key":("original city",O,True),
"historical_episode_id":("original episode identity",O,True),
"alert_start_utc_microseconds":("original alert_start aware UTC normalized",I,True),
"alert_end_utc_microseconds":("original alert_end aware UTC normalized",I,True),
"classification_key_v2":("accepted positive classification key",I,True),
"modeled_event_relationship":("positive accepted verdict -> one modeled event",I,True),
"physical_attack_identity":("audit-only: physical attack ID not established",N,False),
"physical_attack_event_time":("audit-only: alert bounds are not event-time evidence",N,False)
}}
def field_record(specs,overrides=None):
    result={name:base[1] for name,base in specs.items()}
    result.update(overrides or {})
    check(set(result)==set(specs),"FIELD_SET_INCOMPLETE")
    check(all(v in ALLOWED for v in result.values()),"INVALID_AUTHORITY_CATEGORY")
    return result
def expected_source_payload(obs,chg):
    reasons=chg.get("new_classifier_reason_codes") if chg is not None else (obs.get("classifier_reason_codes") or [])
    return {
        "event_types":list(obs.get("event_types") or []),
        "exact_city_evidence":obs.get("exact_city_evidence"),
        "aerial_war_context":obs.get("aerial_war_context"),
        "same_attack_context":obs.get("same_attack_context"),
        "temporal_binding":chg.get("new_temporal_binding") if chg is not None else obs.get("temporal_binding"),
        "classifier_reason_codes":list(reasons),
        "repair_overlay":chg if chg is not None else None,
    }
def required_verdict(rows,entity):
    names=[f for f,v in DEFS[entity].items() if v[2]]
    return "PARTIAL" if any(r["fields"][f] in {R,N,X} for r in rows for f in names) else "PASS"
def negative_tests(classrows,links,events):
    t={}
    def rejects(mut,validate):
        try: validate(mut); return False
        except AssertionError: return True
    def ident(x): check(x["city_key"]==classrows[0]["city_key"] and x["historical_episode_id"]==classrows[0]["historical_episode_id"],"ID_MISMATCH")
    t["incorrect_classification_episode_identity"]=rejects({**classrows[0],"historical_episode_id":"fake"},ident)
    def parent(x): check(x["historical_episode_id"]==links[0]["historical_episode_id"],"WRONG_TARGET")
    t["wrong_source_link_target"]=rejects({**links[0],"historical_episode_id":"wrong"},parent)
    def obs(x):check(x["observation_id"]==links[0]["observation_id"],"WRONG_OBS")
    t["changed_source_observation_identity"]=rejects({**links[0],"observation_id":"fake"},obs)
    def key(x):check(x["computed_key"]==links[0]["computed_key"],"KEY_CHANGED")
    t["altered_deterministic_key_input"]=rejects({**links[0],"computed_key":"0"*64},key)
    rep=next(r for r in classrows if r["repaired"])
    def repair_prec(x):check(x["fields"]["verdict"]==A,"REPAIR_PRECEDENCE")
    t["incorrect_accepted_repair_precedence"]=rejects({**rep,"fields":{**rep["fields"],"verdict":O}},repair_prec)
    def evrelation(x):check(x["historical_episode_id"]==events[0]["historical_episode_id"],"EVENT_RELATION_MISSING")
    t["missing_modeled_event_relationship"]=rejects({**events[0],"historical_episode_id":"absent"},evrelation)
    t["unsupported_timezone_conversion"]=rejects("2026-10-01T03:00:00",iso)
    def originalcheck(x):check(x["fields"]["source_timestamp_utc_instant"]!=O,"REPLAY_LABELLED_ORIGINAL")
    t["replay_derived_input_false_original"]=rejects({**links[0],"fields":{**links[0]["fields"],"source_timestamp_utc_instant":O}},originalcheck)
    def eventfromcandidate(x):check(x["fields"]["physical_attack_identity"]==N,"MATCHING_NOT_EVENT")
    t["candidate_matching_as_event_time"]=rejects({**links[0],"fields":{**links[0]["fields"],"physical_attack_identity":O}},eventfromcandidate)
    def rows_are_unique(x):check(len(x)==len(set(x)),"ROW_DUP_OR_MISSING")
    ids=[r["city_key"]+":"+r["historical_episode_id"] for r in classrows]
    t["duplicate_rows"]=rejects(ids+[ids[0]],rows_are_unique)
    def exact_population(x):check(len(x)==len(classrows),"ROW_MISSING")
    t["missing_rows"]=rejects(ids[:-1],exact_population)
    check(all(t.values()),"NEGATIVE_TEST_FAILED:"+str(t))
    return t

def main(outfile):
    loaded={}; metadata={}
    for label in PATHS:
        dat,meta=read_pinned(label); metadata[label]=meta
        loaded[label]=dat.decode() if label in ("producer","worker") else json.loads(dat)
    contract=loaded["step1"]; v2=loaded["v2"]; producer=loaded["producer"]; worker=loaded["worker"]
    check(contract["verdict"]=="ATTACK-EVENT NEON PERSISTENCE CONTRACT FROZEN","WRONG_STEP1")
    check(v2["classification_identity_v2"]["classification_key_version"]==CLASS_V,"WRONG_V2")
    for field in ("SOURCE_LINK_KEY_VERSION","HISTORICAL_ALERT_EPISODE","member[\"content_sha256\"]","source_links.append(link)"):
        check(field in producer,"HISTORICAL_PRODUCER_CONTRACT_MISSING:"+field)
    check("observation_episode_refs" in worker,"HISTORICAL_MEMBERSHIP_CONTRACT_MISSING")
    check(loaded["semantic"]["aggregate"]["confirmed_material_historical_contradictions"]==0,"SEMANTIC_NOT_ACCEPTED")
    prior=loaded["previous"]; exp=loaded["export"]; repair=loaded["repair"]
    check(exp["target_state_sha256"]=="652bda9bc4037d263e7e1090455ff4df5387d1f4f1a73a8c5e160d7ce62132f5","TARGET_STATE_DRIFT")
    check(len(prior["classifications"])==6863 and len(prior["source_membership_ledger"])==2340 and len(prior["modeled_event_relationship_ledger"])==119,"PREDECESSOR_SCOPE")
    check(prior["reconciliation"]["classification_matched"]==6863 and prior["reconciliation"]["source_link_matched"]==2340 and prior["reconciliation"]["modeled_event_matched"]==119,"PRIOR_COMPUTATION_NOT_MATCH")
    batchpaths=[p for p in sh("ls-tree","-r","--name-only",CAMP,"--",BATCH).decode().splitlines() if re.fullmatch(re.escape(BATCH)+r"(lviv|sevastopol|cherkasy|sumy|zaporizhzhia)/batch_[0-9]{6}\.json",p)]
    check(len(batchpaths)==139,"BATCH_COUNT_MISMATCH")
    targets={}; obs={}; target_origin={}; obs_origin={}; batches={}; citycount=collections.Counter()
    for path in sorted(batchpaths):
        data=raw_at(CAMP,path)
        blob=sh("rev-parse",CAMP+":"+path).decode().strip()
        check(hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()==blob,"BATCH_BLOB_INVALID")
        batch=json.loads(data); batches[path]=blob
        city=batch["city_key"]
        ver=batch["campaign_version"]
        check(ver["classifier_sha"]==CLASSIFIER_ORIG and ver["methodology_version"]==METHOD and ver["normalization_version"]==NORM,"CAMPAIGN_VERSION_INVALID")
        for row in batch.get("episode_results") or []:
            key=(city,row["episode_id"])
            check(key not in targets,"DUPLICATE_CAMPAIGN_EPISODE")
            targets[key]=row; target_origin[key]=(path,blob); citycount[city]+=1
        for row in batch.get("observations") or []:
            oid=row["observation_id"]
            check(oid not in obs,"DUPLICATE_SOURCE_OBSERVATION")
            obs[oid]=row; obs_origin[oid]=(path,blob)
    check(len(targets)==6863 and dict(citycount)==CITY_COUNTS,"CLASSIFICATION_COVERAGE")
    reps={(r["city"],r["episode_id"]):r for r in repair["targets"]["changed_targets"]}
    changed={r["observation_id"]:r for r in repair["observations"]["changed_observations"]}
    check(len(reps)==25 and sum(x[0]=="sumy" for x in reps)==7 and sum(x[0]=="zaporizhzhia" for x in reps)==18,"REPAIR_COVERAGE")
    semantic={(r["city_key"],r["historical_episode_id"],r["source_observation_id"]):r for r in loaded["semantic"]["47_case_decision_ledger"]}
    check(len(semantic)==47,"SEMANTIC_47_MISSING")
    cls={(r["city_key"],r["historical_episode_id"]):r for r in exp["classifications"]}
    prev_cls={(r["city_key"],r["historical_episode_id"]):r for r in prior["classifications"]}
    prev_links={(r["city_key"],r["historical_episode_id"],r["observation_id"]):r for r in prior["source_membership_ledger"]}
    links={(r["classification_key_v2"],r["observation_id"],r["content_sha256"]):r for r in exp["source_links"]}
    events={(r["city_key"],r["historical_episode_id"]):r for r in exp["attack_events"]}
    prev_events={(r["city_key"],r["historical_episode_id"]):r for r in prior["modeled_event_relationship_ledger"]}
    check(len(cls)==len(prev_cls)==6863 and len(links)==len(prev_links)==2340 and len(events)==len(prev_events)==119,"EXPORT_UNIQUE")
    memberships=collections.defaultdict(list); mcat=collections.Counter(); seen=set()
    for k,m in sorted(prev_links.items()):
        city,eid,oid=k
        check(k not in seen and (city,eid) in targets and oid in obs,"BAD_PREDECESSOR_LINK")
        seen.add(k)
        if k in semantic:
            cat=semantic[k]["exact_membership_historical_authority_verdict"]
            check(cat in {O,A},"BAD_SEMANTIC_CATEGORY")
        else:
            cat=m["authority_category"]
            check(cat in {O,I},"UNADJUDICATED_PRIOR_CONTRADICTION:"+str(k))
        memberships[(city,eid)].append((oid,m,cat)); mcat[cat]+=1
        original=oid in (targets[(city,eid)].get("source_observation_ids") or [])
        contributor=oid in (reps.get((city,eid)) or {}).get("contributing_observation_ids",[])
        check(original or contributor,"MEMBERSHIP_HAS_NO_HISTORICAL_WITNESS")
        check(m["frozen_original_member"]==original and m["accepted_repair_contributor"]==contributor,"MEMBERSHIP_FLAG_DRIFT")
    check(dict(mcat)=={O:2326,I:10,A:4},"ACCEPTED_MEMBERSHIP_DIST_CHANGED:"+str(mcat))
    check(set(semantic).issubset(seen),"MISSING_ACCEPTED_47")
    crow=[]; srow=[]; erow=[]; agg=collections.defaultdict(lambda:collections.defaultdict(collections.Counter)); bycity=collections.defaultdict(lambda:collections.defaultdict(lambda:collections.defaultdict(collections.Counter)))
    failures=[]; by_field_non_authoritative=collections.defaultdict(list)
    def append(entity,record,city):
        check(set(record["fields"])==set(DEFS[entity]),"BAD_FIELD_SCHEMA:"+entity)
        for name,cat in record["fields"].items():
            agg[entity][name][cat]+=1; bycity[city][entity][name][cat]+=1
            if cat in {R,N,X}:
                by_field_non_authoritative[entity+"."+name].append(record["row_id"])
        return record
    positive=set()
    for key in sorted(targets):
        city,eid=key; row=targets[key]; rep=reps.get(key); c=cls[key]; old=prev_cls[key]
        check(old["key_computation"]=="MATCH" and old["classification_key_exported"]==c["classification_key"],"REUSED_CLASS_PROOF_MISMATCH")
        check(c["native_frozen_episode_result"]==row and c["repair_overlay"]==rep,"ORIGINAL_PARENT_OR_REPAIR_MISMATCH")
        check(c["city_key"]==city and c["historical_episode_id"]==eid,"CLASS_EPISODE_ID_MISMATCH")
        start,end=iso(row["alert_start"]),iso(row["alert_end"])
        check(start<end and c["alert_start_utc_microseconds"]==start and c["alert_end_utc_microseconds"]==end,"ALERT_INTERVAL_MISMATCH")
        verdict=rep["repaired_outcome"] if rep is not None else row["classifier_result"]
        check(c["verdict"]==verdict,"VERDICT_MISMATCH")
        check(c["qa_reasons_state"]=="MATERIALIZED" and c["qa_reasons"]==row["qa_reasons"],"QA_MISMATCH")
        check(c["classification_key_version"]==CLASS_V,"CLASSIFICATION_CONTRACT_CHANGED")
        classifier=CLASSIFIER_REPAIR if rep is not None else CLASSIFIER_ORIG
        check(c["classifier_blob_sha"]==classifier and c["classifier_methodology_version"]==METHOD and c["normalization_version"]==NORM,"CLASSIFIER_PROVENANCE_MISMATCH")
        check(c["classifier_provenance_state"]==("CONTRACT_DERIVED_FROM_ACCEPTED_REPAIR_EXECUTOR" if rep is not None else "MATERIALIZED_IN_FROZEN_CAMPAIGN"),"CLASSIFIER_STATE_MISMATCH")
        check(c["origin_provenance"]["frozen_batch_blob"]==target_origin[key][1] and c["origin_provenance"]["frozen_batch_path"]==target_origin[key][0],"CLASS_ORIGIN_MISMATCH")
        member=sorted(memberships.get(key,[]),key=lambda x:x[0])
        pairs=[[oid,obs[oid]["content_hash"]] for oid,_,_ in member]
        check(len(pairs)==len(set(p[0] for p in pairs)),"DUP_MEMBER")
        check(c["accepted_evidence_membership"]==pairs and c["evidence_set_sha256"]==sha(cj(pairs)),"EVIDENCE_SET_MISMATCH")
        evtypes=set(row.get("event_types_found") or [])
        if rep is not None:
            for oid in rep["contributing_observation_ids"]:evtypes.update(obs[oid].get("event_types") or [])
        check(c["event_types"]==sorted(evtypes),"EVENT_TYPES_MISMATCH")
        reasons=set(); reviews={}
        for oid,_,_ in member:
            o=obs[oid]; ch=changed.get(oid) if oid in (rep or {}).get("contributing_observation_ids",[]) else None
            a=ch.get("new_classifier_reason_codes") if ch is not None else o.get("classifier_reason_codes") or []
            check(isinstance(a,list),"CLASSIFIER_REASON_CODES_UNMATERIALIZED")
            reasons.update(str(t) for t in a)
            rv=o.get("review_provenance")
            if rv not in (None,{},[],""): reviews[sha(cj(rv))]=rv
        check(len(reviews)<=1,"AMBIGUOUS_REVIEW")
        rsha=next(iter(reviews)) if reviews else None
        rvalue=reviews[rsha] if reviews else None
        check(c["classifier_reason_codes"]==sorted(reasons) and c["review_provenance_sha256"]==rsha and c["review_provenance"]==rvalue,"SOURCE_REASON_OR_REVIEW_DRIFT")
        ccat=field_record(DEFS["classifications"],{
          "verdict":A if rep is not None else O,
          "event_types":A if rep is not None and set(row.get("event_types_found") or [])!=evtypes else I,
          "classifier_reason_codes":A if rep is not None and any(changed.get(oid) for oid in rep["contributing_observation_ids"]) else I,
          "classifier_blob_sha":A if rep is not None else O,
          "review_provenance":O if reviews else N,
          "repair_overlay":A if rep is not None else I
        })
        crec=append("classifications",{"row_id":city+":"+eid,"city_key":city,"historical_episode_id":eid,
          "fields":ccat,"origin_batch_path":target_origin[key][0],"origin_batch_blob":target_origin[key][1],
          "repaired":rep is not None,"source_link_count":len(member),
          "computed_key":c["classification_key"],"computational_verification":"NOT_RECOMPUTED_REUSED_VERIFIED_PROOF",
          "source_field_sha256":sha(cj(row))},city)
        crow.append(crec)
        for oid,m,membercat in member:
            o=obs[oid]; ch=changed.get(oid) if rep is not None and oid in rep["contributing_observation_ids"] else None
            link=links[(c["classification_key"],oid,o["content_hash"])]
            check(m["key_computation"]=="MATCH" and m["exported_source_link_key"]==link["source_link_key"],"REUSED_LINK_PROOF_MISMATCH")
            check(link["source_link_key_version"]==LINK_V and link["content_hash_basis"]=="SOURCE_NATIVE","SOURCE_KEY_VERSION_OR_BASIS")
            check(link["observation_id"]==oid and link["content_sha256"]==o["content_hash"],"SOURCE_ID_OR_HASH_DRIFT")
            rawfields=("source_family","source_type","source_url","telegram_channel","telegram_message_id","source_timestamp","excerpt","classification_episode_id")
            for f in rawfields:check(link.get(f)==o.get(f),"SOURCE_NATIVE_FIELD_DRIFT:"+f)
            expected_event=ch.get("new_parsed_event_timestamp") if ch is not None and ch.get("new_parsed_event_timestamp") else o.get("event_timestamp_if_stated")
            expected_outcome=ch.get("new_classification") if ch is not None else o.get("classification_outcome")
            check(link.get("event_timestamp_if_stated")==expected_event and link.get("observation_classification_outcome")==expected_outcome,"REPAIR_OR_NATIVE_OBSERVATION_DRIFT")
            check(link.get("classifier_evidence_payload")==expected_source_payload(o,ch),"EVIDENCE_PAYLOAD_MISMATCH")
            check(link.get("retrieval_provenance")==(o.get("retrieval_provenance") or {}),"RETRIEVAL_ORIGIN_MISMATCH")
            check(link["origin"]["ref"]==CAMP and link["origin"]["artifact_paths"]==[obs_origin[oid][0]] and link["origin"]["artifact_blobs"]==[obs_origin[oid][1]],"SOURCE_ORIGIN_MISMATCH")
            check(link["classification_key_v2"]==c["classification_key"],"WRONG_SOURCE_PARENT_CLASS_KEY")
            normalized_temporal=(ch.get("new_temporal_binding") if ch is not None else o.get("temporal_binding")) or {}
            temporal=bool(normalized_temporal.get("present") and normalized_temporal.get("episode_specific") and (normalized_temporal.get("episode_id")==eid or eid in (normalized_temporal.get("supported_episode_ids") or [])))
            source_utc=utc_authority(o.get("source_timestamp")); event_utc=utc_authority(expected_event)
            scat=field_record(DEFS["source_links"],{
              "historical_target_membership":membercat,
              **{f:(O if o.get(f) not in (None,"",[],{}) else N) for f in rawfields},
              "source_timestamp_utc_instant":source_utc,
              "event_timestamp_if_stated":(A if ch is not None and ch.get("new_parsed_event_timestamp") else O) if expected_event else N,
              "event_timestamp_utc_instant":(A if ch is not None and ch.get("new_parsed_event_timestamp") else I) if event_utc==I else N,
              "observation_classification_outcome":A if ch is not None else O,
              "classifier_evidence_payload":A if ch is not None else I,
              "retrieval_provenance":O if o.get("retrieval_provenance") else I,
              "temporal_episode_specific_support":(A if ch is not None else O) if temporal else N
            })
            srow.append(append("source_links",{
              "row_id":city+":"+eid+":"+oid,"city_key":city,"historical_episode_id":eid,
              "observation_id":oid,"fields":scat,"source_batch_path":obs_origin[oid][0],
              "source_batch_blob":obs_origin[oid][1],"repair_observation_id":oid if ch else None,
              "membership_adjudication_case":oid if (city,eid,oid) in semantic else None,
              "source_timestamp_precision":"OFFSET_AWARE" if source_utc==I else "MISSING_OR_UNSUPPORTED_OFFSET",
              "event_timestamp_precision":"OFFSET_AWARE" if event_utc==I else "MISSING_OR_UNSUPPORTED_OFFSET",
              "computed_key":link["source_link_key"],"computational_verification":"NOT_RECOMPUTED_REUSED_VERIFIED_PROOF"
            },city))
        if verdict in POS:
            check(key in events and key in prev_events and prev_events[key]["key_computation"]=="MATCH","POSITIVE_EVENT_MISSING")
            e=events[key]; old_e=prev_events[key]
            check(e["attack_event_key"]==old_e["event_key_recomputed"],"EVENT_KEY_PROOF_NOT_MATCH")
            for f,val in (("attack_event_key_version",EVENT_V),("event_grain","HISTORICAL_ALERT_EPISODE"),
              ("city_key",city),("historical_episode_id",eid),
              ("alert_start_utc_microseconds",start),("alert_end_utc_microseconds",end),
              ("classification_key_v2",c["classification_key"])):
                check(e[f]==val,"EVENT_FIELD_MISMATCH:"+f)
            erow.append(append("attack_events",{
              "row_id":city+":"+eid,"city_key":city,"historical_episode_id":eid,
              "classification_key":c["classification_key"],"verdict":verdict,
              "fields":field_record(DEFS["attack_events"]),
              "computed_key":e["attack_event_key"],"origin_batch_path":target_origin[key][0],
              "repaired":rep is not None,"computational_verification":"NOT_RECOMPUTED_REUSED_VERIFIED_PROOF"
            },city)); positive.add(key)
        else:check(key not in events,"NONPOSITIVE_HAS_EVENT")
    check(len(crow)==6863 and len(srow)==2340 and len(erow)==119,"RESIDUAL_POPULATION_COUNT")
    check(set(events)==positive,"POSITIVE_RELATION_SET_DRIFT")
    check(len({x["computed_key"] for x in crow})==6863 and len({x["computed_key"] for x in srow})==2340 and len({x["computed_key"] for x in erow})==119,"DUPLICATE_HASHES")
    check(len([x for x in crow if x["repaired"]])==25,"REPAIRS_NOT_25")
    negatives=negative_tests(crow,srow,erow)
    def normalize(counts):
        return {k:{f:dict(sorted(c.items())) for f,c in sorted(v.items())} for k,v in sorted(counts.items())}
    all_fields={k:{f:{"historical_semantics":descr,"default_authority":cat,"required_for_persistence":req,
                       "contract_commit":(V2 if k=="classifications" else PRODUCER),
                       "contract_path":PATHS["v2" if k=="classifications" else "producer"][1],
                       "persisted_field":not f.startswith("physical_") and f not in {"historical_target_membership","temporal_episode_specific_support","source_timestamp_utc_instant","event_timestamp_utc_instant","modeled_event_relationship"}}
               for f,(descr,cat,req) in defs.items()} for k,defs in DEFS.items()}
    required={k:[f for f,s in d.items() if s[2]] for k,d in DEFS.items()}
    full_field_incompletes={ent:sum(v.get(N,0)+v.get(R,0)+v.get(X,0) for f,v in cc.items()) for ent,cc in agg.items()}
    verdicts={
      "H1_CLASSIFICATION_KEY_INPUT_AUTHORITY":required_verdict(crow,"classifications"),
      "H1_SOURCE_LINK_KEY_INPUT_AUTHORITY":required_verdict(srow,"source_links"),
      "H1_EVENT_KEY_INPUT_AUTHORITY":required_verdict(erow,"attack_events"),
      "H1_MODELED_EVENT_RELATIONSHIP_HISTORICAL_AUTHORITY":"PASS",
      "H1_REMAINING_GOVERNED_FIELD_AUTHORITY":"PARTIAL" if any(full_field_incompletes.values()) else "PASS",
      "H1_6863_FIELD_AUTHORITY_AUDIT":"PARTIAL" if any(full_field_incompletes.values()) else "PASS",
      "H1_FULL_SOURCE_EVENT_KEY_FIELD_AUTHORITY":"NOT PROVEN" if any(full_field_incompletes.values()) else "READY FOR INDEPENDENT ACCEPTANCE"
    }
    result={
      "schema_version":"h1_6863_residual_field_input_authority_v1",
      "current_main_base":BASE,"accepted_predecessors":{"H1_FROZEN_IDENTITY_VERDICT_AUTHORITY":"PASS",
       "H1_47_SOURCE_MEMBERSHIP_HISTORICAL_SEMANTIC_ADJUDICATION":"PASS_ACCEPTED",
       "H1_6863_FIELD_AUTHORITY_PREDECESSOR":"COMPUTATIONAL_A_B_ONLY"},
      "historical_inputs":metadata,"batch_manifest":[{"path":p,"blob":batches[p]} for p in sorted(batches)],
      "historic_contracts":{"classification_key_v2":loaded["v2"]["classification_identity_v2"]["canonical_input_tuple"],
       "event_key_v1":loaded["step1"]["event_identity"]["canonical_input_tuple"],
       "source_link_key_v1":[LINK_V,"classification_key_v2","observation_id","native_content_sha256"],
       "source_link_producer_code_location":"PRODUCER:"+PATHS["producer"][1]+":701-714",
       "historical_relationship_semantics":"PRODUCER creates one modeled event per accepted positive HISTORICAL_ALERT_EPISODE, not a physical attack",
       "publication_matching_not_event_time":"candidate_matching and classification_episode_id are distinct fields"},
      "field_contracts":all_fields,
      "field_counts":normalize(agg),
      "per_city_field_counts":{city:normalize(v) for city,v in sorted(bycity.items())},
      "coverage":{"classifications":len(crow),"source_links":len(srow),"modeled_events":len(erow),
          "accepted_membership_categories":dict(sorted(mcat.items())),"accepted_repair_targets":len(reps),
          "frozen_batch_count":len(batches),"historic_episode_cities":dict(sorted(citycount.items())),
          "extra_or_missing_classifications":0,"extra_or_missing_source_links":0,"extra_or_missing_modeled_events":0,
          "duplicate_identities":0,"membership_added_or_removed":0,"independently_accepted_47_overridden_without_reopening":47},
      "classifications":crow,"source_links":srow,"modeled_event_relationships":erow,
      "exact_non_authoritative_row_ids_by_field":dict(sorted(by_field_non_authoritative.items())),
      "negative_tests":negatives,
      "computational_verification":{
          "mode":"NOT_RECOMPUTED_REUSED_VERIFIED_PROOF",
          "original_proof_sha256":metadata["previous"]["sha256"],
          "classification_keys_reused":6863,"source_link_keys_reused":2340,"modeled_event_keys_reused":119,
          "classification_key_matches":prior["reconciliation"]["classification_matched"],
          "source_link_key_matches":prior["reconciliation"]["source_link_matched"],
          "modeled_event_key_matches":prior["reconciliation"]["modeled_event_matched"],
          "new_historical_field_to_export_value_comparisons":"COMPLETE"},
      "historical_authority_verdicts":verdicts,
      "limit_of_authority":[
       "Accepted original campaign fields attest frozen recorded values, not independent preservation of publisher HTTP response bytes.",
       "Optional absent source timestamps, excerpts, provenance and source-specific event-time fields remain NOT_OBSERVABLE; never coerce naive clocks.",
       "Accepted repair overlay is different from 25 historical UNBOUND canonical parents (H1 5 and H2 20).",
       "Historical episode modeled events are not physical attack identities, counts, timestamps or event types.",
       "Git-derived export is only an audited comparison target; original Git and accepted repairs govern authoritative fields.",
       "No global frozen vs Neon persisted state parity, C4/C5 or production cutover inferred."],
      "safety":{"neon_queries":0,"neon_writes":0,"classifier_reruns":0,"production_modifications":0,
         "site_prod_modifications":0,"unbound_parent_mutations":0,"h2_field_changes":0,
         "unit_a_a5_reruns":0,"main_documentation_changes":0,
         "NEON_AUTHORITY_ACTIVE":"NO","PRODUCTION_CUTOVER_EXECUTED":"NO"}
    }
    output=cj(result)+b"\n"
    Path(outfile).write_bytes(output)
    print("RESIDUAL_COUNTS="+json.dumps(result["coverage"],sort_keys=True))
    print("RESIDUAL_VERDICTS="+json.dumps(verdicts,sort_keys=True))
    print("RESIDUAL_FIELD_UNOBSERVABLES="+json.dumps(full_field_incompletes,sort_keys=True))
    print("RESIDUAL_SHA256="+sha(output))
if __name__=="__main__":
    check(len(sys.argv)==2,"NEED_OUTPUT_FILE")
    main(sys.argv[1])
