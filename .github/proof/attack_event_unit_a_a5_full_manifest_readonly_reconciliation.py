#!/usr/bin/env python3
"""Independent read-only Unit A A5 full-manifest current-snapshot proof.

No A5 writes, retries, classifier, discovery, remediation or historical backfill.
Rebuilds accepted A4 projection and delta from pinned pre-A5 authorities independently
of the A5 execution JSON, then compares every accepted persistence field to actual
canonical rows inside one server-verified REPEATABLE READ / READ ONLY snapshot.
"""
from __future__ import annotations
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse
from uuid import UUID

BRANCH = "unit-a-a5-full-manifest-readonly-reconciliation-2026-10-10"
BASE = "f068de2132c4d1e2ce2d0b3489edecade3fa345c"
REPO = "olegbalakin-cmyk/kyiv-air-alerts-grafana"
PROJECT = "green-cake-44216048"
DB_BRANCH = "br-bold-mode-b5rub8pq"
DB_NAME = "neondb"
HOST = "ep-still-violet-b5bg6mhp.c-7.us-east-2.aws.neon.tech"
ORIG_RUN = 38079407732
ORIG_HEAD = "6bf16057f57fa7949e17c658b560032b3cd57f0f"
ORIG_BRANCH = "attack-event-unit-a-a5-authorized-execution-2026-10-10"
REVAL_PATH = "research/attack_event_execution_unit_a_a5_current_state_revalidation_2026-10-10.json"
REVAL_BLOB = "6c94245a770ad199beff18e13e2892c59d104108"
PROJECTION_SHA = "7978087ad00f37d0d1eb9f4326a478d5760e79cd7f7a68ae2be39fc5211bffa3"
DELTA_SHA = "6070b6dbfc03e16b5236aed5b3cb090fa066100857a9c4f7bed502d6bb294aa3"
OUT = Path("research/attack_event_unit_a_a5_full_manifest_readonly_reconciliation_2026-10-10.json")
PINS = {
  "a4": ("b3708f2d3b18ca4e877e8fae0e923ada72f845a7",
         "research/attack_event_execution_unit_a_a4_independent_reacceptance_v5_2026-10-10.json",
         "7e1becd3327ed3bfca4d4076ff99d45d4e4d3c8b",
         "6ff9b3d2e6dec717f8d5115705ce739915442b9f5530256107f0e42e0d501818"),
  "a5_pre": ("3bd876ef0f81f6138c0665d8e41ed5843fb44894",
         REVAL_PATH, REVAL_BLOB,
         "dd8a30a764b9050b2024ce9197e144fd9126aa4555c6257534d5e2a0cab12430"),
  "a5_commit": ("bca72a36986581730eb966ff95849dca19aa1574",
         "research/attack_event_execution_unit_a_a5_authorized_execution_2026-10-10.json",
         "1feee426e045dd39691bd1ac21a291f6ab438bf9",
         "4062159090e56c2cb2b92ba5839a240e9a4002d21d8e6d78b2c8bf91b2c0f848"),
  "a4_verifier": ("01b5e4933f5aa717a844c1ac57ed7a525b68e5ae",
         ".github/proof/attack_event_unit_a_a4_independent_reacceptance_v5.py",
         None, None),
  "a5_executor": (ORIG_HEAD,
         ".github/proof/attack_event_unit_a_a5_authorized_execution.py",
         "5a847d4bb4d5962011dbf1dff5b1ed748d033449", None),
}
POSITIVE = {"STRICT_EVENT_POSITIVE", "SENSITIVITY_EVENT_POSITIVE"}
EXPECTED_ACTIONS = {"INSERT_INITIAL":1713,"INSERT_SOURCE_LINK":1559,"INSERT_EVENT":10}
CLASS_INSERT_FIELDS = (
    "classification_key_version classification_key historical_episode_id city_key "
    "alert_start_at alert_end_at verdict is_event positive_tier event_types "
    "qa_reasons_state qa_reasons classifier_reason_codes classifier_blob_sha "
    "classifier_methodology_version normalization_version evidence_set_sha256 "
    "review_provenance_sha256 human_review_state review_provenance"
).split()
SOURCE_INSERT_FIELDS = (
    "source_link_key_version source_link_key observation_id source_family source_type "
    "source_type_state source_url telegram_channel telegram_message_id source_timestamp "
    "source_timestamp_state source_timestamp_raw event_timestamp_if_stated excerpt "
    "content_sha256 content_hash_basis observation_classification_outcome "
    "classification_episode_id evidence_payload retrieval_provenance"
).split()
STATIC_GENERATED_IDS = {"classification_uid","source_uid","source_link_uid",
                        "attack_event_uid","attack_event_source_uid","id","source_id"}
DYNAMIC_TIMES = {"created_at","updated_at","classified_at"}
MISMATCH_LIMIT = 5

def normalized(x):
    if isinstance(x, UUID):
        return str(x)
    if isinstance(x, datetime):
        if x.tzinfo is None:
            raise ValueError("NAIVE_DB_TIMESTAMP")
        return x.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    if isinstance(x, date):
        return x.isoformat()
    if isinstance(x, Decimal):
        return str(x)
    if isinstance(x, dict):
        return {k:normalized(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):
        return [normalized(v) for v in x]
    return x

def canonical(x):
    return json.dumps(normalized(x), sort_keys=True, ensure_ascii=False,
                      separators=(",",":"), allow_nan=False).encode("utf8")

def sha(x):
    return hashlib.sha256(x).hexdigest()

def hashed(x):
    return sha(canonical(x))

def git(*args):
    p = subprocess.run(["git",*args], capture_output=True,
        env=dict(os.environ,GIT_NO_LAZY_FETCH="1",GIT_TERMINAL_PROMPT="0"))
    if p.returncode:
        raise RuntimeError("PINNED_GIT_OBJECT_UNAVAILABLE")
    return p.stdout

def safe_example(category,key,field,expected=None,observed=None):
    # Do not emit payload, personally identifying excerpts or URLs.
    return {"category":category, "identity_sha256":sha(str(key).encode("utf8")),
            "field":field, "expected_sha256":hashed(expected),
            "observed_sha256":hashed(observed)}

def mismatch(report,category,key,field,expected=None,actual=None):
    report["mismatch_counts"][category] += 1
    if len(report["bounded_mismatches"]) < MISMATCH_LIMIT:
        report["bounded_mismatches"].append(safe_example(category,key,field,expected,actual))

def read_pin(name,report):
    ref,path,blob,digest=PINS[name]
    actual=git("rev-parse",ref+":"+path).decode().strip()
    if blob is not None and blob!=actual:
        raise RuntimeError("PIN_BLOB_MISMATCH_"+name)
    content=git("show",ref+":"+path)
    observed=sha(content)
    if digest is not None and digest!=observed:
        raise RuntimeError("PIN_SHA256_MISMATCH_"+name)
    report["authorities"][name]={"commit":ref,"path":path,"blob":actual,"sha256":observed}
    return content

def import_a4(data):
    p=Path("/tmp/unit_a_a4_independent_verifier_pinned.py")
    p.write_bytes(data)
    spec=importlib.util.spec_from_file_location("unit_a_a4_independent",p)
    mod=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=mod
    spec.loader.exec_module(mod)
    mod.BRANCH=BRANCH
    return mod

def independent_manifest(report):
    if os.getenv("GITHUB_REF_NAME")!=BRANCH:
        raise RuntimeError("UNAUTHORIZED_PROOF_BRANCH")
    if git("merge-base","HEAD",BASE).decode().strip()!=BASE:
        raise RuntimeError("PROOF_BRANCH_BASE_NOT_ANCESTOR")
    for name in PINS:
        read_pin(name,report)
    a4=json.loads(git("show",PINS["a4"][0]+":"+PINS["a4"][1]))
    pre=json.loads(git("show",PINS["a5_pre"][0]+":"+PINS["a5_pre"][1]))
    commit=json.loads(git("show",PINS["a5_commit"][0]+":"+PINS["a5_commit"][1]))
    if not (a4["A4_ACCEPTANCE_GATE"]=="PASS"
            and a4["A5_MANIFEST_ACCEPTED"]=="YES"
            and a4["delta"]["run_a_sha256"]==DELTA_SHA
            and pre["A5_CURRENT_STATE_GATE"]=="PASS"
            and pre["manifest"]["recomputed_delta_sha256_before"]==DELTA_SHA
            and commit["verdict"]=="ATTACK-EVENT EXECUTION UNIT A A5 ATOMIC PERSISTENCE = COMMITTED"
            and commit["writes"]=={"classifications":1713,"sources":1559,"events":10,"total":3282}):
        raise RuntimeError("FROZEN_ACCEPTED_AUTHORITIES_MISMATCH")
    mod=import_a4(git("show",PINS["a4_verifier"][0]+":"+PINS["a4_verifier"][1]))
    r=mod.report_new()
    # Unlike the original A5 executor, first generate the A3/six-field/A4
    # projection and partition from pinned primitive inputs before opening producer.
    recovery,adapter=mod.verify_frozen(r)
    evidence=mod.primitive(r)
    projection_a=mod.projected_fresh(recovery,adapter)
    projection_b=mod.projected_fresh(recovery,adapter)
    mod.check_projection(r,projection_a,projection_b,evidence)
    bindings,parents,classes,sources,events,actions=mod.partition_from_frozen(projection_a,evidence)
    b_evidence=mod.parse("snapshot")["semantic_evidence"]["evidence"]
    bind2,p2,c2,s2,e2,action_b=mod.partition_from_frozen(projection_b,b_evidence)
    if not (bindings==bind2 and parents==p2 and classes==c2
            and sources==s2 and events==e2
            and canonical(actions)==canonical(action_b)):
        raise RuntimeError("INDEPENDENT_A_B_MANIFEST_NONDETERMINISM")
    producer=mod.parse("producer")
    frozen=producer["A5_frozen_delta_manifest"]
    diff=mod.compare_to_producer(actions,frozen)
    if any(v!=0 for k,v in diff.items() if k not in ("example",)) or diff["example"] is not None:
        raise RuntimeError("INDEPENDENT_VS_PRODUCER_MANIFEST_MISMATCH")
    delta=mod.make_delta(projection_a,bindings,actions)
    if not (mod.hashed(delta)==DELTA_SHA
            and mod.hashed(projection_a)==PROJECTION_SHA
            and mod.hashed(mod.make_delta(projection_b,bind2,action_b))==DELTA_SHA):
        raise RuntimeError("ACCEPTED_MANIFEST_DIGEST_MISMATCH")
    observed=Counter(v["action"] for _,v in mod.flat(actions))
    if dict(observed)!=EXPECTED_ACTIONS:
        raise RuntimeError("INDEPENDENT_ACTION_PARTITION_MISMATCH")
    preconditions=mod.precondition_check(projection_a,evidence,bindings,actions)
    if preconditions["checked"]!=3282 or preconditions["incomplete"]!=0:
        raise RuntimeError("FROZEN_PRE_A5_PRECONDITIONS_MISMATCH")
    report["expected"]={
       "projection_sha256":mod.hashed(projection_a),
       "delta_sha256":mod.hashed(delta),
       "independent_a_b":"EQUAL",
       "independent_vs_producer":diff,
       "action_counts":dict(sorted(observed.items())),
       "parent_binding_sha256":mod.hashed(sorted(bindings.items())),
       "positive_expected":10,"nonpositive_expected":1703,
       "original_pre_A5_state_preconditions_checked":3282}
    return actions,projection_a,bindings

def field_value(col,val,metadata):
    if val is None:
        return None
    data_type=metadata.get(col,{}).get("data_type","")
    if data_type in ("timestamp with time zone","timestamp without time zone"):
        if isinstance(val,str):
            val=datetime.fromisoformat(val.replace("Z","+00:00"))
        if data_type=="timestamp without time zone":
            return val.isoformat() if isinstance(val,datetime) else str(val)
        return normalized(val)
    return normalized(val)

def row_field_match(row,expected,columns):
    unequal=[]
    for k,want in expected.items():
        if k not in row or field_value(k,row[k],columns)!=field_value(k,want,columns):
            unequal.append(k)
    return unequal

def origin_payload(kind, artifact_blob, observation_id=None):
    o={"kind":kind,"repository":REPO,"ref":ORIG_BRANCH,"commit":ORIG_HEAD,
       "workflow_run_id":ORIG_RUN,"accepted_delta_sha256":DELTA_SHA,
       "accepted_projection_sha256":PROJECTION_SHA,
       "accepted_revalidation_sha256":"dd8a30a764b9050b2024ce9197e144fd9126aa4555c6257534d5e2a0cab12430",
       "artifact_blob":artifact_blob}
    if observation_id is not None:
        o["observation_id"]=observation_id
    return o

def expected_class(action):
    s=action["semantic_row"]
    row={k:s[k] for k in CLASS_INSERT_FIELDS}
    p=origin_payload("unit_a_a5_authorized_execution",action["semantic_row_sha256"])
    row.update({
       "alert_type":"AIR","originating_frozen_case_id":None,
       "originating_frozen_case_id_state":"NOT_APPLICABLE",
       "binding_state":"BOUND","alert_episode_uid":action["alert_episode_uid"],
       "origin_repository":REPO,"origin_ref":ORIG_BRANCH,
       "origin_commit_sha":ORIG_HEAD,"origin_artifact_path":REVAL_PATH,
       "origin_artifact_blob_sha":REVAL_BLOB,"origin_target_state_sha256":DELTA_SHA,
       "origin_workflow_run_id":ORIG_RUN,
       "supersedes_classification_uid":None,"revision_reason":None,
       "correction_provenance":{},"persisted_by_run_id":None,
       "origin_provenance":p,"origin_provenance_sha256":hashed(p)
    })
    return row

def expected_source(action,cuid):
    s=action["semantic_source_row"]
    row={k:s[k] for k in SOURCE_INSERT_FIELDS}
    p=origin_payload("unit_a_a5_authorized_execution_source",
       action["semantic_source_row_sha256"],s["observation_id"])
    row.update({
      "classification_uid":cuid,
      "origin_artifact_path":REVAL_PATH,
      "origin_git_ref":ORIG_BRANCH,"origin_git_blob_sha":REVAL_BLOB,
      "raw_object_path":None,"origin_provenance":p,
      "origin_provenance_sha256":hashed(p)
    })
    return row

def expected_event(action,classification_action,cuid):
    s=classification_action["semantic_row"]
    return {
      "attack_event_key_version":"attack-event-key-v1",
      "attack_event_key":action["attack_event_key"],
      "event_grain":"HISTORICAL_ALERT_EPISODE",
      "historical_episode_id":action["historical_episode_id"],
      "city_key":action["city_key"],"alert_type":"AIR",
      "alert_start_at":s["alert_start_at"],"alert_end_at":s["alert_end_at"],
      "event_status":"ACTIVE","current_classification_uid":cuid,
      "binding_state":"BOUND","alert_episode_uid":classification_action["alert_episode_uid"],
      "correction_provenance":{
        "kind":"UNIT_A_A5_AUTHORIZED_INITIAL_EVENT",
        "accepted_delta_sha256":DELTA_SHA,"workflow_run_id":ORIG_RUN},
      "created_by_run_id":None,"updated_by_run_id":None
    }

def source_stat(report,label,rows,expected_by_key,columns):
    observed={}
    expected={}
    for k,row in sorted(expected_by_key.items()):
        observed[k]={f:rows[k].get(f) for f in row} if k in rows else None
        expected[k]=row
    report["fingerprints"][label+"_expected"]=hashed(expected)
    report["fingerprints"][label+"_actual"]=hashed(observed)

def verify_extras(report,kind,key,row,expected,columns):
    for field,val in row.items():
        if field in expected: continue
        if field in STATIC_GENERATED_IDS:
            if val is None:
                mismatch(report,kind,key,"generated_uid_missing:"+field)
            else:
                try: UUID(str(val))
                except ValueError: mismatch(report,kind,key,"generated_uid_invalid:"+field)
        elif field in DYNAMIC_TIMES:
            if val is None and columns.get(field,{}).get("is_nullable")!="YES":
                mismatch(report,kind,key,"generated_timestamp_missing:"+field)
            elif val is not None and not isinstance(val,datetime):
                mismatch(report,kind,key,"generated_timestamp_not_datetime:"+field)
            elif isinstance(val,datetime) and val.tzinfo is None:
                mismatch(report,kind,key,"generated_timestamp_naive:"+field)
        elif val is None and columns.get(field,{}).get("is_nullable")=="YES":
            continue
        else:
            # Unknown nonnull/unmodeled columns cannot be silently certified.
            report["unmodeled_columns"][kind].add(field)

def by(rows,field):
    d=defaultdict(list)
    for row in rows:
        d[str(row.get(field))].append(row)
    return d

def compare(report,actions,projection,bindings,data,meta):
    ca=actions["classification_actions"]
    sa=actions["source_actions"]
    ea=actions["event_actions"]
    cls=projection["classifications"]
    parent_rows,class_rows,source_rows,event_rows=data
    report["examined_rows"]={
       "parents":len(parent_rows),"classifications":len(class_rows),
       "source_links":len(source_rows),"events":len(event_rows)}
    p_by=by(parent_rows,"legacy_episode_id")
    c_by=by(class_rows,"classification_key")
    c_ep=by(class_rows,"historical_episode_id")
    s_by=by(source_rows,"source_link_key")
    e_by=by(event_rows,"attack_event_key")
    e_ep=by(event_rows,"historical_episode_id")
    cx={c["classification_key"]:c for c in cls}
    ca_key={a["classification_key"]:a for a in ca}
    uid_by_key={}
    parent_ok=0
    class_ok=0
    source_ok=0
    event_ok=0
    nonpos_ok=0
    residual=[]
    expected_c={}
    actual_c={}
    expected_s={}
    actual_s={}
    expected_e={}
    actual_e={}
    selected_uids=set()
    all_parent_uids={str(v) for v in bindings.values()}
    for a in ca:
        key=a["classification_key"]
        s=a["semantic_row"]
        eid=s["historical_episode_id"]
        parent_matches=p_by.get(str(eid),[])
        match=[v for v in parent_matches if
               all(field_value(f,v.get(f),meta["alert_episodes"])==
                   field_value(f,ev,meta["alert_episodes"])
                   for f,ev in s["parent_identity"].items())]
        if len(parent_matches)==1 and len(match)==1 and str(match[0]["episode_uid"])==str(a["alert_episode_uid"]):
            parent_ok+=1
        else:
            mismatch(report,"parent",key,"parent_identity_or_binding",
                     {"expected_binding":a["alert_episode_uid"]},
                     {"found":len(parent_matches),"matches":len(match)})
        rows=c_by.get(key,[])
        erows=c_ep.get(str(eid),[])
        want=expected_class(a)
        expected_c[key]=want
        actual_c[key]={f:rows[0].get(f) for f in want} if len(rows)==1 else None
        errors=[]
        if len(rows)!=1: errors.append("classification_key_cardinality")
        else:
            errors+=row_field_match(rows[0],want,meta["attack_event_classifications"])
            if str(rows[0]["historical_episode_id"])!=str(eid):
                errors.append("episode_binding")
            if str(rows[0]["alert_episode_uid"])!=str(a["alert_episode_uid"]):
                errors.append("parent_uid_binding")
            selected_uids.add(str(rows[0]["classification_uid"]))
            uid_by_key[key]=str(rows[0]["classification_uid"])
            verify_extras(report,"classification",key,rows[0],want,
                          meta["attack_event_classifications"])
        superseded={str(v["supersedes_classification_uid"]) for v in erows
                    if v.get("supersedes_classification_uid") is not None}
        tips=[v for v in erows if str(v["classification_uid"]) not in superseded]
        if len(erows)!=1 or len(tips)!=1 or len(rows)!=1 or str(tips[0]["classification_uid"])!=str(rows[0]["classification_uid"]):
            errors.append("competing_revision_or_unexpected_tip")
        if errors:
            for f in sorted(set(errors)):
                mismatch(report,"classification",key,f,
                         want.get(f),rows[0].get(f) if len(rows)==1 else len(rows))
            if len(rows)==0 and len(erows)==0:
                residual.append({"category":"INSERT_INITIAL","identity":key,"reason":"missing_exact_classification"})
            else:
                residual.append({"category":"CLASSIFICATION_CONFLICT","identity":key,"reason":"non_idempotent_semantics"})
        else:
            class_ok+=1
    all_c_uids={str(x["classification_uid"]) for x in class_rows}
    extra_c=[x for x in class_rows if str(x["classification_uid"]) not in selected_uids]
    for x in extra_c:
        mismatch(report,"classification_extra",x["classification_uid"],"unexpected_associated_classification")
    report["relationships"]["classification_to_parent_checked"]=len(ca)
    report["relationships"]["classification_to_parent_valid"]=parent_ok
    report["relationships"]["unique_current_tips"]=class_ok
    expected_source_keys=set()
    for a in sa:
        key=a["source_link_key"]
        expected_source_keys.add(key)
        target=a["target_classification_key"]
        cuid=uid_by_key.get(target)
        # Compute frozen source payload even if target class is absent;
        # this is a residual/conflict, never a candidate for execution here.
        want=expected_source(a,cuid)
        expected_s[key]=want
        rows=s_by.get(key,[])
        actual_s[key]={f:rows[0].get(f) for f in want} if len(rows)==1 else None
        errors=[]
        if len(rows)!=1: errors.append("source_key_cardinality")
        if cuid is None: errors.append("target_classification_missing")
        if len(rows)==1:
            errors+=row_field_match(rows[0],want,meta["attack_event_sources"])
            if str(rows[0]["classification_uid"])!=str(cuid):
                errors.append("source_to_classification_uid")
            verify_extras(report,"source",key,rows[0],want,meta["attack_event_sources"])
        if errors:
            for f in sorted(set(errors)):
                mismatch(report,"source",key,f,want.get(f),
                         rows[0].get(f) if len(rows)==1 else len(rows))
            if len(rows)==0 and cuid is not None:
                residual.append({"category":"INSERT_SOURCE_LINK","identity":key,"reason":"missing_exact_source"})
            else:
                residual.append({"category":"SOURCE_CONFLICT","identity":key,"reason":"non_idempotent_semantics"})
        else: source_ok+=1
    extra_s=[v for v in source_rows
             if v["source_link_key"] not in expected_source_keys]
    for v in extra_s:
        mismatch(report,"source_extra",v.get("source_link_key"),"unexpected_associated_source")
    for a in ea:
        key=a["attack_event_key"]
        target=a["desired_classification_key"]
        ca_row=ca_key[target]
        cuid=uid_by_key.get(target)
        want=expected_event(a,ca_row,cuid)
        expected_e[key]=want
        rows=e_by.get(key,[])
        actual_e[key]={f:rows[0].get(f) for f in want} if len(rows)==1 else None
        err=[]
        if len(rows)!=1: err.append("attack_event_key_cardinality")
        if cuid is None: err.append("positive_classification_missing")
        if len(rows)==1:
            err+=row_field_match(rows[0],want,meta["attack_events"])
            verify_extras(report,"event",key,rows[0],want,meta["attack_events"])
        same_ep=e_ep.get(str(a["historical_episode_id"]),[])
        if len(same_ep)!=1: err.append("unexpected_alternate_positive_event")
        if cx[target]["verdict"] not in POSITIVE or not cx[target]["is_event"]:
            err.append("positive_frozen_verdict")
        if err:
            for f in sorted(set(err)):
                mismatch(report,"event",key,f,want.get(f),rows[0].get(f) if len(rows)==1 else len(rows))
            if len(rows)==0 and len(same_ep)==0 and cuid is not None:
                residual.append({"category":"INSERT_EVENT","identity":key,"reason":"missing_positive_event"})
            else:
                residual.append({"category":"EVENT_CONFLICT","identity":key,"reason":"non_idempotent_semantics"})
        else: event_ok+=1
    positive_ids={str(a["historical_episode_id"]) for a in ea}
    negative=[c for c in cls if str(c["historical_episode_id"]) not in positive_ids]
    for c in negative:
        eid=str(c["historical_episode_id"])
        if not e_ep.get(eid):
            nonpos_ok+=1
        else:
            mismatch(report,"nonpositive",c["classification_key"],"unexpected_event_for_nonpositive")
            residual.append({"category":"NONPOSITIVE_CONFLICT","identity":c["classification_key"],"reason":"unexpected_positive_event"})
    selected_event_keys={a["attack_event_key"] for a in ea}
    unexpected_events=[v for v in event_rows if v["attack_event_key"] not in selected_event_keys]
    for v in unexpected_events:
        if str(v["historical_episode_id"]) not in positive_ids:
            continue  # Already recorded under the 1,703 nonpositive episodes.
        mismatch(report,"event_extra",v["attack_event_key"],"unexpected_event_for_positive_episode")
    source_stat(report,"classifications", {x["classification_key"]:x for x in class_rows},
                expected_c,meta["attack_event_classifications"])
    # Fingerprint full selected persisted semantic values; generated UIDs are
    # checked separately and not mistaken for frozen deterministic identities.
    report["fingerprints"]["source_links_expected"]=hashed(expected_s)
    report["fingerprints"]["source_links_actual"]=hashed(actual_s)
    report["fingerprints"]["events_expected"]=hashed(expected_e)
    report["fingerprints"]["events_actual"]=hashed(actual_e)
    report["fingerprints"]["all_readback_rows"]=hashed({
        "parents":sorted([hashed(v) for v in parent_rows]),
        "classifications":sorted([hashed(v) for v in class_rows]),
        "sources":sorted([hashed(v) for v in source_rows]),
        "events":sorted([hashed(v) for v in event_rows])})
    report["partitions"]={
       "target_records":3282,
       "parents":{"expected":1713,"valid":parent_ok,"observed":len(parent_rows)},
       "classifications":{"expected":1713,"matched":class_ok,"observed":len(class_rows),"extra":len(extra_c)},
       "source_links":{"expected":1559,"matched":source_ok,"observed":len(source_rows),"extra":len(extra_s)},
       "positive_events":{"expected":10,"matched":event_ok,"observed":sum(len(e_by.get(a["attack_event_key"],[])) for a in ea)},
       "nonpositive_no_event":{"expected":1703,"matched":nonpos_ok,"observed_target_episodes":len(negative)}
    }
    residual.sort(key=lambda x:(x["category"],x["identity"],x["reason"]))
    report["residual"]={
       "recomputed_from_persisted_rows":True,
       "counts":{
        "RESIDUAL_INSERT_INITIAL":sum(x["category"]=="INSERT_INITIAL" for x in residual),
        "RESIDUAL_INSERT_SOURCE_LINK":sum(x["category"]=="INSERT_SOURCE_LINK" for x in residual),
        "RESIDUAL_INSERT_EVENT":sum(x["category"]=="INSERT_EVENT" for x in residual),
        "RESIDUAL_CONFLICTS":sum(x["category"].endswith("_CONFLICT") for x in residual),
        "RESIDUAL_A5_MUTATIONS":len(residual)},
       "first_residual_example":({
          "category":residual[0]["category"],
          "identity_sha256":sha(residual[0]["identity"].encode()),
          "reason":residual[0]["reason"]} if residual else None),
       "fingerprint_definition":"sha256(canonical_json({schema_version,accepted_manifest_sha256,residual_actions}))",
       "fingerprint_sha256":hashed({"schema_version":1,"accepted_manifest_sha256":DELTA_SHA,
                                    "residual_actions":residual})
    }
    report["relationships"]["source_to_classification_checked"]=len(sa)
    report["relationships"]["source_to_classification_valid"]=source_ok
    report["relationships"]["positive_to_classification_checked"]=len(ea)
    report["relationships"]["positive_to_classification_valid"]=event_ok
    report["relationships"]["nonpositive_absence_checked"]=len(negative)
    report["relationships"]["nonpositive_absence_valid"]=nonpos_ok

def sql_select(cur,report,name,sql,params=()):
    if not re.match(r"^\s*SELECT\b",sql,re.I):
        raise RuntimeError("NON_SELECT_SQL_FORBIDDEN")
    report["transaction"]["select_count"]+=1
    report["transaction"]["query_names"].append(name)
    cur.execute(sql,params)
    return cur.fetchall()

def one_readonly_snapshot(report,actions,projection,bindings):
    if os.getenv("PHASE1_PROD_SHADOW_BRANCH_ID")!=DB_BRANCH:
        raise RuntimeError("PINNED_NEON_BRANCH_VARIABLE_MISSING_OR_WRONG")
    url=os.getenv("PHASE1_PROD_SHADOW_DATABASE_URL")
    if not url or urlparse(url).hostname!=HOST:
        raise RuntimeError("PINNED_NEON_CONNECTION_HOST_MISSING_OR_WRONG")
    from psycopg import connect
    from psycopg.rows import dict_row
    ids=sorted(c["historical_episode_id"] for c in projection["classifications"])
    keys=sorted(a["classification_key"] for a in actions["classification_actions"])
    skeys=sorted(a["source_link_key"] for a in actions["source_actions"])
    ekeys=sorted(c["attack_event_key"] for c in projection["classifications"])
    puids=sorted(str(x) for x in bindings.values())
    report["transaction"]["connection_attempts"]=1
    conn=connect(url,autocommit=True,connect_timeout=20,row_factory=dict_row,
                 options="-c default_transaction_read_only=on -c statement_timeout=180000")
    report["transaction"]["connections"]=1
    try:
        with conn.cursor() as cur:
            cur.execute("BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            report["transaction"]["begin_issued"]=True
            try:
                state=sql_select(cur,report,"server_mode_identity_snapshot",
                    "SELECT current_setting('transaction_isolation') AS isolation, "
                    "current_setting('transaction_read_only') AS read_only, "
                    "current_database() AS database_name, "
                    "pg_current_snapshot()::text AS snapshot, "
                    "pg_backend_pid() AS backend_pid")[0]
                report["transaction"].update({
                    "isolation":state["isolation"],"read_only":state["read_only"]=="on",
                    "database":state["database_name"],"snapshot":state["snapshot"],
                    "backend_pid":state["backend_pid"],
                    "branch":DB_BRANCH,"project":PROJECT,"host_verified":True})
                if not (state["isolation"]=="repeatable read" and state["read_only"]=="on"
                        and state["database_name"]==DB_NAME):
                    raise RuntimeError("SERVER_CONFIRMED_SNAPSHOT_CONTRACT_FAILED")
                colrows=sql_select(cur,report,"all_canonical_columns",
                    "SELECT table_name,column_name,data_type,is_nullable,column_default "
                    "FROM information_schema.columns WHERE table_schema='public' "
                    "AND table_name=ANY(%s) ORDER BY table_name,ordinal_position",
                    (["alert_episodes","attack_event_classifications","attack_event_sources","attack_events"],))
                meta=defaultdict(dict)
                for x in colrows: meta[x["table_name"]][x["column_name"]]=x
                for tab in ("alert_episodes","attack_event_classifications","attack_event_sources","attack_events"):
                    if not meta.get(tab): raise RuntimeError("CANONICAL_SCHEMA_TABLE_MISSING")
                report["canonical_columns"]={tab:sorted(c) for tab,c in meta.items()}
                constraints=sql_select(cur,report,"canonical_constraint_inventory",
                   "SELECT conrelid::regclass::text AS table_name,conname,contype,"
                   "pg_get_constraintdef(oid) AS definition FROM pg_constraint "
                   "WHERE connamespace='public'::regnamespace AND "
                   "conrelid=ANY(%s::regclass[]) ORDER BY table_name,conname",
                   (["public.alert_episodes","public.attack_event_classifications",
                     "public.attack_event_sources","public.attack_events"],))
                report["constraints_fingerprint_sha256"]=hashed(constraints)
                report["constraints_count"]=len(constraints)
                parent=sql_select(cur,report,"all_1713_target_parent_rows",
                   "SELECT * FROM public.alert_episodes WHERE legacy_episode_id=ANY(%s)",(ids,))
                classes=sql_select(cur,report,"all_target_classes_and_competing_revisions",
                   "SELECT * FROM public.attack_event_classifications "
                   "WHERE historical_episode_id=ANY(%s) OR classification_key=ANY(%s) "
                   "OR alert_episode_uid=ANY(%s::uuid[])",(ids,keys,puids))
                sources=sql_select(cur,report,"target_sources_and_all_associated_source_rows",
                   "SELECT s.* FROM public.attack_event_sources s WHERE s.source_link_key=ANY(%s) "
                   "OR s.classification_uid IN (SELECT c.classification_uid "
                   "FROM public.attack_event_classifications c "
                   "WHERE c.historical_episode_id=ANY(%s) "
                   "OR c.classification_key=ANY(%s) "
                   "OR c.alert_episode_uid=ANY(%s::uuid[]))",
                   (skeys,ids,keys,puids))
                events=sql_select(cur,report,"target_events_and_all_alternate_events",
                   "SELECT * FROM public.attack_events WHERE historical_episode_id=ANY(%s) "
                   "OR attack_event_key=ANY(%s) OR alert_episode_uid=ANY(%s::uuid[])",
                   (ids,ekeys,puids))
                state2=sql_select(cur,report,"confirm_same_snapshot",
                   "SELECT pg_current_snapshot()::text AS snapshot,"
                   "current_setting('transaction_read_only') AS read_only,"
                   "current_setting('transaction_isolation') AS isolation")[0]
                if (state2["snapshot"]!=state["snapshot"] or state2["read_only"]!="on"
                        or state2["isolation"]!="repeatable read"):
                    raise RuntimeError("SNAPSHOT_CHANGED_OR_NO_LONGER_READ_ONLY")
                compare(report,actions,projection,bindings,
                        (parent,classes,sources,events),meta)
                report["transaction"]["same_snapshot_verified"]=True
            finally:
                cur.execute("ROLLBACK")
                report["transaction"]["explicit_rollback"]=True
    finally:
        conn.close()

def report_new():
    return {
      "schema_version":1,"kind":"unit_a_a5_full_manifest_readonly_reconciliation",
      "coordination_main_at_start":BASE,"proof_branch":BRANCH,
      "proof_execution_sha":os.getenv("GITHUB_SHA"),
      "proof_workflow_run_id":os.getenv("GITHUB_RUN_ID"),
      "historical_A5_COMMITTED_preserved":True,
      "historical_A5_conformance":"DEVIATION CONFIRMED",
      "verdict":"UNIT A A5 FULL-MANIFEST RECONCILIATION = BLOCKED",
      "COMMITTED_DATA_INTEGRITY":"NOT_FULLY_VERIFIED",
      "IDEMPOTENCY_EVIDENCE":"PARTIAL",
      "CONCURRENCY_SAFETY":"UNPROVEN",
      "authorities":{},"expected":{},
      "transaction":{"project":PROJECT,"branch":DB_BRANCH,"database":None,
         "isolation":None,"read_only":False,"host_verified":False,
         "connections":0,"connection_attempts":0,"select_count":0,
         "query_names":[],"begin_issued":False,"explicit_rollback":False,
         "same_snapshot_verified":False,"attempted_writes":0,"committed_writes":0},
      "safety":{"a5_executed":False,"a5_retried":False,"a5_repaired":False,
                "sql_write_statements":0,"production_modified":False,
                "site_prod_modified":False,"classifier_reruns":0,"historical_backfills":0},
      "mismatch_counts":Counter(),"bounded_mismatches":[],
      "unmodeled_columns":defaultdict(set),"partitions":{},"relationships":{},
      "residual":{},"fingerprints":{},"examined_rows":{},
      "phase":"INIT","error_type":None
    }

def save(report):
    report["mismatch_counts"]=dict(sorted(report["mismatch_counts"].items()))
    report["unmodeled_columns"]={k:sorted(v) for k,v in sorted(report["unmodeled_columns"].items())}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_bytes(json.dumps(normalized(report),ensure_ascii=False,sort_keys=True,
                  indent=2,allow_nan=False).encode("utf8")+b"\n")

def main():
    r=report_new()
    try:
        actions,projection,bindings=independent_manifest(r)
        r["phase"]="INDEPENDENT_FROZEN_MANIFEST_RECONSTRUCTED"
        one_readonly_snapshot(r,actions,projection,bindings)
        r["phase"]="SINGLE_READ_ONLY_SNAPSHOT_COMPARED"
        total_mismatches=sum(r["mismatch_counts"].values())
        partitions=r["partitions"]
        complete=(partitions.get("parents",{}).get("valid")==1713
                  and partitions.get("classifications",{}).get("matched")==1713
                  and partitions.get("source_links",{}).get("matched")==1559
                  and partitions.get("positive_events",{}).get("matched")==10
                  and partitions.get("nonpositive_no_event",{}).get("matched")==1703)
        zero_residual=r["residual"]["counts"]["RESIDUAL_A5_MUTATIONS"]==0
        if total_mismatches or not complete or not zero_residual:
            r["verdict"]="UNIT A A5 FULL-MANIFEST RECONCILIATION = CONTRADICTION"
            r["COMMITTED_DATA_INTEGRITY"]="CONTRADICTION"
            r["IDEMPOTENCY_EVIDENCE"]="CONTRADICTION"
        elif r["unmodeled_columns"]:
            r["verdict"]="UNIT A A5 FULL-MANIFEST RECONCILIATION = PARTIAL"
            r["COMMITTED_DATA_INTEGRITY"]="NOT_FULLY_VERIFIED"
            r["IDEMPOTENCY_EVIDENCE"]="PARTIAL"
        else:
            r["verdict"]="UNIT A A5 FULL-MANIFEST RECONCILIATION = PASS"
            r["COMMITTED_DATA_INTEGRITY"]="VERIFIED_AT_CURRENT_SNAPSHOT"
            r["IDEMPOTENCY_EVIDENCE"]="INDEPENDENTLY_PROVEN_AT_CURRENT_SNAPSHOT"
    except Exception as exc:
        r["error_type"]=type(exc).__name__
        r["bounded_error_code"]=str(exc)[:160] if isinstance(exc,RuntimeError) else type(exc).__name__
    finally:
        save(r)
        print("VERDICT="+r["verdict"])
        print("PHASE="+r["phase"])
        print("EXPECTED="+json.dumps(r["expected"],sort_keys=True)[:1100])
        print("TRANSACTION="+json.dumps(r["transaction"],sort_keys=True))
        print("PARTITIONS="+json.dumps(r["partitions"],sort_keys=True))
        print("MISMATCH_COUNTS="+json.dumps(r["mismatch_counts"],sort_keys=True))
        print("UNMODELED_COLUMNS="+json.dumps(r["unmodeled_columns"],sort_keys=True))
        print("RESIDUAL="+json.dumps(r["residual"],sort_keys=True))
        print("ERROR="+str(r["error_type"]))
        print("ARTIFACT_SHA256="+sha(OUT.read_bytes()))
        print("NO_DATABASE_WRITES=TRUE NO_A5_EXECUTION=TRUE CONCURRENCY_SAFETY=UNPROVEN")

if __name__=="__main__":
    main()
