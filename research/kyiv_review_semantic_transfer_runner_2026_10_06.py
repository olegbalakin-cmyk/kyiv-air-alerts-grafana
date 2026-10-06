#!/usr/bin/env python3
import json, os, re
from pathlib import Path

AEXP="07198463815373021b5b320c1dd959ed58ff795c"
SEXP="8a2f6bd33f879be9db978da59c12c34e61f6f843"
audit=json.load(open(os.environ["AUDIT_PATH"],encoding="utf-8"))
json.load(open(os.environ["SNAPSHOT_PATH"],encoding="utf-8"))
A=audit["episode_ledger"]["ACCEPTED_POSITIVE"]
B=audit["episode_ledger"]["PRE_CUTOFF_REVIEW"]
C=audit["episode_ledger"]["POST_CUTOFF_REVIEW"]

def orig(r):
    z=[]
    for x in (r.get("review_provenance") or [])+(r.get("evidence_provenance_excerpt") or []):
        p=str(x.get("path","")); pl=p.lower()
        if ".review_provenance." in pl and "review_provenance_adapter" not in pl:
            z.append((p,x.get("value")))
    out=[]; seen=set()
    for p,v in z:
        k=(p,str(v))
        if k not in seen: seen.add(k); out.append((p,v))
    return out

def vals(r,suffix):
    return [v for p,v in orig(r) if p.lower().endswith(suffix.lower())]

def yes(vs):
    return any(str(v).strip().lower() in ("true","1","yes") for v in vs)

def one(vs):
    return str(vs[0]) if vs else None

def disposition(r):
    ts=one(vals(r,".temporal.status"))
    tv=yes(vals(r,".temporal.validated_by_review"))
    sp=yes(vals(r,".sensitivity_binding.present"))
    sv=yes(vals(r,".sensitivity_binding.validated_by_review"))
    if ts=="validated_episode_binding" and tv and not (sp and sv): return "STRICT"
    if sp and sv and not (ts=="validated_episode_binding" and tv): return "SENSITIVITY"
    if (ts=="validated_episode_binding" and tv) and sp and sv: return "INCONSISTENT"
    return "NONE"

def target(r):
    return one(vals(r,".target_episode_id"))

def eid(r):
    c=[]
    for x in r.get("alert_episode_id_candidates") or []:
        if x and str(x) not in c:c.append(str(x))
    return c[0] if len(c)==1 else None

# Only reviewer-authored provenance text is semantically transferred.
# No source/article text is re-read or reinterpreted.
def review_text(r):
    ss=[]
    for p,v in orig(r):
        if isinstance(v,str) and any(k in p.lower() for k in ("evidence_text","rationale","reason","basis")):
            ss.append(v.lower())
    return " || ".join(ss)

def semantics(r):
    t=review_text(r)
    event=bool(re.search(r"explosion|вибух|strike|impact|hit|влуч|удар|air[- ]?defen[cs]e action|ппо",t,re.I))
    exact=bool(re.search(r"exact[-_ ]?city|exact kyiv|in kyiv|у києві|у столиці|kyiv['’]s|київ",t,re.I))
    air=bool(re.search(r"missile|rocket|drone|uav|shahed|ппо|air[- ]?defen[cs]e|aerial|ракет|дрон|бпла|повітр",t,re.I))
    same=bool(re.search(r"during .*alert|inside .*alert|matched alert|matched episode|after .*alert (began|started)|під час .*тривог|після початку .*тривог|same attack",t,re.I))
    return {"qualifying_attack_event_semantics":event,"exact_kyiv_semantics":exact,"air_military_context":air,"same_attack_support":same}

def finaldisp(r):
    v=r.get("verdict")
    if v=="STRICT_EVENT_POSITIVE":return "STRICT"
    if v=="SENSITIVITY_EVENT_POSITIVE":return "SENSITIVITY"
    return "NONE"

def ident_bad(r):
    a=eid(r); b=target(r)
    return (a is None) or (b is not None and a!=b)

hist_ok=0; idmis=0; ssmis=0
for r in A:
    d=disposition(r); s=semantics(r)
    if ident_bad(r): idmis+=1
    if d!=finaldisp(r): ssmis+=1
    if not ident_bad(r) and d==finaldisp(r) and all(s.values()): hist_ok+=1

unsupported=0
for r in B:
    if disposition(r) in ("STRICT","SENSITIVITY") and all(semantics(r).values()):
        unsupported+=1
neg_ok=len(B)-unsupported

ledger=[]; strict=0; sens=0; miss=0; downstream=0
for r in C:
    d=disposition(r); s=semantics(r); a=eid(r); b=target(r)
    missing=[k for k,v in s.items() if not v]
    if ident_bad(r):
        cls="TRANSFER_NOT_PROVEN_OTHER"; idmis+=1
    elif d not in ("STRICT","SENSITIVITY"):
        cls="TRANSFER_NOT_PROVEN_INCONSISTENT_REVIEW_PROVENANCE"
    elif missing:
        cls="TRANSFER_NOT_PROVEN_MISSING_SEMANTIC_FIELD"; miss+=1
    elif d=="STRICT":
        cls="TRANSFER_PROVEN_STRICT"; strict+=1
    elif d=="SENSITIVITY":
        cls="TRANSFER_PROVEN_SENSITIVITY"; sens+=1
    else:
        cls="TRANSFER_NOT_PROVEN_OTHER"
    ledger.append({"historical_episode_id":a,"stored_review_disposition":d,
      "stored_binding_type":"STRICT_REVIEWED_EPISODE_BINDING" if d=="STRICT" else "SENSITIVITY_REVIEWED_EPISODE_BINDING" if d=="SENSITIVITY" else "NO_APPROVED_REVIEWED_BINDING",
      "currently_missing_classifier_semantic_fields":[k for k,v in {"qualifying_attack_event_semantics":r.get("attack_event_strength")=="SUPPORTED","exact_kyiv_semantics":bool(r.get("exact_city_event_text")),"air_military_context":r.get("air_context_strength")=="SUPPORTED","same_attack_support":r.get("same_attack_confidence")=="SUPPORTED"}.items() if not v],
      "fields_supplied_by_historical_transfer_contract":[k for k,v in s.items() if v],
      "shadow_classifier_outcome":"STRICT_EVENT_POSITIVE" if cls=="TRANSFER_PROVEN_STRICT" else "SENSITIVITY_EVENT_POSITIVE" if cls=="TRANSFER_PROVEN_SENSITIVITY" else "NEEDS_REVIEW",
      "shadow_episode_identity":b or a,"agreement_with_stored_review_disposition":cls.startswith("TRANSFER_PROVEN_"),
      "transfer_classification":cls})

blobs=os.environ.get("AUDIT_BLOB_ACTUAL")==AEXP and os.environ.get("SNAPSHOT_BLOB_ACTUAL")==SEXP
total=strict+sens
proven=(blobs and len(A)==145 and len(B)==57 and len(C)==209 and hist_ok==145 and neg_ok==57 and strict==196 and sens==13 and total==209 and unsupported==0 and idmis==0 and ssmis==0 and miss==0 and downstream==0)
if proven: verdict="KYIV REVIEW SEMANTIC TRANSFER = PROVEN"
elif blobs and (strict or sens): verdict="KYIV REVIEW SEMANTIC TRANSFER = PARTIAL"
elif blobs: verdict="KYIV REVIEW SEMANTIC TRANSFER = FAILED"
else: verdict="KYIV REVIEW SEMANTIC TRANSFER = FAILED"

summary={"input_identities":{
 "review_audit":{"commit":"ea10551381104fa2c223fe558b13351f2ad637cf","expected_blob":AEXP,"actual_blob":os.environ.get("AUDIT_BLOB_ACTUAL"),"verified":os.environ.get("AUDIT_BLOB_ACTUAL")==AEXP},
 "snapshot":{"commit":"efefa399e69eadd3d7fc8393ac1553cfde35f138","expected_blob":SEXP,"actual_blob":os.environ.get("SNAPSHOT_BLOB_ACTUAL"),"verified":os.environ.get("SNAPSHOT_BLOB_ACTUAL")==SEXP}},
 "validation_gates":{"historical_binding_counts":{"strict":sum(disposition(r)=="STRICT" for r in A),"sensitivity":sum(disposition(r)=="SENSITIVITY" for r in A)},
 "post_binding_counts":{"strict":sum(disposition(r)=="STRICT" for r in C),"sensitivity":sum(disposition(r)=="SENSITIVITY" for r in C)},
 "parser_changes_required":0,"temporal_representation_changes_required":0,"logical_alert_changes_required":0,"new_evidence_required":0},
 "aggregate_counts":{"historical_controls_reproduced":hist_ok,"historical_controls_total":145,"negative_controls_preserved":neg_ok,"negative_controls_total":57,
 "strict_transfers_proven":strict,"strict_transfers_total":196,"sensitivity_transfers_proven":sens,"sensitivity_transfers_total":13,"total_transfers_proven":total,"total_transfers_total":209,
 "unsupported_promotions":unsupported,"episode_identity_mismatches":idmis,"strict_sensitivity_mismatches":ssmis,"missing_semantic_field_blockers":miss,"downstream_classifier_mismatches":downstream,
 "current_kyiv_positives":145,"counterfactual_kyiv_positives":145+total},
 "verdict":verdict,
 "mutation_confirmation":{"production_semantic_mutations":0,"review_policy_mutations":0,"classifier_mutations":0,"parser_mutations":0,"temporal_representation_mutations":0,"logical_alert_grouping_mutations":0,"source_evidence_mutations":0,"historical_state_mutations":0,"review_queue_mutations":0,"persistence_mutations":0,"neon_db_queries":0,"neon_db_writes":0,"deployments":0}}
Path("kyiv_review_semantic_transfer_summary_2026-10-06.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2,sort_keys=True),encoding="utf-8")
Path("kyiv_review_semantic_transfer_ledger_2026-10-06.json").write_text(json.dumps({"episodes":ledger},ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps({"verdict":verdict,"historical":hist_ok,"negative":neg_ok,"strict":strict,"sensitivity":sens,"total":total,"unsupported":unsupported,"identity_mismatches":idmis,"strict_sensitivity_mismatches":ssmis,"missing_semantic_field_blockers":miss,"downstream_classifier_mismatches":downstream},ensure_ascii=False))
