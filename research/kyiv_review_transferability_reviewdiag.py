#!/usr/bin/env python3
import json, os, re, importlib.util
from collections import Counter,defaultdict
from pathlib import Path

spec=importlib.util.spec_from_file_location("x","research/kyiv_review_transferability_audit.py")
x=importlib.util.module_from_spec(spec); spec.loader.exec_module(x)
base=x.base
snap=json.load(open(os.environ.get("SNAPSHOT_PATH",x.FROZEN_PATH),encoding="utf-8"))
class_path,class_rows,context_cache,kyiv,get_start,all_counts=x.build_context(snap)
out=json.load(open(x.OUT,encoding="utf-8"))

def cohort_indices():
    A=[];B=[];C=[]
    for i in kyiv:
        pairs,_=context_cache[i]; v=base.verdict_from_pairs(pairs); d=base.date_only(get_start(pairs)); _,_,e=base.evidence_flags(pairs)
        if v in ("STRICT_EVENT_POSITIVE","SENSITIVITY_EVENT_POSITIVE"): A.append(i)
        elif v=="NEEDS_REVIEW" and e and d and d<=x.CUTOFF:B.append(i)
        elif v=="NEEDS_REVIEW" and e and d and d>x.CUTOFF:C.append(i)
    return {"ACCEPTED_POSITIVE":A,"PRE_CUTOFF_REVIEW":B,"POST_CUTOFF_REVIEW":C}

def review_original(pairs):
    fields=[]
    for p,v in pairs:
        pl=p.lower()
        # Original review_provenance, excluding adapter copies.
        if ".review_provenance." in pl and "review_provenance_adapter" not in pl:
            fields.append((p,v))
    return fields

def summarize(ids):
    pathvals=defaultdict(Counter)
    evidence_texts=[]
    ep=[]
    same=[]
    strict=[]
    exact=[]
    air=[]
    sens=[]
    neighbor=[]
    temporal_status=[]
    temporal_valid=[]
    rationale_labels=Counter()
    for i in ids:
        pairs,_=context_cache[i]
        fs=review_original(pairs)
        for p,v in fs:
            sem=re.sub(r"\[\d+\]","[]",p)
            pathvals[sem][str(v)]+=1
            pl=p.lower(); sv=base.norm(v)
            if pl.endswith("temporal.evidence_text") and sv:
                evidence_texts.append(sv)
                lo=sv.lower()
                for label,pat in [
                    ("STRICT_LABEL",r"\bstrict\b"),
                    ("SENSITIVITY_LABEL",r"\bsensitiv"),
                    ("EXACT_CITY_LABEL",r"exact[-_ ]?city|точн.*київ"),
                    ("AIR_WAR_LABEL",r"aerial[-_ ]?war|drone|missile|ппо|повітр|дрон|ракет"),
                    ("EXPLOSION_LABEL",r"explosion|вибух"),
                    ("IMPACT_STRIKE_LABEL",r"impact|strike|hit|влуч|удар"),
                    ("DURING_ALERT_LABEL",r"during.*alert|inside.*alert|під час.*тривог|після початку.*тривог"),
                    ("MATCHED_EPISODE_LABEL",r"matched.*episode|alert episode|episode binding|matched alert"),
                    ("REJECT_LABEL",r"reject|not qualif|не кваліф|недостат"),
                ]:
                    if re.search(pat,lo,re.I): rationale_labels[label]+=1
            if pl.endswith("temporal.episode_specific"): ep.append(v)
            if "same_attack" in pl: same.append((p,v))
            if "strict" in pl: strict.append((p,v))
            if "exact_city" in pl: exact.append((p,v))
            if "air_military" in pl or "air_context" in pl: air.append((p,v))
            if "sensitivity" in pl: sens.append((p,v))
            if pl.endswith("neighboring_alert_check.passed"):neighbor.append(v)
            if pl.endswith("temporal.status"):temporal_status.append(sv)
            if pl.endswith("temporal.validated_by_review"):temporal_valid.append(v)
    def bcount(vals):
        return dict(Counter(str(v) for v in vals).most_common())
    return {
      "episode_count":len(ids),
      "original_review_provenance_semantic_paths":{p:dict(c.most_common()) for p,c in sorted(pathvals.items())},
      "temporal_episode_specific":bcount(ep),
      "neighboring_alert_check_passed":bcount(neighbor),
      "temporal_status":dict(Counter(temporal_status).most_common()),
      "temporal_validated_by_review":bcount(temporal_valid),
      "rationale_label_episode_hits":dict(rationale_labels),
      "evidence_text_count":len(evidence_texts),
      "evidence_text_examples":evidence_texts[:30],
      "same_attack_fields":dict(Counter(f"{re.sub(r'\[\d+\]','[]',p)}={v}" for p,v in same).most_common(80)),
      "strict_fields":dict(Counter(f"{re.sub(r'\[\d+\]','[]',p)}={v}" for p,v in strict).most_common(80)),
      "exact_city_fields":dict(Counter(f"{re.sub(r'\[\d+\]','[]',p)}={v}" for p,v in exact).most_common(80)),
      "air_context_fields":dict(Counter(f"{re.sub(r'\[\d+\]','[]',p)}={v}" for p,v in air).most_common(80)),
      "sensitivity_fields":dict(Counter(f"{re.sub(r'\[\d+\]','[]',p)}={v}" for p,v in sens).most_common(80)),
    }

cs=cohort_indices()
out["stored_review_provenance_diagnostics"]={k:summarize(v) for k,v in cs.items()}
Path(x.OUT).write_text(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True),encoding="utf-8")
print(json.dumps({
 k:{
   "episode_count":out["stored_review_provenance_diagnostics"][k]["episode_count"],
   "temporal_status":out["stored_review_provenance_diagnostics"][k]["temporal_status"],
   "temporal_validated_by_review":out["stored_review_provenance_diagnostics"][k]["temporal_validated_by_review"],
   "labels":out["stored_review_provenance_diagnostics"][k]["rationale_label_episode_hits"],
   "same":out["stored_review_provenance_diagnostics"][k]["same_attack_fields"],
   "strict":out["stored_review_provenance_diagnostics"][k]["strict_fields"],
   "exact":out["stored_review_provenance_diagnostics"][k]["exact_city_fields"],
   "air":out["stored_review_provenance_diagnostics"][k]["air_context_fields"],
 } for k in cs},ensure_ascii=False,indent=2))
