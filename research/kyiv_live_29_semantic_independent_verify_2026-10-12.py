#!/usr/bin/env python3
"""Independently enumerate raw queue references, avoiding primary ledger as count authority."""
import hashlib,json,subprocess,sys
from collections import Counter,defaultdict
from datetime import datetime
from pathlib import Path
PIN="92d57bbbfad60e6c09bb92372b1e84f38fa6ced4"
O="research/kyiv_live_29_semantic_outputs"
def blob(sha):
    return json.loads(subprocess.check_output(["git","cat-file","blob",sha]))
def walk(v,ids):
    if isinstance(v,dict):
        for k,x in v.items():
            yield from walk(x,ids)
    elif isinstance(v,list):
        for x in v: yield from walk(x,ids)
    elif isinstance(v,str) and v in ids: yield v
def main():
    state=blob("b255f516a8598bbd28faaa1a651249f4064b5620")
    queue=blob("e7777b88bf1912572df10eb252f991ea6456feba")
    eps=[e for e in state["cities"]["kyiv"]["episodes"] if datetime.fromisoformat(e["alert_end"].replace("Z","+00:00"))>=datetime.fromisoformat("2026-10-07T19:05:00+00:00")]
    ids={e["episode_id"] for e in eps}
    assert len(eps)==len(ids)==29
    expected_refs=Counter()
    expected_pair=set()
    candidate_set=set()
    explicit=set()
    triggeronly=set()
    classifier=set()
    conflicting=set()
    approved=set()
    held=set()
    rejected=set()
    for c in queue:
        cid=c.get("candidate_id")
        refset=list(walk(c,ids))
        if not refset:continue
        candidate_set.add(cid)
        for e in refset:expected_pair.add((cid,e))
        root_class=(c.get("classification_evidence") or {})
        if not isinstance(root_class,dict):root_class={}
        comp=c.get("composition_provenance") or {}
        if not isinstance(comp,dict):comp={}
        nested=root_class.get("episode_level_composition") or {}
        if not isinstance(nested,dict):nested={}
        targetset={str(v) for v in (root_class.get("classification_episode_id"),comp.get("target_episode_id"),nested.get("target_episode_id")) if isinstance(v,str) and v}
        if len(targetset)>1:conflicting.add(cid)
        if str(c.get("status")) in ("approved_strict","approved_sensitivity") and targetset and c.get("matched_episode_id") and str(c["matched_episode_id"]) not in targetset:conflicting.add(cid)
        human=c.get("review_provenance") or {}
        adapter=root_class.get("review_provenance_adapter") or {}
        if isinstance(human,dict) and isinstance(adapter,dict) and adapter.get("usable") is True and targetset and human.get("target_episode_id") and str(human["target_episode_id"]) not in targetset:conflicting.add(cid)
        finalset={v for v in targetset if v in ids}
        if finalset: classifier.add(cid)
        allmatched=c.get("matched_episode_ids") or []
        if not isinstance(allmatched,list):allmatched=[]
        temporal={v for v in allmatched if isinstance(v,str) and v in ids}
        temporal.update(v for v in (c.get("matched_episode_id"),) if isinstance(v,str) and v in ids)
        if temporal or finalset:explicit.add(cid)
        triggers=c.get("trigger_episode_ids") or []
        if not isinstance(triggers,list):triggers=[triggers] if isinstance(triggers,str) else []
        if set(triggers)&ids and not temporal and not finalset and not any(x in ids for x in walk({k:v for k,v in c.items() if k!="trigger_episode_ids"},ids)):triggeronly.add(cid)
        # Independent top-level accounting; ledger verification performed separately.
        for k in c:
            count=sum(1 for e in walk(c[k],ids))
            expected_refs[k]+=count
        disp=c.get("review_disposition")
        hist=c.get("review_history")
        decisions=[]
        for obj in [disp]+(hist if isinstance(hist,list) else []):
            if isinstance(obj,dict):
                for key in ("decision","disposition","action","outcome","review_decision"):
                    if isinstance(obj.get(key),str) and obj[key].strip():
                        decisions.append(obj[key].strip().upper());break
        if decisions:
            d=decisions[-1]
            if d in ("APPROVE","APPROVED","PROMOTE","PROMOTED","ACCEPT","ACCEPTED","CONFIRMED"):approved.add(cid)
            elif d in ("HOLD","HELD","NEEDS_REVIEW","DEFER","DEFERRED","PENDING"):held.add(cid)
            elif d in ("REJECT","REJECTED","DISMISS","DISMISSED"):rejected.add(cid)
    ledger=json.loads((Path(O)/"02_candidate_binding_ledger.json").read_text())
    dispositions=json.loads((Path(O)/"03_candidate_dispositions.json").read_text())
    count=json.loads((Path(O)/"08_count_reconciliation.json").read_text())["corrected"]
    epsout=json.loads((Path(O)/"04_kyiv_29_episodes.json").read_text())
    assert len(epsout)==29
    assert all(x["episode_id"] in ids for x in epsout)
    assert len(queue)==count["original_candidate_records"]
    assert len(candidate_set)==count["candidate_rows_with_any_cohort_reference"]
    assert len(expected_pair)==count["distinct_candidate_episode_pairs_any"]
    assert sum(expected_refs.values())==count["raw_references_all_fields"]==len(ledger)
    assert {k:v for k,v in sorted(expected_refs.items()) if v}==count["raw_references_by_top_level_root"],(expected_refs,count["raw_references_by_top_level_root"])
    assert len(explicit)==count["candidate_rows_with_explicit_stored_relationship"]
    assert len(classifier)==count["candidate_rows_with_final_classifier_binding"]
    assert len(triggeronly)==count["candidate_rows_trigger_references_only"]
    assert len(conflicting)==count["candidate_rows_with_conflicting_final_bindings"]
    assert len(approved)==count["candidate_rows_review_approved"]
    assert len(held)==count["candidate_rows_review_held"]
    assert len(rejected)==count["candidate_rows_review_rejected"]
    assert len({x["candidate_id"] for x in dispositions})==len(candidate_set)
    assert set((x["candidate_id"],x["episode_id"]) for x in ledger)==expected_pair
    assert set(x["candidate_id"] for x in ledger)==candidate_set
    assert set(x["episode_id"] for x in ledger)<=ids
    assert sum(e["followups_scheduled"] for e in epsout)==116
    assert sum(e["followups_due"] for e in epsout)==55
    assert sum(e["followups_marked_checked"] for e in epsout)==55
    result={"independent_raw_reconstruction":True,"all_assertions_passed":True,
            "original_records":len(queue),"related_candidates":len(candidate_set),
            "raw_references":sum(expected_refs.values()),"distinct_pairs":len(expected_pair),
            "explicit_candidates":len(explicit),"classifier_binding_candidates":len(classifier),
            "trigger_only_candidates":len(triggeronly),"conflict_candidates":len(conflicting),
            "human_approved":len(approved),"human_held":len(held),"human_rejected":len(rejected),
            "original_queue_git_object":"e7777b88bf1912572df10eb252f991ea6456feba",
            "checked_identity_count":29}
    print("INDEPENDENT_RAW_VERIFIER_PASS",json.dumps(result,sort_keys=True))
    return result
if __name__=="__main__":main()
